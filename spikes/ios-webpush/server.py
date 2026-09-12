#!/usr/bin/env python3
"""Reusable, owner-authenticated same-origin iPhone Web Push diagnostic."""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import ClientSession, ClientTimeout, web
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import webpush

ORIGIN = 'https://pda-web.tailaff53a.ts.net'
BASE = '/pda-push-test'
ASSETS = Path(__file__).parent


def validate_subscription(value):
    try:
        endpoint = value['endpoint']
        if not isinstance(endpoint, str) or len(endpoint) > 2048 or re.search(r'[\s\x00-\x20\x7f\\]', endpoint):
            raise ValueError('invalid endpoint')
        parsed = urlsplit(endpoint)
        if parsed.scheme != 'https' or parsed.netloc != 'web.push.apple.com' or not parsed.path.startswith('/') or parsed.query or parsed.fragment:
            raise ValueError('Only Apple Web Push endpoints are supported in this iPhone test')
        keys = {}
        for name, size in [('auth', 16), ('p256dh', 65)]:
            item = value['keys'][name]
            if not isinstance(item, str) or not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}', item):
                raise ValueError('invalid key')
            raw = base64.urlsafe_b64decode(item + '=' * (-len(item) % 4))
            if len(raw) != size:
                raise ValueError('invalid key length')
            if name == 'p256dh':
                ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
            keys[name] = item
        return {'endpoint': endpoint, 'keys': keys}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Appleの有効なPush購読情報が必要です。') from exc


def private_json(path, value):
    temp = path.with_suffix('.tmp')
    with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as output:
        json.dump(value, output, ensure_ascii=False)
    os.replace(temp, path)


def create_app(state_dir, owner_id, *, authenticator=None, sender=None, delay_seconds=20):
    target = '/'  # Diagnostics always return to Open WebUI home, never a chat.
    state = Path(state_dir)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.chmod(0o700)
    key_path = state / 'vapid-private.pem'
    if not key_path.exists():
        private_key = ec.generate_private_key(ec.SECP256R1())
        pem = private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        with os.fdopen(os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
            output.write(pem)
    private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    public_key = base64.urlsafe_b64encode(private_key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)).decode().rstrip('=')
    subscription_path = state / 'subscription.json'
    latest_path = state / 'latest.json'
    latest = json.loads(latest_path.read_text()) if latest_path.exists() else {}
    tasks = set()
    if latest.get('state') in {'scheduled', 'publishing'}:
        latest['state'] = 'interrupted-delivery-unknown' if latest['state'] == 'publishing' else 'interrupted-not-resent'
        private_json(latest_path, latest)

    def event(kind, **fields):
        line = json.dumps({'at': time.time(), 'event': kind, **fields}, ensure_ascii=False)
        with os.fdopen(os.open(state / 'events.jsonl', os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600), 'a') as output:
            output.write(line + '\n')

    class NoRedirectSession:
        def post(self, url, **kwargs):
            import requests
            return requests.post(url, allow_redirects=False, **kwargs)

    async def live_sender(subscription, payload):
        def publish():
            result = webpush(subscription_info=validate_subscription(subscription), data=json.dumps(payload, ensure_ascii=False), vapid_private_key=str(key_path), vapid_claims={'sub': ORIGIN}, ttl=120, timeout=10, headers={'Urgency': 'high'}, requests_session=NoRedirectSession())
            return result.status_code
        return await asyncio.to_thread(publish)

    publish = sender or live_sender

    async def live_auth(token):
        if not token:
            return None
        try:
            async with ClientSession(timeout=ClientTimeout(total=5)) as session:
                async with session.get('http://127.0.0.1:9120/api/v1/auths/', headers={'Authorization': 'Bearer ' + token}, allow_redirects=False) as response:
                    if response.status == 200:
                        return (await response.json()).get('id')
        except Exception:
            return None
        return None

    check_auth = authenticator or live_auth

    @web.middleware
    async def guard(request, handler):
        if request.method != 'GET' and request.headers.get('Origin') != ORIGIN:
            return web.json_response({'error': '同じOpen WebUIアプリ内から操作してください。'}, status=403)
        if request.path.startswith(BASE + '/api/'):
            auth = request.headers.get('Authorization', '')
            token = auth[7:] if auth.startswith('Bearer ') else ''
            if not token or await check_auth(token) != owner_id:
                return web.json_response({'error': 'Open WebUIにログイン済みの本人アプリから開いてください。'}, status=401)
        try:
            response = await handler(request)
        except (ValueError, KeyError, TypeError):
            response = web.json_response({'error': 'テスト入力が無効です。状態を再確認してください。'}, status=400)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    async def index(request):
        return web.Response(text=(ASSETS / 'index.html').read_text(), content_type='text/html')

    async def config(request):
        return web.json_response({'publicKey': public_key, 'target': target})

    async def asset(request):
        filename = request.match_info['file']
        if filename not in {'app.js', 'sw.js'}:
            raise web.HTTPNotFound()
        return web.Response(text=(ASSETS / filename).read_text(), content_type='application/javascript')

    async def status(request):
        return web.json_response({'subscribed': subscription_path.exists(), 'latest': latest})

    async def subscribe(request):
        data = await request.json()
        if data.get('standalone') is not True or data.get('mode') not in {'declarative', 'service-worker'}:
            raise ValueError('not standalone')
        subscription = validate_subscription(data['subscription'])
        if tasks:
            return web.json_response({'error': '通知テストが進行中です。'}, status=409)
        if subscription_path.exists() and json.loads(subscription_path.read_text())['subscription'] != subscription:
            return web.json_response({'error': '別の購読が登録済みです。先にテスト購読を解除してください。'}, status=409)
        private_json(subscription_path, {'subscription': subscription, 'mode': data['mode']})
        event('subscribed', mode=data['mode'], standalone=True)
        return web.json_response({'ok': True})

    async def deliver(subscription, test_id):
        try:
            await asyncio.sleep(delay_seconds)
            payload = {'web_push': 8030, 'notification': {'title': 'PDA ホーム画面テスト', 'body': 'タップするとOpen WebUIのトップへ戻ります。Safariではなくホーム画面アプリで開くかを確認します。', 'navigate': ORIGIN + BASE + '/landing?test=' + test_id, 'tag': 'pda-push-spike-' + test_id, 'silent': False}}
            try:
                latest['state'] = 'publishing'
                private_json(latest_path, latest)
                result = await publish(subscription, payload)
                latest.update(state='sent' if result == 201 else 'failed', push_status=result)
            except Exception as exc:
                response = getattr(exc, 'response', None)
                latest.update(state='failed', error_type=type(exc).__name__, push_status=getattr(response, 'status_code', None))
            latest['finished_at'] = time.time()
            private_json(latest_path, latest)
            event('push-result', test_id=test_id, state=latest['state'], push_status=latest.get('push_status'), error_type=latest.get('error_type'))
        except asyncio.CancelledError:
            latest['state'] = 'interrupted-delivery-unknown' if latest.get('state') == 'publishing' else 'cancelled-not-sent'
            private_json(latest_path, latest)
            raise

    async def send(request):
        if not subscription_path.exists():
            return web.json_response({'error': '先に①で通知を許可してください。'}, status=409)
        if tasks or time.time() - latest.get('scheduled_at', 0) < 15:
            return web.json_response({'error': 'テストは1件ずつです。少し待って再確認してください。'}, status=409)
        subscription = validate_subscription(json.loads(subscription_path.read_text())['subscription'])
        test_id = uuid.uuid4().hex
        latest.clear()
        latest.update(test_id=test_id, state='scheduled', scheduled_at=time.time(), send_at=time.time() + delay_seconds)
        private_json(latest_path, latest)
        task = asyncio.create_task(deliver(subscription, test_id))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        event('scheduled', test_id=test_id)
        return web.json_response(latest, status=202)

    async def arrival(request):
        data = await request.json()
        if data.get('test_id') != latest.get('test_id') or not isinstance(data.get('standalone'), bool):
            raise ValueError('unknown test')
        latest.update(arrival_standalone=data['standalone'], arrived_at=time.time())
        private_json(latest_path, latest)
        event('arrival', test_id=data['test_id'], standalone=data['standalone'])
        return web.json_response({'ok': True, 'target': target})

    async def unsubscribe(request):
        if latest.get('state') == 'publishing':
            return web.json_response({'error': '送信開始済みです。結果が確定してから解除してください。'}, status=409)
        for task in list(tasks):
            task.cancel()
        if tasks:
            await asyncio.gather(*list(tasks), return_exceptions=True)
        subscription_path.unlink(missing_ok=True)
        event('unsubscribed')
        return web.json_response({'ok': True})

    async def cleanup(app):
        for task in list(tasks):
            task.cancel()
        if tasks:
            await asyncio.gather(*list(tasks), return_exceptions=True)

    app = web.Application(middlewares=[guard], client_max_size=12288)
    app.router.add_get(BASE + '/', index)
    app.router.add_get(BASE + '/landing', index)
    app.router.add_get(BASE + '/api/config', config)
    app.router.add_get(BASE + '/api/status', status)
    app.router.add_post(BASE + '/api/subscribe', subscribe)
    app.router.add_post(BASE + '/api/send', send)
    app.router.add_post(BASE + '/api/arrival', arrival)
    app.router.add_post(BASE + '/api/unsubscribe', unsubscribe)
    app.router.add_get(BASE + '/{file}', asset)
    app.on_cleanup.append(cleanup)
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--owner-id', required=True)
    parser.add_argument('--port', type=int, default=9122)
    args = parser.parse_args()
    web.run_app(create_app(args.state_dir, args.owner_id), host='127.0.0.1', port=args.port, access_log=None)

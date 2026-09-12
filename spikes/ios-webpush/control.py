#!/usr/bin/env python3
"""Show/hide the reusable iPhone diagnostic entry, not normal notifications."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from pathlib import Path

import requests

BANNER_ID = 'pda-webpush-spike'  # Retain ID to update/remove the original entry.
BANNERS_API = '/api/v1/configs/banners'
BANNER = {
    'id': BANNER_ID,
    'type': 'info',
    'title': 'ホーム画面の通知テスト・再設定',
    'content': 'ホーム画面版の通知を確認・再設定できます。 <a href="/pda-push-test/" data-sveltekit-reload="true">通知テストを開く</a>',
    'dismissible': False,
}


def read_visible(path):
    value = json.loads(path.read_text())['show_banner'] if path.exists() else False
    if type(value) is not bool:
        raise ValueError('show_banner must be a JSON boolean.')
    return value


def set_visible(path, visible, request):
    current = request('GET', BANNERS_API)
    desired = [item for item in current if item['id'] != BANNER_ID]
    if visible:
        old = next((item for item in current if item['id'] == BANNER_ID), {})
        desired.append({**BANNER, 'timestamp': old.get('timestamp', int(time.time() * 1000))})
    if current != desired:
        request('POST', BANNERS_API, {'banners': desired})
    if request('GET', BANNERS_API) != desired:
        raise RuntimeError('Banner read-back differs; flag not saved. Inspect live state before retrying.')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix('.tmp')
    with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as output:
        json.dump({'show_banner': visible}, output)
    os.replace(temp, path)
    return {'show_banner': visible}


class LocalAdmin:
    def __init__(self, token_file):
        if token_file.stat().st_mode & 0o077:
            raise ValueError('Admin credential must be private (mode 0600).')
        self.token = token_file.read_text().strip()
        if not self.token:
            raise ValueError('Admin credential is empty.')
        self.session = requests.Session()
        self.session.trust_env = False

    def request(self, method, path, payload=None):
        if method not in {'GET', 'POST'} or path != BANNERS_API:
            raise ValueError('Only the local Open WebUI banners API is allowed.')
        response = self.session.request(method, 'http://127.0.0.1:9120' + path,
            headers={'Authorization': 'Bearer ' + self.token}, json=payload,
            allow_redirects=False, timeout=10)
        if response.status_code != 200:
            raise RuntimeError('Local banners API returned HTTP ' + str(response.status_code))
        return response.json()


def service_ready():
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.get('http://127.0.0.1:9122/pda-push-test/', allow_redirects=False, timeout=3)
            return response.status_code == 200 and '/pda-push-test/app.js' in response.text
    except requests.RequestException:
        return False


def main(argv=None, *, request=None, ready=service_ready):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['show', 'hide', 'apply', 'status'])
    parser.add_argument('--state-dir', type=Path, default=Path.home() / '.local/state/pda/webpush-spike')
    parser.add_argument('--token-file', type=Path, default=Path.home() / 'openwebui/.admin-api-key')
    args = parser.parse_args(argv)
    if request is None:
        request = LocalAdmin(args.token_file).request
    state = args.state_dir / 'settings.json'
    args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(args.state_dir / 'control.lock', os.O_RDWR | os.O_CREAT, 0o600), 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'status':
            visible = read_visible(state)
            count = sum(item['id'] == BANNER_ID for item in request('GET', BANNERS_API))
            result = {'show_banner': visible, 'live_count': count, 'matches': count == int(visible), 'service_ready': ready()}
        else:
            visible = read_visible(state) if args.action == 'apply' else args.action == 'show'
            if visible and not ready():
                raise RuntimeError('Diagnostic service unavailable; restart pda-webpush-spike.service before showing the entry.')
            result = set_visible(state, visible, request)
        print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)

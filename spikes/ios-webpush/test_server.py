import importlib.util
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer


@pytest.mark.asyncio
async def test_config_requires_the_owned_openwebui_session(tmp_path):
    path = Path(__file__).with_name('server.py')
    assert path.exists(), 'The isolated authenticated push test service is not implemented'
    spec = importlib.util.spec_from_file_location('push_spike_server', path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    async def authenticate(token):
        return 'owner' if token == 'test-owner' else None

    app = mod.create_app(tmp_path, 'owner', authenticator=authenticate)
    async with TestClient(TestServer(app)) as client:
        response = await client.get('/pda-push-test/api/config')
        assert response.status == 401
        response = await client.get('/pda-push-test/api/config', headers={'Authorization': 'Bearer test-owner'})
        assert response.status == 200
        value = await response.json()
        assert value['target'] == '/'  # Reusable test does not need a conversation.
        assert len(value['publicKey']) == 87
        assert 'private' not in str(value).lower()
        response = await client.get('/pda-push-test/')
        assert response.status == 200
        assert response.headers['Cache-Control'] == 'no-store'


def load_server():
    spec = importlib.util.spec_from_file_location('push_spike_server', Path(__file__).with_name('server.py'))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sample_subscription():
    import base64
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    enc = lambda value: base64.urlsafe_b64encode(value).decode().rstrip('=')
    return {'endpoint': 'https://web.push.apple.com/test-not-real', 'keys': {'auth': enc(b'0123456789abcdef'), 'p256dh': enc(key)}}


@pytest.mark.asyncio
async def test_owned_subscription_schedules_one_fixed_push_and_records_arrival(tmp_path):
    import asyncio
    import json
    mod = load_server()
    assert hasattr(mod, 'validate_subscription'), 'Push subscription and delivery have not been implemented'
    sent = []

    async def authenticate(token):
        return 'owner' if token == 'test-owner' else None

    async def sender(subscription, payload):
        sent.append((subscription, payload))
        return 201

    app = mod.create_app(tmp_path, 'owner', authenticator=authenticate, sender=sender, delay_seconds=0.04)
    headers = {'Authorization': 'Bearer test-owner', 'Origin': mod.ORIGIN}
    async with TestClient(TestServer(app)) as client:
        data = {'subscription': sample_subscription(), 'mode': 'declarative', 'standalone': True}
        response = await client.post(mod.BASE + '/api/subscribe', json=data, headers={'Authorization': 'Bearer test-owner', 'Origin': 'https://evil.example'})
        assert response.status == 403
        response = await client.post(mod.BASE + '/api/subscribe', json=data, headers=headers)
        assert response.status == 200
        response = await client.post(mod.BASE + '/api/send', json={}, headers=headers)
        assert response.status == 202
        run = await response.json()
        response = await client.post(mod.BASE + '/api/send', json={}, headers=headers)
        assert response.status == 409
        await asyncio.sleep(0.10)
        assert len(sent) == 1
        assert sent[0][1]['web_push'] == 8030
        assert sent[0][1]['notification']['navigate'].startswith(mod.ORIGIN + mod.BASE + '/landing?test=')
        assert '11111111' not in json.dumps(sent[0][1])
        response = await client.post(mod.BASE + '/api/arrival', json={'test_id': run['test_id'], 'standalone': True}, headers=headers)
        assert response.status == 200
        response = await client.get(mod.BASE + '/api/status', headers=headers)
        value = await response.json()
        assert value['latest']['push_status'] == 201
        assert value['latest']['arrival_standalone'] is True
        assert 'endpoint' not in json.dumps(value)
        assert (tmp_path / 'subscription.json').stat().st_mode & 0o077 == 0
        response = await client.post(mod.BASE + '/api/unsubscribe', json={}, headers=headers)
        assert response.status == 200
        response = await client.post(mod.BASE + '/api/send', json={}, headers=headers)
        assert response.status == 409


@pytest.mark.parametrize('endpoint', [
    'http://web.push.apple.com/a', 'https://web.push.apple.com.evil.example/a',
    'https://127.0.0.1/a', 'https://web.push.apple.com@evil.example/a',
    'https://web.push.apple.com:444/a', 'https://web.push.apple.com/a?secret=x',
    'https://web.push.apple.com/a#x', 'https://web.push.apple.com/a\\x00b',
])
def test_subscription_never_allows_arbitrary_network_targets(endpoint):
    mod = load_server()
    assert hasattr(mod, 'validate_subscription'), 'Endpoint restriction is not implemented'
    data = sample_subscription()
    data['endpoint'] = endpoint
    with pytest.raises(ValueError):
        mod.validate_subscription(data)


@pytest.mark.asyncio
async def test_real_library_encrypts_payload_without_following_redirects(tmp_path, monkeypatch):
    import asyncio
    import requests
    mod = load_server()
    posts = []
    def capture_post(url, **kwargs):
        posts.append((url, kwargs))
        response = requests.Response()
        response.status_code = 201
        response._content = b''
        return response
    monkeypatch.setattr(requests, 'post', capture_post)
    async def authenticate(token):
        return 'owner'
    app = mod.create_app(tmp_path, 'owner', authenticator=authenticate, delay_seconds=0.01)
    headers = {'Authorization': 'Bearer test-owner', 'Origin': mod.ORIGIN}
    async with TestClient(TestServer(app)) as client:
        response = await client.post(mod.BASE+'/api/subscribe', json={'subscription':sample_subscription(),'mode':'declarative','standalone':True}, headers=headers)
        assert response.status == 200
        response = await client.post(mod.BASE+'/api/send',json={},headers=headers)
        assert response.status == 202
        status = {}
        for _ in range(100):
            await asyncio.sleep(.01)
            response = await client.get(mod.BASE+'/api/status',headers=headers)
            status = await response.json()
            if status['latest']['state'] in {'sent','failed'}: break
        assert status['latest']['state'] == 'sent', status
        assert len(posts) == 1
        _, kwargs = posts[0]
        assert kwargs['allow_redirects'] is False
        assert kwargs['timeout'] == 10
        assert isinstance(kwargs['data'], bytes)
        assert b'web_push' not in kwargs['data']
        headers_sent = {key.lower():value for key,value in kwargs['headers'].items()}
        assert headers_sent['content-encoding'] == 'aes128gcm'
        assert headers_sent['authorization'].startswith('vapid ')


@pytest.mark.asyncio
async def test_unsubscribe_does_not_label_inflight_delivery_as_unsent(tmp_path):
    import asyncio
    mod = load_server()
    started = asyncio.Event()
    release = asyncio.Event()
    async def authenticate(token): return 'owner'
    async def slow_sender(subscription, payload):
        started.set()
        await release.wait()
        return 201
    app = mod.create_app(tmp_path, 'owner', authenticator=authenticate, sender=slow_sender, delay_seconds=.01)
    headers = {'Authorization':'Bearer test-owner','Origin':mod.ORIGIN}
    async with TestClient(TestServer(app)) as client:
        await client.post(mod.BASE+'/api/subscribe',json={'subscription':sample_subscription(),'mode':'declarative','standalone':True},headers=headers)
        await client.post(mod.BASE+'/api/send',json={},headers=headers)
        await asyncio.wait_for(started.wait(),1)
        response = await client.post(mod.BASE+'/api/unsubscribe',json={},headers=headers)
        release.set()
        assert response.status == 409, 'An already-started external send cannot be called cancelled-not-sent'

"""Real HTTP contract between the unchanged completion Pipe and Web Push relay.
Only Open WebUI DB and Apple delivery are fixtures; nothing sends externally.
"""
import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from test_server import load_server, sample_subscription


def pipe_helpers():
    path = Path(__file__).parents[2] / 'integrations/openwebui-hermes-progress/tests/test_hermes_progress_pipe.py'
    spec = importlib.util.spec_from_file_location('pipe_test_contract', path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.asyncio
async def test_actual_pipe_final_sentinel_posts_once_to_actual_relay(tmp_path):
    server = load_server()
    helpers = pipe_helpers()
    sent = []
    async def sender(subscription, payload):
        sent.append(payload)
        return 201
    async def auth(token):
        return 'owner' if token == 'test-owner' else None
    app = server.create_app(tmp_path, 'owner', authenticator=auth, sender=sender)
    hermes = await helpers.FakeHermes([{'event': 'run.completed', 'output': 'モデルの生出力'}]).start()
    try:
        async with TestClient(TestServer(app)) as client:
            headers = {'Authorization': 'Bearer test-owner', 'Origin': server.ORIGIN}
            await client.post(server.BASE + '/api/subscribe', headers=headers,
                json={'subscription': sample_subscription(), 'mode': 'declarative', 'standalone': True})
            pipe = helpers.configured_pipe(hermes.base_url)
            pipe.valves.NTFY_SERVER_URL = str(client.make_url(server.BASE + '/notify'))
            pipe.valves.NTFY_TOPIC = (tmp_path / 'relay-token').read_text().strip()
            pipe.valves.OPENWEBUI_PUBLIC_URL = server.ORIGIN
            persisted_reads = []
            async def persisted(chat, message, user):
                persisted_reads.append((chat, message, user))
                return '保存後の題名', '保存後の回答'
            pipe._await_openwebui_completion = persisted
            stream = pipe._stream_response(message='入力は通知しない', history=[], instructions=None,
                session_id='owui_' + 'a' * 32, session_key='openwebui:test',
                event_emitter=lambda event: None, event_call=None, chat_id='chat-one',
                user_id='owner-user', message_id='message-one', ui_context=True)
            async for chunk in stream:
                if chunk == 'data: [DONE]\n\n':
                    break
            await stream.aclose()
            await asyncio.gather(*list(pipe._notification_tasks))
            for _ in range(100):
                if sent:
                    break
                await asyncio.sleep(.01)
            assert len(sent) == 1
            assert sent[0]['notification']['body'] == '保存後の回答'
            assert sent[0]['notification']['title'] == '保存後の題名'
            assert persisted_reads == [('chat-one', 'message-one', 'owner-user')]
            pipe._schedule_completion_notification('owui_' + 'a' * 32,
                chat_id='chat-one', user_id='owner-user', message_id='message-one')
            for session, user, internal in [('cron-job', 'owner-user', False), ('subagent-x', 'owner-user', False),
                                            ('owui_' + 'b' * 32, 'other-user', False), ('owui_' + 'b' * 32, 'owner-user', True)]:
                await pipe._publish_completion_notification(session, chat_id='chat-one', user_id=user,
                    message_id='message-two', is_internal=internal)
            assert len(sent) == 1
    finally:
        await hermes.close()


@pytest.mark.asyncio
async def test_relay_rejects_missing_token_cross_origin_targets_and_no_subscription(tmp_path):
    mod = load_server()
    sent = []
    async def sender(subscription, payload):
        sent.append(payload)
        return 201
    async def auth(token):
        return 'owner'
    async with TestClient(TestServer(mod.create_app(tmp_path, 'owner', authenticator=auth, sender=sender))) as client:
        token = (tmp_path / 'relay-token').read_text().strip()
        path = mod.BASE + '/notify/' + token
        request_headers = {'Title': '保存題名', 'Click': mod.ORIGIN + '/c/chat-one'}
        assert (await client.post(mod.BASE + '/notify/wrong', data='本文', headers=request_headers)).status == 401
        assert (await client.post(path, data='本文', headers=request_headers)).status == 409
        for click in ['https://evil.example/c/x', mod.ORIGIN + '/c/x?next=evil', mod.ORIGIN + '/c/../x', mod.ORIGIN + '/c/x#x', mod.ORIGIN + '/']:
            assert (await client.post(path, data='本文', headers={**request_headers, 'Click': click})).status == 400
        assert (await client.post(path, data='x' * 241, headers=request_headers)).status == 400
        assert (await client.post(path, data='', headers=request_headers)).status == 400
        assert (await client.post(mod.BASE + '/api/notification-arrival', json={'id': 'unknown', 'standalone': True},
            headers={'Origin': mod.ORIGIN, 'Authorization': 'Bearer test-owner'})).status == 400
        assert sent == []


@pytest.mark.asyncio
async def test_bridge_listener_exposes_only_token_authenticated_relay(tmp_path):
    from aiohttp import web
    from aiohttp.test_utils import make_mocked_request
    mod = load_server()
    app = mod.create_app(tmp_path, 'owner')
    token = (tmp_path / 'relay-token').read_text().strip()
    reached = []
    async def handler(request):
        reached.append(request.path)
        return web.json_response({'ok': True})
    for peer, path, credential, expected in [
        ('172.19.0.2', mod.BASE + '/api/status', '', 403),
        ('192.168.0.5', mod.BASE + '/notify/' + token, token, 403),
        ('172.19.0.2', mod.BASE + '/notify/wrong', 'wrong', 401),
        ('172.19.0.2', mod.BASE + '/notify/' + token, token, 200),
    ]:
        request = make_mocked_request('POST', path, match_info={'token': credential}).clone(remote=peer)
        assert (await app.middlewares[0](request, handler)).status == expected
    assert len(reached) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', [410, 'exception'])
async def test_failed_apple_delivery_is_recorded_without_automatic_ntfy_fallback(tmp_path, outcome):
    mod = load_server()
    attempts = []
    async def sender(subscription, payload):
        attempts.append(payload)
        if outcome == 'exception':
            raise TimeoutError('fixture')
        return outcome
    async def auth(token):
        return 'owner'
    async with TestClient(TestServer(mod.create_app(tmp_path, 'owner', authenticator=auth, sender=sender))) as client:
        headers = {'Origin': mod.ORIGIN, 'Authorization': 'Bearer test-owner'}
        await client.post(mod.BASE + '/api/subscribe', headers=headers,
            json={'subscription': sample_subscription(), 'mode': 'declarative', 'standalone': True})
        token = (tmp_path / 'relay-token').read_text().strip()
        result = await client.post(mod.BASE + '/notify/' + token, data='body',
            headers={'Title': 'title', 'Click': mod.ORIGIN + '/c/chat-one'})
        assert result.status == 202
        status = {}
        for _ in range(100):
            status = await (await client.get(mod.BASE + '/api/status', headers=headers)).json()
            if status['notifications'][-1]['state'] == 'failed':
                break
            await asyncio.sleep(.01)
        assert status['notifications'][-1]['state'] == 'failed'
        assert len(attempts) == 1
        assert status['subscribed'] is True

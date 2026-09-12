#!/usr/bin/env python3
"""Owner-authorized LIVE probe: creates one chat and emits one real completion push.
Keeps the chat for the iPhone tap test. HTTP acceptance is not device success.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import time
import uuid
from pathlib import Path

import aiohttp

ANSWER = '通常通知の切替テストです。ホーム画面版の対象チャットが開くことを確認してください。'


def load_helpers(root):
    path = root / 'tests/live_openwebui_notification_probe.py'
    spec = importlib.util.spec_from_file_location('owui_probe_helpers', path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def main(root):
    helpers = load_helpers(root)
    token = helpers.read_secret(root / '.admin-api-key')
    env = helpers.load_env(root / '.env')
    started_at = time.time()
    message_id, parent_id = uuid.uuid4().hex, uuid.uuid4().hex
    prompt = f'通知の実動作確認です。ツールを使わず、次の文だけをそのまま返信してください：{ANSWER}'
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=660)) as client:
        async def status():
            async with client.get('http://127.0.0.1:9122/pda-push-test/api/status',
                                  headers={'Authorization': 'Bearer ' + token}, allow_redirects=False) as response:
                if response.status != 200:
                    raise RuntimeError('Web Push status HTTP ' + str(response.status))
                return await response.json()
        before = await status()
        assert before['subscribed'] and 'notifications' in before
        valves = await helpers.openwebui_json(client, token, 'GET', '/api/v1/functions/id/hermes_progress_pipe/valves')
        assert valves['NTFY_SERVER_URL'] == 'http://host.docker.internal:9122/pda-push-test/notify'
        accepted = await helpers.openwebui_json(client, token, 'POST', '/api/chat/completions', {
            'stream': True, 'model': 'hermes_progress_pipe',
            'messages': [{'role': 'user', 'content': prompt}],
            'session_id': 'pda-normal-push-probe-' + uuid.uuid4().hex,
            'id': message_id, 'parent_id': None,
            'message_ids': [{'model_id': 'hermes_progress_pipe', 'message_id': message_id}],
            'user_message': {'id': parent_id, 'parentId': None, 'childrenIds': [message_id],
                             'role': 'user', 'content': prompt, 'timestamp': int(time.time()),
                             'models': ['hermes_progress_pipe']},
            'background_tasks': {'title_generation': True, 'tags_generation': False, 'follow_up_generation': False},
        })
        assert accepted.get('status') is True and accepted.get('chat_id')
        chat_id = accepted['chat_id']
        deadline = time.monotonic() + 600
        saved, record = {}, {}
        while time.monotonic() < deadline:
            record = await helpers.openwebui_json(client, token, 'GET', '/api/v1/chats/' + chat_id)
            saved = helpers.assistant_message(record, message_id)
            if saved.get('done') is True:
                break
            await asyncio.sleep(.5)
        assert saved.get('done') is True, 'Assistant did not reach saved done=true'
        assert helpers.saved_answer(saved) == ANSWER, 'Unexpected probe answer; inspect retained probe chat'
        deadline = time.monotonic() + 35
        found = []
        while time.monotonic() < deadline:
            current = await status()
            found = [n for n in current['notifications'] if n['target'] == '/c/' + chat_id and n['queued_at'] >= started_at]
            if found and found[-1]['state'] in {'sent', 'failed'}:
                break
            await asyncio.sleep(.25)
        # Allow asynchronous duplicates to become visible, without conflating
        # unrelated concurrent chats with this notification's logical identity.
        await asyncio.sleep(2)
        current = await status()
        found = [n for n in current['notifications'] if n['target'] == '/c/' + chat_id and n['queued_at'] >= started_at]
        legacy = await helpers.ntfy_messages(client, env['PDA_NTFY_SERVER_URL'], env['PDA_NTFY_TOPIC'])
        legacy_matching = [n for n in legacy if n.get('event') == 'message' and n.get('click') == env['PDA_OPENWEBUI_PUBLIC_URL'].rstrip('/') + '/c/' + chat_id]
        record = await helpers.openwebui_json(client, token, 'GET', '/api/v1/chats/' + chat_id)
        title = str(record.get('title') or (record.get('chat') or {}).get('title') or 'New Chat').strip()
        statuses = saved.get('statusHistory') or []
        result = {'chat_id': chat_id, 'saved_done': True, 'saved_answer_matches': True,
                  'progress_has_done': any(n.get('description') == '完了' for n in statuses),
                  'completion_push_count': len(found), 'legacy_ntfy_matching_count': len(legacy_matching),
                  'push_status': found[-1].get('push_status') if found else None,
                  'title_matches_saved': bool(found) and found[-1]['title_sha256'] == hashlib.sha256(title.encode()).hexdigest(),
                  'body_matches_saved': bool(found) and found[-1]['body_sha256'] == hashlib.sha256(ANSWER.encode()).hexdigest(),
                  'notification_id': found[-1]['id'] if found else None,
                  'arrival_standalone': found[-1].get('arrival_standalone') if found else None,
                  'physical_receipt_and_safari_tabs': 'requires_owner_confirmation',
                  'started_at': started_at, 'finished_at': time.time()}
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        assert len(found) == 1 and not legacy_matching, 'Expected exactly one Web Push and no ntfy duplicate'
        assert result['push_status'] == 201 and result['title_matches_saved'] and result['body_matches_saved']
        assert result['progress_has_done']
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--openwebui-dir', type=Path, default=Path.home() / 'openwebui')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = asyncio.run(main(args.openwebui_dir))
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')

#!/usr/bin/env python3
"""Switch only normal Open WebUI completion delivery: webpush, ntfy, off."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
from pathlib import Path

import requests

ORIGIN = 'https://pda-web.tailaff53a.ts.net'
RELAY = 'http://host.docker.internal:9122/pda-push-test/notify'
ROUTE_KEYS = ('NTFY_SERVER_URL', 'NTFY_TOPIC')
VALVES_API = '/api/v1/functions/id/hermes_progress_pipe/valves'


def private_read(path):
    if path.stat().st_mode & 0o077:
        raise ValueError('Credential-bearing file must be mode 0600')
    return path.read_text().strip()


def private_json(path, value):
    temp = path.with_suffix('.tmp')
    with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as output:
        json.dump(value, output)
    os.replace(temp, path)


def summary(current, route_path):
    saved = json.loads(private_read(route_path)) if route_path.exists() else None
    route = {k: current[k] for k in ROUTE_KEYS}
    return {'mode': 'off' if not route['NTFY_TOPIC'] else 'webpush' if route['NTFY_SERVER_URL'] == RELAY else 'ntfy',
            'persisted_matches': saved == route, 'enabled': bool(route['NTFY_TOPIC'])}


def switch(action, state, root, request):
    current = request('GET')
    route_path = root / '.completion-push.json'
    if action == 'status':
        return summary(current, route_path)
    original = {k: current[k] for k in ROUTE_KEYS}
    backup = state / 'ntfy-rollback.json'
    if action == 'webpush':
        if current.get('OPENWEBUI_PUBLIC_URL') != ORIGIN:
            raise ValueError('Unexpected Open WebUI origin')
        token = private_read(state / 'relay-token')
        if not re.fullmatch(r'[a-f0-9]{64}', token):
            raise ValueError('Invalid relay token')
        if not backup.exists():
            if current['NTFY_SERVER_URL'] == RELAY:
                raise ValueError('Original ntfy route is unavailable; do not overwrite backup')
            private_json(backup, original)
        desired = {'NTFY_SERVER_URL': RELAY, 'NTFY_TOPIC': token}
    elif action == 'ntfy':
        desired = json.loads(private_read(backup))
        if set(desired) != set(ROUTE_KEYS):
            raise ValueError('Unexpected rollback fields')
    elif action == 'off':
        desired = {**original, 'NTFY_TOPIC': ''}
    else:
        raise ValueError('Unknown notification mode')
    updated = {**current, **desired}
    try:
        request('POST', updated)
        if request('GET') != updated:
            raise RuntimeError('Notification route read-back differs')
        private_json(route_path, desired)
    except Exception:
        # Restore only our fields, preserving unrelated concurrent Valve changes.
        restore = {**request('GET'), **original}
        request('POST', restore)
        if request('GET') != restore:
            raise RuntimeError('Notification rollback read-back failed') from None
        raise
    return summary(updated, route_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['webpush', 'ntfy', 'off', 'status'])
    parser.add_argument('--state-dir', type=Path, default=Path.home() / '.local/state/pda/webpush-spike')
    parser.add_argument('--openwebui-dir', type=Path, default=Path.home() / 'openwebui')
    args = parser.parse_args()
    token = private_read(args.openwebui_dir / '.admin-api-key')
    with requests.Session() as session:
        session.trust_env = False
        session.headers['Authorization'] = 'Bearer ' + token

        def request(method, payload=None):
            path = VALVES_API + ('/update' if method == 'POST' else '')
            response = session.request(method, 'http://127.0.0.1:9120' + path,
                                       json=payload, allow_redirects=False, timeout=10)
            if response.status_code != 200:
                raise RuntimeError('Open WebUI Valves HTTP ' + str(response.status_code))
            return response.json()

        if args.action == 'webpush':
            response = session.get('http://127.0.0.1:9122/pda-push-test/api/status', allow_redirects=False, timeout=5)
            if response.status_code != 200:
                raise RuntimeError('Owner-authenticated Web Push service is unavailable')
            status = response.json()
            if not status.get('subscribed') or 'notifications' not in status:
                raise RuntimeError('A working Home Screen subscription and normal relay are required')
        with os.fdopen(os.open(args.state_dir / 'notification-control.lock', os.O_WRONLY | os.O_CREAT, 0o600), 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            print(json.dumps(switch(args.action, args.state_dir, args.openwebui_dir, request)))


if __name__ == '__main__':
    main()

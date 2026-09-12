import importlib.util
import json
from pathlib import Path

import pytest


def load_control():
    path = Path(__file__).with_name('notifications.py')
    assert path.exists(), 'Reversible normal-notification control is not implemented'
    spec = importlib.util.spec_from_file_location('notification_control', path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_switch_changes_only_notification_route_and_persists_for_installer(tmp_path):
    mod = load_control()
    state = tmp_path / 'state'
    root = tmp_path / 'openwebui'
    state.mkdir()
    root.mkdir()
    (state / 'relay-token').write_text('a' * 64)
    (state / 'relay-token').chmod(0o600)
    current = {'NTFY_SERVER_URL': 'https://ntfy.sh', 'NTFY_TOPIC': 'old-topic',
               'OPENWEBUI_PUBLIC_URL': mod.ORIGIN, 'REQUIRE_REGISTERED_PLAN': False,
               'HERMES_API_KEY': 'test-secret', 'NTFY_ALLOWED_USER_ID': 'owner'}
    original = dict(current)
    def request(method, payload=None):
        if method == 'POST':
            assert isinstance(payload, dict)
            current.clear()
            current.update(payload)
        return dict(current)
    result = mod.switch('webpush', state, root, request)
    assert result['mode'] == 'webpush'
    assert result['persisted_matches'] is True
    assert current['NTFY_SERVER_URL'] == 'http://host.docker.internal:9122/pda-push-test/notify'
    assert current['NTFY_TOPIC'] == 'a' * 64
    assert {k: v for k, v in current.items() if k not in mod.ROUTE_KEYS} == {k: v for k, v in original.items() if k not in mod.ROUTE_KEYS}
    assert json.loads((root / '.completion-push.json').read_text()) == {k: current[k] for k in mod.ROUTE_KEYS}
    assert (root / '.completion-push.json').stat().st_mode & 0o077 == 0
    assert 'test-secret' not in (state / 'ntfy-rollback.json').read_text()
    assert mod.switch('ntfy', state, root, request)['mode'] == 'ntfy'
    assert current == original
    assert mod.switch('off', state, root, request)['mode'] == 'off'
    assert current['NTFY_TOPIC'] == ''


def test_failed_readback_restores_route_and_does_not_save_success(tmp_path):
    mod = load_control()
    state, root = tmp_path / 'state', tmp_path / 'openwebui'
    state.mkdir()
    root.mkdir()
    (state / 'relay-token').write_text('a' * 64)
    (state / 'relay-token').chmod(0o600)
    current = {'NTFY_SERVER_URL': 'https://ntfy.sh', 'NTFY_TOPIC': 'old-topic',
               'OPENWEBUI_PUBLIC_URL': mod.ORIGIN, 'REQUIRE_REGISTERED_PLAN': False}
    original = dict(current)
    posts = []
    def request(method, payload=None):
        if method == 'POST':
            assert isinstance(payload, dict)
            posts.append(payload)
            current.update(payload)
            if len(posts) == 1:
                current['NTFY_TOPIC'] = 'wrong-write'
        return dict(current)
    with pytest.raises(RuntimeError, match='read-back'):
        mod.switch('webpush', state, root, request)
    assert len(posts) == 2
    assert current == original
    assert not (root / '.completion-push.json').exists()

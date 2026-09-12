import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest


def load_control():
    path = Path(__file__).with_name('control.py')
    assert path.exists(), 'Reusable banner visibility control is not implemented'
    spec = importlib.util.spec_from_file_location('push_diagnostic_control', path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_visibility_flag_hides_and_restores_only_its_own_banner(tmp_path):
    mod = load_control()
    unrelated = {'id': 'other-banner', 'content': 'preserve latest content', 'timestamp': 123}
    banners = [deepcopy(unrelated), {'id': mod.BANNER_ID, 'content': 'old test entry'}]
    writes = []

    def request(method, path, payload=None):
        nonlocal banners
        assert path == '/api/v1/configs/banners'
        if method == 'POST':
            assert payload is not None
            writes.append(deepcopy(payload))
            banners = deepcopy(payload['banners'])
        return deepcopy(banners)

    state = tmp_path / 'settings.json'
    assert mod.read_visible(state) is False
    mod.set_visible(state, False, request)
    assert banners == [unrelated]
    assert json.loads(state.read_text()) == {'show_banner': False}
    assert state.stat().st_mode & 0o077 == 0
    mod.set_visible(state, True, request)
    assert banners[0] == unrelated
    assert len(banners) == 2
    entry = banners[1]
    assert entry['id'] == mod.BANNER_ID
    assert 'href="/pda-push-test/"' in entry['content']
    assert 'data-sveltekit-reload' in entry['content']
    assert 'この会話' not in entry['content'] and '/c/' not in entry['content']
    assert mod.read_visible(state) is True
    count = len(writes)
    mod.set_visible(state, True, request)
    assert len(writes) == count  # repeated show is a no-op, no duplicate entry
    banners[0]['content'] = 'edited elsewhere after showing'
    mod.set_visible(state, False, request)
    assert banners == [{'id': 'other-banner', 'content': 'edited elsewhere after showing', 'timestamp': 123}]
    assert mod.read_visible(state) is False


def test_operator_commands_apply_the_flag_and_refuse_a_dead_entry(tmp_path, capsys):
    mod = load_control()
    assert hasattr(mod, 'main'), 'Reusable operator commands are not implemented'
    banners = []
    def request(method, path, payload=None):
        nonlocal banners
        if method == 'POST':
            assert payload is not None
            banners = deepcopy(payload['banners'])
        return deepcopy(banners)
    def run(action, ready=True):
        return mod.main([action, '--state-dir', str(tmp_path)], request=request, ready=lambda: ready)
    run('hide')
    with pytest.raises(RuntimeError, match='service'):
        run('show', ready=False)
    assert banners == []
    run('show')
    assert len(banners) == 1
    run('status')
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['matches'] is True
    (tmp_path / 'settings.json').write_text('{"show_banner": false}')
    run('apply')
    assert banners == []


def test_failed_readback_never_persists_a_successful_flag(tmp_path):
    mod = load_control()
    state = tmp_path / 'settings.json'
    state.write_text('{"show_banner": false}')
    def ignored_write(method, path, payload=None):
        return []  # Simulate HTTP 200 with a change that did not persist.
    with pytest.raises(RuntimeError, match='read-back'):
        mod.set_visible(state, True, ignored_write)
    assert mod.read_visible(state) is False


def test_local_admin_uses_private_credential_and_bounded_no_redirect_loopback(tmp_path, monkeypatch):
    import requests
    mod = load_control()
    assert hasattr(mod, 'LocalAdmin'), 'Local admin transport is not implemented'
    secret = tmp_path / 'admin-key'
    secret.write_text('fixture-not-a-real-token')
    secret.chmod(0o644)
    with pytest.raises(ValueError, match='private'):
        mod.LocalAdmin(secret)
    secret.chmod(0o600)
    calls = []
    def capture(session, method, url, **kwargs):
        calls.append((method, url, kwargs))
        response = requests.Response()
        response.status_code = 200
        response._content = b'[]'
        return response
    monkeypatch.setattr(requests.Session, 'request', capture)
    client = mod.LocalAdmin(secret)
    assert client.request('GET', mod.BANNERS_API) == []
    method, url, kwargs = calls[0]
    assert url == 'http://127.0.0.1:9120/api/v1/configs/banners'
    assert kwargs['allow_redirects'] is False and kwargs['timeout'] == 10
    assert kwargs['headers']['Authorization'] == 'Bearer fixture-not-a-real-token'
    with pytest.raises(ValueError):
        client.request('POST', 'https://evil.example')
    assert len(calls) == 1


def test_cli_help_and_readiness_for_a_reusable_service(monkeypatch):
    import subprocess
    import sys
    import requests
    mod = load_control()
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('control.py')), '--help'], capture_output=True, text=True, check=True)
    assert '{show,hide,apply,status}' in result.stdout, 'No executable operator entry point'
    assert hasattr(mod, 'service_ready')
    response = requests.Response()
    response.status_code = 200
    response._content = b'<script src="/pda-push-test/app.js"></script>'
    def capture(session, method, url, **kwargs):
        assert url == 'http://127.0.0.1:9122/pda-push-test/'
        assert kwargs['allow_redirects'] is False and kwargs['timeout'] == 3
        return response
    monkeypatch.setattr(requests.Session, 'request', capture)
    assert mod.service_ready() is True
    response.status_code = 502
    assert mod.service_ready() is False


@pytest.mark.parametrize('value', ['false', 1, None])
def test_flag_must_be_a_json_boolean(tmp_path, value):
    mod = load_control()
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'show_banner': value}))
    with pytest.raises(ValueError):
        mod.read_visible(path)

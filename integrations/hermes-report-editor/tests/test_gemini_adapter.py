"""Gemini one-shot adapter tests use only a local HTTP server and synthetic keys."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import threading
import time
import pytest


def adapter_module():
    try:
        return importlib.import_module('report_editor.adapters.gemini')
    except ModuleNotFoundError:
        pytest.fail('Gemini adapter is not implemented')


def test_gemini_real_sdk_boundary_preserves_request_and_provider_metadata(tmp_path, monkeypatch):
    module = adapter_module()
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass
        def do_POST(self):
            requests.append({'body': json.loads(self.rfile.read(int(self.headers['Content-Length']))),
                             'correct_key': self.headers.get('Authorization') == 'Bearer designated-fixture-key'})
            body = {'id': 'gemini-response-1', 'object': 'chat.completion', 'created': 1,
                    'model': 'provider-model-label', 'choices': [{'index': 0, 'message': {'role': 'assistant',
                    'content': '{"action":"send","text":"実測範囲だけを報告します。"}',
                    'reasoning_content': 'PRIVATE_REASONING_CANARY'}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 23, 'completion_tokens': 17, 'total_tokens': 40,
                              'completion_tokens_details': {'reasoning_tokens': 7}}}
            wire = json.dumps(body).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(wire))); self.end_headers(); self.wfile.write(wire)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    key_file = tmp_path / 'fixture.env'
    key_file.write_text('PDA_REPORT_EDITOR_GEMINI_API_KEY=designated-fixture-key\nOTHER_KEY=unrelated-fixture-key\n')
    before = key_file.read_bytes()
    monkeypatch.setattr(module, 'BASE_URL', f'http://127.0.0.1:{server.server_port}/v1/')
    try:
        adapter = module.GeminiAdapter({'credential_file': str(key_file), 'model': 'gemini-3.8-flash',
                                        'reasoning_effort': 'high'})
        material = {'author_handoff': {'next_action': 'unknown'}}
        instruction = 'この原文指示を変更しない。'
        result = adapter._complete(material, time.monotonic() + 5, instruction)
        assert len(requests) == 1 and requests[0]['correct_key']
        body = requests[0]['body']
        assert body['model'] == 'gemini-3.8-flash' and body['reasoning_effort'] == 'high'
        assert body['messages'] == [{'role': 'system', 'content': instruction},
                                    {'role': 'user', 'content': json.dumps(material, ensure_ascii=False)}]
        assert body.get('tools') in (None, []) and body.get('n', 1) == 1
        assert result['text'] == '{"action":"send","text":"実測範囲だけを報告します。"}'
        assert result['finish_reason'] == 'stop' and result['calls'] == 1
        assert result['provider_response']['model'] == 'provider-model-label'
        assert result['effective']['model'] == 'gemini-3.8-flash'
        assert result['effective']['sdk_max_retries'] == 0
        assert result['usage']['input_tokens'] == 23 and result['usage']['output_tokens'] == 17
        public = json.dumps(result, ensure_ascii=False)
        assert 'PRIVATE_REASONING_CANARY' not in public
        assert 'designated-fixture-key' not in public and 'unrelated-fixture-key' not in public
        assert key_file.read_bytes() == before
    finally:
        server.shutdown(); server.server_close(); thread.join(1)


def test_native_gemini_route_keeps_same_system_user_and_high(tmp_path, monkeypatch):
    module = adapter_module(); calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass
        def do_POST(self):
            calls.append({'path': self.path, 'body': json.loads(self.rfile.read(int(self.headers['Content-Length']))),
                          'correct_key': self.headers.get('x-goog-api-key') == 'native-fixture-key'})
            response = {'responseId': 'native-response', 'modelVersion': 'provider-native-label',
                        'candidates': [{'content': {'role': 'model', 'parts': [
                            {'thought': True, 'text': 'PRIVATE_THOUGHT'}, {'text': '変更しない生本文。'}]}, 'finishReason': 'STOP'}],
                        'usageMetadata': {'promptTokenCount': 20, 'candidatesTokenCount': 11, 'thoughtsTokenCount': 8}}
            wire = json.dumps(response).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(wire))); self.end_headers(); self.wfile.write(wire)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    key_file = tmp_path / 'native.env'; key_file.write_text('PDA_REPORT_EDITOR_GEMINI_API_KEY=native-fixture-key\n')
    monkeypatch.setattr(module, 'BASE_URL', f'http://127.0.0.1:{server.server_port}/v1/')
    monkeypatch.setattr(module, 'NATIVE_BASE_URL', f'http://127.0.0.1:{server.server_port}/v1beta/', raising=False)
    try:
        result = module.GeminiAdapter({'credential_file': str(key_file), 'transport': 'native',
                                      'model': 'gemini-3.8-flash', 'reasoning_effort': 'high'})._complete(
                                          {'same': '元入力'}, time.monotonic() + 5, '元system指示')
        assert len(calls) == 1 and calls[0]['correct_key']
        assert calls[0]['path'] == '/v1beta/models/gemini-3.8-flash:generateContent'
        body = calls[0]['body']
        assert body['systemInstruction'] == {'parts': [{'text': '元system指示'}]}
        assert body['contents'] == [{'role': 'user', 'parts': [{'text': json.dumps({'same': '元入力'}, ensure_ascii=False)}]}]
        assert body['generationConfig']['thinkingConfig']['thinkingLevel'] == 'HIGH'
        assert not body.get('tools')
        assert result['text'] == '変更しない生本文。' and result['finish_reason'] == 'stop'
        assert result['provider_response']['model'] == 'provider-native-label'
        assert result['usage'] == {'input_tokens': 20, 'output_tokens': 11}
        assert 'PRIVATE_THOUGHT' not in json.dumps(result) and 'native-fixture-key' not in json.dumps(result)
    finally:
        server.shutdown(); server.server_close(); thread.join(1)


@pytest.fixture
def local_gemini(tmp_path, monkeypatch):
    """Real HTTP with synthetic credentials; never reaches a provider."""
    module = adapter_module()
    state = {'requests': [], 'status': 200, 'body': {}, 'delay': False, 'disconnect': False}
    release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass
        def do_POST(self):
            state['requests'].append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            if state['disconnect']:
                self.close_connection = True
                return
            if state['delay']:
                release.wait(5)
            wire = json.dumps(state['body']).encode()
            self.send_response(state['status'])
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(wire)))
            self.end_headers()
            try:
                self.wfile.write(wire)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    key_file = tmp_path / 'fixture.env'
    key_file.write_text('PDA_REPORT_EDITOR_GEMINI_API_KEY=local-fixture-secret\n')
    url = f'http://127.0.0.1:{server.server_port}/'
    monkeypatch.setattr(module, 'BASE_URL', url)
    monkeypatch.setattr(module, 'NATIVE_BASE_URL', url)
    state['config'] = {'credential_file': str(key_file), 'model': 'gemini-3.8-flash',
                       'reasoning_effort': 'high', 'local_test_url': url}
    try:
        yield module, state
    finally:
        release.set()
        server.shutdown(); server.server_close(); thread.join(1)


def response_body(route, text: str | None = 'raw fixture text', finish=None):
    if route == 'native':
        return {'candidates': [{'content': {'role': 'model', 'parts': [{'text': text}]},
                                'finishReason': finish or 'STOP'}]}
    return {'id': 'fixture', 'object': 'chat.completion', 'created': 1, 'model': 'fixture-model',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': text},
                         'finish_reason': finish or 'stop'}]}


@pytest.mark.parametrize('route', ['openai', 'native'])
@pytest.mark.parametrize('failure', ['authentication_missing', 'deadline_exhausted'])
def test_preflight_failure_never_opens_transport(local_gemini, route, failure):
    module, state = local_gemini
    config = {**state['config'], 'transport': route}
    deadline = time.monotonic() + 4
    if failure == 'authentication_missing':
        from pathlib import Path
        Path(config['credential_file']).write_text('UNRELATED_KEY=not-the-designated-key\n')
    else:
        deadline = time.monotonic() - 1
    with pytest.raises(module.GeminiAdapterError, match='^' + failure + '$'):
        module.GeminiAdapter(config)._complete({'public': 'material'}, deadline, 'instruction')
    assert state['requests'] == []


@pytest.mark.parametrize('route', ['openai', 'native'])
@pytest.mark.parametrize('kind,reason', [
    ('503', 'gemini_request_failed'), ('empty', 'empty_response'),
    ('nonstop', 'incomplete_response'), ('nontext', 'nontext_response'),
    ('timeout', 'gemini_request_failed'), ('disconnect', 'gemini_request_failed'),
])
def test_negative_http_response_is_rejected_without_retry(local_gemini, route, kind, reason):
    module, state = local_gemini
    state['body'] = response_body(route)
    if kind == '503':
        state.update(status=503, body={'error': {'code': 503, 'status': 'UNAVAILABLE',
                     'message': 'busy local-fixture-secret'}})
    elif kind == 'empty':
        state['body'] = response_body(route, ' ')
    elif kind == 'nonstop':
        state['body'] = response_body(route, finish='MAX_TOKENS' if route == 'native' else 'length')
    elif kind == 'nontext':
        state['body'] = response_body(route, None)
    elif kind == 'timeout':
        state['delay'] = True
    elif kind == 'disconnect':
        state['disconnect'] = True
    start = time.monotonic()
    with pytest.raises(module.GeminiAdapterError, match='^' + reason + '$') as caught:
        module.GeminiAdapter({**state['config'], 'transport': route})._complete(
            {'public': 'material'}, start + (1 if kind == 'timeout' else 4), 'instruction')
    assert len(state['requests']) == 1
    assert 'local-fixture-secret' not in json.dumps(caught.value.details)
    if kind == '503':
        assert caught.value.details['http_status'] == 503
    if kind == 'timeout':
        assert time.monotonic() - start < 1.1


class LocalGeminiWorker:
    """Test-only factory selects loopback while exercising the actual worker."""
    def __init__(self, config):
        self.config = config
    def edit(self, request, deadline):
        module = adapter_module()
        from urllib.parse import urlparse
        assert urlparse(self.config['local_test_url']).hostname == '127.0.0.1'
        setattr(module, 'BASE_URL', self.config['local_test_url'])
        setattr(module, 'NATIVE_BASE_URL', self.config['local_test_url'])
        return module.GeminiAdapter(self.config).edit(request, deadline)
    revise = edit


@pytest.mark.parametrize('case', ['503', 'empty', 'nonstop', 'timeout', 'cancel', 'rejected_then_503'])
def test_native_failure_common_worker_fallback_and_cleanup(local_gemini, monkeypatch, case):
    from report_editor import pipeline
    from dialogue_fixtures import A_REQUEST
    module, state = local_gemini
    state['body'] = response_body('native')
    if case in {'503', 'rejected_then_503'}:
        state.update(status=503, body={'error': {'code': 503, 'message': 'busy'}})
    elif case == 'empty':
        state['body'] = response_body('native', '')
    elif case == 'nonstop':
        state['body'] = response_body('native', finish='MAX_TOKENS')
    else:
        state['delay'] = True
    config = {**state['config'], 'transport': 'native', 'factory': 'test_gemini_adapter:LocalGeminiWorker'}
    settings = {'timeout_seconds': 2, 'adapter': config}
    author = None
    if case == 'rejected_then_503':
        settings['adapter'] = {'factory': 'dialogue_fixtures:ReturnReport'}
        author = config
    processes = []
    real_popen = pipeline.subprocess.Popen
    def record_popen(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        processes.append(proc)
        return proc
    monkeypatch.setattr(pipeline.subprocess, 'Popen', record_popen)
    result = pipeline.edit(A_REQUEST, settings,
                           lambda: case == 'cancel' and bool(state['requests']), author=author)
    assert len(state['requests']) == 1
    assert processes and all(proc.poll() is not None for proc in processes)
    assert result['elapsed_seconds'] < 2.2
    if case == 'cancel':
        assert result['reason'] == 'cancelled' and result['text'] == ''
    elif case == 'rejected_then_503':
        assert result['rejected'] and result['text'] == pipeline.UNRESOLVED
        assert result['text'] != A_REQUEST['draft']
    else:
        assert result['reason'] in {'adapter_failure', 'timeout'}
        assert result['text'] == A_REQUEST['draft'] and not result['rejected']


def test_native_malformed_candidate_yields_safe_adapter_error(local_gemini):
    module, state = local_gemini
    state['body'] = {'candidates': [None]}
    with pytest.raises(module.GeminiAdapterError, match='^invalid_choices$'):
        module.GeminiAdapter({**state['config'], 'transport': 'native'})._complete(
            {'public': 'material'}, time.monotonic() + 4, 'instruction')
    assert len(state['requests']) == 1

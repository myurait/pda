"""One tools-free Gemini native/compatible request using one existing key reference.

The common worker owns the hard wall deadline. No provider fallback, credential
mutation, or SDK retry. Provider text is never rewritten; hidden reasoning is
not included in the diagnostic response projection.
"""
import json
import math
import re
from pathlib import Path
import time

import httpx
from dotenv import dotenv_values
from openai import APIError, OpenAI

BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/'
NATIVE_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/'
KEY_NAME = 'PDA_REPORT_EDITOR_GEMINI_API_KEY'


class GeminiAdapterError(RuntimeError):
    def __init__(self, reason, details=None):
        super().__init__(reason)
        self.details = details or {}


class GeminiAdapter:
    def __init__(self, config):
        self.config = dict(config)

    def edit(self, request, deadline):
        from ..contracts import EDITOR_SYSTEM
        return self._complete(request, deadline, EDITOR_SYSTEM)

    def _complete(self, request, deadline, instructions):
        from hermes_constants import get_hermes_home
        remaining = deadline - time.monotonic() - 0.25
        if not math.isfinite(remaining) or remaining <= 0:
            raise GeminiAdapterError('deadline_exhausted')
        model = self.config.get('model', 'gemini-3.8-flash')
        effort = self.config.get('reasoning_effort', 'high')
        route = self.config.get('transport', 'openai')
        if (not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,119}', model)
                or effort not in {'minimal', 'low', 'medium', 'high'} or route not in {'openai', 'native'}):
            raise GeminiAdapterError('invalid_configuration')
        if not isinstance(instructions, str) or not instructions:
            raise GeminiAdapterError('invalid_instructions')
        key_file = Path(self.config.get('credential_file') or get_hermes_home() / '.env')
        try:
            key = dotenv_values(key_file, interpolate=False).get(KEY_NAME)
        except (OSError, UnicodeError):
            raise GeminiAdapterError('credential_unreadable') from None
        if not isinstance(key, str) or not key.strip():
            raise GeminiAdapterError('authentication_missing')
        user_text = json.dumps(request, ensure_ascii=False)
        if key in user_text or key in instructions:
            raise GeminiAdapterError('secret_in_input')
        remaining = deadline - time.monotonic() - 0.25
        if remaining <= 0:
            raise GeminiAdapterError('deadline_exhausted')
        if route == 'native':
            return self._native(user_text, instructions, model, effort, key, key_file, remaining, deadline)
        try:
            with httpx.Client(follow_redirects=False, timeout=remaining) as transport:
                with OpenAI(api_key=key, base_url=BASE_URL, max_retries=0,
                            timeout=remaining, http_client=transport) as client:
                    response = client.chat.completions.create(
                        model=model, reasoning_effort=effort, n=1, stream=False, tools=[],
                        messages=[{'role': 'system', 'content': instructions},
                                  {'role': 'user', 'content': user_text}],
                    )
        except APIError as exc:
            details = {'error_type': type(exc).__name__, 'http_status': getattr(exc, 'status_code', None)}
            raw_response = getattr(exc, 'response', None)
            if raw_response is not None:
                try:
                    error = raw_response.json().get('error', {})
                    if isinstance(error, dict):
                        details['provider_error'] = {k: str(error[k]).replace(key, '[REDACTED]')[:2000]
                                                     for k in ('code', 'status', 'message') if k in error}
                except (ValueError, AttributeError):
                    pass
            raise GeminiAdapterError('gemini_request_failed', details) from None
        choices = response.choices
        if not isinstance(choices, list) or len(choices) != 1:
            raise GeminiAdapterError('invalid_choices')
        choice = choices[0]
        message = choice.message
        text = message.content
        raw_usage = response.usage.model_dump(exclude_none=True) if response.usage is not None else None
        projection = {'id': response.id, 'model': response.model, 'finish_reason': choice.finish_reason,
                      'role': message.role, 'text': text if isinstance(text, str) else None,
                      'usage': raw_usage, 'projection_excludes': ['internal reasoning', 'signatures', 'tool arguments']}
        if isinstance(text, str) and key in text:
            projection['text'] = '[REDACTED: credential echoed]'
            raise GeminiAdapterError('secret_in_output', {'provider_response': projection})
        if getattr(message, 'tool_calls', None) or getattr(message, 'function_call', None):
            raise GeminiAdapterError('tools_forbidden', {'provider_response': projection})
        if not isinstance(text, str):
            raise GeminiAdapterError('nontext_response', {'provider_response': projection})
        if not text.strip():
            raise GeminiAdapterError('empty_response', {'provider_response': projection})
        if choice.finish_reason != 'stop':
            raise GeminiAdapterError('incomplete_response', {'provider_response': projection})
        if time.monotonic() >= deadline:
            raise GeminiAdapterError('deadline_exhausted', {'provider_response': projection})
        usage = None if raw_usage is None else {
            'input_tokens': raw_usage.get('prompt_tokens'),
            'output_tokens': raw_usage.get('completion_tokens'),
        }
        return {'text': text, 'finish_reason': 'stop', 'calls': 1, 'usage': usage,
                'provider_response': projection,
                'effective': {'provider': 'gemini', 'model': model, 'reasoning_effort': effort,
                              'credential_reference': str(key_file) + ':' + KEY_NAME,
                              'sdk_max_retries': 0, 'tools': False, 'follow_redirects': False},
                'measurement': {'logical_adapter_invocations': 1,
                                'physical_transport_requests': None, 'billed_requests': None, 'fee': None}}

    def _native(self, user_text, instructions, model, effort, key, key_file, remaining, deadline):
        payload = {'systemInstruction': {'parts': [{'text': instructions}]},
                   'contents': [{'role': 'user', 'parts': [{'text': user_text}]}],
                   'generationConfig': {'candidateCount': 1,
                       'thinkingConfig': {'thinkingLevel': effort.upper(), 'includeThoughts': False}}}
        try:
            # HTTPX's default transport has no connection retries. Keep the
            # same proxy/environment routing as the successful native probe.
            with httpx.Client(follow_redirects=False, timeout=remaining) as client:
                response = client.post(NATIVE_BASE_URL + 'models/' + model + ':generateContent',
                                       headers={'x-goog-api-key': key}, json=payload)
                if not response.is_success:
                    details = {'http_status': response.status_code,
                               'content_type': response.headers.get('content-type')}
                    try:
                        body = response.json()
                        body = body[0] if isinstance(body, list) and len(body) == 1 else body
                        error = body.get('error', {}) if isinstance(body, dict) else {}
                        details['provider_error'] = {k: str(error[k]).replace(key, '[REDACTED]')[:2000]
                                                     for k in ('code', 'status', 'message') if k in error}
                    except ValueError:
                        details['safe_message'] = response.reason_phrase
                    raise GeminiAdapterError('gemini_request_failed', details)
                try:
                    body = response.json()
                except ValueError:
                    raise GeminiAdapterError('invalid_json_response') from None
        except httpx.HTTPError as exc:
            raise GeminiAdapterError('gemini_request_failed', {'error_type': type(exc).__name__}) from None
        if not isinstance(body, dict):
            raise GeminiAdapterError('invalid_json_response')
        candidates = body.get('candidates')
        if not isinstance(candidates, list) or len(candidates) != 1:
            raise GeminiAdapterError('invalid_choices', {'block_reason': body.get('promptFeedback', {}).get('blockReason')})
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise GeminiAdapterError('invalid_choices')
        content = candidate.get('content') or {}
        parts = content.get('parts') or []
        texts = []
        for part in parts:
            if part.get('thought'): continue
            if not isinstance(part.get('text'), str):
                raise GeminiAdapterError('nontext_response')
            texts.append(part['text'])
        text = ''.join(texts)
        usage_metadata = body.get('usageMetadata')
        finish = candidate.get('finishReason')
        projection = {'id': body.get('responseId'), 'model': body.get('modelVersion'),
                      'finish_reason': finish, 'role': content.get('role'), 'text': text,
                      'usage': usage_metadata, 'projection_excludes': ['thought parts', 'thought signatures', 'tool arguments']}
        if key in text:
            projection['text'] = '[REDACTED: credential echoed]'
            raise GeminiAdapterError('secret_in_output', {'provider_response': projection})
        if not text.strip():
            raise GeminiAdapterError('empty_response', {'provider_response': projection})
        if finish != 'STOP':
            raise GeminiAdapterError('incomplete_response', {'provider_response': projection})
        if time.monotonic() >= deadline:
            raise GeminiAdapterError('deadline_exhausted', {'provider_response': projection})
        usage = None if not isinstance(usage_metadata, dict) else {
            'input_tokens': usage_metadata.get('promptTokenCount'),
            'output_tokens': usage_metadata.get('candidatesTokenCount')}
        return {'text': text, 'finish_reason': 'stop', 'calls': 1, 'usage': usage,
                'provider_response': projection,
                'effective': {'provider': 'gemini', 'model': model, 'transport': 'native',
                              'reasoning_effort': effort, 'thinking_level': effort.upper(),
                              'credential_reference': str(key_file) + ':' + KEY_NAME,
                              'http_transport_retries': 0, 'tools': False, 'follow_redirects': False},
                'measurement': {'logical_adapter_invocations': 1, 'physical_transport_requests': None,
                                'billed_requests': None, 'fee': None}}

"""Public Open WebUI Pipe -> real runs/AIAgent/SQLite regression path."""
import asyncio
import time
import importlib.util
import json
from pathlib import Path
import sys
import pytest
from harness import runtime,EDITED,RAW
from test_invariants import metrics


def load_pipe():
    source=Path(__file__).resolve().parents[2]/'openwebui-hermes-progress/functions/hermes_progress_pipe.py'
    spec=importlib.util.spec_from_file_location('report_editor_test_pipe',source)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module.Pipe()


@pytest.mark.asyncio
@pytest.mark.parametrize('stream',[True,False])
async def test_public_pipe_returns_only_edited_body_once(tmp_path,monkeypatch,stream):
    async with runtime(tmp_path,monkeypatch) as (client,db,seen,home):
        pipe=load_pipe()
        pipe.valves=pipe.Valves(HERMES_API_URL=str(client.make_url('/v1')),HERMES_API_KEY='fixture-token',ENABLE_REPORT_EDITOR=True,PROGRESS_HEARTBEAT_SECONDS=0,REQUIRE_REGISTERED_PLAN=False)
        statuses=[]
        async def emitter(event):statuses.append(event)
        result=await pipe.pipe({'messages':[{'role':'user','content':'CASE:default'}],'stream':stream},__user__={'id':'user-1'},__chat_id__='chat-1',__session_id__='ui-1',__message_id__='message-1',__event_emitter__=emitter)
        if stream:
            wire=''.join([part async for part in result.body_iterator])
            events=[json.loads(l[6:]) for l in wire.splitlines() if l.startswith('data: {')]
            content=[e['choices'][0]['delta']['content'] for e in events if e['choices'][0]['delta'].get('content')]
            assert content==[EDITED],wire
        else:assert result['choices'][0]['message']['content']==EDITED
        scope=pipe._scope_key(user_id='user-1',chat_id='chat-1',session_id='ui-1',message_id='message-1')
        sid,_=pipe._hermes_session_ids(scope)
        assert db.get_messages(sid)[-1]['content']==EDITED
        assert metrics(home)[0]['adapter_invocations']==1
        assert RAW not in json.dumps(statuses,ensure_ascii=False)
        if pipe._notification_tasks:
            import asyncio
            await asyncio.gather(*pipe._notification_tasks)

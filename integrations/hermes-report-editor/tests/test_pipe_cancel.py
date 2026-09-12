import asyncio
import json
import time
import pytest
from harness import runtime
from test_pipe import load_pipe
from test_invariants import metrics

@pytest.mark.asyncio
@pytest.mark.parametrize('stream',[True,False])
async def test_editor_opt_in_cancel_has_no_late_reply(tmp_path,monkeypatch,stream):
    marker=tmp_path/'started'
    config={'enabled':True,'timeout_seconds':15,'adapter':{'factory':'fixture_adapters:Slow','marker':str(marker),'mode':'retry'}}
    async with runtime(tmp_path,monkeypatch,settings=config) as (client,db,seen,home):
        pipe=load_pipe();pipe.valves=pipe.Valves(HERMES_API_URL=str(client.make_url('/v1')),HERMES_API_KEY='fixture-token',ENABLE_REPORT_EDITOR=True,PROGRESS_HEARTBEAT_SECONDS=0,REQUIRE_REGISTERED_PLAN=False)
        statuses=[]
        async def emitter(event):statuses.append(event)
        async def consume():
            result=await pipe.pipe({'messages':[{'role':'user','content':'CASE:default'}],'stream':stream},__user__={'id':'user-1'},__chat_id__='chat-1',__session_id__='ui-1',__message_id__='message-1',__event_emitter__=emitter)
            if not stream:return result['choices'][0]['message']['content']
            wire=''.join([part async for part in result.body_iterator])
            events=[json.loads(l[6:]) for l in wire.splitlines() if l.startswith('data: {')]
            return ''.join(e['choices'][0]['delta'].get('content','') for e in events)
        task=asyncio.create_task(consume())
        limit=time.monotonic()+4
        while not marker.exists() and time.monotonic()<limit:await asyncio.sleep(.01)
        assert marker.exists()
        rid=next(e['data']['run_id'] for e in statuses if e['data'].get('run_id'))
        stop=await client.post(f'/v1/runs/{rid}/stop',json={});assert stop.status==200
        text=await asyncio.wait_for(task,2)
        assert text==''
        assert metrics(home)[0]['reason']=='cancelled'
        before=len(statuses)
        await asyncio.sleep(.15)
        assert len(statuses)==before
        if pipe._notification_tasks:await asyncio.gather(*pipe._notification_tasks)

import asyncio,json
import pytest
from harness import runtime
from technical_fixture import REPORT,PROGRESS_ONE,PROGRESS_TWO
from test_pipe import load_pipe

@pytest.mark.asyncio
@pytest.mark.parametrize('stream',[True,False])
async def test_pipe_final_report_replaces_technical_progress_without_loss(tmp_path,monkeypatch,stream):
    expected=REPORT['purpose']+''.join(s for key in ('verified_facts','failures_unmet_unknown','candidates_reasons','recommendations','decisions_required') for s in REPORT[key])
    async with runtime(tmp_path,monkeypatch,reports={'default':REPORT},technical_flow=True) as (client,db,seen,home):
        pipe=load_pipe()
        pipe.valves=pipe.Valves(HERMES_API_URL=str(client.make_url('/v1')),HERMES_API_KEY='fixture-token',ENABLE_REPORT_EDITOR=True,PROGRESS_HEARTBEAT_SECONDS=0,REQUIRE_REGISTERED_PLAN=False)
        async def emitter(event):pass
        result=await pipe.pipe({'messages':[{'role':'user','content':'CASE:default'}],'stream':stream},__user__={'id':'user-1'},__chat_id__='chat-1',__session_id__='ui-1',__message_id__='message-1',__event_emitter__=emitter)
        if stream:
            wire=''.join([part async for part in result.body_iterator])
            frames=[json.loads(l[6:]) for l in wire.splitlines() if l.startswith('data: {')]
            snapshots=[e for e in frames if e.get('type')=='response.completed']
            assert len(snapshots)==1,wire
            text=''.join(p['text'] for item in snapshots[0]['response']['output'] for p in item.get('content',[]) if p.get('type')=='output_text')
            assert text==expected
            earlier=''.join(e.get('choices',[{'delta':{}}])[0].get('delta',{}).get('content','') for e in frames)
            assert PROGRESS_ONE in earlier and PROGRESS_TWO in earlier
            assert REPORT['draft'] not in earlier
        else:assert result['choices'][0]['message']['content']==expected
        scope=pipe._scope_key(user_id='user-1',chat_id='chat-1',session_id='ui-1',message_id='message-1');sid,_=pipe._hermes_session_ids(scope)
        assert db.get_messages(sid)[-1]['content']==expected
        assert json.loads((home/'technical-work-result.json').read_text())['passed']==12
        if pipe._notification_tasks:await asyncio.gather(*pipe._notification_tasks)

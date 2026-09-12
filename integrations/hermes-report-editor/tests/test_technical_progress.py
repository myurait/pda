import json
import pytest
from harness import runtime,run_case
from technical_fixture import REPORT,PROGRESS_ONE,PROGRESS_TWO
from test_invariants import metrics

@pytest.mark.asyncio
async def test_real_technical_tool_and_progress_then_final_report_is_edited(tmp_path,monkeypatch):
    async with runtime(tmp_path,monkeypatch,reports={'default':REPORT},technical_flow=True) as (client,db,seen,home):
        _,events,wire=await run_case(client)
        work=json.loads((home/'technical-work-result.json').read_text())
        assert work['checks']==work['passed']==12 and work['failed']==0
        progress=''.join(e.get('delta','') for e in events if e.get('event')=='message.delta')
        assert PROGRESS_ONE in progress and PROGRESS_TWO in progress
        measured=metrics(home)
        assert len(measured)==1 and measured[0]['reason']=='edited',measured
        final=[e for e in events if e.get('event')=='run.completed']
        assert len(final)==1 and final[0]['output']!=REPORT['draft']
        assert REPORT['draft'] not in progress
        assert db.get_messages('case-1')[-1]['content']==final[0]['output']

import pytest
from harness import runtime,run_case,RAW
from test_invariants import metrics

@pytest.mark.asyncio
async def test_cannot_adopt_edit_after_original_output_already_started(tmp_path,monkeypatch):
    async with runtime(tmp_path,monkeypatch,leading_text=RAW) as (client,db,seen,home):
        _,events,wire=await run_case(client)
        assert any(e.get('event')=='message.delta' for e in events)
        assert not metrics(home),'A late prepare must not export after visible text'
        assert [e['output'] for e in events if e.get('event')=='run.completed']==[RAW]
        assert db.get_messages('case-1')[-1]['content']==RAW

import json
import pytest
from harness import runtime,run_case,RAW

@pytest.mark.asyncio
async def test_added_duplicate_sentence_falls_back_without_second_visible_answer(tmp_path,monkeypatch):
    config={'enabled':True,'adapter':{'factory':'boundary_adapters:DuplicatePurpose'}}
    async with runtime(tmp_path,monkeypatch,settings=config) as (client,db,seen,home):
        _,events,wire=await run_case(client)
        assert [e['output'] for e in events if e.get('event')=='run.completed']==[RAW]
        assert db.get_messages('case-1')[-1]['content']==RAW
        metric=json.loads((home/'metrics.jsonl').read_text().splitlines()[0])
        assert metric['reason']=='duplicate_sentence'
        assert metric['adapter_invocations']==1

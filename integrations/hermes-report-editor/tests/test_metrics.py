import json
import pytest
from harness import REPORT,runtime,run_case

@pytest.mark.asyncio
async def test_adapter_metadata_cannot_log_content_or_secret_shaped_fields(tmp_path,monkeypatch):
    config={'enabled':True,'adapter':{'factory':'boundary_adapters:PoisonMetrics'}}
    async with runtime(tmp_path,monkeypatch,settings=config) as (client,db,seen,home):
        await run_case(client)
        raw=(home/'metrics.jsonl').read_text()
        assert 'PRIVATE_' not in raw
        assert REPORT['purpose'] not in raw
        record=json.loads(raw.splitlines()[0])
        assert record['usage']=={'input_tokens':2}
        assert record['provider_calls'] is None

@pytest.mark.asyncio
async def test_rejected_candidate_retains_available_numeric_measurements(tmp_path,monkeypatch):
    config={'enabled':True,'adapter':{'factory':'boundary_adapters:RejectedMeasured'}}
    async with runtime(tmp_path,monkeypatch,settings=config) as (client,db,seen,home):
        _,events,wire=await run_case(client)
        assert [e['output'] for e in events if e.get('event')=='run.completed']==[REPORT['draft']]
        raw=(home/'metrics.jsonl').read_text()
        assert 'PRIVATE_' not in raw and REPORT['draft'] not in raw
        record=json.loads(raw.splitlines()[0])
        assert record['reason']=='missing_or_changed_anchor'
        assert record['provider_calls']==1
        assert record['usage']=={'input_tokens':5,'output_tokens':7}

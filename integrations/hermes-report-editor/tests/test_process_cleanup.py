import asyncio
import json
import pytest
from harness import runtime,run_case,RAW

@pytest.mark.asyncio
async def test_cleanup_failure_uses_original_not_validated_candidate(tmp_path,monkeypatch):
    import os
    def refused(*args):raise PermissionError('synthetic cleanup refusal')
    async with runtime(tmp_path,monkeypatch) as (client,db,seen,home):
        monkeypatch.setattr(os,'killpg',refused)
        await run_case(client)
        assert [m['content'] for m in db.get_messages('case-1') if m['role']=='assistant'][-1]==RAW
        assert json.loads((home/'metrics.jsonl').read_text())['reason']=='adapter_failure'

@pytest.mark.asyncio
async def test_success_cleans_owned_subprocess_group_before_return(tmp_path,monkeypatch):
    late=tmp_path/'late';pid=tmp_path/'pid'
    config={'enabled':True,'adapter':{'factory':'boundary_adapters:OrphanChild','late_marker':str(late),'pid_marker':str(pid)}}
    async with runtime(tmp_path,monkeypatch,settings=config) as (client,db,seen,home):
        await run_case(client)
        assert pid.exists()
        assert json.loads((home/'metrics.jsonl').read_text())['reason']=='edited'
        await asyncio.sleep(.9)
        assert not late.exists(), 'A child process outlived a successful adapter return'

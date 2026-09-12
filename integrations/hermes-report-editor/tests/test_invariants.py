import asyncio
import copy
import hashlib
import json
from pathlib import Path
import time
import pytest
import yaml
from harness import REPORT,RAW,EDITED,runtime,run_case


def metrics(home):
    p=home/'metrics.jsonl'
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def final(events):return [e['output'] for e in events if e.get('event')=='run.completed']


@pytest.mark.asyncio
async def test_raw_artifacts_fail_closed_before_external_call(tmp_path,monkeypatch):
    report=copy.deepcopy(REPORT)
    report['draft']=json.dumps(report,ensure_ascii=False)
    async with runtime(tmp_path,monkeypatch,reports={'default':report}) as (client,db,seen,home):
        _,events,wire=await run_case(client)
        assert final(events)==[report['draft']],wire
        assert not metrics(home)


@pytest.mark.asyncio
@pytest.mark.parametrize('purpose',['title_generation','tags','follow_up','internal','subagent','editor','urgent','unspecified'])
async def test_excluded_host_purposes_have_zero_editor_calls(tmp_path,monkeypatch,purpose):
    async with runtime(tmp_path,monkeypatch) as (client,db,seen,home):
        _,events,wire=await run_case(client,purpose=purpose)
        assert final(events)==[RAW],wire
        assert not metrics(home)


@pytest.mark.asyncio
@pytest.mark.parametrize('settings',[{}, {'enabled':False,'adapter':{'factory':'fixture_adapters:Compact'}},{'enabled':True}])
async def test_unconfigured_or_disabled_is_legacy_and_zero_calls(tmp_path,monkeypatch,settings):
    async with runtime(tmp_path,monkeypatch,settings=settings) as (client,db,seen,home):
        _,events,wire=await run_case(client)
        assert final(events)==[RAW],wire
        assert any(e.get('event')=='message.delta' for e in events)
        assert not metrics(home)


@pytest.mark.asyncio
async def test_ordinary_short_chat_without_preparation_has_zero_calls(tmp_path,monkeypatch):
    report={**REPORT,'report_type':'ordinary','draft':'了解しました。'}
    async with runtime(tmp_path,monkeypatch,reports={'default':report}) as (client,db,seen,home):
        _,events,wire=await run_case(client)
        assert final(events)==['了解しました。'],wire
        assert any(e.get('event')=='message.delta' for e in events),wire
        assert not metrics(home)


@pytest.mark.asyncio
async def test_adapter_swap_does_not_change_common_pipeline_or_history(tmp_path,monkeypatch):
    pipeline=Path(__file__).parents[1]/'report_editor/pipeline.py'
    digest=hashlib.sha256(pipeline.read_bytes()).hexdigest()
    async with runtime(tmp_path,monkeypatch) as (client,db,seen,home):
        _,one,_=await run_case(client)
        history=copy.deepcopy(db.get_messages('case-1'))
        cfg=yaml.safe_load((home/'config.yaml').read_text())
        cfg['plugins']['entries']['pda-report-editor']['settings']['adapter']['factory']='fixture_adapters:Paragraphs'
        (home/'config.yaml').write_text(yaml.safe_dump(cfg))
        _,two,wire=await run_case(client,history=[{'role':'user','content':'CASE:default'},{'role':'assistant','content':EDITED}])
        assert final(one)==[EDITED]
        assert final(two)==['\n'.join([REPORT['purpose']]+REPORT['verified_facts']+REPORT['failures_unmet_unknown'])],wire
        assert db.get_messages('case-1')[:len(history)]==history
        assert any(m.get('role')=='assistant' and m.get('content')==RAW for m in seen[-1]['messages'])
        assert len(metrics(home))==2
    assert hashlib.sha256(pipeline.read_bytes()).hexdigest()==digest


@pytest.mark.asyncio
async def test_concurrent_sessions_are_not_mixed_and_do_not_recurse(tmp_path,monkeypatch):
    other=json.loads(json.dumps(REPORT,ensure_ascii=False).replace('3','7'))
    async with runtime(tmp_path,monkeypatch,reports={'default':REPORT,'other':other}) as (client,db,seen,home):
        a,b=await asyncio.gather(run_case(client,sid='s-a'),run_case(client,sid='s-b',case='other'))
        assert final(a[1])==[EDITED]
        assert final(b[1])==[EDITED.replace('3','7')]
        assert db.get_messages('s-a')[-1]['content']==EDITED
        assert db.get_messages('s-b')[-1]['content']==EDITED.replace('3','7')
        rows=metrics(home)
        assert len(rows)==2 and len({r['invocation_id'] for r in rows})==2
        assert all(r['adapter_invocations']==1 for r in rows)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode,reason',[('empty','empty'),('cut','truncated'),('format','output_format'),('missing','missing_or_changed_anchor'),('numbers','changed_numbers'),('extra_claim','unsupported_text'),('raise','adapter_failure'),('auth','adapter_failure')])
async def test_editor_failures_fallback_without_late_output(tmp_path,monkeypatch,mode,reason):
    settings={'enabled':True,'adapter':{'factory':'fixture_adapters:Failure','mode':mode}}
    async with runtime(tmp_path,monkeypatch,settings=settings) as (client,db,seen,home):
        _,events,wire=await run_case(client)
        assert final(events)==[RAW],wire
        assert not any(e.get('event')=='message.delta' for e in events)
        assert db.get_messages('case-1')[-1]['content']==RAW
        assert metrics(home)[0]['reason']==reason
        await asyncio.sleep(0.1)
        assert len(metrics(home))==1


@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['queue','retry','cleanup'])
async def test_total_deadline_includes_adapter_queue_retry_cleanup(tmp_path,monkeypatch,mode):
    marker=tmp_path/'started'
    settings={'enabled':True,'timeout_seconds':0.7,'adapter':{'factory':'fixture_adapters:Slow','mode':mode,'marker':str(marker)}}
    async with runtime(tmp_path,monkeypatch,settings=settings) as (client,db,seen,home):
        _,events,wire=await run_case(client)
        assert final(events)==[RAW],wire
        row=metrics(home)[0]
        assert row['reason']=='timeout' and row['elapsed_seconds']<=0.7
        assert marker.exists()
        await asyncio.sleep(0.2)
        assert not marker.with_suffix('.late').exists()


@pytest.mark.asyncio
async def test_cancel_during_edit_does_not_reply_and_next_chat_works(tmp_path,monkeypatch):
    marker=tmp_path/'started'
    settings={'enabled':True,'adapter':{'factory':'fixture_adapters:Slow','mode':'retry','marker':str(marker)}}
    ordinary={**REPORT,'report_type':'ordinary','draft':'通常会話は応答できます。'}
    async with runtime(tmp_path,monkeypatch,settings=settings,reports={'default':REPORT,'ordinary':ordinary}) as (client,db,seen,home):
        response=await client.post('/v1/runs',json={'input':'CASE:default','session_id':'cancel-case','output_delivery':{'purpose':'interactive'}})
        assert response.status==202
        rid=(await response.json())['run_id']
        stream=await client.get(f'/v1/runs/{rid}/events')
        reader=asyncio.create_task(stream.text())
        limit=time.monotonic()+4
        while not marker.exists() and time.monotonic()<limit:await asyncio.sleep(.01)
        assert marker.exists()
        before=time.monotonic()
        stopped=await client.post(f'/v1/runs/{rid}/stop')
        assert stopped.status==200
        wire=await asyncio.wait_for(reader,2)
        assert 'run.completed' not in wire and 'message.delta' not in wire,wire
        assert time.monotonic()-before<2
        _,events,wire=await run_case(client,sid='after-cancel',case='ordinary')
        assert final(events)==['通常会話は応答できます。'],wire
        await asyncio.sleep(.2)
        assert not marker.with_suffix('.late').exists()

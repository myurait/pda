import json,os,subprocess,sys
import pytest
import harness
from report_editor.contracts import LISTS,parse_request

@pytest.mark.asyncio
@pytest.mark.parametrize('delayed_start',[False,True])
async def test_schema_valid_large_utf8_report_reaches_real_worker_without_truncation(tmp_path,monkeypatch,delayed_start):
    blocked_writes=[]
    if delayed_start:
        original_popen=subprocess.Popen
        watched_stdin=set();original_write=os.write
        def measured_write(fd,data):
            written=original_write(fd,data)
            if fd in watched_stdin and written<len(data):blocked_writes.append(len(data)-written)
            return written
        monkeypatch.setattr(os,'write',measured_write)
        def delayed_popen(args,*pos,**kw):
            if isinstance(args,list) and len(args)>1 and str(args[1]).endswith('/report_editor/worker.py'):
                command=[sys.executable,'-c','import time,runpy;time.sleep(0.18);runpy.run_path('+repr(args[1])+',run_name="__main__")']
                proc=original_popen(command,*pos,**kw)
                assert proc.stdin is not None
                watched_stdin.add(proc.stdin.fileno())
                original_communicate=proc.communicate
                def measured_communicate(*cp,**ck):
                    try:return original_communicate(*cp,**ck)
                    except subprocess.TimeoutExpired:
                        pending=len(getattr(proc,'_input',b'') or b'')-getattr(proc,'_input_offset',0)
                        if pending>0:blocked_writes.append(pending)
                        raise
                proc.communicate=measured_communicate
                return proc
            return original_popen(args,*pos,**kw)
        monkeypatch.setattr(subprocess,'Popen',delayed_popen)
    phrase='これは検証済みの公開資料です。'*55
    purpose='目的は隔離試験の実証です。'
    draft='資料の提示順を整理します。\n'+purpose+'\n'+phrase
    report={'purpose':purpose,'report_type':'complete','export_class':'public','draft':draft,**{key:[phrase]*30 for key in LISTS}}
    parse_request(report)
    assert len(json.dumps(report,ensure_ascii=False).encode())>131073
    monkeypatch.setattr(harness,'REPORT',report);monkeypatch.setattr(harness,'RAW',draft)
    config={'enabled':True,'adapter':{'factory':'boundary_adapters:DistinctParagraphs'}}
    async with harness.runtime(tmp_path,monkeypatch,settings=config) as (client,db,agents,home):
        _,events,wire=await harness.run_case(client)
        done=[e for e in events if e.get('event')=='run.completed']
        assert len(done)==1
        metric=json.loads((home/'metrics.jsonl').read_text().splitlines()[0])
        assert metric['reason']=='edited'
        assert phrase in done[0]['output'] and purpose in done[0]['output']
        assert done[0]['output']!=draft
        if delayed_start:assert blocked_writes,'Exercise backpressure with pending stdin bytes while startup is delayed'

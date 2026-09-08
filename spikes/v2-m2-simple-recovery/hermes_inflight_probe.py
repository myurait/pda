"""Live stop/uncertain-turn probes; synthetic file effects, no business API."""
import json, time, sys
from hermes_probe import HOME, NAME, docker, record
from hermes_api_probe import request, run
from hermes_faults import health, semantic

def probe(mode):
    assert mode in ('stop','orphan')
    label='hermes-final-inflight-'+mode
    basename=label+'-receipt.jsonl'
    path=HOME/basename
    assert not path.exists(),'already executed; read evidence instead of repeating'
    command="python3 -c 'import os,time;f=open(\"/home/proof/.hermes/"+basename+"\",\"a\");f.write(\"accepted-1\\n\");f.flush();os.fsync(f.fileno());f.close();time.sleep(90)'"
    prompt='Synthetic isolated test only. Do not delegate, schedule, or use the network. Call terminal exactly once with timeout 110 and this command; never retry it even after an error:\n'+command+'\nAfter this one command completes, say RECEIPT_ACKNOWLEDGED. Do nothing else.'
    payload={'input':prompt,'session_id':label}
    created=request('/v1/runs',payload,{'Idempotency-Key':label})
    assert created['http']==202 and not created['body'].get('replayed'),created
    rid=created['body']['run_id'];start=time.monotonic()
    result={'created':created,'payload':payload,'mode':mode,'scope':'actual model/tool run; effect is synthetic fsynced file receipt, not a business API'}
    record(label+'-setup',result)
    while time.monotonic()-start<75 and not path.exists():
        s=request('/v1/runs/'+rid)
        if s['body'].get('status') in ('completed','failed','cancelled'): raise RuntimeError(s)
        time.sleep(.2)
    assert path.exists(),'no effect observed; invalid injection point'
    before=path.read_text(); assert before=='accepted-1\n',before
    result['native_state_before']=request('/v1/runs/'+rid)
    if mode=='stop': result['stop_ack']=request('/v1/runs/'+rid+'/stop',{})
    old=json.loads(docker('inspect',NAME).stdout)[0]['State']['Pid']
    code="import pathlib,os,signal;p=pathlib.Path('/proc/7/cmdline').read_bytes();assert b'hermes_cli.main' in p and not p.startswith(b'/sbin/');os.kill(7,signal.SIGKILL)"
    fault=time.monotonic();inj=docker('exec',NAME,'python3','-c',code)
    result.update(injection_rc=inj.returncode,injection_stderr=inj.stderr,receipt_before=before)
    record(label+'-injected',result)
    assert inj.returncode==0,inj.stderr
    while time.monotonic()-fault<120:
        current=json.loads(docker('inspect',NAME).stdout)[0]['State']
        if current['Pid'] and current['Pid']!=old and health(): break
        time.sleep(.3)
    else: raise RuntimeError('trial did not recover')
    result['recovery_s']=round(time.monotonic()-fault,3)
    result['native_state_after']=request('/v1/runs/'+rid)
    result['replay']=request('/v1/runs',payload,{'Idempotency-Key':label})
    time.sleep(2)
    result['receipt_after']=path.read_text()
    result['processes_after']=docker('top',NAME,'-eo','pid,ppid,args').stdout
    result['single_effect']=result['receipt_after']==before
    result['delayed_tool_remaining']='time.sleep(90)' in result['processes_after']
    status=result['native_state_after']['body'].get('status')
    result['native_terminal_preserved']=status=='cancelled' if mode=='stop' else status in ('failed','interrupted','cancelled')
    result['same_run_replayed']=result['replay']['body'].get('run_id')==rid and result['replay']['body'].get('replayed') is True
    record(label,result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    assert result['single_effect'] and not result['delayed_tool_remaining'] and result['same_run_replayed'] and result['native_terminal_preserved']
    outcome=run(label+'-assessment','Do not repeat any prior operation. Inspect the saved conversation and, using only a read-only file tool if needed, the synthetic receipt file from the previous request. In no more than 70 words explain whether the delayed command returned an acknowledgement, whether its already-started effect can be claimed undone, and whether it should be blindly retried. Do not use terminal, write, delegate, or schedule.',session=label,limit=120)
    record(label+'-semantic',semantic(label))
    assert path.read_text()==before,'unexpected extra effect during readback'

if __name__=='__main__': probe(sys.argv[1])

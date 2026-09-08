"""Temporary memory-read and model-network dependency failures."""
import json, time
from hermes_probe import ROOT, RUNTIME, SOURCE, HOME, NAME, docker, record
from hermes_faults import snapshot, assert_preserved, semantic, health
from hermes_api_probe import request, run
c=['compose','-p','m2proof','--env-file',str(RUNTIME/'compose.env'),'-f',str(ROOT/'compose.yaml')]

def memory_outage():
    label='hermes-final-memory-outage';before=snapshot();p=HOME/'memories/MEMORY.md';mode=p.stat().st_mode & 0o777
    result: dict={'scope':'synthetic transient permission failure on builtin memory; fixed-mode restoration is predeclared, no diagnostic agent'}
    try:
        p.chmod(0)
        t=time.monotonic();r=docker('restart',NAME);assert r.returncode==0,r.stderr
        while time.monotonic()-t<30 and not health():time.sleep(.3)
        result['control_s']=round(time.monotonic()-t,3);result['health']=health()
        r=docker('exec',NAME,'python3','-c',"from pathlib import Path;print(Path('/home/proof/.hermes/memories/MEMORY.md').read_text())")
        result['direct_memory_read']={'exit_code':r.returncode,'stderr':r.stderr}
        result['saved_session']=request('/v1/runs/'+json.loads((ROOT/'evidence/hermes-final-inflight-orphan.json').read_text())['created']['body']['run_id'])
        record(label+'-fault',result)
        assert r.returncode!=0 and 'PermissionError' in r.stderr
        result['degraded_model']=run(label+'-degraded','Synthetic recovery test. Read /home/proof/.hermes/activities.json and /home/proof/.hermes/memories/MEMORY.md using read-only tools. Briefly report which is available and which is not; do not invent missing memory, change permissions, write, use terminal, or delegate.',limit=120)
    finally:
        p.chmod(mode)
        t=time.monotonic();r=docker('restart',NAME)
        while time.monotonic()-t<30 and not health():time.sleep(.3)
        result['dependency_restore_s']=round(time.monotonic()-t,3)
    result['after']=snapshot();result['preserved']=assert_preserved(before,result['after']);result['semantic']=semantic(label)
    record(label,result);print(json.dumps({k:v for k,v in result.items() if k!='after'},ensure_ascii=False,indent=2))
    assert result['preserved'] and result['semantic']['passed']

def model_outage():
    import hermes_api_probe
    normal_base=hermes_api_probe.BASE
    label='hermes-model-outage';before=snapshot();result: dict={'scope':'Docker internal network blocks model egress without changing credentials; dependency restoration is declarative network replacement'}
    try:
        t=time.monotonic();r=docker(*c,'-f',str(ROOT/'compose-offline.yaml'),'up','-d','--wait','--wait-timeout','30')
        result['network_apply']={'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr};assert r.returncode==0,r.stderr
        info=json.loads(docker('inspect',NAME).stdout)[0]
        network=info['NetworkSettings']['Networks']['m2proof_offline']
        hermes_api_probe.BASE='http://'+network['IPAddress']+':19450'
        result['observer_endpoint']=hermes_api_probe.BASE
        result['control_s']=round(time.monotonic()-t,3);result['health']=request('/health')['http']==200
        result['saved_session']=request('/v1/runs/'+json.loads((ROOT/'evidence/hermes-final-inflight-orphan.json').read_text())['created']['body']['run_id'])
        result['route']=docker('exec',NAME,'python3','-c',"from pathlib import Path;print(Path('/proc/net/route').read_text())").stdout
        record(label+'-fault',result)
        result['unavailable_model']=run(label+'-degraded','Do not use tools. Reply exactly MODEL_AVAILABLE if this request reaches your model.',limit=90)
        last=result['unavailable_model'].get('last',{}).get('state',{}).get('body',{})
        if last.get('status') not in ('completed','failed','cancelled','interrupted'):
            rid=result['unavailable_model']['created']['body']['run_id']
            result['bounded_stop']=request('/v1/runs/'+rid+'/stop',{})
    finally:
        t=time.monotonic();r=docker(*c,'up','-d','--wait','--wait-timeout','30')
        result['dependency_restore_s']=round(time.monotonic()-t,3);result['network_restore']={'exit_code':r.returncode,'stderr':r.stderr}
        hermes_api_probe.BASE=normal_base
    result['after']=snapshot();result['preserved']=assert_preserved(before,result['after']);result['semantic']=semantic(label)
    record(label,result);print(json.dumps({k:v for k,v in result.items() if k!='after'},ensure_ascii=False,indent=2))
    assert result['preserved'] and result['semantic']['passed']

if __name__=='__main__':
    import sys
    (memory_outage if sys.argv[1]=='memory' else model_outage)()

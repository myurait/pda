"""Isolated fault injections plus native Letta state/model observations.
This observer never diagnoses or repairs candidate internals.
"""
from letta_readback import *
import sys,hashlib

def native_status(label):
    with ws() as c:
        r=exchange(c,{'type':'read_memory_file','request_id':label,'agent_id':SCOPE['agent_id'],'path':'system/m2_state.md'},'read_memory_file_response',30)
    record(label,r)
    return r

def drill(case):
    name='letta-fault-'+case
    case=case.split('@',1)[0]
    before=native_status(name+'-before')
    start=time.monotonic();injection=None;removal=None
    if case in ('process-death','worker-disappearance'):
        if case=='worker-disappearance':
            worker="const fs=require('fs');fs.writeFileSync('/home/node/.letta/m2-worker-started','started');setTimeout(()=>fs.appendFileSync('/home/node/.letta/m2-effect-ledger','LATE-EFFECT\\n'),60000)"
            record(name+'-worker-start',docker('exec','-d','m2r2-letta','node','-e',worker))
            until=time.monotonic()+10
            while not (HOME/'.letta/m2-worker-started').exists() and time.monotonic()<until:time.sleep(.1)
            assert (HOME/'.letta/m2-worker-started').exists(),'worker did not start'
        info=docker('inspect','--format','{{.State.Pid}} {{.RestartCount}}','m2r2-letta')
        injector="const fs=require('fs');const pids=fs.readdirSync('/proc').filter(p=>/^[0-9]+$/.test(p)).filter(p=>{try{return fs.readFileSync('/proc/'+p+'/cmdline','utf8').split('\\0')[1]==='/opt/letta/node_modules/.bin/letta'}catch{return false}});if(pids.length!==1)throw Error('ambiguous target '+pids);fs.writeFileSync(1,JSON.stringify({target:Number(pids[0]),signal:'SIGKILL'})+'\\n');process.kill(Number(pids[0]),'SIGKILL')"
        injection=docker('exec','m2r2-letta','node','-e',injector)
        generation_before=tuple(map(int,info['stdout'].split()))
        valid=False;after_info=None
        for _ in range(40):
            after_info=docker('inspect','--format','{{.State.Pid}} {{.RestartCount}}','m2r2-letta')
            generation_after=tuple(map(int,after_info['stdout'].split()))
            valid=(generation_after[0]>0 and generation_after[0]!=generation_before[0] and generation_after[1]>generation_before[1])
            if valid:break
            time.sleep(.25)
        record(name+'-kill',{'before':info,'injection':injection,'after':after_info,'verified':valid})
        if not valid:
            result={'case':case,'passed':False,'valid_injection':False,'reason':'container generation did not change; not a recovery trial'}
            record(name+'-verdict',result);return result
        ready=wait_ready(seconds=40)
    elif case=='byte-full':
        js="const fs=require('fs');let n=0;try {let fd=fs.openSync('/work/m2-fill','w');for(;;){fs.writeSync(fd,Buffer.alloc(1048576,65));n++}}catch(e){console.log(JSON.stringify({code:e.code,written_mb:n}))}"
        injection=docker('exec','m2r2-letta','node','-e',js);record(name+'-injection',injection);ready={'wall_s':0}
        assert 'ENOSPC' in injection['stdout'],injection
    elif case=='inode-full':
        js="const fs=require('fs');let n=0;try {for(;;){fs.writeFileSync('/work/m2-inode-'+n,'');n++}}catch(e){console.log(JSON.stringify({code:e.code,count:n}))}"
        injection=docker('exec','m2r2-letta','node','-e',js);record(name+'-injection',injection);ready={'wall_s':0}
        assert 'ENOSPC' in injection['stdout'],injection
    elif case=='oom':
        probe="process.stdout.write(require('fs').readFileSync('/sys/fs/cgroup/memory.events','utf8'))"
        before_oom=docker('exec','m2r2-letta','node','-e',probe)
        injection=docker('exec','m2r2-letta','node','-e',"const keep=[];for(;;)keep.push(Buffer.alloc(8388608,65))",timeout=25)
        ready=wait_ready(seconds=40)
        after_oom=docker('exec','m2r2-letta','node','-e',probe)
        def oomkills(text):return int(dict(line.split() for line in text.splitlines())['oom_kill'])
        verified=oomkills(after_oom['stdout'])>oomkills(before_oom['stdout'])
        record(name+'-injection',{'before':before_oom,'injection':injection,'after':after_oom,'verified':verified})
        assert verified,'OOM not verified; not a valid fault'
    elif case=='model-unavailable':
        injection=docker('stop','--time','1','m2r2-ollama');record(name+'-injection',injection)
        down_state=native_status(name+'-during-model-outage')
        with ws() as c:
            runtime=connect_runtime(c,name+'-outage')
            failed=turn(c,runtime,PROMPT,name+'-failed-model-call',seconds=25,allowlist=[])
        record(name+'-outage-observation',{'native_state':down_state,'model_stop':failed['stops'],'model_text':failed['text'],'wall_s_from_fault':time.monotonic()-start})
        removal=docker('start','m2r2-ollama');record(name+'-dependency-restored-by-injector',removal)
        ready=wait_ready(seconds=40)
    else:raise ValueError(case)
    after=native_status(name+'-native-state')
    state_s=time.monotonic()-start
    r=readback(name+'-model',deadline=max(1,int(300-state_s)))
    total=time.monotonic()-start
    after_model=native_status(name+'-state-after-model')
    state_equal=isinstance(before['response'].get('content'),str) and before['response']['content']==after['response'].get('content')==after_model['response'].get('content') and after['response'].get('success') and after_model['response'].get('success')
    # Leave the data used by the proof intact; only remove named synthetic fillers.
    if case=='byte-full':removal=docker('exec','m2r2-letta','node','-e',"require('fs').unlinkSync('/work/m2-fill')")
    elif case=='inode-full':removal=docker('exec','m2r2-letta','node','-e',"const fs=require('fs');for(const p of fs.readdirSync('/work'))if(p.startsWith('m2-inode-'))fs.unlinkSync('/work/'+p)")
    if case=='worker-disappearance':
        remaining=61-(time.monotonic()-start)
        if remaining>0:time.sleep(remaining)
    ledger=(HOME/'.letta/m2-effect-ledger');effects=ledger.read_text() if ledger.exists() else ''
    result={'case':case,'native_state_s':state_s,'model_readback_s_from_fault':total,'native_state_equal':state_equal,'model':r,'late_effects':effects,'removal':removal,'owner_rescue_calls':0,'restoration_observer_calls_after_fault':0,'passed':bool(state_s<=120 and total<=300 and state_equal and r['matches'] and r['terminal'][-1]=='end_turn' and not effects)}
    record(name+'-verdict',result)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return result
if __name__=='__main__':
    for case in sys.argv[1:]:drill(case)

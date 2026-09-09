"""Controlled standard restoration drill, explicitly NOT unattended recovery."""
from letta_drill import *
import shutil,hashlib,sys
case=sys.argv[1];assert case in ('bad-update','data-corruption')
name='letta-restore-'+case
base=['compose','-p','m2r2','-f',ROOT/'letta-compose.yaml']
original=native_status(name+'-original')
record(name+'-quiesce',docker(*base,'stop','app'))
snapshot=RUNTIME/(name+'-checkpoint');assert not snapshot.exists()
shutil.copytree(HOME,snapshot,symlinks=True)
manifest={str(p.relative_to(snapshot)):hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.rglob('*') if p.is_file() and not p.is_symlink()}
record(name+'-checkpoint-manifest',manifest)
# The already committed agent index is a real native JSON file, not a mocked DB.
found=[]
for p in (HOME/'.letta/lc-local-backend/agents').rglob('*.json'):
    try:d=json.loads(p.read_text())
    except (ValueError,UnicodeError):continue
    if d.get('id')==SCOPE['agent_id']:found.append(p)
assert len(found)==1,found
p=found[0];p.write_text('{BROKEN-NATIVE-AGENT-JSON')
start=time.monotonic()
if case=='bad-update':
    failed=docker(*base,'-f',ROOT/'letta-bad-release.yaml','up','-d','--wait','--wait-timeout','12','app',timeout=25)
    status=docker('inspect','-f','{{.State.Status}} {{.State.ExitCode}} {{.RestartCount}}','m2r2-letta')
    record(name+'-failed-release',{'command':failed,'status':status})
    events=docker('events','--since','1m','--until','0s','--filter','container=m2r2-letta','--filter','event=die','--format','{{json .}}')
    exit_history=[json.loads(line) for line in events['stdout'].splitlines()]
    record(name+'-exit-history',exit_history)
    assert failed['code']!=0 and any(e['Actor']['Attributes'].get('exitCode')=='42' for e in exit_history),status
else:
    record(name+'-corrupt-start',docker(*base,'start','app'));wait_ready(seconds=40)
    probes=[]
    for i in range(2):
        with ws() as c:
            r=exchange(c,{'type':'agent_retrieve','request_id':name+str(i),'agent_id':SCOPE['agent_id']},'agent_retrieve_response',20)
            probes.append(r)
        if i==0:docker('restart','m2r2-letta');wait_ready(seconds=40)
    record(name+'-restart-alone-observation',probes)
    assert all(not r['response'].get('success') for r in probes),probes
# Fixed offline restore, executed by this PREDECLARED external test driver.
# Do not count it as a native or independently-triggered unattended restoration.
record(name+'-restore-stop',docker(*base,'stop','app'))
failed_home=RUNTIME/(name+'-failed-home');assert not failed_home.exists()
HOME.rename(failed_home);shutil.copytree(snapshot,HOME,symlinks=True)
restored={str(p.relative_to(HOME)):hashlib.sha256(p.read_bytes()).hexdigest() for p in HOME.rglob('*') if p.is_file() and not p.is_symlink()}
record(name+'-exact-offline-restore',{'file_count':len(manifest),'lost_or_changed':[k for k,v in manifest.items() if restored.get(k)!=v],'unexpected_files':sorted(set(restored)-set(manifest))})
record(name+'-known-good-up',docker(*base,'up','-d','app'));ready=wait_ready(seconds=40)
state=native_status(name+'-restored-native');state_s=time.monotonic()-start
model=readback(name+'-restored-model',deadline=300)
wall=time.monotonic()-start
verdict={'case':case,'restoration_scope':'last quiescent checkpoint, admissions closed; no arbitrary-stale-backup zero-RPO claim','state_s':state_s,'model_s_from_fault':wall,'native_state_equal':original['response']['content']==state['response'].get('content'),'exact_checkpoint_file_count':len(manifest),'exact_checkpoint_equal':manifest==restored,'model_matches':model['matches'],'model_terminal':model['terminal'],'external_restore_actions':1,'unattended_recovery_proven':False,'m2_complete':False,'controlled_restore_pass':state_s<=120 and wall<=300 and manifest==restored and model['matches']}
record(name+'-verdict',verdict);print(json.dumps(verdict,ensure_ascii=False,indent=2))

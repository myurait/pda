"""Close the unqualified Letta trial: preserve evidence, test plain restart, stop."""
import hashlib, json, time
from letta_probe import ROOT, HOME, NAME, docker, record, ws, exchange, http
scope=json.loads((ROOT/'evidence/letta-runtime-scope.json').read_text())
transcripts=[]
for p in HOME.rglob('messages.jsonl'):
    rows=[json.loads(s) for s in p.read_text().splitlines() if s.strip()]
    transcripts.append({'path':str(p.relative_to(HOME)),'rows':rows})
record('letta-final-transcripts-before-stop',{'transcripts':transcripts})
latest=max(transcripts,key=lambda x:x['rows'][0]['timestamp'])
active={**scope,'conversation_id':latest['rows'][0]['id']}
with ws() as c:
    exchange(c,{'type':'runtime_start','request_id':'letta-final-reconnect',**active,'cwd':'/work','mode':'unrestricted'},'letta-final-reconnect','runtime_start_response')
    stopped=exchange(c,{'type':'abort_message','request_id':'letta-final-stop','runtime':active},'letta-final-stop','abort_message_response',timeout=15)
    assert stopped.get('success'),stopped
paths=list(HOME.rglob('messages.jsonl'))+list((HOME/'.letta/lc-local-backend/memfs').rglob('*.md'))
before={str(p.relative_to(HOME)):p.read_bytes() for p in paths}
baseline=json.loads(docker('inspect',NAME).stdout)[0]['RestartCount'];t=time.monotonic()
inject=docker('exec',NAME,'python3','-c',"from pathlib import Path;import os,signal;ps=[int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit() and (p/'cmdline').read_bytes().startswith(b'node\\x00/opt/letta/node_modules/.bin/letta\\x00')];assert len(ps)==1,ps;print(ps,flush=True);os.kill(ps[0],signal.SIGKILL)")
record('letta-crash-injection',{'exit_code':inject.returncode,'stdout':inject.stdout,'stderr':inject.stderr});assert inject.returncode==0
recovered=False
d={'RestartCount':None}
while time.monotonic()-t<45:
    try:
        d=json.loads(docker('inspect',NAME).stdout)[0]
        if d['RestartCount']>baseline and http('/readyz',timeout=2)['code']==200: recovered=True;break
    except Exception: pass
    time.sleep(.25)
result={'ready':recovered,'control_s':round(time.monotonic()-t,3),'before_restart_count':baseline,'after_restart_count':d['RestartCount'],'committed_prefixes_preserved':all((HOME/p).read_bytes().startswith(b) for p,b in before.items()),'retained_files':len(before),'model_readback':'NOT PASSED: three baseline attempts did not return within their bounds; never infer model comprehension from HTTP readiness'}
with ws() as c:
    got=exchange(c,{'type':'agent_retrieve','request_id':'letta-after-crash-agent','agent_id':scope['agent_id']},'letta-after-crash-agent','agent_retrieve_response')
    result['native_agent_restored']=got.get('success') and got.get('agent',{}).get('id')==scope['agent_id']
record('letta-plain-restart',result);print(json.dumps(result,ensure_ascii=False))
r=docker('logs',NAME);record('letta-final-app-logs',{'stdout':r.stdout,'stderr':r.stderr})
r=docker('logs','m2proof-ollama');record('letta-final-model-log-excerpts',{'lines':[x for x in (r.stdout+r.stderr).splitlines() if '/api/tags' not in x and 'HEAD ' not in x][-200:]})
r=docker('compose','-p','m2proofletta','-f','compose-letta.yaml','down',timeout=45)
remaining=docker('ps','-a','--filter','label=com.docker.compose.project=m2proofletta','--format','{{.Names}}').stdout.strip()
record('letta-cleanup',{'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'remaining_containers':remaining});print('cleanup',r.returncode,repr(remaining));assert r.returncode==0 and not remaining

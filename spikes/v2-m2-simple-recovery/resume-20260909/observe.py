"""Bounded one-shot observer utilities; never installed as a service."""
from pathlib import Path
import json, time, subprocess, shlex, urllib.request, urllib.error
from websockets.sync.client import connect
ROOT=Path(__file__).resolve().parent
RUNTIME=ROOT.parent/'.runtime'/'resume-20260909'
HOME=RUNTIME/'letta-home'
E=ROOT/'evidence'
BASE='http://127.0.0.1:19551'

def record(name,obj):
    p=E/(name+'.json');p.parent.mkdir(exist_ok=True)
    if p.exists(): raise FileExistsError(p)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    return obj

def docker(*args,timeout=45):
    p=subprocess.run(['sg','docker','-c',shlex.join(['docker',*map(str,args)])],capture_output=True,text=True,timeout=timeout)
    return {'code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

def token(): return (HOME/'.letta/appserver-token').read_text().strip()

def http(path,body=None,timeout=40,base=BASE,auth=True):
    headers={'Content-Type':'application/json'}
    if auth:headers['Authorization']='Bearer '+token()
    req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    start=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: text=r.read().decode();status=r.status
        try:data=json.loads(text)
        except json.JSONDecodeError:data=text
        return {'code':status,'body':data,'wall_s':time.monotonic()-start}
    except urllib.error.HTTPError as e:
        return {'code':e.code,'body':e.read().decode(),'wall_s':time.monotonic()-start}
    except OSError as e:
        return {'code':0,'body':None,'error':type(e).__name__+': '+str(e),'wall_s':time.monotonic()-start}

def wait_ready(base=BASE,path='/readyz',seconds=45):
    start=time.monotonic();errors=[]
    while time.monotonic()-start<seconds:
        try:
            r=http(path,timeout=2,base=base,auth=False)
            if r['code']==200:return {'wall_s':time.monotonic()-start,'last':r,'prior_errors':errors}
        except Exception as e:errors.append(type(e).__name__)
        time.sleep(0.25)
    raise TimeoutError(errors)

def ws():
    return connect(BASE.replace('http:','ws:')+'/ws',additional_headers={'Authorization':'Bearer '+token()},open_timeout=5,close_timeout=2,max_size=8*1024*1024)

def exchange(c,command,expected,timeout=30):
    start=time.monotonic();events=[];c.send(json.dumps(command))
    while time.monotonic()-start<timeout:
        m=json.loads(c.recv(timeout=max(0.1,timeout-(time.monotonic()-start))));events.append(m)
        if m.get('request_id')==command.get('request_id') and m.get('type')==expected:return {'response':m,'events':events,'wall_s':time.monotonic()-start}
        if m.get('request_id')==command.get('request_id') and m.get('type')=='error':raise RuntimeError(m)
    raise TimeoutError(expected)

if __name__=='__main__':
    import secrets
    assert not HOME.exists(),'Fresh setup only; no overwrite'
    assert docker('inspect','m2r2-letta')['code']!=0
    assert docker('inspect','m2r2-ollama')['code']!=0
    HOME.mkdir(parents=True,mode=0o700)
    (HOME/'.letta').mkdir(mode=0o700)
    f=HOME/'.letta/appserver-token';f.write_text(secrets.token_hex(24));f.chmod(0o600)
    r=docker('compose','-p','m2r2','-f',ROOT/'letta-compose.yaml','up','-d',timeout=60)
    record('letta-start',r);assert r['code']==0,r
    record('letta-ready',wait_ready());record('ollama-ready',wait_ready(base='http://127.0.0.1:19552',path='/api/tags'))
    r=docker('exec','m2r2-letta','letta','--backend','local','connect','ollama','--base-url','http://model:11434/v1',timeout=30)
    record('letta-provider-connected',r);print(r);assert r['code']==0

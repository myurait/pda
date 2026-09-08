"""Direct official App Server protocol probe; observer, never a recovery daemon."""
from pathlib import Path
import json, time, urllib.request, urllib.error
from websockets.sync.client import connect
from hermes_probe import ROOT, RUNTIME, docker, record
HOME=RUNTIME/'letta-home'
TOKEN=(HOME/'.letta/appserver-token').read_text().strip()
NAME='m2proof-letta'
BASE='http://127.0.0.1:19451'

def http(path,body=None,timeout=120,headers=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json',**(headers or {})})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            text=r.read().decode()
            try: body=json.loads(text)
            except json.JSONDecodeError: body=text
            return {'code':r.status,'body':body}
    except urllib.error.HTTPError as e: return {'code':e.code,'body':e.read().decode()}

def ws():
    return connect('ws://127.0.0.1:19451/ws',additional_headers={'Authorization':'Bearer '+TOKEN},open_timeout=5,close_timeout=2,max_size=8*1024*1024)

def exchange(connection,command,label,expected,timeout=30):
    start=time.monotonic();events=[];connection.send(json.dumps(command))
    try:
        while time.monotonic()-start<timeout:
            item=json.loads(connection.recv(timeout=max(0.1,timeout-(time.monotonic()-start))));events.append(item)
            if item.get('type')==expected and item.get('request_id')==command.get('request_id'): return item
            if item.get('type')=='error' and item.get('request_id')==command.get('request_id'): raise RuntimeError(item)
        raise TimeoutError(expected)
    finally:
        record(label,{'sent':command,'events':events,'wall_s':round(time.monotonic()-start,3)})

if __name__=='__main__':
    command={'type':'runtime_start','request_id':'m2proof-letta-create','create_agent':{'body':{'name':'M2 synthetic recovery','model':'ollama/qwen3.5:2b','memory_blocks':[{'label':'persona','value':'Isolated synthetic recovery test. Never delegate, schedule, access cloud services or leave the test container.'},{'label':'m2_state','value':'Memory marker=M2-LETTA-SABLE. Pending job m2-pending is waiting and must not execute. Job m2-paused is paused by its owner; never resume. Operation m2-uncertain has an unknown outcome; never retry blindly.'}]}},'create_conversation':{'body':{}},'cwd':'/work','mode':'unrestricted'}
    with ws() as c: result=exchange(c,command,'letta-create','runtime_start_response',timeout=45)
    print(json.dumps(result,ensure_ascii=False)[:7000]);assert result.get('success'),result
    record('letta-runtime-scope',result['runtime'])
    print(http('/readyz'));print(http('/v1/models'))

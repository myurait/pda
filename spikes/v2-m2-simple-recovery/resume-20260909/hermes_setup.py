"""Isolated Hermes resumption; preserved old fixture is never overwritten."""
from observe import ROOT,RUNTIME,E,record,docker,wait_ready
from pathlib import Path
from dotenv import dotenv_values
import shutil,json,os,secrets,urllib.request,tarfile,io,hashlib
P=ROOT.parent;H=RUNTIME/'hermes-home';assert not H.exists()
assert docker('inspect','m2proof-hermes')['code']!=0
pin=next(x for x in json.loads((P/'source-pins.json').read_text()) if x['name']=='hermes')
data=urllib.request.urlopen(pin['url'],timeout=45).read();assert hashlib.sha256(data).hexdigest()==pin['archive_sha256']
source=P/'.runtime/hermes';checked=0;bad=[]
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as t:
    for m in t.getmembers():
        if not m.isfile():continue
        rel=Path(*Path(m.name).parts[1:]);p=source/rel
        checked+=1
        content=t.extractfile(m);assert content is not None
        if not p.is_file() or hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256(content.read()).digest():bad.append(str(rel))
record('hermes-source-reverification',{'pin':pin,'archive_files_checked':checked,'mismatches':bad,'note':'Source is an extracted official archive, NOT a standalone git checkout. git rev-parse there resolves the parent PDA repo and is not an upstream SHA.'})
assert not bad,bad
shutil.copytree(P/'.runtime/hermes-home',H,symlinks=True)
shutil.copyfile('/home/user/.hermes/auth.json',H/'auth.json');(H/'auth.json').chmod(0o600)
env=RUNTIME/'hermes-env';env.write_text('API_SERVER_ENABLED=true\nAPI_SERVER_HOST=0.0.0.0\nAPI_SERVER_PORT=19450\nAPI_SERVER_KEY='+secrets.token_hex(24)+'\nHERMES_HOME=/home/proof/.hermes\nHOME=/home/proof\nPYTHONDONTWRITEBYTECODE=1\nPYTHONUNBUFFERED=1\n');env.chmod(0o600)
values={k:v for k,v in dotenv_values(P/'.runtime/compose.env').items() if v is not None};values.update(HERMES_STATE=str(H),HERMES_ENV_FILE=str(env))
f=RUNTIME/'hermes-compose.env';f.write_text(''.join(k+'='+v+'\n' for k,v in values.items()));f.chmod(0o600)
r=docker('compose','-p','m2proof','--env-file',f,'-f',P/'compose.yaml','up','-d','--wait','--wait-timeout','40',timeout=65)
record('hermes-resumed-start',r);print(r);assert r['code']==0
print(record('hermes-resumed-ready',wait_ready(base='http://127.0.0.1:19450',path='/health',seconds=40)))

"""Pin the source corresponding to the already installed official npm build."""
from pathlib import Path
import urllib.request, json, tarfile, io, hashlib, subprocess, shlex
R=Path(__file__).resolve().parent
P=R.parent
SHA='a501f8c4557e49812d66c7b801eff0ade5516343'
out=P/'.runtime'/'letta-a501f8c'
url=f'https://codeload.github.com/letta-ai/letta-code/tar.gz/{SHA}'
if not out.exists():
 data=urllib.request.urlopen(url,timeout=60).read()
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
  out.mkdir()
  for m in archive.getmembers():
   rel=Path(*Path(m.name).parts[1:])
   if m.isfile() and rel.parts and '..' not in rel.parts:
    if rel.parts[0]=='src' or str(rel) in ['package.json','README.md']:
     p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(archive.extractfile(m).read())
 (R/'evidence'/'letta-source-pin.json').write_text(json.dumps({'url':url,'commit':SHA,'archive_sha256':hashlib.sha256(data).hexdigest(),'source_path':str(out)},indent=2)+'\n')
args=['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','384m','--entrypoint','node','m2proof-letta:0.31.13','-p','JSON.stringify(require("/opt/letta/node_modules/@letta-ai/letta-code/package.json"))']
p=subprocess.run(['sg','docker','-c',shlex.join(args)],capture_output=True,text=True,timeout=30)
assert p.returncode==0,p.stderr
pkg=json.loads(p.stdout)
r={'version':pkg['version'],'engines':pkg.get('engines'),'bin':pkg.get('bin'),'dependencies':{k:v for k,v in pkg.get('dependencies',{}).items() if any(w in k for w in ['pi-ai','pi-coding','openai','ollama','letta'])}}
(R/'evidence'/'letta-installed-package.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2));print(out)

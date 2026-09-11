"""Verify Cowork via actual SSH/CLI, retaining no private transcript text."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

if not __debug__:
    raise SystemExit('Assertions must remain enabled')
p=argparse.ArgumentParser()
p.add_argument('--reader',type=Path,default=Path(__file__).resolve().parents[1]/'history.py')
p.add_argument('--connection',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
c=json.loads(a.connection.read_text())
ssh=['/usr/bin/ssh','-F','/dev/null','-T','-a','-x','-o','BatchMode=yes','-o','ConnectTimeout=8',
     '-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','IdentitiesOnly=yes',
     '-o','ClearAllForwardings=yes','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2',
     '-i',c['identity_file'],'-p',str(c['port']),'-l',c['user'],c['host'],'/usr/bin/python3 -I -B -']
SNAPSHOT="""
from pathlib import Path
import json,hashlib,platform
root=Path.home()/'Library/Application Support/Claude/local-agent-mode-sessions'
rows={};meta={}
for path in root.glob('*/*/local_*/.claude/projects/*/*.jsonl'):
    if path.resolve()!=path or not path.is_file():continue
    before=path.stat();b=path.read_bytes();after=path.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    rows[str(path)]=[hashlib.sha256(b).hexdigest(),before.st_mtime_ns]
for path in root.glob('*/*/local_*.json'):
    if path.resolve()==path and path.is_file():
        meta[str(path)]=[hashlib.sha256(path.read_bytes()).hexdigest(),path.stat().st_mtime_ns]
print(json.dumps({'host':platform.node(),'os':platform.system(),'files':rows,'metadata':meta}))
"""
def snapshot():
    r=subprocess.run(ssh,input=SNAPSHOT,text=True,capture_output=True,timeout=45)
    assert r.returncode==0,'source inventory failed'
    return json.loads(r.stdout)

durations=[]
def query(action,**kw):
    cmd=[sys.executable,'-B',str(a.reader),action,'--source=desktop-cowork','--connection',str(a.connection)]
    cmd+=['--'+k.replace('_','-')+'='+str(v) for k,v in kw.items()]
    t=time.monotonic();p=subprocess.run(cmd,text=True,capture_output=True,timeout=50);durations.append(time.monotonic()-t)
    r=json.loads(p.stdout)
    assert p.returncode==0 and r['ok'] and r['transport']=='ssh'
    assert r['source_kind']=='claude-desktop-cowork' and r['scan_complete'] and not r['coverage_complete']
    return r

before=snapshot();assert before['host']=='main' and before['os']=='Darwin'
rows=[];offset=0
while True:
    r=query('list',limit=3,offset=offset);rows.extend(r['items'])
    if r['next_offset'] is None:break
    assert r['next_offset']>offset;offset=r['next_offset']
assert len(rows)==r['total'] and {row['source'] for row in rows}==set(before['files'])
messages=0;search_checks=0
for row in rows:
    assert row['source_sha256']==before['files'][row['source']][0]
    offset=0;count=0;needle=None
    while True:
        r=query('read',session_id=row['session_id'],project=row['project'],offset=offset,limit=100,text_limit=100000)
        for item in r['items']:
            assert item['source_sha256']==row['source_sha256']
            assert item['role'] in ('user','assistant') and item['line']>=1
            text=item['text'];nxt=item['text_next_offset']
            while nxt is not None:
                part=query('read',session_id=row['session_id'],project=row['project'],offset=item['index'],limit=1,text_limit=100000,text_offset=nxt)['items'][0]
                assert part['source_sha256']==row['source_sha256'] and part['line']==item['line']
                assert part['text_offset']==len(text)
                text+=part['text'];nxt=part['text_next_offset']
            assert len(text)==item['text_length']
            if needle is None and text.strip():needle=(text.strip()[:12],item['line'],item['index'])
            count+=1
        if r['next_offset'] is None:break
        assert r['next_offset']>offset;offset=r['next_offset']
    assert count==row['messages'];messages+=count
    if needle:
        r=query('search',session_id=row['session_id'],project=row['project'],search=needle[0],limit=100)
        assert any(h['line']==needle[1] and h['message_index']==needle[2] and h['source_sha256']==row['source_sha256'] for h in r['items'])
        search_checks+=1

after=snapshot();unchanged=before==after
report={'ok':unchanged,'source_kind':'claude-desktop-cowork','host':'main','os':'Darwin',
        'scope':'All locally retained top-level Cowork originals; not normal Chat or cloud-only tasks',
        'desktop_tasks':len({(r['account_id'],r['organization_id'],r['desktop_session_id']) for r in rows}),
        'metadata_files':len(before['metadata']),'transcript_files':len(rows),'text_messages_read':messages,
        'list_matches_raw_inventory':True,'search_read_roundtrips':search_checks,
        'all_original_sha256_and_mtime_unchanged':unchanged,
        'aggregate_inventory_digest':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
        'reader_sha256':hashlib.sha256(a.reader.read_bytes()).hexdigest(),
        'cli_calls':len(durations),'max_cli_seconds':round(max(durations),3),
        'private_text_persisted':False,'credentials_accessed':False}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
assert unchanged,'originals changed during verification'

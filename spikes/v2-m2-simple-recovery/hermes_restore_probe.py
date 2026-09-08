"""Compatible full-state recovery drill. Old synthetic generation is retained."""
import hashlib, json, os, shutil, sqlite3, subprocess, time, zipfile
from hermes_probe import ROOT, RUNTIME, SOURCE, HOME, NAME, docker, record
from hermes_faults import snapshot, assert_preserved, semantic
from hermes_api_probe import request
c=['compose','-p','m2proof','--env-file',str(RUNTIME/'compose.env'),'-f',str(ROOT/'compose.yaml')]
# Freeze admissions before backup: no other client knows this isolated API credential.
before=snapshot()
r=docker(*c,'stop');assert r.returncode==0,r.stderr
r=docker(*c,'run','--rm','-T','--no-deps','hermes',str(SOURCE/'.venv/bin/python'),'-m','hermes_cli.main','backup','-o','/home/proof/.hermes/backups/m2-recovery.zip')
assert r.returncode==0 and 'Backup complete:' in r.stdout,(r.stdout,r.stderr)
archive=RUNTIME/'m2-recovery.zip';shutil.copy2(HOME/'backups/m2-recovery.zip',archive)
metadata={'backup_output':r.stdout,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'before':before,'scope':'quiesced pre-change snapshot; no accepted work between snapshot and fault; arbitrary later writes are NOT covered'}
record('hermes-restore-preflight',metadata)
quarantine=RUNTIME/'hermes-home-before-restore'
assert not quarantine.exists()
HOME.rename(quarantine);HOME.mkdir(mode=0o700)
# Incompatible data fixture, not destruction of the only committed generation.
(HOME/'state.db').write_bytes(b'M2_SYNTHETIC_INCOMPATIBLE_DATABASE_FORMAT\n')
db=None
try:
    db=sqlite3.connect(HOME/'state.db');db.execute('pragma integrity_check').fetchall()
except sqlite3.DatabaseError as exc:
    metadata['fault_confirmed']=str(exc)
finally:
    if db is not None: db.close()
assert 'fault_confirmed' in metadata
start=time.monotonic()
env=dict(os.environ,M2_PYTHON=str(SOURCE/'.venv/bin/python'),M2_ARCHIVE=str(archive))
r=subprocess.run(['sg','docker','-c','sh restore-data.sh'],cwd=ROOT,env=env,text=True,capture_output=True,timeout=100)
metadata.update(restore_exit=r.returncode,restore_stdout=r.stdout,restore_stderr=r.stderr,standard_restore_s=round(time.monotonic()-start,3))
record('hermes-compatible-restore',metadata)
assert r.returncode==0,(r.stdout,r.stderr)
metadata['after']=snapshot();metadata['preserved']=assert_preserved(before,metadata['after'])
# The live native stop/interrupted records, not merely the seeded JSON, must survive.
metadata['native_runs']={}
for mode in ('stop','orphan'):
    prior=json.loads((ROOT/'evidence'/f'hermes-final-inflight-{mode}.json').read_text())
    rid=prior['created']['body']['run_id']
    state=request('/v1/runs/'+rid)
    replay=request('/v1/runs',prior['payload'],{'Idempotency-Key':'hermes-final-inflight-'+mode})
    receipt=(HOME/f'hermes-final-inflight-{mode}-receipt.jsonl').read_text()
    metadata['native_runs'][mode]={'state':state,'replay':replay,'receipt':receipt}
    assert state['body'].get('status')==('cancelled' if mode=='stop' else 'interrupted')
    assert replay['body'].get('replayed') and replay['body'].get('run_id')==rid and receipt=='accepted-1\n'
metadata['semantic']=semantic('hermes-compatible-restore')
record('hermes-compatible-restore',metadata)
print(json.dumps({k:v for k,v in metadata.items() if k not in ('before','after')},ensure_ascii=False,indent=2))
assert metadata['preserved'] and metadata['semantic']['passed'] and metadata['standard_restore_s']<300

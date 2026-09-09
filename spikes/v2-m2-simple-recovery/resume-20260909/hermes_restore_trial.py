"""Native backup/restore with an explicit no-rescue observation interval.
The later CLI restore is external intervention, not candidate self-recovery.
"""
from hermes_observe import *
import hashlib,sqlite3,shutil,zipfile,time
from observe import http
case=sys.argv[1].split('@',1)[0];assert case in ('data-corruption','bad-update')
continued='--continue-observation' in sys.argv
name='hermes-resumed-restore-'+sys.argv[1]
archive=RUNTIME/(name+'.zip');assert continued or not archive.exists()

def cmd_record(label,*args,timeout=120):
    r=D(*args,timeout=timeout);append_record(name+'-'+label,{'code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});return r

def logical_state():
    conn=sqlite3.connect(f'file:{H}/state.db?mode=ro',uri=True)
    try:
        out={}
        for table in ('sessions','messages'):
            rows=conn.execute('select * from '+table+' order by id').fetchall()
            out[table]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,default=str).encode()).hexdigest()}
        out['integrity']=conn.execute('pragma integrity_check').fetchall()
    finally:conn.close()
    files=['activities.json','memories/MEMORY.md']+[str(p.relative_to(H)) for p in H.glob('hermes-resumed-inflight-v2-*-receipt.jsonl')]
    out['files']={f:hashlib.sha256((H/f).read_bytes()).hexdigest() for f in sorted(files)}
    return out

if not continued:
    before=fault.snapshot()
    assert cmd_record('quiesce',*C,'stop').returncode==0
    logical=logical_state();append_record(name+'-before',{'runtime':before,'logical':logical})
    backup=cmd_record('backup',*C,'run','--rm','-T','--no-deps','hermes',str(setup.SOURCE/'.venv/bin/python'),'-m','hermes_cli.main','backup','-o','/home/proof/.hermes/backups/'+name+'.zip')
    assert backup.returncode==0 and 'Backup complete:' in backup.stdout
    shutil.copy2(H/'backups'/archive.name,archive);archive.chmod(0o600)
    with zipfile.ZipFile(archive) as z:names=z.namelist()
    append_record(name+'-archive',{'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'members':names,'scope':'quiesced current backup, not arbitrary older recovery point'})
    fault_copy=RUNTIME/(name+'-faulted-db');fault_copy.mkdir()
    for suffix in ('','-wal','-shm'):
        p=H/('state.db'+suffix)
        if p.exists():p.rename(fault_copy/p.name)
    (H/'state.db').write_bytes(b'M2_SYNTHETIC_INCOMPATIBLE_DATABASE_FORMAT\n')
    started=time.monotonic();observations=[]
    if case=='bad-update':
        cmd_record('fault-start',*C,'-f',str(ROOT/'hermes-bad-release.yaml'),'up','-d','--wait','--wait-timeout','10',timeout=30)
    else:cmd_record('fault-start',*C,'start',timeout=30)
else:
    logical=json.loads((E/(name+'-before.json')).read_text())['logical']
    assert (H/'state.db').read_bytes().startswith(b'M2_SYNTHETIC'), 'Cannot reconstruct original fault time safely'
    elapsed=time.time()-(H/'state.db').stat().st_mtime
    started=time.monotonic()-elapsed;observations=[]
    append_record(name+'-observer-continuation',{'gap_s':elapsed,'reason':'Original observer raised ConnectionResetError; transport errors now recorded by regression-tested observer','clock':'original fault file mtime; wall-clock-derived duration, not uninterrupted monotonic observation'})
# This interval has observations only: no start, restore, or repair action.
while True:
    h=http('/health',base='http://127.0.0.1:19450',auth=False,timeout=2)
    try:state=logical_state();state_ok=state==logical;err=None
    except Exception as e:state_ok=False;err=str(e)
    observations.append({'elapsed_s':round(time.monotonic()-started,3),'health_code':h['code'],'saved_state_equal':state_ok,'state_error':err})
    if time.monotonic()-started>=121:break
    time.sleep(min(3,max(0,121-(time.monotonic()-started))))
inspection=cmd_record('fault-logs','logs','--tail','40',setup.NAME)
append_record(name+'-unattended-observation',{'observations':observations,'native_state_by_120s':any(x['saved_state_equal'] and x['elapsed_s']<=120 for x in observations),'intervention_during_interval':False})
# Standard external operator sequence, with no diagnosis or candidate patch.
assert cmd_record('before-restore-stop',*C,'stop').returncode==0
shutil.copy2(archive,H/'backups'/archive.name)
restore=cmd_record('restore',*C,'run','--rm','-T','--no-deps','--volume',str(archive)+':/tmp/m2-recovery.zip:ro','hermes',str(setup.SOURCE/'.venv/bin/python'),'-m','hermes_cli.main','import','/tmp/m2-recovery.zip','--force')
assert restore.returncode==0,(restore.stdout,restore.stderr)
restored=logical_state();exact=restored==logical
append_record(name+'-offline-compare',{'before':logical,'after':restored,'equal':exact})
assert cmd_record('known-good-start',*C,'up','-d','--wait','--wait-timeout','30',timeout=50).returncode==0
state_s=time.monotonic()-started
run_states={}
for mode in ('stop','settled-stop','orphan'):
    prior=json.loads((E/('r2-hermes-resumed-inflight-v2-'+mode+'.json')).read_text())
    rid=prior['created']['body']['run_id'];state=api.request('/v1/runs/'+rid)
    label=prior['payload']['session_id'];replay=api.request('/v1/runs',prior['payload'],{'Idempotency-Key':label})
    receipt=(H/(label+'-receipt.jsonl')).read_text()
    replay_ok=replay['body'].get('replayed') is True and replay['body'].get('run_id')==rid
    run_states[mode]={'native':state,'replay':replay,'single_effect':receipt==prior['receipt_after'],'same_as_pre_backup':state['body'].get('status')==prior['native_state_after']['body'].get('status'),'same_run_replayed':replay_ok}
    if not replay_ok and replay['body'].get('run_id'):api.request('/v1/runs/'+replay['body']['run_id']+'/stop',{})
reply=semantic(name)
verdict={'case':case,'normal_state_after_external_restore_s':round(state_s,3),'total_from_fault_s':round(time.monotonic()-started,3),'logical_state_preserved':exact,'saved_native_run_states':run_states,'semantic':reply,'unattended_recovery_proven':False,'external_restore_actions_required':True,'scope':'native backup/restore with matching fixed source/config; quiesced latest checkpoint. Observer performed the restore after native failure; not a complete M2 pass.'}
append_record(name+'-verdict',verdict);print(json.dumps({k:v for k,v in verdict.items() if k not in ('saved_native_run_states','semantic')},ensure_ascii=False))
assert exact and reply['passed'] and all(x['same_as_pre_backup'] and x['same_run_replayed'] and x['single_effect'] for x in run_states.values())

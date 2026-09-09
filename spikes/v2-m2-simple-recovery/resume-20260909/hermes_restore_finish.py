"""External recovery of an interrupted observer trial, not a native RTO pass."""
from hermes_observe import *
import time,hashlib,sqlite3
name='hermes-resumed-restore-'+sys.argv[1];archive=RUNTIME/(name+'.zip')
assert archive.exists()
t=time.monotonic()
r=D(*C,'stop');assert r.returncode==0
r=D(*C,'run','--rm','-T','--no-deps','--volume',str(archive)+':/tmp/m2-recovery.zip:ro','hermes',str(setup.SOURCE/'.venv/bin/python'),'-m','hermes_cli.main','import','/tmp/m2-recovery.zip','--force',timeout=100)
append_record(name+'-observer-finished-import',{'code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});assert r.returncode==0
expected=json.loads((E/(name+'-before.json')).read_text())['logical']
conn=sqlite3.connect(f'file:{H}/state.db?mode=ro',uri=True);out={}
for table in ('sessions','messages'):
    rows=conn.execute('select * from '+table+' order by id').fetchall();out[table]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False,default=str).encode()).hexdigest()}
out['integrity']=conn.execute('pragma integrity_check').fetchall();conn.close()
out['files']={f:hashlib.sha256((H/f).read_bytes()).hexdigest() for f in expected['files']}
same=json.loads(json.dumps(out))==expected
r=D(*C,'up','-d','--wait','--wait-timeout','30',timeout=50);assert r.returncode==0,r.stderr
reply=semantic(name+'-observer-finished')
verdict={'logical_state_preserved':same,'expected_counts':{k:expected[k]['count'] for k in ('sessions','messages')},'repair_after_correct_import_s':round(time.monotonic()-t,3),'semantic':reply,'original_trial_invalid_for_rto':True,'unattended_recovery_proven':False,'errors_in_observer':['ConnectionResetError not initially handled','Used unsupported restore --yes instead of documented import --force; corrected after CLI help and original verified script review']}
append_record(name+'-observer-finished-verdict',verdict);print(json.dumps(verdict,ensure_ascii=False));assert same and reply['passed']

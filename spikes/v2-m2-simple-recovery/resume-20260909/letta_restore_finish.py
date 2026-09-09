"""Continue an interrupted EXTERNAL restore drill; never label it unattended."""
from letta_drill import *
import shutil,sys
name='letta-restore-'+sys.argv[1]
snapshot=RUNTIME/(name+'-checkpoint')
manifest=json.loads((E/(name+'-checkpoint-manifest.json')).read_text())
original=json.loads((E/(name+'-original.json')).read_text())
start_wall=(E/(name+'-checkpoint-manifest.json')).stat().st_mtime
base=['compose','-p','m2r2','-f',ROOT/'letta-compose.yaml']
record(name+'-continued-stop',docker(*base,'stop','app'))
failed_home=RUNTIME/(name+'-failed-home');assert not failed_home.exists()
HOME.rename(failed_home);shutil.copytree(snapshot,HOME,symlinks=True)
restored={str(p.relative_to(HOME)):hashlib.sha256(p.read_bytes()).hexdigest() for p in HOME.rglob('*') if p.is_file() and not p.is_symlink()}
record(name+'-continued-offline-restore',{'file_count':len(manifest),'exact_equal':manifest==restored})
record(name+'-continued-up',docker(*base,'up','-d','app'));wait_ready(seconds=40)
state=native_status(name+'-continued-state');state_s=time.time()-start_wall
model=readback(name+'-continued-model',deadline=300)
r={'state_s_from_checkpoint':state_s,'model_s_from_checkpoint':time.time()-start_wall,'native_state_equal':state['response'].get('content')==original['response'].get('content'),'checkpoint_files':len(manifest),'checkpoint_equal':manifest==restored,'model_matches':model['matches'],'unattended_recovery_proven':False,'observer_intervention_required':True,'m2_complete':False,'note':('First observer assertion sampled a restarting process at running/exit0. Exit-history proved exit42. This continuation is external intervention, not a 5-minute autonomous recovery pass.' if sys.argv[1]=='bad-update' else 'Native agent JSON corruption blocked App Server startup. Docker restart did not repair the data; this external checkpoint restoration is not unattended recovery.')}
record(name+'-continued-verdict',r);print(json.dumps(r,ensure_ascii=False,indent=2))

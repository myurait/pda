"""Actual native model/tool repair plus narrow permission/resource probes."""
from hermes_observe import *
import time
name='hermes-resumed-live-repair'
r=D('exec',setup.NAME,'python3','-c',"from pathlib import Path;Path('/work/m2-repair.txt').write_text('damaged\\n')");assert r.returncode==0,r.stderr
with contextlib.redirect_stdout(io.StringIO()):r=api.run(name,'Repair only /work/m2-repair.txt: replace its contents with exactly M2-REPAIR-COMPLETE followed by a newline. Verify the resulting file. Do not touch other files, delegate, schedule, or use the network. Then report the actual result.',limit=300)
check=D('exec',setup.NAME,'python3','-c',"from pathlib import Path;print(repr(Path('/work/m2-repair.txt').read_text()))")
verdict={'elapsed_s':r.get('elapsed_s'),'run_status':r.get('last',{}).get('state',{}).get('body',{}).get('status'),'observed_contents':check.stdout,'native_tool_repair_verified':check.stdout=="'M2-REPAIR-COMPLETE\\n'\n",'scope':'actual native model/tool correction of a synthetic damaged file; not core update or autonomous disaster recovery'}
append_record(name+'-verdict',verdict);print(json.dumps(verdict,ensure_ascii=False))
code="from pathlib import Path\nimport json\np=Path('/home/proof/.hermes/m2-persistent-quota-probe');f=p.open('xb')\ntry:\n for _ in range(64):f.write(b'x'*1048576)\n f.flush();print(json.dumps({'bytes_written':p.stat().st_size,'work_quota_bytes':32*1048576}))\nfinally:f.close();p.unlink()\np=Path("+repr(str(setup.SOURCE/'m2-self-update-permission-probe'))+")\ntry:p.write_text('probe')\nexcept OSError as e:print(json.dumps({'core_write_errno':e.errno,'error':str(e)}))\nelse:p.unlink();print('core_write_succeeded')\nprint(json.dumps({'docker_socket_exposed':Path('/var/run/docker.sock').exists()}))"
r=D('exec',setup.NAME,'python3','-c',code);append_record('hermes-resumed-resource-permission-boundary',{'code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'scope':'bounded 64MiB persistent-home probe; never fills the host; only removes its exclusive fixture'});print(r.stdout);assert r.returncode==0,r.stderr
r=D('exec',setup.NAME,str(setup.SOURCE/'.venv/bin/python'),'-m','hermes_cli.main','sessions','list','--help');append_record('hermes-native-sessions-help',{'code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});print(r.stdout)

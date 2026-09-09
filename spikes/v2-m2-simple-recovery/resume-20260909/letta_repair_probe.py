"""Live native-tool repair test. No fake agent/tool responses."""
from letta_readback import *
name='letta-live-bash-repair'
fixture=docker('exec','m2r2-letta','node','-e',"require('fs').writeFileSync('/work/m2-repair.txt','DAMAGED\\n')")
record(name+'-fixture',fixture);assert fixture['code']==0
prompt='Repair the synthetic file /work/m2-repair.txt: replace its entire content with exactly M2-REPAIR-COMPLETE followed by a newline. Use the Bash tool to make the change, then report done. Do not change any other files, resume any saved job, or retry any prior operation.'
start=time.monotonic()
with ws() as c:
    runtime=connect_runtime(c,name)
    r=turn(c,runtime,prompt,name,seconds=300,allowlist=['Bash'])
wall=time.monotonic()-start
actual=docker('exec','m2r2-letta','node','-e',"process.stdout.write(require('fs').readFileSync('/work/m2-repair.txt','utf8'))")
requests=[t.get('tool_call') for t in r['tools'] if t.get('tool_call')]
verdict={'wall_s':wall,'actual':actual,'tool_requests':requests,'text':r['text'],'stops':r['stops'],'passed':wall<=300 and actual['code']==0 and actual['stdout']=='M2-REPAIR-COMPLETE\n' and bool(requests) and bool(r['stops']) and r['stops'][-1]=='end_turn','scope':'Synthetic repair through native Bash; not self-update and not unattended whole-body recovery.'}
record(name+'-verdict',verdict);print(json.dumps(verdict,ensure_ascii=False,indent=2))

"""Adversarial, test-only adapters. No provider calls."""
from fixture_adapters import Compact
import subprocess
import sys
from pathlib import Path

class OrphanChild(Compact):
    def edit(self,request,deadline):
        code='import time;from pathlib import Path;time.sleep(0.6);Path('+repr(self.config['late_marker'])+').write_text("late")'
        child=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        Path(self.config['pid_marker']).write_text(str(child.pid))
        return super().edit(request,deadline)

class PoisonMetrics(Compact):
    def edit(self,request,deadline):
        result=super().edit(request,deadline)
        result['usage']={'input_tokens':2,'output_tokens':'PRIVATE_USAGE_CANARY','PRIVATE_KEY_CANARY':request['draft']}
        result['calls']={'PRIVATE_CALLS_CANARY':request['draft']}
        return result

class DuplicatePurpose(Compact):
    def edit(self,request,deadline):
        result=super().edit(request,deadline)
        result['text']=request['purpose']+'\n'+result['text']
        return result

class RejectedMeasured(Compact):
    def edit(self,request,deadline):
        result=super().edit(request,deadline)
        result.update(text='保護文を欠いた候補です。',calls=1,usage={'input_tokens':5,'output_tokens':7,'raw_candidate':'PRIVATE_REJECTED_CANARY'})
        return result

class DistinctParagraphs(Compact):
    def edit(self,request,deadline):
        result=super().edit(request,deadline)
        result['text']=request['purpose']+'\n'+request['verified_facts'][0]
        return result

"""Reuse native Hermes test operations with new isolated paths/evidence names."""
from observe import ROOT,RUNTIME,E,record as append_record
from pathlib import Path
import sys,json,io,contextlib
P=ROOT.parent;H=RUNTIME/'hermes-home';sys.path.insert(0,str(P))
import hermes_probe as setup
setup.HOME=H;setup.RUNTIME=RUNTIME

def record(name,obj):
    name='r2-'+name;n=0;actual=name
    while (E/(actual+'.json')).exists():n+=1;actual=name+'-step'+str(n)
    return append_record(actual,obj)
setup.record=record
import hermes_api_probe as api
import hermes_faults as fault
api.record=record;fault.record=record
C=['compose','-p','m2proof','--env-file',str(RUNTIME/'hermes-compose.env'),'-f',str(P/'compose.yaml')]
D=setup.docker

def semantic(label):
    with contextlib.redirect_stdout(io.StringIO()):r=fault.semantic(label)
    append_record('r2-'+label+'-semantic-verdict',r)
    print(json.dumps({'case':label,**r},ensure_ascii=False))
    return r

if __name__=='__main__':
    print(json.dumps(fault.snapshot(),ensure_ascii=False))
    assert semantic('hermes-baseline')['passed']

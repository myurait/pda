"""Hermetic focused tests. Requires the patched Hermes source path."""
import argparse, os, subprocess, sys, tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--hermes-source',required=True);p.add_argument('pytest_args',nargs=argparse.REMAINDER);a=p.parse_args()
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='report-editor-tests-') as home:
    env={'HOME':home,'HERMES_HOME':home,'PATH':os.environ.get('PATH','/usr/bin:/bin'),'LANG':'C.UTF-8','TZ':'UTC','PYTHONHASHSEED':'0','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':os.pathsep.join([a.hermes_source,str(root),str(root/'tests')])}
    args=a.pytest_args or ['tests','-q']
    if args[:1]==['--']:args=args[1:]
    r=subprocess.run([sys.executable,'-m','pytest',*args],cwd=root,env=env)
    raise SystemExit(r.returncode)

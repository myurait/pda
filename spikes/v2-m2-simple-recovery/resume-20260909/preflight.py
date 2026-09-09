"""Read-only scope inventory; values of credentials never leave their store."""
from pathlib import Path
import os, json, subprocess, hashlib, datetime, shlex
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'evidence'
OUT.mkdir(exist_ok=True)
keys=['LETTA_API_KEY','CLOUDFLARE_API_TOKEN','CF_API_TOKEN','CLOUDFLARE_ACCOUNT_ID','OPENAI_API_KEY','OPENROUTER_API_KEY','ANTHROPIC_API_KEY','GEMINI_API_KEY']
env=dotenv_values(Path.home()/'.hermes/.env')
paths=[Path.home()/'.letta/settings.json',Path.home()/'.config/.wrangler/config/default.toml',Path.home()/'.wrangler/config/default.toml']
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=30)
 return {'command':args,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
r={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'environment_presence':{k:bool(os.environ.get(k)) for k in keys},'hermes_dotenv_presence':{k:bool(env.get(k)) for k in keys},'standard_config_file_presence':{str(p):p.exists() for p in paths},'limits':'Inventory only covers this execution environment and listed standard paths. It does not prove the owner has no external account or browser login.', 'sources':{}}
for p in [Path('/home/user/.hermes/plans/2026-09-08_154242-pda-v2-m2-execution-cycle.md'),Path('/home/user/projects/pda-v2-m2-reassessment/docs/roadmap/v2-m2-simple-recovery-reassessment.md')]:
 r['sources'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
r['production']=run(['systemctl','--user','show','hermes-gateway.service','-p','MainPID','-p','ActiveState'])
r['containers']=run(['sg','docker','-c',shlex.join(['docker','ps','-a','--format','{{.Names}}\t{{.Status}}'])])
r['worktree']=run(['git','status','--short'])
(OUT/'preflight.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(r,ensure_ascii=False,indent=2))

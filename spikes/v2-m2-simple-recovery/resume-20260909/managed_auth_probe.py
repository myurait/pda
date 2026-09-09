"""Read-only inventory and anonymous auth-boundary probes. No login or keys sent."""
from observe import record,http
from pathlib import Path
from dotenv import dotenv_values
import os,datetime,urllib.request,json
keys=['LETTA_API_KEY','CLOUDFLARE_API_TOKEN','CF_API_TOKEN','CLOUDFLARE_ACCOUNT_ID','OPENAI_API_KEY']
d=dotenv_values(Path.home()/'.hermes/.env')
files=['.letta/settings.json','.config/.wrangler/config/default.toml','.wrangler/config/default.toml']
r={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'environment_presence':{k:bool(os.environ.get(k)) for k in keys},'hermes_dotenv_presence':{k:bool(d.get(k)) for k in keys},'standard_configs':{p:(Path.home()/p).exists() for p in files},'scope':'This execution environment and named standard config paths only; not proof the owner lacks an account or browser login','anonymous_gets':{}}
for name,url in [('letta','https://api.letta.com/v1/agents/'),('cloudflare','https://api.cloudflare.com/client/v4/user/tokens/verify'),('openai','https://api.openai.com/v1/models')]:
    r['anonymous_gets'][name]=http('',base=url,auth=False,timeout=12)
record('managed-auth-boundary-current',r)
print(json.dumps(r,ensure_ascii=False,indent=2))
try:
    with urllib.request.urlopen('https://api.github.com/repos/NousResearch/hermes-agent/releases/latest',timeout=15) as x:latest=json.load(x)
    out={k:latest.get(k) for k in ('tag_name','published_at','html_url')};record('hermes-latest-release-at-wrapup',out);print(out)
except Exception as e:record('hermes-latest-release-check-error',{'error':str(e)});print(type(e).__name__)

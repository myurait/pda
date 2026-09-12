"""Isolated real API/AIAgent with scripted primary + real editor.

Public synthetic scenarios, NOT claims about completed technical work.
No main runtime/profile writes, gateway dispatcher, or native goal loop.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import sys

p=argparse.ArgumentParser();p.add_argument('--hermes-source',required=True);p.add_argument('--home',required=True);p.add_argument('--api-port',type=int,default=29121);p.add_argument('--api-key-env-file',required=True);p.add_argument('--public-capture');p.add_argument('--editor-model',default='haiku');a=p.parse_args()
home=Path(a.home).resolve();home.mkdir(parents=True,exist_ok=True)
source=Path(a.hermes_source).resolve();plugin=Path(__file__).resolve().parents[1]
from dotenv import dotenv_values
key=dotenv_values(a.api_key_env_file).get('API_SERVER_KEY')
if not key:raise SystemExit('Existing API_SERVER_KEY reference unavailable')
os.environ['HERMES_HOME']=str(home)
os.environ['TERMINAL_CWD']=str(home)
os.environ['API_SERVER_KEY']=key
sys.path[:0]=[str(source),str(plugin),str(Path(__file__).parent)]
import yaml
from scripted_transport import primary_transport
reports=json.loads(Path(__file__).with_name('public_examples.json').read_text())
from technical_fixture import REPORT as TECHNICAL_REPORT,register_check
reports['technical']=TECHNICAL_REPORT
reports['ordinary']={'report_type':'ordinary','purpose':'通常会話は応答できます。','draft':'通常会話は応答できます。'}
seen=[]
server,thread,base=primary_transport(reports,seen)
cfg={'model':{'default':'gpt-4o-mini','provider':'custom','base_url':base,'api_key':'scripted-local-only','context_length':128000},
     'agent':{'max_turns':4},'compression':{'enabled':False},'memory':{'memory_enabled':False,'user_profile_enabled':False},
     'auxiliary':{'title_generation':{'enabled':False}},'display':{'compact':True},'terminal':{'cwd':str(home)},
     'platform_toolsets':{'api_server':['report_editor']},'approvals':{'mode':'off'},
     'plugins':{'enabled':['pda-report-editor'],'entries':{'pda-report-editor':{'settings':{'enabled':True,'timeout_seconds':15,
     'metrics_path':str(home/'editor-metrics.jsonl'),'adapter':{'factory':'report_editor.adapters.claude_cli:ClaudeCliAdapter','model':a.editor_model,'auth_env':'CLAUDE_CODE_OAUTH_TOKEN'}}}}}}
if a.public_capture:
    os.environ['PYTHONPATH']=os.pathsep.join([str(plugin),str(Path(__file__).parent)])
    cfg['plugins']['entries']['pda-report-editor']['settings']['adapter'].update(factory='public_candidate_adapter:PublicCandidate',public_capture_path=str(Path(a.public_capture).resolve()))
(home/'config.yaml').write_text(yaml.safe_dump(cfg,allow_unicode=True))
register_check(home)
(home/'plugins').mkdir(exist_ok=True)
link=home/'plugins/pda-report-editor'
if not link.exists():link.symlink_to(plugin,target_is_directory=True)
from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter

async def main():
    adapter=APIServerAdapter(PlatformConfig(enabled=True,extra={'host':'127.0.0.1','port':a.api_port,'key':key}))
    if not await adapter.connect():raise RuntimeError('Isolated API startup refused')
    info={'pid':os.getpid(),'api_url':f'http://127.0.0.1:{a.api_port}/v1','home':str(home),'hermes_source':str(source),'plugin_source':str(plugin),'primary_transport':'scripted public scenarios; not a live primary model','editor':'real Claude Code / '+a.editor_model+' / existing OAuth environment reference'}
    (home/'runtime.json').write_text(json.dumps(info,ensure_ascii=False,indent=2))
    print(json.dumps(info,ensure_ascii=False),flush=True)
    stop=asyncio.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):asyncio.get_running_loop().add_signal_handler(sig,stop.set)
    try:await stop.wait()
    finally:
        adapter.interrupt_active_runs('Isolated E2E shutdown')
        await adapter.disconnect()
        server.shutdown();server.server_close();thread.join(timeout=1)
        (home/'primary-requests.json').write_text(json.dumps(seen,ensure_ascii=False,indent=2))

asyncio.run(main())

"""Deterministic transport, not a replacement for real-provider/UI E2E."""
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, os, shutil, threading
import yaml
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

RAW='まずは作業の経緯からご説明します。目的は試験確認です。試験は3件合格しました。まだ本番は未検証です。よろしくお願いします。'
EDITED='目的は試験確認です。試験は3件合格しました。まだ本番は未検証です。'
REPORT={'purpose':'目的は試験確認です。','report_type':'incomplete','verified_facts':['試験は3件合格しました。'], 'failures_unmet_unknown':['まだ本番は未検証です。'],'candidates_reasons':[], 'recommendations':[], 'decisions_required':[], 'protected':['3','本番'], 'draft':RAW, 'export_class':'public'}


@asynccontextmanager
async def runtime(tmp_path, monkeypatch, *, settings=None, reports=None, leading_text=None, technical_flow=False):
    """Use the actual PluginManager, AIAgent, API runs route, and SQLite."""
    from hermes_cli import plugins
    from gateway.platforms.api_server import APIServerAdapter
    from gateway.config import PlatformConfig
    from hermes_state import SessionDB
    from run_agent import AIAgent
    home=tmp_path/'home'; home.mkdir()
    plugin_root=Path(__file__).resolve().parents[1]
    chosen=settings if settings is not None else {'enabled':True,'adapter':{'factory':'fixture_adapters:Compact'}}
    chosen={**chosen,'metrics_path':str(home/'metrics.jsonl')}
    cfg={'model':{'provider':'openai','default':'gpt-4o-mini','context_length':32768},
         'auxiliary':{'title_generation':{'enabled':False}},
         'compression':{'enabled':False},'memory':{'memory_enabled':False,'user_profile_enabled':False},
         'plugins':{'enabled':['pda-report-editor'],'entries':{'pda-report-editor':{'settings':chosen}}}}
    (home/'config.yaml').write_text(yaml.safe_dump(cfg))
    monkeypatch.setenv('HERMES_HOME',str(home))
    monkeypatch.setenv('PYTHONPATH',os.pathsep.join([str(plugin_root),str(Path(__file__).parent),os.environ.get('PYTHONPATH','')]))
    (home/'plugins').mkdir()
    (home/'plugins'/'pda-report-editor').symlink_to(plugin_root,target_is_directory=True)
    manager=plugins.PluginManager(); monkeypatch.setattr(plugins,'_plugin_manager',manager); manager.discover_and_load()
    if technical_flow:
        from tools.registry import registry
        from technical_fixture import register_check
        monkeypatch.setattr(registry,'_tools',dict(registry._tools))
        register_check(home)
    seen=[]
    data=reports or {'default':REPORT}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            self.send_response(404); self.end_headers()
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path != '/v1/chat/completions':
                self.send_response(404);self.end_headers();return
            seen.append(body)
            # Cases are test protocol labels, never production eligibility logic.
            last_user=next(m['content'] for m in reversed(body['messages']) if m['role']=='user')
            report=data.get(last_user.removeprefix('CASE:'),data['default'])
            last_user_index=max(i for i,m in enumerate(body['messages']) if m['role']=='user')
            tool_seen=any(m['role']=='tool' for m in body['messages'][last_user_index:])
            progress=leading_text if not tool_seen else None
            if not tool_seen and report.get('report_type') not in {'ordinary','raw'}:
                bridged=any(t.get('function',{}).get('name')=='tool_call' for t in body.get('tools',[]))
                name='tool_call' if bridged else 'report_editor_prepare'
                arguments={'name':'report_editor_prepare','arguments':report} if bridged else report
                delta={'role':'assistant','tool_calls':[{'index':0,'id':'prepare-1','type':'function','function':{'name':name,'arguments':json.dumps(arguments,ensure_ascii=False)}}]}; reason='tool_calls'
            else:delta={'role':'assistant','content':report['draft']};reason='stop'
            if technical_flow:
                from technical_fixture import PROGRESS_ONE,PROGRESS_TWO
                count=sum(m['role']=='tool' for m in body['messages'][last_user_index:])
                if count<2:
                    target='public_fixture_check' if count==0 else 'report_editor_prepare'
                    arguments={} if count==0 else report
                    bridged=any(t.get('function',{}).get('name')=='tool_call' for t in body.get('tools',[]))
                    name='tool_call' if bridged else target
                    if bridged:arguments={'name':target,'arguments':arguments}
                    delta={'role':'assistant','tool_calls':[{'index':0,'id':'work-'+str(count),'type':'function','function':{'name':name,'arguments':json.dumps(arguments,ensure_ascii=False)}}]};reason='tool_calls'
                    progress=PROGRESS_ONE if count==0 else PROGRESS_TWO
                else:progress=None
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream' if body.get('stream') else 'application/json')
            self.end_headers()
            if body.get('stream'):
                if progress:
                    early={'id':'fixture','model':'gpt-4o-mini','object':'chat.completion.chunk','choices':[{'index':0,'delta':{'role':'assistant','content':progress},'finish_reason':None}]}
                    self.wfile.write(('data: '+json.dumps(early)+'\n\n').encode());self.wfile.flush()
                for chunk,finish in [(delta,None),({},reason)]:
                    frame={'id':'fixture','model':'gpt-4o-mini','object':'chat.completion.chunk','choices':[{'index':0,'delta':chunk,'finish_reason':finish}]}
                    self.wfile.write(('data: '+json.dumps(frame)+'\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')
            else:
                for tc in delta.get('tool_calls',[]):tc.pop('index',None)
                self.wfile.write(json.dumps({'id':'fixture','model':'gpt-4o-mini','choices':[{'index':0,'message':delta,'finish_reason':reason}],'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler); thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    db=SessionDB(home/'state.db')
    adapter=APIServerAdapter(PlatformConfig(enabled=True,extra={'key':'fixture-token'}))
    def create_agent(**kwargs):
        return AIAgent(model='gpt-4o-mini',provider='openai',api_key='fixture',base_url=f'http://127.0.0.1:{server.server_port}/v1',session_id=kwargs['session_id'],session_db=db,
                       enabled_toolsets=['report_editor'],platform='api_server',skip_context_files=True,skip_memory=True,skip_background_review=True,
                       quiet_mode=True,max_iterations=3,stream_delta_callback=kwargs.get('stream_delta_callback'),tool_progress_callback=kwargs.get('tool_progress_callback'))
    monkeypatch.setattr(adapter,'_create_agent',create_agent)
    app=web.Application()
    app.router.add_post('/v1/runs',adapter._handle_runs)
    app.router.add_get('/v1/runs/{run_id}/events',adapter._handle_run_events)
    app.router.add_get('/v1/runs/{run_id}',adapter._handle_get_run)
    app.router.add_post('/v1/runs/{run_id}/stop',adapter._handle_stop_run)
    try:
        async with TestClient(TestServer(app),headers={'Authorization':'Bearer fixture-token'}) as client:
            yield client,db,seen,home
    finally:
        server.shutdown();server.server_close();thread.join(timeout=1);db.close()


async def run_case(client, *, sid='case-1', purpose='interactive', case='default', history=None):
    response=await client.post('/v1/runs',json={'input':'CASE:'+case,'session_id':sid,'output_delivery':{'purpose':purpose},'conversation_history':history or []})
    assert response.status==202
    rid=(await response.json())['run_id']
    stream=await client.get(f'/v1/runs/{rid}/events')
    wire=await stream.text()
    events=[json.loads(l[6:]) for l in wire.splitlines() if l.startswith('data: {')]
    return rid,events,wire

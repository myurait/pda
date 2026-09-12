"""Explicit opt-in live primary eligibility probe; never collected by pytest.
Five finite requests to the REAL configured primary model, real
AIAgent/API/SQLite and real editor. No implementation worker, no native goal.
Reads existing credential reference into memory; never copies/refreshes it.
"""
import argparse,asyncio,datetime,hashlib,json,logging,os,sqlite3,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--hermes-source',required=True);p.add_argument('--evidence',required=True);a=p.parse_args()
R=Path(a.evidence).resolve();plugin=Path(__file__).resolve().parents[1];source=Path(a.hermes_source).resolve()
root=Path('/home/user/.hermes')
c=sqlite3.connect('file:'+str(root/'state.db')+'?mode=ro',uri=True)
goal=json.loads(c.execute('SELECT value FROM state_meta WHERE key=?',('goal:20260911_115451_c2637e',)).fetchone()[0]);c.close()
assert goal['status']=='active' and goal['turns_used']<goal['max_turns']
import yaml
production=yaml.safe_load((root/'config.yaml').read_text());model=production['model']['default'];provider=production['model']['provider']
assert provider=='openai-codex' and model=='gpt-6-astra'
store=json.loads((root/'auth.json').read_text());token=store.get('providers',{}).get(provider,{}).get('tokens',{}).get('access_token')
assert isinstance(token,str) and token,'Existing primary credential reference unavailable; no login or refresh attempted'
del store
home=R/('real-primary-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S'));home.mkdir()
os.environ['HERMES_HOME']=str(home);os.environ['TERMINAL_CWD']=str(home)
sys.path[:0]=[str(source),str(plugin),str(Path(__file__).parent)]
config={'model':{'default':model,'provider':provider,'context_length':256000},'agent':{'max_turns':6},'compression':{'enabled':False},'memory':{'memory_enabled':False,'user_profile_enabled':False},'auxiliary':{'title_generation':{'enabled':False}},'display':{'compact':True},'terminal':{'cwd':str(home)},'platform_toolsets':{'api_server':['report_editor']},'plugins':{'enabled':['pda-report-editor'],'entries':{'pda-report-editor':{'settings':{'enabled':True,'timeout_seconds':15,'metrics_path':str(home/'metrics.jsonl'),'adapter':{'factory':'report_editor.adapters.claude_cli:ClaudeCliAdapter','model':'sonnet','auth_env':'CLAUDE_CODE_OAUTH_TOKEN'}}}}}}
(home/'config.yaml').write_text(yaml.safe_dump(config,allow_unicode=True));(home/'plugins').mkdir();(home/'plugins/pda-report-editor').symlink_to(plugin,target_is_directory=True)
logging.disable(logging.CRITICAL)
from aiohttp import web
from aiohttp.test_utils import TestClient,TestServer
from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter
from hermes_state import SessionDB
from hermes_cli.auth import DEFAULT_CODEX_BASE_URL
from run_agent import AIAgent
from report_editor.contracts import parse_request,validate_result
from technical_fixture import register_check
cases=[
 {'name':'report','purpose':'interactive','expected_editor':True,'prompt':'隔離環境の公開fixtureを public_fixture_check で実際に検証してください。途中で短い日本語の進捗本文を出してから処理し、最後に技術作業後の報告を返してください。結果はtoolの実測に基づけ、本番データが未検証であることも明記してください。架空の実装成功や新しい試験を捏造せず、確認範囲・推奨・実際に必要な判断を区別してください。'},
 {'name':'ordinary','purpose':'interactive','expected_editor':False,'prompt':'通常の短い会話です。こんにちは、とだけ返してください。'},
 {'name':'ordinary_disabled','purpose':'interactive','expected_editor':False,'editor_enabled':False,'prompt':'通常の短い会話です。こんにちは、とだけ返してください。'},
 {'name':'json','purpose':'interactive','expected_editor':False,'prompt':'成果物としてJSONだけ返してください。内容は {"ok":true,"count":3} です。説明・見出しは不要です。'},
 {'name':'urgent','purpose':'urgent','expected_editor':False,'prompt':'緊急の状況回答の試験です。新たな処理はせず「処理は停止中です。」だけをすぐ返してください。'}
]
async def main():
 db=SessionDB(home/'state.db');adapter=APIServerAdapter(PlatformConfig(enabled=True,extra={'key':'isolated-public-fixture-only'}));agents=[]
 register_check(home)
 def create(**kw):
  agent=AIAgent(model=model,provider=provider,api_mode='codex_responses',api_key=token,base_url=DEFAULT_CODEX_BASE_URL,session_id=kw['session_id'],session_db=db,enabled_toolsets=['report_editor'],platform='api_server',skip_context_files=True,skip_memory=True,skip_background_review=True,quiet_mode=True,max_iterations=6,reasoning_config={'effort':'max'},stream_delta_callback=kw.get('stream_delta_callback'),tool_progress_callback=kw.get('tool_progress_callback'))
  agents.append(agent);return agent
 adapter._create_agent=create
 app=web.Application();app.router.add_post('/v1/runs',adapter._handle_runs);app.router.add_get('/v1/runs/{run_id}/events',adapter._handle_run_events);app.router.add_post('/v1/runs/{run_id}/stop',adapter._handle_stop_run)
 results=[]
 try:
  async with TestClient(TestServer(app),headers={'Authorization':'Bearer isolated-public-fixture-only'}) as client:
   for case in cases:
    config['plugins']['entries']['pda-report-editor']['settings']['enabled']=case.get('editor_enabled',True)
    (home/'config.yaml').write_text(yaml.safe_dump(config,allow_unicode=True))
    start=time.monotonic();sid='real-primary-'+case['name'];resp=await client.post('/v1/runs',json={'input':case['prompt'],'session_id':sid,'output_delivery':{'purpose':case['purpose']}});assert resp.status==202
    rid=(await resp.json())['run_id'];resp=await client.get('/v1/runs/'+rid+'/events')
    try:wire=await asyncio.wait_for(resp.text(),145)
    except asyncio.TimeoutError:
     await client.post('/v1/runs/'+rid+'/stop');raise
    events=[json.loads(line[6:]) for line in wire.splitlines() if line.startswith('data: {')];done=[x for x in events if x.get('event')=='run.completed'];assert len(done)==1,(case['name'],[x.get('event') for x in events])
    rows=db.get_messages(sid);calls=[];exported=[]
    for row in rows:
     tool_calls=row.get('tool_calls') or []
     if isinstance(tool_calls,str):tool_calls=json.loads(tool_calls)
     for tc in tool_calls:
      f=tc.get('function',tc);name=f.get('name');args=f.get('arguments',{})
      if isinstance(args,str):args=json.loads(args)
      if name=='tool_call':name=args.get('name');args=args.get('arguments',{})
      calls.append(name)
      if name=='report_editor_prepare':exported.append(parse_request(args))
    metrics=[json.loads(x) for x in (home/'metrics.jsonl').read_text().splitlines()] if (home/'metrics.jsonl').exists() else []
    own=[x for x in metrics if x['invocation_id']==rid]
    work=None;progress=[]
    if case['expected_editor']:
     work=json.loads((home/'technical-work-result.json').read_text());assert work['passed']==work['checks']==12
     progress=[x for x in events if x.get('event') in ('message.delta','message.interim')]
     assert progress,'Real technical work must retain visible interim progress'
    assert len(own)==int(case['expected_editor']),(case['name'],calls,own)
    if case['expected_editor']:
     assert len(exported)==1 and own[0]['reason']=='edited' and own[0]['adapter_invocations']==1,(calls,own)
     assert validate_result(exported[0],{'text':done[0]['output'],'finish_reason':'stop'})==done[0]['output']
     assert not any(exported[0]['draft'] in (x.get('delta') or x.get('content') or '') for x in progress)
     assert rows[-1]['api_content']==exported[0]['draft']
    else:assert 'report_editor_prepare' not in calls
    if case['name']=='json':assert json.loads(done[0]['output'])=={'ok':True,'count':3}
    assert rows[-1]['content']==done[0]['output']
    delta_text=''.join(e.get('delta','') for e in events if e.get('event')=='message.delta')
    if case['name']=='ordinary_disabled':
     enabled=next(x for x in results if x['case']=='ordinary')
     assert done[0]['output']==enabled['output']
     assert bool(delta_text)==bool(enabled['streamed_text'])
    result={'case':case['name'],'streamed_text':delta_text,'event_types':dict(__import__('collections').Counter(e.get('event') for e in events)),'purpose':case['purpose'],'expected_editor':case['expected_editor'],'run_id':rid,'session_id':sid,'model':agents[-1].model,'provider':provider,'reasoning':'max','elapsed_seconds':time.monotonic()-start,'tool_names':calls,'exported_request':exported,'output':done[0]['output'],'metrics':own,'api_history_equal':True,'technical_work':work if case['expected_editor'] else None,'interim_events':progress if case['expected_editor'] else [],'passed':True}
    results.append(result);(home/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('exported_request','output')},ensure_ascii=False),flush=True)
 finally:
  adapter.interrupt_active_runs('finite real primary probe ended');db.close()
 assert len(results)==5
 result={'status':'passed','real_primary':True,'real_editor':True,'home':str(home),'primary_config_mutated':False,'credential_copied_or_refreshed':False,'editor_call_not_forced_by_prompt':True,'cases':results}
 (R/'real-primary-verified.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':'passed','cases':len(results),'evidence':str(R/'real-primary-verified.json')},ensure_ascii=False))
asyncio.run(main())

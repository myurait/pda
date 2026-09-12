import json
import os
import sys
import pytest
from harness import runtime,run_case,RAW,EDITED

@pytest.mark.asyncio
async def test_claude_adapter_uses_toolsless_single_turn_contract(tmp_path,monkeypatch):
    executable=tmp_path/'claude-fixture'
    executable.write_text('#!'+sys.executable+'\n'+'''import json,os,sys
args=sys.argv[1:]
assert args[args.index('--tools')+1]==''
assert args[args.index('--max-turns')+1]=='1'
assert '--no-session-persistence' in args and '--strict-mcp-config' in args
assert args[args.index('--setting-sources')+1]==''
assert os.environ.get('REPORT_EDITOR_TEST_SECRET') is None
request=json.loads(sys.stdin.read())
assert set(request)=={'purpose','report_type','verified_facts','failures_unmet_unknown','candidates_reasons','recommendations','decisions_required','protected','draft','export_class'}
text=''.join([request['purpose']]+request['verified_facts']+request['failures_unmet_unknown'])
print(json.dumps({'type':'system','subtype':'init','tools':[],'model':'claude-test'}))
print(json.dumps({'type':'result','subtype':'success','result':text,'is_error':False,'stop_reason':'end_turn','num_turns':1,'modelUsage':{'claude-test':{'inputTokens':10,'outputTokens':5}},'usage':{'input_tokens':10,'output_tokens':5},'total_cost_usd':0.01}))
''')
    executable.chmod(0o700)
    monkeypatch.setenv('CLAUDE_CODE_OAUTH_TOKEN','fixture-only')
    monkeypatch.setenv('REPORT_EDITOR_TEST_SECRET','must-not-inherit')
    settings={'enabled':True,'adapter':{'factory':'report_editor.adapters.claude_cli:ClaudeCliAdapter','executable':str(executable),'model':'claude-test','auth_env':'CLAUDE_CODE_OAUTH_TOKEN'}}
    async with runtime(tmp_path,monkeypatch,settings=settings) as (client,db,seen,home):
        _,events,wire=await run_case(client)
        assert [e['output'] for e in events if e.get('event')=='run.completed']==[EDITED],wire
        measurement=json.loads((home/'metrics.jsonl').read_text().splitlines()[0])
        assert measurement['usage']['total_cost_usd']==0.01


@pytest.mark.asyncio
async def test_prepared_report_is_edited_once_on_runs_and_history(tmp_path,monkeypatch):
    async with runtime(tmp_path,monkeypatch) as (client,db,seen,home):
        rid,events,wire=await run_case(client)
        done=[e for e in events if e.get('event')=='run.completed']
        assert len(done)==1,wire
        assert done[0]['output']==EDITED,wire
        assert not any(e.get('event') in {'message.delta','reasoning.available','message.interim'} for e in events),wire
        rows=db.get_messages('case-1')
        assert rows[-1]['content']==EDITED
        assert rows[-1]['api_content']==RAW
        # The primary's last answer is not a re-generation from editor output.
        assert all(EDITED != m.get('content') for call in seen for m in call['messages'])
        assert len(seen)==2

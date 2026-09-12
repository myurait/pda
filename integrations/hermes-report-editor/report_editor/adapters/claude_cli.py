"""Claude Code print adapter. No tools, hooks, persistence, or recursion.

Credential references and all vendor-specific protocol handling stay here.
The parent pipeline owns the process group and total wall-clock deadline.
"""
import json
import os
from pathlib import Path
import subprocess
import time

from ..contracts import EDITOR_SYSTEM as SYSTEM


class ClaudeCliAdapter:
    def __init__(self,config):self.config=config

    def edit(self,request,deadline):
        model=self.config['model']
        executable=self.config.get('executable','claude')
        auth_env=self.config.get('auth_env','CLAUDE_CODE_OAUTH_TOKEN')
        if auth_env not in {'CLAUDE_CODE_OAUTH_TOKEN','ANTHROPIC_API_KEY'}:raise ValueError('invalid_auth_reference')
        credential=os.environ.get(auth_env)
        if not credential:raise ValueError('authentication_missing')
        # Empty cwd/HOME provided by the outer worker; no global CLAUDE.md,
        # project settings, credential-bearing environment, or auth-file copy.
        env={k:os.environ[k] for k in ('PATH','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR') if k in os.environ}
        env.update(HOME=str(Path.cwd()),CLAUDE_CONFIG_DIR=str(Path.cwd()/'.claude'),
                   DISABLE_TELEMETRY='1',DISABLE_ERROR_REPORTING='1',
                   CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',MAX_THINKING_TOKENS='0')
        env[auth_env]=credential
        command=[executable,'-p','--model',model,'--effort','low','--max-turns','1',
                 '--tools','','--setting-sources','','--settings','{"disableAllHooks":true,"enabledPlugins":{}}',
                 '--disable-slash-commands','--strict-mcp-config','--mcp-config','{"mcpServers":{}}',
                 '--no-session-persistence','--no-chrome','--system-prompt',SYSTEM,
                 '--output-format','stream-json','--verbose']
        r=subprocess.run(command,input=json.dumps(request,ensure_ascii=False),text=True,
                         stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env,
                         timeout=max(0.001,deadline-time.monotonic()-0.25))
        if r.returncode or len(r.stdout)>131072:raise ValueError('cli_failure')
        events=[json.loads(line) for line in r.stdout.splitlines() if line.strip()]
        inits=[e for e in events if e.get('type')=='system' and e.get('subtype')=='init']
        results=[e for e in events if e.get('type')=='result']
        if len(inits)!=1 or inits[0].get('tools')!=[] or len(results)!=1:raise ValueError('protocol_violation')
        for e in events:
            if any(c.get('type')=='tool_use' for c in e.get('message',{}).get('content',[]) if isinstance(c,dict)):
                raise ValueError('tools_forbidden')
        result=results[0]
        effective=inits[0].get('model')
        if (result.get('subtype')!='success' or result.get('is_error') is not False
                or result.get('api_error_status') or result.get('num_turns')!=1
                or result.get('stop_reason')!='end_turn' or not effective
                or effective not in result.get('modelUsage',{})):
            raise ValueError('incomplete_result')
        usage={k:result.get('usage',{}).get(k) for k in ('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens')}
        usage.update(total_cost_usd=result.get('total_cost_usd'),effective_model=effective,
                     api_retry_events=sum(e.get('type')=='system' and e.get('subtype')=='api_retry' for e in events))
        return {'text':result['result'],'finish_reason':'stop','calls':1,'usage':usage}

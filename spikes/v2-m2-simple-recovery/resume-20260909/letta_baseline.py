"""Reproduce Letta baseline with complete native event observation."""
from observe import *
import sys
label=sys.argv[1] if len(sys.argv)>1 else 'letta-baseline-r2'
model=sys.argv[2] if len(sys.argv)>2 else 'ollama/qwen3.5:2b'
seconds=int(sys.argv[3]) if len(sys.argv)>3 else 90
body={'name':label,'model':model,'model_settings':{'max_tokens':128,'context_window_limit':8192,'reasoning':{'reasoning_effort':'none'}},'memory_blocks':[{'label':'persona','value':'Isolated local synthetic test. No delegation, schedules, cloud tools, or external actions.'},{'label':'m2_state','value':'Memory marker=M2-LETTA-SABLE. Pending job m2-pending is waiting; do not execute. Job m2-paused is paused by owner; never resume. Operation m2-uncertain has an unknown outcome; never retry blindly.'}]}
cmd={'type':'runtime_start','request_id':label+'-create','create_agent':{'body':body},'create_conversation':{'body':{}},'cwd':'/work','mode':'unrestricted'}
start=time.monotonic();events=[]
with ws() as c:
    created=exchange(c,cmd,'runtime_start_response',45)
    record(label+'-create',{'sent':cmd,**created})
    result=created['response'];assert result.get('success'),result
    runtime=result['runtime'];record(label+'-scope',runtime)
    inp={'type':'input','runtime':runtime,'payload':{'kind':'create_message','messages':[{'role':'user','content':'Use saved memory only. Do not use tools or execute jobs. Return one JSON object: memory_marker, pending_job, paused_job, unknown_operation, allowed_to_retry_unknown (boolean).','client_message_id':label+'-read'}]}}
    if len(sys.argv)>4:
        inp['payload']['client_tool_allowlist']=sys.argv[4].split(',') if sys.argv[4] else []
    c.send(json.dumps(inp));start=time.monotonic();terminal=False;error=None
    try:
        while time.monotonic()-start<seconds:
            try:
                m=json.loads(c.recv(timeout=min(5,max(0.1,seconds-(time.monotonic()-start)))))
            except TimeoutError:
                continue
            events.append(m)
            if m.get('delta',{}).get('message_type') not in ('reasoning_message','assistant_message'):
                print(json.dumps(m,ensure_ascii=False)[:300],flush=True)
            d=m.get('delta',{})
            if d.get('message_type')=='stop_reason' or d.get('type')=='stop_reason':
                terminal=True;break
    except Exception as e:error=repr(e)
    record(label,{'sent':inp,'events':events,'wall_s':time.monotonic()-start,'terminal_observed':terminal,'error':error})
    if not terminal:
        try:record(label+'-abort',exchange(c,{'type':'abort_message','request_id':label+'-abort','runtime':runtime},'abort_message_response',15))
        except Exception as e:record(label+'-abort-error',{'error':repr(e)})
print('OBSERVED',label,'terminal',terminal,'error',error,flush=True)

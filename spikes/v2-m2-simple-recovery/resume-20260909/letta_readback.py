"""Read persisted state through native Letta, with an explicit output schema."""
from observe import *
import sys,re
SCOPE=json.loads((E/'letta-baseline-r2-clean-4cpu-scope.json').read_text())
PROMPT='Read your saved memory. Return JSON: memory_marker (the saved marker string), pending_job (the saved waiting job ID), paused_job (the saved owner-paused job ID), unknown_operation (the saved uncertain operation ID), allowed_to_resume_paused (boolean), allowed_to_retry_unknown (boolean). IDs must be copied exactly from memory, not replaced with status or null. Do not use tools or execute any job.'
EXPECTED={'memory_marker':'M2-LETTA-SABLE','pending_job':'m2-pending','paused_job':'m2-paused','unknown_operation':'m2-uncertain','allowed_to_resume_paused':False,'allowed_to_retry_unknown':False}

def summarize(events):
    text='';stops=[];tools=[];usage=[]
    for m in events:
        d=m.get('delta',{});kind=d.get('message_type')
        if kind=='assistant_message':
            content=d.get('content',[])
            text+=content if isinstance(content,str) else ''.join(x.get('text','') for x in content if x.get('type')=='text')
        if kind=='stop_reason':stops.append(d.get('stop_reason'))
        if kind=='usage_statistics':usage.append(d)
        if kind in ('tool_call_message','tool_return_message','approval_request_message'):tools.append(d)
    return {'text':text,'stops':stops,'tools':tools,'usage':usage}

def turn(c,runtime,prompt,label,seconds=290,allowlist=None):
    command={'type':'input','runtime':runtime,'payload':{'kind':'create_message','client_tool_allowlist':allowlist if allowlist is not None else ['Read','Write','Bash'],'messages':[{'role':'user','content':prompt,'client_message_id':label}]}}
    c.send(json.dumps(command));start=time.monotonic();events=[];error=None
    try:
        while time.monotonic()-start<seconds:
            try:m=json.loads(c.recv(timeout=min(4,max(.1,seconds-(time.monotonic()-start)))))
            except TimeoutError:continue
            events.append(m)
            d=m.get('delta',{})
            if d.get('message_type')=='stop_reason' and d.get('stop_reason') not in ('requires_approval','tool_calls'):
                break
    except Exception as e:error=repr(e)
    result={'command':command,'wall_s':time.monotonic()-start,'error':error,'events':events,**summarize(events)}
    record(label,result)
    return result

def connect_runtime(c,label,conversation=None):
    cmd={'type':'runtime_start','request_id':label+'-start','agent_id':SCOPE['agent_id'],'cwd':'/work','mode':'unrestricted','skill_sources':[]}
    if conversation:cmd['conversation_id']=conversation
    else:cmd['create_conversation']={'body':{}}
    r=exchange(c,cmd,'runtime_start_response',30)
    record(label+'-start',r);assert r['response'].get('success'),r
    return r['response']['runtime']

def readback(label,deadline=290):
    with ws() as c:
        runtime=connect_runtime(c,label)
        r=turn(c,runtime,PROMPT,label,seconds=deadline,allowlist=[])
        try:
            text=r['text'].strip()
            fenced=re.findall(r'```json\s*(\{[\s\S]*?\})\s*```',text)
            data=json.loads(fenced[0] if len(fenced)==1 else text)
        except Exception:data=None
        verdict={'wall_s':r['wall_s'],'text':r['text'],'data':data,'expected':EXPECTED,'matches':data==EXPECTED,'terminal':r['stops'],'tools_called':len(r['tools']),'runtime':runtime}
        record(label+'-check',verdict)
        return verdict

if __name__=='__main__':
    label=sys.argv[1]
    if label=='letta-schema-baseline':
        with ws() as c:
            r=exchange(c,{'type':'agent_update','request_id':label+'-settings','agent_id':SCOPE['agent_id'],'body':{'model_settings':{'max_tokens':384,'context_window_limit':8192,'reasoning':{'reasoning_effort':'none'}}}},'agent_update_response')
            record(label+'-settings',r)
    print(json.dumps(readback(label),ensure_ascii=False,indent=2))

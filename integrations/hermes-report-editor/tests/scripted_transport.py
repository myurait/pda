"""Public synthetic primary-model transport for deterministic E2E scenarios."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import threading


def primary_transport(data,seen):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            self.send_response(404);self.end_headers()
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path!='/v1/chat/completions':
                self.send_response(404);self.end_headers();return
            seen.append(body)
            last_user=next(m['content'] for m in reversed(body['messages']) if m['role']=='user')
            report=data.get(last_user.removeprefix('CASE:'),next(iter(data.values())))
            last_user_index=max(i for i,m in enumerate(body['messages']) if m['role']=='user')
            tool_seen=any(m['role']=='tool' for m in body['messages'][last_user_index:])
            if not tool_seen and report.get('report_type') not in {'ordinary','raw'}:
                bridged=any(t.get('function',{}).get('name')=='tool_call' for t in body.get('tools',[]))
                name='tool_call' if bridged else 'report_editor_prepare'
                arguments={'name':'report_editor_prepare','arguments':report} if bridged else report
                delta={'role':'assistant','tool_calls':[{'index':0,'id':'prepare-1','type':'function','function':{'name':name,'arguments':json.dumps(arguments,ensure_ascii=False)}}]};reason='tool_calls'
            else:delta={'role':'assistant','content':report['draft']};reason='stop'
            progress=None
            if last_user=='CASE:technical':
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
            self.send_response(200);self.send_header('Content-Type','text/event-stream' if body.get('stream') else 'application/json');self.end_headers()
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
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    return server,thread,f'http://127.0.0.1:{server.server_port}/v1'

"""Provider-independent, fail-open output pipeline with a total process budget."""
from contextlib import ExitStack
import json
import math
import os
from pathlib import Path
import signal
import selectors
import subprocess
import sys
import tempfile
import time
from .contracts import validate_result

_USAGE_FIELDS = {
    'input_tokens','output_tokens','cache_read_input_tokens',
    'cache_creation_input_tokens','duration_ms','duration_api_ms',
    'total_cost_usd','api_retry_events',
}


def _measurements(candidate):
    """Accept only bounded numbers under known non-content field names."""
    calls=candidate.get('calls')
    calls=calls if type(calls) is int and 0<=calls<=1 else None
    raw=candidate.get('usage')
    usage=None
    if isinstance(raw,dict):
        usage={key:value for key,value in raw.items() if key in _USAGE_FIELDS
               and type(value) in (int,float) and 0<=value<=10**12 and math.isfinite(value)}
    return calls,usage


def _stop_process_group(proc,deadline):
    """Kill only this invocation's group, even if its leader already exited."""
    try:os.killpg(proc.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    if proc.poll() is None:
        proc.wait(timeout=max(0.01,deadline-time.monotonic()))


def edit(request,settings,cancelled):
    start=time.monotonic()
    limit=min(15.0,max(0.3,float(settings.get('timeout_seconds',15.0))))
    deadline=start+limit
    result={'text':request['draft'],'reason':'adapter_failure','adapter_invocations':0,'provider_calls':None,'usage':None}
    proc=None
    try:
        if cancelled():
            result.update(text='',reason='cancelled');return result
        payload=json.dumps({'request':request,'adapter':settings['adapter'],'deadline':deadline},ensure_ascii=False).encode()
        with tempfile.TemporaryDirectory(prefix='report-editor-') as cwd, ExitStack() as cleanup:
            proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name('worker.py'))],
                                  stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                  cwd=cwd,start_new_session=True)
            assert proc.stdin is not None and proc.stdout is not None
            # LIFO: terminate/reap before removing the worker's scratch directory.
            cleanup.callback(proc.stdout.close)
            cleanup.callback(proc.stdin.close)
            cleanup.callback(_stop_process_group,proc,deadline)
            result['adapter_invocations']=1
            selector=cleanup.enter_context(selectors.DefaultSelector())
            os.set_blocking(proc.stdin.fileno(),False)
            os.set_blocking(proc.stdout.fileno(),False)
            selector.register(proc.stdin,selectors.EVENT_WRITE,'input')
            selector.register(proc.stdout,selectors.EVENT_READ,'output')
            sent=0;out=bytearray();output_closed=False
            while True:
                if cancelled():result.update(text='',reason='cancelled');break
                remaining=deadline-time.monotonic()-0.2  # Reserve kill/reap/cleanup in this same budget.
                if remaining<=0:result['reason']='timeout';break
                for key,_ in selector.select(min(0.04,remaining)):
                    if key.data=='input':
                        try:sent+=os.write(proc.stdin.fileno(),memoryview(payload)[sent:])
                        except BlockingIOError:continue
                        if sent==len(payload):
                            selector.unregister(proc.stdin);proc.stdin.close()
                    else:
                        try:chunk=os.read(proc.stdout.fileno(),min(65536,131073-len(out)))
                        except BlockingIOError:continue
                        if chunk:out.extend(chunk)
                        else:
                            selector.unregister(proc.stdout);output_closed=True
                if cancelled():result.update(text='',reason='cancelled');break
                if time.monotonic()>=deadline-0.2:result['reason']='timeout';break
                if len(out)>131072:break
                if not output_closed or proc.poll() is None:continue
                if proc.returncode!=0:break
                response=json.loads(out)
                candidate=response.get('result')
                if isinstance(candidate,dict):
                    calls,usage=_measurements(candidate)
                    result.update(provider_calls=calls,usage=usage)
                result['text']=validate_result(request,candidate)
                result.update(reason='edited')
                break
    except ValueError as exc:
        # Only our fixed reason codes may leave the process; no arbitrary errors.
        result['text']=request['draft']
        reason=str(exc)
        result['reason']=reason if reason in {'output_schema','truncated','empty','output_format','missing_or_changed_anchor','changed_numbers','secret_output','unsupported_text','duplicate_sentence'} else 'output_schema'
    except Exception:
        result['text']=request['draft']
        result['reason']='adapter_failure'
    finally:
        result['elapsed_seconds']=round(time.monotonic()-start,6)
    return result


def record_metrics(settings,context,result):
    path=settings.get('metrics_path')
    if not path:return
    try:
        row={k:result.get(k) for k in ('reason','adapter_invocations','provider_calls','usage','elapsed_seconds')}
        row['invocation_id']=context.invocation_id
        with open(path,'a',encoding='utf-8') as stream:stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    except Exception:
        pass  # Observability cannot own chat availability.

"""Bounded synthetic API probe. No retry of a model request on failure."""
from pathlib import Path
import json, time, urllib.request, urllib.error, sys
from hermes_probe import ROOT, RUNTIME, record
BASE = 'http://127.0.0.1:19450'

def request(path, body=None, headers=None, timeout=10):
    values = dict(line.split('=', 1) for line in (RUNTIME/'hermes-env').read_text().splitlines() if '=' in line)
    h = {'Authorization':'Bearer '+values['API_SERVER_KEY'], 'Content-Type':'application/json'}
    h.update(headers or {})
    req = urllib.request.Request(BASE+path, data=None if body is None else json.dumps(body).encode(), headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {'http': r.status, 'body':json.loads(r.read())}
    except urllib.error.HTTPError as e:
        raw=e.read().decode()
        try: value=json.loads(raw)
        except ValueError: value=raw
        return {'http':e.code,'body':value}

def run(label, prompt, session=None, limit=180):
    payload = {'input':prompt}
    if session: payload['session_id']=session
    start=time.monotonic()
    created=request('/v1/runs',payload,{'Idempotency-Key':'m2proof-'+label})
    record(label+'-request',{'input':payload,'created':created})
    if created['http'] != 202: return created
    rid=created['body']['run_id']
    states=[]
    while time.monotonic()-start < limit:
        state=request('/v1/runs/'+rid)
        states.append({'elapsed_s':round(time.monotonic()-start,3),'state':state})
        if state['body'].get('status') in ('completed','failed','cancelled'):
            break
        time.sleep(1)
    result={'created':created,'last':states[-1] if states else None,'elapsed_s':round(time.monotonic()-start,3)}
    record(label,result)
    # Only final state is returned; raw final contents remain synthetic.
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':
    run(sys.argv[1],Path(sys.argv[2]).read_text(),sys.argv[3] if len(sys.argv)>3 else None)

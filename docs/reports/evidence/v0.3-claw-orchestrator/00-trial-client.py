import argparse
import datetime
import json
from pathlib import Path
import subprocess
import threading
import time
import urllib.request
import urllib.error

EVIDENCE = Path('/home/user/pda-v03a/docs/reports/evidence/v0.3-claw-orchestrator')
SCRATCH = '/home/user/v03/work/claw-orchestrator/scratch'
BASE = 'http://127.0.0.1:5123'
PROMPT = 'hello.py に、名前を引数で受け取って挨拶する関数を足し、README.md に使い方を 1 行書き足してください。何をしているかを短く書きながら進めてください。'
LOCK = threading.Lock()

def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')

def record(file, kind, data):
    with LOCK, (EVIDENCE / file).open('a') as f:
        f.write(f'{stamp()} {kind} {json.dumps(data, ensure_ascii=False)}\n')

def api(path, body=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=360) as r:
            return {'http': r.status, 'body': json.load(r)}
    except urllib.error.HTTPError as e:
        return {'http': e.code, 'body': json.loads(e.read())}

def output(args):
    return subprocess.check_output(args, text=True)

def pids():
    cgroup = output(['systemctl', '--user', 'show', 'v03-claw-orchestrator.service', '-p', 'ControlGroup', '--value']).strip()
    found = set()
    for file in (Path('/sys/fs/cgroup') / cgroup.lstrip('/')).rglob('cgroup.procs'):
        found.update(int(pid) for pid in file.read_text().split())
    return found

def snapshot(file, rss=False):
    ids = pids()
    columns = 'pid,ppid,etime,rss,args' if rss else 'pid,ppid,etime,args'
    full = output(['ps', '-eo', columns, '--forest'])
    rows = [line for line in full.splitlines()[1:] if line.strip() and int(line.split()[0]) in ids]
    with LOCK, (EVIDENCE / file).open('a') as f:
        f.write(stamp() + ' $ ps -eo ' + columns + ' --forest\n')
        f.write('Filtered to v03-claw-orchestrator.service cgroup PIDs.\n')
        f.write(full.splitlines()[0] + '\n' + '\n'.join(rows) + '\n')
        if rss:
            f.write('sum_RSS_KiB=' + str(sum(int(row.split()[3]) for row in rows)) + '\n')
    return ids

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=['claude', 'codex'])
    parser.add_argument('test', choices=['run', 'stop'])
    parser.add_argument('--attempt', type=int, default=1)
    args = parser.parse_args()
    number = {'claude': {'run': '02', 'stop': '03'}, 'codex': {'run': '04', 'stop': '05'}}[args.engine][args.test]
    file = f'{number}-{args.engine}-' + ('stream.txt' if args.test == 'run' else 'stop.txt')
    key = f't{number}-{args.engine}-a{args.attempt}'
    name = 'openai-' + key
    config = {'name': name, 'engine': args.engine, 'cwd': SCRATCH,
              'permissionMode': 'bypassPermissions', 'skipPersistence': True}
    record(file, 'START_REQUEST', config)
    started = api('/session/start', config)
    record(file, 'START_RESPONSE', started)
    if not started['body'].get('ok'):
        print(json.dumps(started, ensure_ascii=False), flush=True)
        return
    done = threading.Event()
    first_content = threading.Event()
    errors = []
    def reader():
        body = {'model': args.engine, 'messages': [{'role': 'user', 'content': PROMPT}], 'stream': True}
        record(file, 'SEND_REQUEST', {'path': '/v1/chat/completions', 'X-Session-Id': key, 'body': body})
        req = urllib.request.Request(BASE + '/v1/chat/completions', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json', 'X-Session-Id': key})
        try:
            with urllib.request.urlopen(req, timeout=330) as r:
                record(file, 'SEND_HTTP', {'status': r.status, 'content-type': r.headers.get('Content-Type')})
                for raw in r:
                    line = raw.decode().rstrip()
                    if not line:
                        continue
                    record(file, 'SSE', line)
                    if line.startswith('data: {'):
                        obj = json.loads(line[6:])
                        if obj.get('error'):
                            errors.append(obj['error'])
                        if any(c.get('delta', {}).get('content') for c in obj.get('choices', [])):
                            first_content.set()
        except Exception as e:
            errors.append(str(e))
            record(file, 'CLIENT_ERROR', str(e))
        finally:
            done.set()
    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    started_at = time.monotonic()
    captured = False
    stopped = False
    while not done.wait(0.1):
        elapsed = time.monotonic() - started_at
        if not captured and elapsed >= 2:
            snapshot(f'06-ps-{args.engine}.txt')
            if args.engine == 'claude' and args.test == 'run':
                snapshot('07-resources.txt', rss=True)
            captured = True
        if args.test == 'stop' and first_content.is_set():
            before = api('/session/status', {'name': name})
            record(file, 'STATUS_BEFORE_STOP', before)
            before_pids = pids()
            record(file, 'CGROUP_PIDS_BEFORE_STOP', sorted(before_pids))
            t = time.monotonic()
            record(file, 'STOP_REQUEST', {'path': '/session/stop', 'name': name})
            answer = api('/session/stop', {'name': name})
            duration = time.monotonic() - t
            record(file, 'STOP_RESPONSE', {'response': answer, 'elapsed_seconds': round(duration, 4)})
            record(file, 'STATUS_AFTER_STOP', api('/session/status', {'name': name}))
            record(file, 'CGROUP_PIDS_AFTER_STOP', sorted(pids()))
            record(file, 'PROCESSES_REMOVED', sorted(before_pids - pids()))
            main_pid = int(output(['systemctl', '--user', 'show', 'v03-claw-orchestrator.service', '-p', 'MainPID', '--value']))
            child_pids = before_pids - {main_pid}
            while child_pids & pids() and time.monotonic() - t < 10:
                time.sleep(0.05)
            record(file, 'PROCESS_EXIT_CHECK', {'remaining_child_pids': sorted(child_pids & pids()),
                                                'elapsed_seconds': round(time.monotonic() - t, 4)})
            stopped = True
            break
        if elapsed > 310:
            record(file, 'OBSERVATION_TIMEOUT', elapsed)
            record(file, 'CLEANUP_STOP', api('/session/stop', {'name': name}))
            break
    thread.join(timeout=10)
    record(file, 'OBSERVATION_SUMMARY', {'elapsed_seconds': round(time.monotonic()-started_at, 3),
                                       'first_content_received': first_content.is_set(),
                                       'stop_requested_during_run': stopped, 'stream_finished': done.is_set(), 'errors': errors})
    record(file, 'FINAL_STATUS', api('/session/status', {'name': name}))
    if args.test == 'run':
        diff = output(['git', '-C', SCRATCH, 'diff', '--', 'README.md', 'hello.py'])
        (EVIDENCE / f'{number}-{args.engine}-result.txt').write_text(stamp() + ' $ git diff -- README.md hello.py\n' + diff)
    if not stopped:
        record(file, 'CLEANUP_STOP', api('/session/stop', {'name': name}))
    print(json.dumps({'test': number, 'engine': args.engine, 'stream_content': first_content.is_set(),
                      'stopped': stopped, 'errors': errors}, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()

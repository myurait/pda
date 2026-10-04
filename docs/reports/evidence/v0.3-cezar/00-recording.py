import argparse
import datetime as dt
import json
import re
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

BASE = 'http://127.0.0.1:5103/api/v1/p/scratch'
EVIDENCE = Path('/home/user/pda-v03a/docs/reports/evidence/v0.3-cezar')
SCRATCH = Path('/home/user/v03/work/cezar/scratch')
PROMPT = 'hello.py に、名前を引数で受け取って挨拶する関数を足し、README.md に使い方を 1 行書き足してください。何をしているかを短く書きながら進めてください。'
TERMINAL = {'review', 'done', 'failed', 'cancelled'}

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds')

def clean(value):
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if re.fullmatch(r'(?:access_token|refresh_token|id_token|api_key|password|authorization|secret|credential)', k, re.I) else clean(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'\b(?:sk-(?:ant-)?[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,})\b', '[REDACTED]', value)
    return value

def encode(value):
    return json.dumps(clean(value), ensure_ascii=False)

def api(path, data=None):
    request = urllib.request.Request(BASE + path, data=json.dumps(data).encode() if data is not None else None,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)

def summary(run):
    keys = ('id', 'runner', 'status', 'steps', 'error', 'branch', 'worktree', 'worktreePath', 'createdAt', 'startedAt', 'finishedAt', 'dispatch', 'totalTokens', 'totalCostUsd', 'usage')
    return {k: run[k] for k in keys if k in run}

def processes():
    root = int(subprocess.check_output(['systemctl', '--user', 'show', 'v03-cezar.service', '-p', 'MainPID', '--value'], text=True))
    raw = subprocess.check_output(['ps', '-eo', 'pid,ppid,etime,args', '--forest', '-ww'], text=True)
    rows = {}
    for line in raw.splitlines()[1:]:
        pieces = line.split(None, 3)
        if len(pieces) == 4:
            rows[int(pieces[0])] = (int(pieces[1]), line)
    selected = {root}
    while True:
        descendants = {pid for pid, (ppid, _) in rows.items() if ppid in selected}
        if descendants <= selected:
            break
        selected |= descendants
    descendants = selected - {root}
    parent = rows.get(root, (0, ''))[0]
    if parent in rows:
        selected.add(parent)
    lines = [line for line in raw.splitlines()[1:] if line.strip() and int(line.split(None, 1)[0]) in selected]
    return root, descendants, raw.splitlines()[0] + '\n' + '\n'.join(lines) + '\n'

class Stream:
    def __init__(self, run_id, path):
        self.run_id, self.path = run_id, path
        self.output_started = threading.Event()
        self.last_run = None
        self.first_output = None
        self.error = None
        self.thread = threading.Thread(target=self.receive, daemon=True)
        self.thread.start()

    def receive(self):
        try:
            with urllib.request.urlopen(BASE + '/runs/' + self.run_id + '/events', timeout=30) as response, self.path.open('a', buffering=1) as out:
                out.write(stamp() + ' SSE connected HTTP ' + str(response.status) + '\n')
                event, data = '', []
                for line in response:
                    line = line.decode().rstrip('\r\n')
                    if line.startswith('event:'):
                        event = line[6:].strip()
                    elif line.startswith('data:'):
                        data.append(line[5:].lstrip())
                    elif not line:
                        if data and any(data):
                            payload = json.loads('\n'.join(data))
                            if event == 'run':
                                self.last_run = payload
                                payload = summary(payload)
                            out.write(stamp() + ' event=' + event + ' data=' + encode(payload) + '\n')
                            kind = payload.get('type', '') if isinstance(payload, dict) else ''
                            if kind in ('text', 'tool-call', 'item.delta'):
                                if not self.first_output:
                                    self.first_output = {'receivedAt': stamp(), 'event': event, 'data': clean(payload)}
                                self.output_started.set()
                        event, data = '', []
        except Exception as error:
            self.error = str(error)
            with self.path.open('a') as out:
                out.write(stamp() + ' STREAM_ERROR ' + str(error) + '\n')

def capture(runner, label):
    root, descendants, raw = processes()
    if not descendants:
        return False
    (EVIDENCE / ('06-ps-' + runner + '.txt')).write_text(stamp() + '\n$ ps -eo pid,ppid,etime,args --forest -ww\ncezar の親と子孫だけを抽出。他サービスは省略。\n' + clean(raw))
    if runner == 'claude':
        ids = ','.join(str(v) for v in sorted(descendants | {root}))
        rss = subprocess.check_output(['ps', '-p', ids, '-o', 'pid,ppid,rss,etime,comm'], text=True)
        (EVIDENCE / '07-resources.txt').write_text(stamp() + '\n' + label + ' 実行中。RSS の単位は KiB。\n$ ps -p ' + ids + ' -o pid,ppid,rss,etime,comm\n' + rss)
    return True

def result(run, prefix):
    # Cezar commits at turn end. Compare the task branch with the unchanged initial main.
    branches = subprocess.check_output(['git', '-C', str(SCRATCH), 'worktree', 'list', '--porcelain'], text=True)
    path = run.get('worktreePath') or run.get('worktree')
    if not isinstance(path, str):
        path = None
    if not path or not Path(path).is_dir():
        branch = run.get('branch') or 'cez/' + run['id'][:8]
        path = str(SCRATCH)
        for block in branches.strip().split('\n\n'):
            if 'branch refs/heads/' + branch in block:
                path = block.splitlines()[0][len('worktree '):]
                break
    diff = subprocess.run(['git', '-C', path, 'diff', 'main'], text=True, capture_output=True)
    local = subprocess.run(['git', '-C', path, 'status', '--short'], text=True, capture_output=True)
    main_diff = subprocess.check_output(['git', '-C', str(SCRATCH), 'diff'], text=True)
    output = stamp() + '\nRun: ' + encode(summary(run)) + '\n$ git -C ' + path + ' diff main\n' + diff.stdout + diff.stderr
    output += '\n$ git -C ' + path + ' status --short\n' + local.stdout
    output += '\n$ git -C ' + str(SCRATCH) + ' diff\n' + main_diff + '\n(製品が分けた task worktree の差分は上記。)\n'
    (EVIDENCE / (prefix + '-result.txt')).write_text(clean(output))

def trial(prefix, runner, stop=False):
    body = {'workflow': 'quick-task', 'task': PROMPT, 'runner': runner, 'autonomous': True, 'worktree': True}
    stream_path = EVIDENCE / (prefix + ('-stop.txt' if stop else '-stream.txt'))
    stream_path.write_text(stamp() + ' POST ' + BASE + '/runs\nrequest=' + encode(body) + '\n')
    run = api('/runs', body)
    with stream_path.open('a') as out:
        out.write(stamp() + ' response=' + encode(run) + '\n')
    print(encode({'prefix': prefix, 'runId': run['id'], 'startedAt': stamp()}), flush=True)
    stream = Stream(run['id'], stream_path)
    start = time.monotonic()
    captured = False
    stop_at = None
    stop_children = set()
    state = None
    while time.monotonic() - start < 360:
        if not captured and not stop and stream.output_started.is_set():
            captured = capture(runner, prefix)
        if stop and stream.output_started.is_set() and stop_at is None:
            _, stop_children, before = processes()
            with stream_path.open('a') as out:
                out.write(stamp() + ' first_output=' + encode(stream.first_output) + '\nBefore stop:\n' + clean(before))
                stop_at = time.monotonic()
                out.write(stamp() + ' POST /runs/' + run['id'] + '/cancel\n')
                response = api('/runs/' + run['id'] + '/cancel', {})
                out.write(stamp() + ' response=' + encode(response) + '\n')
        current = api('/runs/' + run['id'])
        if current['status'] != state:
            state = current['status']
            print(encode({'prefix': prefix, 'status': state, 'elapsed': round(time.monotonic() - start, 3)}), flush=True)
        if current['status'] in TERMINAL:
            if stop:
                elapsed_state = round(time.monotonic() - stop_at, 3) if stop_at else None
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and any(Path('/proc/' + str(p)).exists() for p in stop_children):
                    time.sleep(.05)
                alive = [p for p in stop_children if Path('/proc/' + str(p)).exists()]
                elapsed_exit = round(time.monotonic() - stop_at, 3) if stop_at else None
                with stream_path.open('a') as out:
                    out.write(stamp() + ' stop_observation=' + encode({'status': current['status'], 'secondsToStatus': elapsed_state, 'secondsUntilProcessCheck': elapsed_exit, 'childPidsAtStop': sorted(stop_children), 'childPidsStillPresent': alive, 'firstOutput': stream.first_output}) + '\n')
            else:
                result(current, prefix)
            with stream_path.open('a') as out:
                out.write(stamp() + ' final=' + encode(summary(current)) + '\n')
            print(encode({'prefix': prefix, 'final': summary(current), 'streamError': stream.error}), flush=True)
            return
        time.sleep(.1 if stop else .4)
    with stream_path.open('a') as out:
        out.write(stamp() + ' observation_timeout=360s; cancel=' + encode(api('/runs/' + run['id'] + '/cancel', {})) + '\n')
    print('TIMEOUT ' + prefix, flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('prefix')
    parser.add_argument('runner', choices=['claude', 'codex'])
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    trial(args.prefix, args.runner, args.stop)

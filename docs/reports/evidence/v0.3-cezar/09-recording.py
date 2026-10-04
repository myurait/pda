import sys
import time
from pathlib import Path
from trial import api, stamp, encode, Stream, EVIDENCE, PROMPT, TERMINAL, summary, result

parent_runner, child_runner = sys.argv[1:3]
prefix = '09-' + parent_runner + '-to-' + child_runner
path = EVIDENCE / (prefix + '-parent-stream.txt')
task = f'''cezar の製品内 dispatch による引き継ぎの試用です。あなたは {parent_runner}、依頼先は {child_runner} です。
次の依頼全文を、cezar の組み込みコマンド node "$CEZ_BIN" task create を使い、--runner {child_runner} --retry-limit 0 を付けて、子タスク1つにそのまま渡してください。モデルは指定しないでください。
依頼全文: {PROMPT}
ファイルの実装は子タスクに任せ、あなた自身は hello.py と README.md を編集しないでください。子を作ったら CEZ:MONITORING で待ち、子の報告が戻ったら、その結果と差分を確認して短く報告して終了してください。親への merge や push は不要です。別の skill、MCP、ネイティブ subagent で代用しないでください。作業は指定された scratch とその製品 worktree のみで行い、認証のファイルや /home/user/pda、/home/user/pda-v03a、/home/user/pda.git は読み書きしないでください。'''
body = {'workflow': 'quick-task', 'task': task, 'runner': parent_runner, 'autonomous': True, 'worktree': True,
        'dispatch': {'maxSubtasks': 1, 'inFlight': 1, 'runner': child_runner}}
path.write_text(stamp() + ' POST /runs request=' + encode(body) + '\n')
run = api('/runs', body)
with path.open('a') as out:
    out.write(stamp() + ' response=' + encode(run) + '\n')
streams = {run['id']: Stream(run['id'], path)}
states = {}
children = []
start = time.monotonic()
print(encode({'prefix': prefix, 'parent': run['id']}), flush=True)
while time.monotonic() - start < 360:
    runs = api('/runs')
    tree = [r for r in runs if r['id'] == run['id'] or r.get('dispatch', {}).get('rootRunId') == run['id']]
    for r in tree:
        if r['id'] not in streams:
            child_path = EVIDENCE / (prefix + '-child-' + r['id'][:8] + '-stream.txt')
            child_path.write_text(stamp() + ' observed dispatch child=' + encode(summary(r)) + '\n')
            streams[r['id']] = Stream(r['id'], child_path)
            children.append(r['id'])
        if r['status'] != states.get(r['id']):
            states[r['id']] = r['status']
            print(encode({'prefix': prefix, 'id': r['id'], 'runner': r.get('runner'), 'status': r['status'], 'elapsed': round(time.monotonic() - start, 3)}), flush=True)
    if tree and all(r['status'] in TERMINAL for r in tree):
        with (EVIDENCE / '09-handoff.txt').open('a') as out:
            out.write('\n' + stamp() + ' direction=' + parent_runner + ' -> ' + child_runner + '\n')
            out.write('parent-request=' + encode(body) + '\n')
            out.write('tree=' + encode([summary(r) for r in tree]) + '\n')
            for r in tree:
                stream = streams[r['id']]
                out.write('observation=' + encode({'id': r['id'], 'stream': stream.path.name, 'firstOutput': stream.first_output, 'streamError': stream.error}) + '\n')
                if r['id'] in children:
                    result(r, prefix + '-child-' + r['id'][:8])
        break
    time.sleep(.25)
else:
    with (EVIDENCE / '09-handoff.txt').open('a') as out:
        out.write(stamp() + ' direction=' + parent_runner + ' -> ' + child_runner + ' observation_timeout=360s\n')
        for r in tree:
            if r['status'] not in TERMINAL:
                out.write('cancel=' + encode({'id': r['id'], 'response': api('/runs/' + r['id'] + '/cancel', {})}) + '\n')
print(encode({'prefix': prefix, 'states': states, 'children': children}), flush=True)

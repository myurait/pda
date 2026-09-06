"""Disposable DBOS 2.31.0 durability boundary probe. No LLM or remote calls.

Two cases within one question: does restart skip completed steps, and can
an external side effect before the step checkpoint duplicate?
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def worker(root, case, phase):
    from dbos import DBOS, SetWorkflowID
    root = Path(root).resolve()
    os.chdir(root)
    DBOS(config={
        'name': 'pda-probe',
        'application_version': 'probe-v1',
        'executor_id': 'probe-local',
        'system_database_url': 'sqlite:///' + str(root / 'system.sqlite'),
        'run_admin_server': False,
        'enable_otlp': False,
        'log_level': 'ERROR',
        'max_executor_threads': 2,
    })

    @DBOS.step()
    def completed_step():
        with (root / 'completed-events.txt').open('a') as f:
            f.write('completed-step-executed\n')
            f.flush(); os.fsync(f.fileno())
        return 'saved-result'

    @DBOS.step()
    def interrupted_step():
        if case == 'duplicate-window':
            with (root / 'external-effects.txt').open('a') as f:
                f.write('external-effect-without-idempotency\n')
                f.flush(); os.fsync(f.fileno())
        # The parent kills this process only after the completed step committed.
        if phase == 'start':
            (root / 'kill-ready').write_text('ready')
            time.sleep(30)
        return 'finished'

    @DBOS.workflow()
    def flow():
        first = completed_step()
        second = interrupted_step()
        return {'first': first, 'second': second}

    DBOS.launch()
    try:
        if phase == 'start':
            with SetWorkflowID('synthetic-flow'):
                flow()
        else:
            # Launch recovery, do not invoke the workflow again as a new task.
            result = DBOS.retrieve_workflow('synthetic-flow').get_result()
            print(json.dumps({'recovered': result}), flush=True)
    finally:
        DBOS.destroy()


def harness():
    import importlib.metadata
    from tempfile import mkdtemp
    base = Path(__file__).resolve().parent
    runs = []
    for case in ['completed-checkpoint', 'duplicate-window']:
        root = Path(mkdtemp(prefix=case+'-', dir=base))
        command = [sys.executable, str(Path(__file__).resolve()), '--worker', str(root), '--case', case]
        env = {k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['API_KEY','TOKEN','SECRET','PASSWORD','CONDUCTOR','DBOS_','OTEL_'])}
        with (root / 'start.log').open('w') as log:
            proc = subprocess.Popen(command + ['--phase', 'start'], stdout=log, stderr=log, env=env)
            deadline = time.monotonic() + 12
            while not (root/'kill-ready').exists():
                if proc.poll() is not None:
                    raise RuntimeError('worker exited before crash marker; see '+str(root/'start.log'))
                if time.monotonic() > deadline:
                    proc.kill(); proc.wait()
                    raise TimeoutError('no crash marker')
                time.sleep(0.05)
            proc.kill()
            killed_code = proc.wait(timeout=5)
        began = time.monotonic()
        p = subprocess.run(command + ['--phase', 'recover'], capture_output=True, text=True, timeout=15, env=env)
        (root/'recover.log').write_text(p.stdout+p.stderr)
        p.check_returncode()
        completed = len((root/'completed-events.txt').read_text().splitlines())
        effects = len((root/'external-effects.txt').read_text().splitlines()) if (root/'external-effects.txt').exists() else 0
        assert completed == 1, (case, completed)
        if case == 'duplicate-window':
            assert effects == 2, effects
        assert 'saved-result' in p.stdout and 'finished' in p.stdout, p.stdout
        runs.append({'case':case,'process_exit':killed_code,'recovery_elapsed_seconds':round(time.monotonic()-began,3),'completed_step_count':completed,'non_idempotent_external_effect_count':effects,'output':p.stdout.strip(),'path':str(root),'verdict':'passed'})
    result={'package':'dbos','version':importlib.metadata.version('dbos'),'database':'SQLite local','restart_owner':'test harness starts a fresh process; DBOS does not restart a dead process','cases':runs,'limitations':['synthetic local data only','no paid/model calls','not a PDA integration test','not HA, disk loss, rollback, stop-token or approval verification','one trial per case; elapsed time is not an SLO']}
    (base/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--worker')
    p.add_argument('--case')
    p.add_argument('--phase')
    a=p.parse_args()
    if a.worker:
        worker(a.worker,a.case,a.phase)
    else:
        harness()

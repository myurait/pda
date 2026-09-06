# Disposable DBOS durability probe — PARTIAL

Question: Given a completed step and a second step interrupted by SIGKILL, does a fresh process resume from persisted progress, and can a side effect before its checkpoint duplicate?

## Actual run

Observed 2026-09-06, Python 3.11.15, DBOS 2.31.0, local SQLite. `requirements.txt` records the installed environment. `probe.py` is copied byte-for-byte from the exercised script; SHA-256 `71c41368743e2643558a090fc1646c95717d150d3390d3664edd9e5307db4ee4`.

| Case | Completed-step append count | Non-idempotent interrupted-step append count | Resume wall time | Result |
|---|---:|---:|---:|---|
| completed-checkpoint | 1 | 0 | 2.416 seconds | saved-result / finished |
| duplicate-window | 1 | 2 | 3.402 seconds | saved-result / finished |

The parent test harness killed each worker (`process_exit=-9`) and launched a fresh recovery process. `DBOS.launch()` plus retrieval of the same persisted workflow ID recovered the recorded workflow; no new workflow was submitted as the original task. The in-flight second step is re-executed. In the duplicate-window case it repeats a file append that intentionally has no idempotency key.

`result.json` is the observed output with only local run-directory paths replaced by relative paths. Each case directory preserves `start.log`, `recover.log`, and actual append files. No production state or real user data is included.

## Verdict

PARTIAL: skipping a completed step after a process kill was demonstrated. Preventing duplication of a non-transactional external effect was not provided by persistence alone; the negative case successfully reproduced duplication. A test marked `passed` means its expected observation occurred, not that the workflow provides exactly-once external effects.

The restart owner is the test harness. This is not proof of autonomous process resurrection, host failover, a correct watchdog, a PDA integration, or independent rollback. Each case ran once; these timings are not an SLO or benchmark. No real HTTP effect, model call, paid API, approval, stop epoch, stale digest, split brain, disk loss, or UI was tested. The probe disables DBOS admin serving and OTLP; a network-syscall audit was not performed. Package installation required normal package-registry access.

An initial setup run failed before the workflow because the application name had 31 characters while DBOS allows at most 30. The library validator reproduced this rejection; shortening only the name to `pda-probe` made setup pass. The successful results above are from the subsequent actual run, not fabricated replacement output.

## Reproduce in a disposable directory

Do not run this from production or inside a real workflow database. Copy this folder to a new temporary directory before running because the script writes synthetic case directories and a new `result.json` beside itself.

```sh
PROBE_DIR=$(mktemp -d /tmp/dbos-durability-probe.XXXXXX)
cp probe.py requirements.txt "$PROBE_DIR/"
uv venv "$PROBE_DIR/.venv"
uv pip install --python "$PROBE_DIR/.venv/bin/python" -r "$PROBE_DIR/requirements.txt"
"$PROBE_DIR/.venv/bin/python" "$PROBE_DIR/probe.py"
```

Expected assertions: `completed_step_count == 1` in both cases; `non_idempotent_external_effect_count == 2` in `duplicate-window`; both recovery outputs include `saved-result` and `finished`. All child processes exit or are killed by the harness. The code is disposable research evidence, not a production component or approval to adopt DBOS.

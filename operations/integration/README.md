# Contained execution of worker-authored code (auto-integration gate §6)

`contained_runner.py` is the separate principal design §6 requires wherever the
auto-integration pipeline executes worker-authored code (gates G2, G3, G7, and
future probes). The integration executor holds push capability; if worker code
ran as that principal, a card could reach `origin/main` without passing the gate
bundle. The runner therefore executes that code with no push capability, no
agent-node sync capability, no reachable Kanban or approval ledger, no secret
environment and no network egress, and returns the structured triple G2 judges
on: exit code, collected count, executed count.

Design source: `docs/design/auto-integration-gate.md` §5 (G2 judgement inputs)
and §6 (containment and resource contract).

## What the containment consists of

- `--network=none` — no egress, and no loopback into host services.
- `--read-only` root filesystem, `--cap-drop=ALL`, `--security-opt=no-new-privileges`,
  `--user=<uid>:<gid>`, `--pids-limit`, `--ipc=private`. Never root: an unset or
  zero uid/gid is refused, so the container cannot fall back to root by omission.
- Read-only bind mounts only: the one caller-named worktree plus the fixed
  runtime mounts. Each is mounted from its *resolved* source, so a symlink
  cannot redirect a mount after validation.
- One writable surface: `--tmpfs /tmp` with `nosuid,nodev,noexec`, discarded on
  exit. `HOME` and `TMPDIR` both point inside it. Nothing the contained run does
  reaches host storage.
- A fixed environment allowlist. The host environment is never inherited; caller
  additions are validated by name (denied: `HERMES_*`, `AWS_*`, `GITHUB_*`,
  `GH_*`, `ANTHROPIC_*`, `OPENAI_*`, `CLAUDE_*`, `DOCKER_*`, `SSH_*`, `GOOGLE_*`,
  and any name containing `TOKEN`, `SECRET`, `PASSWORD`, `CREDENTIAL`, `COOKIE`,
  `API_KEY`, `PRIVATE`, `OAUTH`, `SESSION`).
- An enumerated deny-set (`default_secret_paths`). A mount is refused when it
  equals a denied path, sits inside one, or *contains* one. The third case is the
  operative one: it refuses a mount of `/home/user/.hermes` — which holds
  `auth.json`, `.env`, and the Kanban DB carrying the `pda_owner_approvals`
  ledger — while still allowing `/home/user/.hermes/hermes-agent`. A bounded
  secret-shaped-file sweep runs as defence in depth for secrets not on the
  enumeration.
- The deny-set's base is configuration (`secret_home`, `--secret-home`,
  `/home/user` on agent-node), not `$HOME`. It names the account whose secrets
  must stay unreachable, which under design §6 is a *different* account from the
  one running the containment; an unset base is refused rather than defaulted.
  The invoking user's real home, read from the passwd database rather than the
  environment, is denied as well.
- Mount sources must be directories. A single control-plane file cannot be
  mounted on its own, which is the case the bounded sweep structurally could not
  see.
- A digest-pinned image. A tag is refused, and the runner never pulls: the
  digest must already be present locally, so the contained run needs no registry
  capability at all.

Every failure is fail-closed. A refused containment yields no argv, and a run
that cannot establish its preconditions returns `infra_error`, never a pass.

## Judgement output

`run()` returns a `ContainedResult`; the CLI prints it as JSON. `verdict` is one
of:

- `pass` — exit code 0, collected > 0, executed > 0, zero failures and errors.
- `fail` — pytest exit code 1 (tests failed).
- `infra_error` — anything else: pytest exit codes 2–5 (interrupted, internal
  error, usage error, nothing collected), an OOM kill (137), a missing or
  unparseable junit report, a missing `collected N items` line, zero executed
  tests, an exit code that disagrees with the junit report, a junit total above
  the collected count, more than one junit report block, conflicting
  `collected N items` lines, a run over the timeout, an absent or unusable
  docker, an absent pinned image, a static-check finding, or available memory
  below the floor.

There is deliberately no fallback from the junit total to the collected count:
G2 names both because they come from different stages, and a collection that
never reported its size is exactly the infrastructure fault the rule watches
for.

CLI exit codes are distinct per verdict so a caller reading only the code can
tell a test failure from a containment failure: `0` pass, `1` fail, `2` refused
(the containment would not assemble), `3` infra_error.

### What the judgement output does and does not establish

All three values are produced by pytest, and pytest is the worker's own process.
A `conftest.py` is executed during collection, so worker-authored code can write
a self-consistent junit report and exit 0, and the host has no independent
observer inside the container to contradict it. **A `pass` verdict is therefore
not proof that the tests passed; it is proof that nothing detectable
contradicted the claim that they did.**

What the runner does is make forgery detectable rather than silent:

- The report markers and the report path carry a per-run token, so the exact
  bytes that delimit the trusted report are not known ahead of the run.
- A second marker pair anywhere in the output is an `infra_error`, not a value
  to choose between. The parse previously took the *first* occurrence while the
  genuine report was printed *last*, so a clean block printed during collection
  simply won.
- The junit total is reconciled against the collected count.

Closing the residual requires a report surface the payload's process cannot
write — `docker cp` from a non-`--rm` container, or one rw report mount — and so
requires trading away the zero-host-write-surface property. That is an owner
decision and is not taken here; until it is taken, a `pass` from this runner is
one input to G2 and not by itself an integration warrant.

## Input validation (fail-closed)

- Exactly one caller-named mount: the worktree. Runtime mounts are fixed
  configuration, not caller-derived.
- Paths are symlink-resolved and normalised; a worktree or target that resolves
  onto a denied path is refused, as is a target resolving outside the worktree.
- A worktree whose `.git` is a *gitfile* is refused (see Known limitations).
- A runtime mount overlapping the worktree is refused, so which side of the
  trust boundary a file is on is never ambiguous.
- The interpreter must live inside a runtime mount, or it would not exist in the
  container.
- Pytest arguments that would re-open the collection surface, redirect the
  report, or suppress a required judgement input are refused: `-p`, `--plugins`,
  `-c`, `--config-file`, `--rootdir`, `--confcutdir`, `-o`, `--override-ini`,
  `--junit-xml`, `--junitxml`, `--basetemp`, `--pdb`, `--import-mode`, `-q`,
  `--quiet`, and anything containing a `..` segment. `-o python_files=...` is on
  the list because it would rewrite the collection rules after the static check
  inspected the surface; `-q` because it suppresses the `collected N items` line
  that G2 requires and that has no fallback.
  Matching covers the forms pytest's own parser accepts, not just the exact
  spelling: a short option with its value attached (`-pmyplugin`,
  `-opython_files=*.py`), a cluster containing one of the reserved letters
  (`-qq`), and argparse's unique-prefix abbreviations (`--overr=addopts=...`
  reaches `--override-ini`). Matching reserved *letters* over-refuses a cluster
  that merely contains one — `-rfc` for report characters is the realistic case
  — which is the intended direction: such a run is refused with the argument
  named, rather than silently widening the containment.
- `collection_static_check` inspects the collection surface before anything
  runs: a symlink leaving the worktree, and any `conftest.py` / `pytest.ini` /
  `tox.ini` / `setup.cfg` / `pyproject.toml` inside a collection root that is
  either untracked or differs from `baseline_ref` (`--baseline-ref`,
  `origin/main` in the gate). Both halves are needed: a card is submitted as
  commits, so checking untracked files alone would examine nothing in the
  ordinary case, and a tracked `pyproject.toml` can reintroduce every reserved
  argument through `[tool.pytest.ini_options] addopts`. An unresolvable baseline
  ref is a finding, not a skip.
- There is no way to skip the static check. The check runs on every `run()`.

## Resource contract

Per design §6, against agent-node's measured 12 GiB and its 2026-08-22 OOM:
`--memory` with `--memory-swap` set equal to it (no swap — the OOM took the host
unresponsive for tens of minutes by swapping before killing anything),
`--cpus`, `--cpu-shares=512` as the nice equivalent, a `MemAvailable` floor that
defers the run rather than starting it, a wall-clock timeout, and an `flock`
serial lock so contained runs never overlap on one host. The lock is on by
default (`$TMPDIR/pda-contained-runner.lock`); `--lock-path` only relocates it.

## Pinned image

    python@sha256:35d3a4a3d5e42e02ab916d44513a050689f12c0533d45598d229672503fe77ca

That is `python:3.11-bookworm` as resolved on agent-node on 2026-08-29. The full
bookworm image rather than `-slim` because the scope-gate suite drives `git` in
subprocesses and only the full image ships it; installing it at run time is
impossible under `--network=none`.

Pre-pull is a host-side step, outside any contained run:

    docker pull python@sha256:35d3a4a3d5e42e02ab916d44513a050689f12c0533d45598d229672503fe77ca
    python3 operations/integration/contained_runner.py --worktree <worktree> --check-image

## agent-node runtime mounts

Measured 2026-08-29. The hermes venv is an *editable* install
(`__editable__.hermes_agent-0.20.2.pth`), so the checkout that contains it is
part of the interpreter, not an optional extra: without it the suite's
runtime-integration test fails with `No module named 'agent'`. Mounting the
checkout rather than its parent `~/.hermes` is what keeps `auth.json`, `.env` and
`kanban.db` out of the container.

- `/home/user/.hermes/hermes-agent` (contains `venv/`; the interpreter is
  `venv/bin/python`, CPython 3.11.15)
- `/home/user/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu`
- `/home/user/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu` — the
  unversioned path `pyvenv.cfg` names. It is a host symlink; it is mounted from
  the resolved versioned directory onto this declared target, which realises the
  link inside the container without handing the container a link to follow.

Docker on agent-node runs rootless-for-the-user via the `docker` group (uid 1000
is a member); no `sudo` is involved and none is available. `bwrap` is not
installed, which is why the namespace isolation §6 asks for is delivered through
docker.

## Host-dependent verification procedure

These are the parts the unit tests cannot cover. Run them on the host that will
execute G2, after staging the module there. Every container is `--rm`; nothing
is written to host storage and nothing is left resident.

    # (a) the scope-gate suite passes inside the containment
    python3 operations/integration/contained_runner.py \
      --worktree ~/projects/pda \
      --target integrations/hermes-scope-gate/tests

    # (a2) collection-only mode reports the same collection size
    python3 operations/integration/contained_runner.py \
      --worktree ~/projects/pda \
      --target integrations/hermes-scope-gate/tests --mode collect

    # (b) the containment's denials, asserted from inside it
    python3 operations/integration/contained_runner.py \
      --worktree ~/projects/pda \
      --target operations/integration/probe/containment_probe.py \
      --env PDA_PROBE_WORKTREE=/home/user/projects/pda --pytest-arg=-s

    # fail-closed spot checks (no container starts; --print-argv only assembles)
    python3 operations/integration/contained_runner.py --worktree ~/projects/pda \
      --target integrations/hermes-scope-gate/tests \
      --runtime-mount /home/user/.hermes --print-argv
    python3 operations/integration/contained_runner.py --worktree ~/projects/pda \
      --target /etc --print-argv
    python3 operations/integration/contained_runner.py --worktree ~/projects/pda \
      --target integrations/hermes-scope-gate/tests --image python:3.11-bookworm --print-argv
    # the deny-set no longer follows $HOME: this must refuse whatever $HOME is
    HOME=/tmp/nowhere python3 operations/integration/contained_runner.py \
      --worktree ~/projects/pda --target integrations/hermes-scope-gate/tests \
      --runtime-mount /home/user/.hermes/kanban.db --print-argv
    # attached short-option forms are refused, not only the `-o=` spelling
    python3 operations/integration/contained_runner.py --worktree ~/projects/pda \
      --target integrations/hermes-scope-gate/tests \
      --pytest-arg=-opython_files=*.py --print-argv

`probe/containment_probe.py` is intentionally not named `test_*`: pytest collects
a file named explicitly on the command line whatever it is called, so the probe
stays runnable while never being swept into a directory-wide collection on a
host where its assertions cannot hold.

## Measurements, agent-node, 2026-08-29 (HEAD d92efbb)

These runs predate the fixes recorded in
`docs/status/restricted-containment-review-2026-08-29.md`. The containment
properties they measured (egress denied, secrets absent, privileges dropped, the
worktree read-only) are unaffected by those fixes, which changed judgement
parsing, the deny-set base, argument matching and the static check. (a) and (b)
should be re-run on agent-node before G2 is wired, together with the two new
refusal checks below.

(a) `integrations/hermes-scope-gate/tests` through the runner:

    verdict pass, exit_code 0, collected 707, executed 707,
    failures 0, errors 0, skipped 0, duration 9.918s

(a2) collection-only: `verdict pass, collected 707, executed 0, duration 0.623s`.

(b) `containment_probe.py` through the runner: `verdict pass, collected 21,
executed 21, failures 0, errors 0`. The values it measured:

- `~/.hermes/auth.json`, `~/.hermes/.env`, `~/.hermes/kanban.db`,
  `~/.hermes/state.db`, `~/.hermes/config.yaml`, `~/.ssh`, `~/.claude.json` —
  all `exists=False`.
- `listdir('/home/user/.hermes') == ['hermes-agent']`; the checkout's 102 entries
  contain no `.env`.
- HTTPS egress: `URLError: [Errno -3] Temporary failure in name resolution`.
- DNS: `gaierror: [Errno -3] Temporary failure in name resolution`.
- TCP to `1.1.1.1:443`, and to the host's own `192.168.0.59:8642` (Hermes API)
  and `192.168.0.59:9119` (dashboard): all `errno 101 Network is unreachable`.
- Interfaces present: `['lo']` only.
- Writing into the mounted worktree: `errno 30 Read-only file system`. Writing to
  `/` : `errno 30`. Writing under `TMPDIR` (`/tmp/pda-contained-tmp`): succeeds.
- Container environment names: `GIT_AUTHOR_EMAIL`, `GIT_AUTHOR_NAME`,
  `GIT_COMMITTER_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_CONFIG_NOSYSTEM`,
  `GIT_TERMINAL_PROMPT`, `GPG_KEY`, `HOME`, `HOSTNAME`, `LANG`, `LC_ALL`, `PATH`,
  `PWD`, `PYTEST_CURRENT_TEST`, `PYTEST_VERSION`, `PYTHONDONTWRITEBYTECODE`,
  `PYTHONUNBUFFERED`, `PYTHON_SHA256`, `PYTHON_VERSION`, `TMPDIR` — nothing
  secret-bearing (`GPG_KEY`, `PYTHON_SHA256` are the base image's own build
  metadata).
- `/var/run/docker.sock` absent. `uid=1000`, `CapPrm=0`, `CapEff=0`,
  `NoNewPrivs=1`.

Fail-closed spot checks all refused with reasons: `--runtime-mount /home/user/.hermes`
was refused for containing ten enumerated denied paths, and the secondary sweep
additionally named `~/.hermes/.env.bak.20260720_130148` and
`~/.hermes/state-snapshots/20260817-160144-pre-update/{auth.json,.env}` — secrets
outside the enumeration, which is what the sweep is there for. `--target /etc`
and `--image python:3.11-bookworm` were refused for target escape and for an
unpinned image; `--pytest-arg=-o=python_files=*.py` was refused as a
containment-reserved argument.

## Known limitations

- **Gitfile worktrees are refused, not supported.** A worktree created by
  `git worktree add` carries `.git` as a file pointing at a gitdir under the
  parent repository, outside the single mount. Git inside the container would
  then operate against a missing gitdir and every git-driven test would fail for
  a containment reason rather than a code reason, so the runner refuses up front.
  The extension is a second read-only mount of that gitdir; it is not
  implemented, and until it is, the isolated worktrees the improvement lane
  assigns cannot be run through this containment. This must be closed before G2
  is wired to the lane.
- **The secret sweep is bounded** (depth 2, `.git` / `node_modules` /
  `__pycache__` skipped, 4000 directories). The guarantee is the enumeration in
  `default_secret_paths`; the sweep is defence in depth, not a second guarantee.
- **Judgement is parsed from pytest's own output** (the `collected N items` line
  and the junit report carried out through the tmpfs on stdout), because no
  host-writable path is offered to the container. A pytest release that changed
  either would surface as `infra_error`, not as a silent misread. The larger
  consequence is that a `pass` verdict is a claim by the code under test, not an
  independent measurement of it — see "What the judgement output does and does
  not establish". Making it independent requires a trusted report surface and
  therefore an owner decision about the zero-host-write-surface property; it is
  open.
- **`--collect-only` reports collection only.** Static inspection of the
  collection *graph* (imports reached during collection) is not implemented.
- **Docker is the isolation mechanism**, so membership of the `docker` group is
  the trust boundary on the host side. The runner's own principal must not be
  reachable from worker-authored code — that separation is the caller's
  responsibility, not this module's.

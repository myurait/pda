"""Containment wrapper for executing worker-authored code (design §6, gate G2).

The integration executor holds push capability. If worker-authored code ran as
the same principal, a card could reach ``origin/main`` from outside the gate
bundle -- ``integrations/hermes-scope-gate/scope_gate.py`` records that process
side effects of permitted commands are outside its first layer, and the
2026-08-22 adversarial record fixes the same gap. Design §6 therefore requires
that every point where G2/G3/G7 execute worker-authored code runs as a separate
principal with no push capability, no agent-node sync capability, no
Kanban/approval-ledger connection and no secret environment, with egress denied
by default.

This module is that principal. It is a wrapper, not a policy: it assembles one
``docker run`` invocation and refuses to assemble anything that would widen the
containment. Every refusal is fail-closed -- a violation returns no argv at all
rather than a degraded one.

What the containment is made of (each item is load-bearing):

* ``--network=none``     -- no egress, no loopback to host services.
* ``--read-only``        -- container root filesystem is immutable.
* ro bind mounts         -- the one caller-named worktree plus the fixed
                            runtime mounts, each mounted from its *resolved*
                            source so a symlink cannot redirect the mount.
* ``--tmpfs /tmp``       -- the only writable surface, discarded on exit
                            (``nosuid,nodev,noexec``).
* explicit env allowlist -- the base environment is fixed in this module and
                            caller-supplied names are validated; the host
                            environment is never inherited.
* deny-set               -- the secret and control-plane paths of §6 are
                            enumerated under a *configured* base home, and a
                            mount is refused when it equals, sits inside, or
                            *contains* any of them. The third case is the one
                            that matters: it is what refuses a mount of
                            ``/home/user/.hermes`` (which holds ``auth.json``,
                            ``.env`` and the Kanban DB carrying the
                            ``pda_owner_approvals`` ledger) while still allowing
                            ``/home/user/.hermes/hermes-agent``. The base is
                            never ``$HOME``: see ``default_secret_paths``.
                            Mount sources are directories, so a single
                            control-plane file cannot be mounted on its own.
* digest-pinned image    -- a tag is refused; the image must be present locally
                            (this module never pulls, so the run itself needs no
                            registry capability).

The judgement output is the structured triple design §5 G2 requires as input:
process exit code plus collected count *and* executed count, so that a
collection error, an OOM kill or a missing dependency is distinguishable from
"zero failures" and reported as an infrastructure fault rather than a pass.

The limit of that output is stated here rather than left to be discovered: all
three values are produced by pytest, and pytest is the worker's own process. A
``conftest.py`` that writes a self-consistent junit report and then calls
``os._exit(0)`` reports a clean run, and no amount of parsing on the host can
contradict it, because the host has no independent observer inside the
container. What this module does is make forgery *detectable* rather than
silent: the report markers and the report path carry a per-run token that is
not a compile-time constant, a second marker pair anywhere in the output is an
infrastructure fault rather than a value to choose between, and the collected
count is reconciled against the junit totals. Closing the residual needs a
trusted report surface outside the payload's process (``docker cp`` from a
non-``--rm`` container, or one rw report mount) and therefore an explicit
decision against the zero-host-write-surface property; it is not closed here.

Stdlib only, on purpose: the containment must be assemblable by any host that
can run the gate, including hosts whose interpreter is not the hermes venv.
"""
from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

# --------------------------------------------------------------------------
# Pinned execution image
# --------------------------------------------------------------------------

# python:3.11-bookworm, resolved on agent-node 2026-08-29. The *full* bookworm
# image rather than -slim because the scope-gate suite drives ``git`` in
# subprocesses (334 references across its tests) and only the full image ships
# it; installing it at run time is impossible under ``--network=none`` and would
# defeat the pin. The digest -- not the tag -- is the contract: a tag is
# mutable, and a mutable execution base is an unpinned dependency of every
# integration decision.
DEFAULT_IMAGE = (
    "python@sha256:"
    "35d3a4a3d5e42e02ab916d44513a050689f12c0533d45598d229672503fe77ca"
)

_IMAGE_RE = re.compile(r"^[a-z0-9]+(?:[._/-][a-z0-9]+)*@sha256:[0-9a-f]{64}$")

# --------------------------------------------------------------------------
# agent-node measured facts (2026-08-29)
# --------------------------------------------------------------------------

# The venv is an *editable* install of hermes-agent
# (``__editable__.hermes_agent-0.20.2.pth``), so the checkout that contains it
# is part of the interpreter, not an optional extra: without it the suite's
# runtime-integration test fails with ``No module named 'agent'``. Mounting the
# checkout (not its parent ``~/.hermes``) is what keeps ``auth.json``, ``.env``
# and ``kanban.db`` out of the container.
AGENT_NODE_HERMES_CHECKOUT = Path("/home/user/.hermes/hermes-agent")
AGENT_NODE_INTERPRETER = AGENT_NODE_HERMES_CHECKOUT / "venv/bin/python"

# The venv's interpreter is a uv-managed CPython outside the checkout, and
# ``pyvenv.cfg`` names it through the *unversioned* symlink path. Both paths are
# declared: each is mounted from its resolved source onto its declared target,
# which is how the symlink is realised inside the container without giving the
# container a symlink it could follow elsewhere.
AGENT_NODE_UV_PYTHON = Path(
    "/home/user/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu"
)
AGENT_NODE_UV_PYTHON_ALIAS = Path(
    "/home/user/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu"
)

# --------------------------------------------------------------------------
# Deny-set: secrets and control plane (design §6)
# --------------------------------------------------------------------------


def default_secret_paths(home: Path | str) -> tuple[Path, ...]:
    """Paths the containment must never expose, enumerated rather than guessed.

    ``kanban.db`` covers the approval ledger: ``pda_owner_approvals`` is a table
    in the Kanban control DB (``operations/improvement/install.py``), not a
    separate file, so denying the DB denies the ledger.

    ``home`` is required. It used to default to ``Path.home()``, which made the
    enumeration -- the part of the containment that is a guarantee rather than a
    heuristic -- follow ``$HOME``. Design §6 runs the contained execution as a
    *separate principal*, whose ``$HOME`` is not the home holding the secrets
    being denied, and ``$HOME`` is settable by whoever invokes the runner. Under
    either condition the enumeration silently stopped covering anything: no
    denial was emitted, so the drift was invisible. The base is now configured
    (``ContainmentConfig.secret_home``) and unset is refused.
    """
    base = Path(home)
    names = (
        # Hermes credentials and control plane.
        ".hermes/auth.json",
        ".hermes/auth.lock",
        ".hermes/.env",
        ".hermes/config.yaml",
        ".hermes/kanban.db",
        ".hermes/state.db",
        ".hermes/sessions",
        ".hermes/logs",
        ".hermes/cron",
        ".hermes/hooks",
        # Host credentials.
        ".ssh",
        ".aws",
        ".gnupg",
        ".netrc",
        ".git-credentials",
        ".config/gh",
        ".config/gcloud",
        ".docker/config.json",
        # Claude Code credentials (account separation, C-series discipline).
        ".claude.json",
        ".claude/.credentials.json",
    )
    return tuple(base / name for name in names)


def invoking_user_home() -> Path | None:
    """The real home of the invoking uid, from the passwd database.

    Read through ``pwd`` rather than ``$HOME`` on purpose: this is the one home
    an environment variable cannot move. It is unioned into the deny-set so a
    misconfigured ``secret_home`` cannot expose the invoking user's own
    credentials, and it is not a substitute for ``secret_home`` -- on a host
    where the contained principal differs from the secret-holding account, the
    two are different directories and both must be denied.
    """
    try:
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError, OSError):
        return None


# Secondary, heuristic sweep for secrets not on the enumeration above. Bounded
# on purpose: the enumeration is the guarantee, this is defence in depth.
#
# Deliberately *not* extended with ``config.yaml``/``kanban.db``/``state.db``:
# this sweep walks two levels into every mount source, the worktree included, so
# a name that legitimately occurs in a repository would refuse the containment
# rather than a secret. The control-plane files those names denote are covered
# where they actually live -- by the enumeration above, and by the refusal of
# non-directory mount sources in ``validate``, which is what stops a single
# control-plane file from being mounted on its own.
_SECRET_BASENAMES = frozenset(
    {
        ".env",
        ".netrc",
        ".git-credentials",
        "auth.json",
        "credentials.json",
        "credentials",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "id_dsa",
    }
)
_SECRET_SUFFIXES = (".pem", ".p12", ".pfx")
# ``.env.example``/``.env.sample``/``.env.template`` are published templates,
# not secrets; hermes-agent ships ``.env.example``.
_ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")
_SCAN_SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__", ".mypy_cache"})
_SCAN_MAX_DEPTH = 2
_SCAN_MAX_DIRS = 4000

# --------------------------------------------------------------------------
# Environment allowlist
# --------------------------------------------------------------------------

_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_ENV_DENY_SUBSTRINGS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "CREDENTIAL",
    "COOKIE",
    "APIKEY",
    "API_KEY",
    "PRIVATE",
    "OAUTH",
    "SESSION",
)
# ``HERMES_*`` is denied wholesale: the repository conftest records that an
# ambient ``HERMES_KANBAN_DB`` outranks every in-test isolation and leaked
# twelve cards into the production board (t_4a78c98b). ``HERMES_HOME`` is set
# by the tests themselves, inside the container, which is where it belongs.
_ENV_DENY_PREFIXES = (
    "HERMES_",
    "AWS_",
    "GITHUB_",
    "GH_",
    "ANTHROPIC_",
    "OPENAI_",
    "CLAUDE_",
    "DOCKER_",
    "SSH_",
    "GOOGLE_",
)
_RESERVED_ENV_NAMES = frozenset({"HOME", "PATH", "TMPDIR", "PYTHONPATH"})

_CONTAINER_HOME = "/tmp/pda-contained-home"
_CONTAINER_TMPDIR = "/tmp/pda-contained-tmp"


def new_report_token() -> str:
    """A per-run token for the junit report markers and report path.

    The markers used to be module constants, which meant the exact bytes that
    delimit the trusted report were known to the code being judged. Combined
    with the report being printed *after* pytest and the parse taking the first
    occurrence, a payload could print a clean block before pytest ran and win.
    The token is not a secret -- the container can read it from ``/proc`` -- so
    it is not the thing that makes forgery hard; it is what makes a blind
    forgery impossible and, with the duplicate-marker refusal in
    ``_extract_junit``, an adaptive one detectable.
    """
    import secrets

    return secrets.token_hex(16)


def junit_markers(token: str) -> tuple[str, str]:
    return (
        f"<<<PDA-CONTAINED-JUNIT-BEGIN:{token}>>>",
        f"<<<PDA-CONTAINED-JUNIT-END:{token}>>>",
    )


def junit_path(token: str) -> str:
    return f"/tmp/pda-contained-junit-{token}.xml"


# Argument forms that would let the caller re-open the collection surface the
# static check just closed, or overwrite the runner's own report path.
#
# Short options are matched by *letter*, not by string prefix. pytest's parser
# accepts a short option with its value attached (``-pmyplugin``,
# ``-opython_files=*.py``), and the previous exact/``=``-suffix match let every
# attached form through -- which reinstated exactly the collection rewrite and
# plugin loading this list exists to refuse. Matching the letter over-refuses a
# cluster that merely contains one of them (``-rfc`` for report characters is
# the realistic case); that is the intended direction for a containment, and
# such a run is refused with the argument named rather than silently widened.
_DENIED_SHORT_LETTERS = frozenset({"p", "o", "c", "q"})

# Long options are matched including argparse's unique-prefix abbreviations:
# ``--overr=python_files=*.py`` reaches ``--override-ini`` just as well as the
# full spelling does.
_DENIED_LONG_OPTIONS = (
    "--plugins",
    "--config-file",
    "--rootdir",
    "--confcutdir",
    # ``-o python_files=...`` / ``-o addopts=...`` rewrites the collection rules
    # after the static check has inspected the surface, which would make that
    # check a statement about a different collection than the one that runs.
    "--override-ini",
    "--junit-xml",
    "--junitxml",
    "--basetemp",
    "--pdb",
    "--import-mode",
    # ``-q`` suppresses the ``collected N items`` line, and that line is a
    # required G2 judgement input with no fallback. Allowing it would turn every
    # such run into an infrastructure fault.
    "--quiet",
)

# Files whose untracked presence would change what pytest collects.
_COLLECTION_CONFIG_NAMES = frozenset(
    {
        "conftest.py",
        "pytest.ini",
        ".pytest.ini",
        "tox.ini",
        "setup.cfg",
        "pyproject.toml",
    }
)


class ContainmentError(RuntimeError):
    """Raised when the containment cannot be assembled as specified."""

    def __init__(self, violations: Sequence[str]) -> None:
        self.violations = list(violations)
        super().__init__("; ".join(self.violations) or "containment refused")


# --------------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------------


def _resolve(path: Path | str) -> Path:
    """Realise symlinks and normalise, without requiring existence."""
    return Path(path).expanduser().resolve()


def host_subprocess_env() -> dict[str, str]:
    """The environment for every host-side subprocess this module starts.

    One helper for all three call sites (``docker image inspect``, ``git
    status``, ``docker run``) because they have to agree. They did not: the run
    was started with a scrubbed environment while the digest check and the
    tracked-file check inherited the host's, so an ambient ``DOCKER_HOST``
    pointed the "is the pinned image present" question at one daemon and the run
    at another, and an ambient ``GIT_DIR``/``GIT_WORK_TREE`` answered the
    collection-surface question about a different tree than the one mounted.
    """
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}


def _host_run(argv: Sequence[str]) -> subprocess.CompletedProcess[str] | str:
    """Run a host-side helper; return the failure reason instead of raising.

    A missing executable is the case that used to leave the CLI with a bare
    traceback and exit code 1 -- indistinguishable from ``verdict: fail``.
    """
    try:
        return subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            check=False,
            env=host_subprocess_env(),
        )
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        return f"cannot execute {argv[0]!r}: {exc}"


def _is_within(child: Path, parent: Path) -> bool:
    if child == parent:
        return True
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _shallow_secret_hits(root: Path) -> list[Path]:
    """Bounded sweep for secret-looking files under ``root``."""
    hits: list[Path] = []
    visited = 0
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        visited += 1
        if visited > _SCAN_MAX_DIRS:
            break
        try:
            entries = list(os.scandir(current))
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if is_dir:
                if depth < _SCAN_MAX_DEPTH and name not in _SCAN_SKIP_DIRS:
                    stack.append((Path(entry.path), depth + 1))
                continue
            lowered = name.lower()
            if lowered in _SECRET_BASENAMES:
                hits.append(Path(entry.path))
            elif lowered.startswith(".env.") and not lowered.endswith(
                _ENV_TEMPLATE_SUFFIXES
            ):
                hits.append(Path(entry.path))
            elif lowered.endswith(_SECRET_SUFFIXES):
                hits.append(Path(entry.path))
    return hits


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


# ``--volume`` is a ``:``-separated triple and the option list itself is
# comma-separated, so a path carrying either character changes the field count
# of the argument rather than being a path in it.
_MOUNT_FORBIDDEN_CHARS = (":", ",", "\n", "\x00")


@dataclass(frozen=True)
class Mount:
    """One read-only bind mount: resolved source onto declared target."""

    source: Path
    target: Path

    def as_arg(self) -> str:
        return f"{self.source}:{self.target}:ro"

    def field_violations(self) -> list[str]:
        out: list[str] = []
        for label, path in (("source", self.source), ("target", self.target)):
            for char in _MOUNT_FORBIDDEN_CHARS:
                if char in str(path):
                    out.append(
                        f"mount {label} contains {char!r}, which is a "
                        f"--volume field separator: {path}"
                    )
        return out


@dataclass(frozen=True)
class ContainmentConfig:
    """Everything the wrapper is allowed to do, stated up front.

    ``worktree`` is the single caller-named mount. ``runtime_mounts`` are the
    fixed interpreter mounts and are not caller-derived: the design allows the
    contained run to see an interpreter, not to choose its own filesystem.
    """

    worktree: Path
    interpreter: Path
    runtime_mounts: tuple[Path, ...]
    # The base for the enumerated deny-set. Required: see
    # ``default_secret_paths``. ``None`` is refused by ``validate`` rather than
    # falling back to ``$HOME``.
    secret_home: Path | None = None
    # The ref the collection surface is judged against -- the integration
    # baseline, ``origin/main`` in the gate. Required for the same reason:
    # "part of the Git canon" is meaningless without naming the canon.
    baseline_ref: str | None = None
    image: str = DEFAULT_IMAGE
    docker: str = "docker"
    uid: int | None = None
    gid: int | None = None
    memory: str = "4g"
    cpus: str = "2"
    cpu_shares: int = 512
    pids_limit: int = 512
    tmpfs_size: str = "2g"
    timeout_s: int = 1800
    min_free_mem_mb: int = 2048
    # Design §6 states contained runs are always serial on one host, so the lock
    # is on by default; ``None`` is reachable only as an explicit override.
    lock_path: Path | None = field(
        default_factory=lambda: Path(tempfile.gettempdir()) / "pda-contained-runner.lock"
    )
    extra_env: Mapping[str, str] = field(default_factory=dict)
    # *Additional* denied paths. Additive on purpose: this used to be
    # ``secret_paths``, which replaced the enumeration outright, so passing an
    # empty tuple left the deny-set empty and every mount allowed. A caller can
    # widen the deny-set, never narrow it.
    extra_secret_paths: tuple[Path, ...] = ()
    hostname: str = "pda-contained"

    @classmethod
    def for_agent_node(cls, worktree: Path | str, **overrides: Any) -> "ContainmentConfig":
        """Config for agent-node, from the paths measured there on 2026-08-29."""
        params: dict[str, Any] = {
            "worktree": Path(worktree),
            "interpreter": AGENT_NODE_INTERPRETER,
            "runtime_mounts": (
                AGENT_NODE_HERMES_CHECKOUT,
                AGENT_NODE_UV_PYTHON,
                AGENT_NODE_UV_PYTHON_ALIAS,
            ),
            # The literal home the secrets live in, not the runner's ``$HOME``.
            "secret_home": Path("/home/user"),
            "baseline_ref": "origin/main",
            "uid": os.getuid(),
            "gid": os.getgid(),
        }
        params.update(overrides)
        return cls(**params)

    def effective_secret_paths(self) -> tuple[Path, ...]:
        """The enumerated deny-set: configured base, real home, caller additions."""
        bases: list[Path] = []
        if self.secret_home is not None:
            bases.append(Path(self.secret_home))
        real = invoking_user_home()
        if real is not None:
            bases.append(real)
        paths: list[Path] = []
        for base in bases:
            paths.extend(default_secret_paths(base))
        paths.extend(Path(p) for p in self.extra_secret_paths)
        seen: dict[Path, None] = {}
        for path in paths:
            seen.setdefault(_resolve(path), None)
        return tuple(seen)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def _validate_env(extra_env: Mapping[str, str]) -> list[str]:
    violations: list[str] = []
    for name, value in extra_env.items():
        if not _ENV_NAME_RE.match(name):
            violations.append(f"env name is not an allowlist-shaped name: {name!r}")
            continue
        if name in _RESERVED_ENV_NAMES:
            violations.append(f"env name is reserved by the containment: {name}")
            continue
        if any(name.startswith(prefix) for prefix in _ENV_DENY_PREFIXES):
            violations.append(f"env name is on a denied prefix: {name}")
            continue
        if any(token in name for token in _ENV_DENY_SUBSTRINGS):
            violations.append(f"env name looks secret-bearing: {name}")
            continue
        if not isinstance(value, str) or "\n" in value or "\x00" in value:
            violations.append(f"env value for {name} is not a single-line string")
    return violations


def _denied_argument_reason(arg: str) -> str | None:
    """Why this pytest argument is reserved, or ``None`` if it is allowed."""
    if arg == "--":
        return None
    if arg.startswith("--"):
        name = arg.split("=", 1)[0]
        if len(name) <= 2:
            return None
        for option in _DENIED_LONG_OPTIONS:
            # ``option.startswith(name)`` covers argparse's unique-prefix
            # abbreviations; the equality case is the full spelling.
            if option == name or option.startswith(name):
                return f"reserved by the containment (matches {option}): {arg}"
        return None
    if arg.startswith("-") and len(arg) > 1:
        cluster = arg[1:].split("=", 1)[0]
        hits = sorted(set(cluster) & _DENIED_SHORT_LETTERS)
        if hits:
            letters = ", ".join(f"-{h}" for h in hits)
            return f"reserved by the containment (short option {letters}): {arg}"
    return None


def _validate_extra_args(extra_args: Sequence[str]) -> list[str]:
    violations: list[str] = []
    for arg in extra_args:
        if not isinstance(arg, str) or "\x00" in arg:
            violations.append(f"argument is not a plain string: {arg!r}")
            continue
        if ".." in Path(arg).parts:
            violations.append(f"argument contains a parent traversal: {arg}")
            continue
        reason = _denied_argument_reason(arg)
        if reason is not None:
            violations.append(f"argument is {reason}")
    return violations


def validate(
    config: ContainmentConfig,
    targets: Sequence[str] = (),
    extra_args: Sequence[str] = (),
) -> list[str]:
    """Return every reason the containment must be refused (empty = allowed)."""
    violations: list[str] = []

    # The deny-set's base is checked before the deny-set is used: an unset base
    # is what silently emptied the enumeration, so it is a refusal, not a
    # default.
    if config.secret_home is None:
        violations.append(
            "secret_home is unset; the deny-set enumeration has no base and "
            "would cover nothing (set it to the literal home holding the "
            "secrets, e.g. /home/user on agent-node)"
        )
    elif not Path(config.secret_home).is_absolute():
        violations.append(f"secret_home must be an absolute path: {config.secret_home}")

    if config.baseline_ref is None:
        violations.append(
            "baseline_ref is unset; the collection surface cannot be checked "
            "against the Git canon without naming it (e.g. origin/main)"
        )

    # Design §6 and the README both state the contained run is never root.
    if config.uid is None or config.gid is None:
        violations.append(
            "uid and gid must both be set; without --user the container runs as "
            f"root (uid={config.uid}, gid={config.gid})"
        )
    elif config.uid == 0 or config.gid == 0:
        violations.append(
            f"contained runs must not be root (uid={config.uid}, gid={config.gid})"
        )

    secrets = config.effective_secret_paths()

    if not _IMAGE_RE.match(config.image):
        violations.append(
            "execution image must be pinned by digest "
            f"(repo@sha256:<64 hex>), got {config.image!r}"
        )

    worktree_raw = Path(config.worktree)
    if not worktree_raw.is_absolute() and not str(worktree_raw).startswith("~"):
        violations.append(f"worktree must be an absolute path: {worktree_raw}")
    worktree = _resolve(worktree_raw)
    if not worktree.is_dir():
        violations.append(f"worktree is not an existing directory: {worktree}")

    # A worker worktree created by ``git worktree add`` carries ``.git`` as a
    # *file* pointing at a gitdir outside the mount. Git inside the container
    # would then operate against a missing gitdir, and every git-driven test
    # would fail for a containment reason rather than a code reason. Refuse
    # instead of half-working; the ro gitdir mount is the documented extension.
    dot_git = worktree / ".git"
    if dot_git.exists() and not dot_git.is_dir():
        violations.append(
            f"worktree {worktree} uses a gitfile ({dot_git}); the containment "
            "mounts one directory and cannot reach an external gitdir"
        )

    # Mount targets must keep the declared spelling for the interpreter alias
    # so ``pyvenv.cfg`` resolves; source is always the realised path.
    mounts: list[Mount] = [Mount(source=worktree, target=worktree)]
    for raw in config.runtime_mounts:
        target = Path(raw).expanduser()
        if not target.is_absolute():
            violations.append(f"runtime mount must be absolute: {raw}")
            continue
        source = _resolve(raw)
        if not source.exists():
            violations.append(f"runtime mount does not exist: {raw}")
            continue
        # A runtime mount is an interpreter tree. Mounting a single *file*
        # bypasses the bounded secret sweep entirely -- that sweep scandirs its
        # argument and a file raises, yielding zero findings -- so one
        # control-plane file could ride in on a name the enumeration happened
        # not to list. Directories only, structurally.
        if not source.is_dir():
            violations.append(
                f"runtime mount is not a directory: {raw} (the containment "
                "mounts interpreter trees, not individual files)"
            )
            continue
        mounts.append(Mount(source=source, target=target))

    for mount in mounts:
        violations.extend(mount.field_violations())
        for secret in secrets:
            if mount.source == secret:
                violations.append(f"mount {mount.source} is a denied path: {secret}")
            elif _is_within(mount.source, secret):
                violations.append(
                    f"mount {mount.source} is inside denied path {secret}"
                )
            elif _is_within(secret, mount.source):
                violations.append(
                    f"mount {mount.source} contains denied path {secret}"
                )
        if mount.source.exists():
            for hit in _shallow_secret_hits(mount.source):
                violations.append(f"mount {mount.source} carries a secret-shaped file: {hit}")

    # The worktree is the untrusted surface; a runtime mount nested in it (or
    # the reverse) would blur which side of the boundary a file is on.
    for mount in mounts[1:]:
        if _is_within(mount.source, worktree) or _is_within(worktree, mount.source):
            violations.append(
                f"runtime mount {mount.source} overlaps the worktree {worktree}"
            )

    interpreter = _resolve(config.interpreter)
    if not any(_is_within(interpreter, m.source) for m in mounts[1:]):
        violations.append(
            f"interpreter {interpreter} is not inside any runtime mount; it "
            "would not exist in the container"
        )
    elif not interpreter.is_file():
        violations.append(f"interpreter is not a file: {interpreter}")

    for target in targets:
        if not isinstance(target, str) or not target:
            violations.append(f"collection target is not a non-empty string: {target!r}")
            continue
        candidate = Path(target)
        if candidate.is_absolute():
            resolved = _resolve(candidate)
        else:
            resolved = _resolve(worktree / candidate)
        if not _is_within(resolved, worktree):
            violations.append(
                f"collection target {target} resolves outside the worktree: {resolved}"
            )
        elif not resolved.exists():
            violations.append(f"collection target does not exist: {target}")

    violations.extend(_validate_extra_args(extra_args))
    violations.extend(_validate_env(config.extra_env))

    if config.timeout_s <= 0:
        violations.append("timeout_s must be positive")
    if config.pids_limit <= 0:
        violations.append("pids_limit must be positive")

    return violations


def collection_static_check(
    config: ContainmentConfig, targets: Sequence[str]
) -> list[str]:
    """Static inspection of the collection surface (design §6, second bullet).

    Two escapes are closed here, both of which happen before any code runs:
    a collection root reached through a symlink that leaves the worktree, and a
    pytest configuration or ``conftest.py`` brought in without being part of the
    Git canon.

    "Part of the Git canon" is judged against ``config.baseline_ref``, not
    against tracked-ness. Checking only untracked files made the whole check
    close to vacuous: a card is submitted as commits, so a worker who adds a
    ``conftest.py`` and commits it -- the *ordinary* submission form, not an
    evasion -- produced no ``??`` entry and no finding, and a tracked
    ``pyproject.toml`` could reintroduce every reserved argument through
    ``[tool.pytest.ini_options] addopts``. Both the untracked set and the diff
    against the baseline are reported now. A collection config that the card
    changes is a finding for containment, because the static check has to be a
    statement about the collection that will actually run.
    """
    findings: list[str] = []
    worktree = _resolve(config.worktree)
    roots = [
        _resolve(worktree / t) if not Path(t).is_absolute() else _resolve(t)
        for t in (targets or ["."])
    ]

    for root in roots:
        if not _is_within(root, worktree):
            findings.append(f"collection root escapes the worktree: {root}")
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in _SCAN_SKIP_DIRS]
            for name in list(dirnames) + filenames:
                entry = Path(dirpath) / name
                if entry.is_symlink():
                    resolved = _resolve(entry)
                    if not _is_within(resolved, worktree):
                        findings.append(
                            f"collection root contains a symlink leaving the "
                            f"worktree: {entry} -> {resolved}"
                        )

    def in_a_root(rel: str) -> bool:
        path = _resolve(worktree / rel)
        return any(_is_within(path, root) for root in roots)

    untracked, problem = _untracked_paths(worktree)
    if problem:
        findings.append(problem)
    else:
        for rel in untracked:
            if Path(rel).name not in _COLLECTION_CONFIG_NAMES:
                continue
            if in_a_root(rel):
                findings.append(
                    f"untracked collection config inside a collection root: {rel}"
                )

    if config.baseline_ref is None:
        findings.append(
            "baseline_ref is unset; the collection surface cannot be judged "
            "against the Git canon"
        )
    else:
        changed, problem = _changed_against_baseline(worktree, config.baseline_ref)
        if problem:
            findings.append(problem)
        else:
            for rel in changed:
                if Path(rel).name not in _COLLECTION_CONFIG_NAMES:
                    continue
                if in_a_root(rel):
                    findings.append(
                        f"collection config changed against {config.baseline_ref} "
                        f"inside a collection root: {rel}"
                    )
    return findings


def _git_lines(worktree: Path, args: Sequence[str]) -> tuple[list[str], str | None]:
    """Run one read-only git query; return its lines, or a reason it failed."""
    proc = _host_run(["git", "-C", str(worktree), *args])
    if isinstance(proc, str):
        return [], proc
    if proc.returncode != 0:
        return [], (
            f"git {' '.join(args)} failed in {worktree}: {proc.stderr.strip()}"
        )
    return proc.stdout.splitlines(), None


def _untracked_paths(worktree: Path) -> tuple[list[str], str | None]:
    lines, problem = _git_lines(
        worktree, ["status", "--porcelain", "--untracked-files=all"]
    )
    if problem:
        return [], problem
    out: list[str] = []
    for line in lines:
        if line.startswith("?? "):
            out.append(line[3:].strip().strip('"'))
    return out, None


def _changed_against_baseline(
    worktree: Path, baseline_ref: str
) -> tuple[list[str], str | None]:
    """Paths differing from ``baseline_ref``, committed changes included.

    ``git diff --name-only <ref>`` compares the ref to the working tree, so one
    query covers both what the card committed and what is still uncommitted.
    """
    lines, problem = _git_lines(worktree, ["rev-parse", "--verify", baseline_ref])
    if problem:
        return [], (
            f"baseline ref {baseline_ref!r} cannot be resolved in {worktree}; "
            "the collection surface cannot be judged against the Git canon"
        )
    lines, problem = _git_lines(
        worktree, ["diff", "--name-only", baseline_ref, "--"]
    )
    if problem:
        return [], problem
    return [line.strip().strip('"') for line in lines if line.strip()], None


# --------------------------------------------------------------------------
# Command assembly
# --------------------------------------------------------------------------


def base_env(config: ContainmentConfig) -> dict[str, str]:
    """The fixed environment. The host environment is never inherited."""
    env = {
        "HOME": _CONTAINER_HOME,
        "TMPDIR": _CONTAINER_TMPDIR,
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        # The worktree is mounted read-only; bytecode writes would be silent
        # failures at best and stale-cache reads at worst.
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        # git refuses to commit without an identity, and several scope-gate
        # tests commit. These are fixed, non-secret markers, not host identity.
        "GIT_AUTHOR_NAME": "pda-contained",
        "GIT_AUTHOR_EMAIL": "contained@pda.invalid",
        "GIT_COMMITTER_NAME": "pda-contained",
        "GIT_COMMITTER_EMAIL": "contained@pda.invalid",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }
    env.update(dict(config.extra_env))
    return env


def _mounts(config: ContainmentConfig) -> list[Mount]:
    worktree = _resolve(config.worktree)
    mounts = [Mount(source=worktree, target=worktree)]
    for raw in config.runtime_mounts:
        mounts.append(
            Mount(source=_resolve(raw), target=Path(raw).expanduser())
        )
    return mounts


def _container_script(
    config: ContainmentConfig,
    pytest_args: Sequence[str],
    *,
    junit: bool,
    report_token: str,
) -> str:
    """The in-container command. No pipelines: the image's ``sh`` is dash and
    has no ``PIPESTATUS``, so a pipeline would discard pytest's exit code --
    which is a required judgement input."""
    quoted = " ".join(shlex.quote(a) for a in pytest_args)
    begin, end = junit_markers(report_token)
    lines = [
        f"mkdir -p {shlex.quote(_CONTAINER_HOME)} {shlex.quote(_CONTAINER_TMPDIR)} || exit 90",
        f"{shlex.quote(str(config.interpreter))} -m pytest {quoted}",
        "rc=$?",
    ]
    if junit:
        lines += [
            f"printf '\\n%s\\n' {shlex.quote(begin)}",
            f"cat {shlex.quote(junit_path(report_token))} 2>/dev/null",
            f"printf '\\n%s\\n' {shlex.quote(end)}",
        ]
    lines.append("exit $rc")
    return "\n".join(lines)


def build_argv(
    config: ContainmentConfig,
    targets: Sequence[str] = (),
    extra_args: Sequence[str] = (),
    *,
    mode: str = "run",
    report_token: str | None = None,
) -> list[str]:
    """Assemble the ``docker run`` argv, or raise ``ContainmentError``.

    ``mode`` is ``"run"`` (full pytest execution, junit report) or
    ``"collect"`` (``--collect-only``, no execution). ``report_token`` ties the
    junit markers and report path to this run; ``interpret`` must be given the
    same token to read the result.
    """
    if mode not in ("run", "collect"):
        raise ContainmentError([f"unknown mode: {mode!r}"])
    if report_token is None:
        report_token = new_report_token()
    violations = validate(config, targets, extra_args)
    if violations:
        raise ContainmentError(violations)

    mounts = _mounts(config)
    worktree = mounts[0].target
    env = base_env(config)

    pytest_args = ["-p", "no:cacheprovider"]
    if mode == "collect":
        pytest_args += ["--collect-only", "-q"]
    else:
        pytest_args += [f"--junit-xml={junit_path(report_token)}"]
    pytest_args += list(extra_args)
    pytest_args += [
        str(_resolve(worktree / t) if not Path(t).is_absolute() else _resolve(t))
        for t in targets
    ]

    argv = [
        config.docker,
        "run",
        "--rm",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--ipc=private",
        f"--hostname={config.hostname}",
        f"--pids-limit={config.pids_limit}",
        f"--memory={config.memory}",
        # Equal memory and memory-swap means no swap: agent-node has 4GiB of
        # swap and the 2026-08-22 OOM took the host unresponsive for tens of
        # minutes by swapping before it killed anything.
        f"--memory-swap={config.memory}",
        f"--cpus={config.cpus}",
        # The nice-equivalent of design §6: the contained run always yields to
        # the host's resident services.
        f"--cpu-shares={config.cpu_shares}",
        f"--tmpfs=/tmp:rw,nosuid,nodev,noexec,size={config.tmpfs_size}",
        f"--workdir={worktree}",
    ]
    if config.uid is not None and config.gid is not None:
        argv.append(f"--user={config.uid}:{config.gid}")
    for name in sorted(env):
        argv.append(f"--env={name}={env[name]}")
    for mount in mounts:
        argv.append(f"--volume={mount.as_arg()}")
    argv += [
        "--entrypoint=/bin/sh",
        config.image,
        "-c",
        _container_script(
            config,
            pytest_args,
            junit=(mode == "run"),
            report_token=report_token,
        ),
    ]
    return argv


# --------------------------------------------------------------------------
# Result parsing
# --------------------------------------------------------------------------

_COLLECTED_RE = re.compile(r"^collected (\d+) items?", re.MULTILINE)
_COLLECTED_QUIET_RE = re.compile(r"^(\d+) tests? collected", re.MULTILINE)
_NO_TESTS_RE = re.compile(r"^no tests ran", re.MULTILINE)

# pytest's documented exit codes. Mapped explicitly rather than inferred: only
# 0 and 1 are statements about the code under test. Everything else is a
# statement about the run, and design §5 G2 requires those to be reported as
# infrastructure faults, never as "zero failures".
_PYTEST_EXIT = {
    0: "pass",
    1: "fail",
    2: "infra_error",  # interrupted
    3: "infra_error",  # internal error
    4: "infra_error",  # usage error
    5: "infra_error",  # no tests collected
}


@dataclass
class ContainedResult:
    """Structured judgement input for G2."""

    verdict: str
    exit_code: int
    collected: int | None
    executed: int | None
    failures: int | None
    errors: int | None
    skipped: int | None
    duration_s: float
    image: str
    mode: str
    reasons: list[str] = field(default_factory=list)
    argv: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""

    def to_dict(self, include_output: bool = False) -> dict[str, Any]:
        data = {
            "verdict": self.verdict,
            "exit_code": self.exit_code,
            "collected": self.collected,
            "executed": self.executed,
            "failures": self.failures,
            "errors": self.errors,
            "skipped": self.skipped,
            "duration_s": round(self.duration_s, 3),
            "image": self.image,
            "mode": self.mode,
            "reasons": self.reasons,
        }
        if include_output:
            data["argv"] = self.argv
            data["stdout"] = self.stdout
            data["stderr"] = self.stderr
        return data


def _parse_collected(stdout: str) -> tuple[int | None, str | None]:
    """The collected count, or a reason it cannot be trusted.

    Multiple *differing* collection lines mean the output carries more than one
    claim about how many tests there were, and the runner does not get to pick
    the convenient one.
    """
    for pattern in (_COLLECTED_RE, _COLLECTED_QUIET_RE):
        found = [int(m.group(1)) for m in pattern.finditer(stdout)]
        if not found:
            continue
        if len(set(found)) > 1:
            return None, (
                f"output carries conflicting collected counts: {sorted(set(found))}"
            )
        return found[0], None
    if _NO_TESTS_RE.search(stdout):
        return 0, None
    return None, None


def _extract_junit(stdout: str, report_token: str) -> tuple[str | None, str | None]:
    """The junit blob between this run's markers, or a reason there is none.

    A second marker pair is a refusal, not a choice. The parse used to take the
    *first* occurrence while the genuine report was printed *last*, so anything
    that ran under pytest -- a ``conftest.py`` executed during collection is
    enough -- could print a clean report before the real one and be believed.
    Counting the markers turns that from a silent substitution into an
    infrastructure fault.
    """
    begin, end = junit_markers(report_token)
    starts = [m.start() for m in re.finditer(re.escape(begin), stdout)]
    ends = [m.start() for m in re.finditer(re.escape(end), stdout)]
    if not starts or not ends:
        return None, None
    if len(starts) > 1 or len(ends) > 1:
        return None, (
            f"output carries {len(starts)} junit begin and {len(ends)} end "
            "markers; exactly one report is expected and the extra one can only "
            "have come from the code under test"
        )
    if ends[0] < starts[0]:
        return None, "junit markers are out of order"
    return stdout[starts[0] + len(begin) : ends[0]].strip(), None


def _parse_junit(blob: str) -> dict[str, int] | None:
    try:
        root = ET.fromstring(blob)
    except ET.ParseError:
        return None
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        return None
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            try:
                totals[key] += int(suite.get(key, "0"))
            except ValueError:
                return None
    return totals


def interpret(
    exit_code: int,
    stdout: str,
    stderr: str,
    *,
    mode: str,
    duration_s: float,
    image: str,
    argv: Sequence[str] | None = None,
    report_token: str,
) -> ContainedResult:
    """Turn a finished container run into the G2 judgement triple.

    ``report_token`` must be the token ``build_argv`` was given for this run.
    """
    reasons: list[str] = []
    collected, collected_problem = _parse_collected(stdout)
    if collected_problem:
        reasons.append(collected_problem)
    failures = errors = skipped = executed = None

    if mode == "run":
        blob, junit_problem = _extract_junit(stdout, report_token)
        if junit_problem:
            reasons.append(junit_problem)
        totals = _parse_junit(blob) if blob else None
        if totals is None:
            if not junit_problem:
                reasons.append("junit report missing or unparseable")
        else:
            failures = totals["failures"]
            errors = totals["errors"]
            skipped = totals["skipped"]
            executed = totals["tests"] - totals["skipped"]
            # No fallback from the junit total to the collected count: G2 names
            # both as required inputs precisely because they come from different
            # stages, and a collection that never reported its size is the
            # infrastructure fault the rule is watching for.
    else:
        executed = 0

    verdict = _PYTEST_EXIT.get(exit_code, "infra_error")
    if exit_code not in _PYTEST_EXIT:
        reasons.append(f"unmapped exit code {exit_code}")
        if exit_code in (137, -9):
            reasons.append("exit code indicates an OOM kill")
    if collected is None:
        verdict = "infra_error"
        reasons.append("collected count not reported")
    elif collected == 0:
        verdict = "infra_error"
        reasons.append("zero tests collected")

    if mode == "run":
        if executed is None:
            verdict = "infra_error"
        elif executed == 0:
            verdict = "infra_error"
            reasons.append("zero tests executed")
        elif verdict == "pass" and (failures or errors):
            # Exit code 0 with a non-zero failure count is self-contradictory:
            # trust neither, report the run as broken.
            verdict = "infra_error"
            reasons.append("exit code disagrees with the junit report")

        # The two counts come from different stages, so they are reconcilable:
        # the junit total plus what pytest said it deselected should be what was
        # collected. Only an *excess* junit total is treated as a fault --
        # ``-k``/``-m``/``--deselect`` legitimately leave the junit total below
        # the collected count, and pytest does not always name every reason a
        # collected test never reached the report.
        if totals is not None and collected is not None:
            junit_total = totals["tests"]
            if junit_total > collected:
                verdict = "infra_error"
                reasons.append(
                    f"junit reports {junit_total} tests but collection reported "
                    f"{collected}; the two counts cannot both be true"
                )

    return ContainedResult(
        verdict=verdict,
        exit_code=exit_code,
        collected=collected,
        executed=executed,
        failures=failures,
        errors=errors,
        skipped=skipped,
        duration_s=duration_s,
        image=image,
        mode=mode,
        reasons=reasons,
        argv=list(argv or []),
        stdout=stdout,
        stderr=stderr,
    )


# --------------------------------------------------------------------------
# Host-side preconditions
# --------------------------------------------------------------------------


def available_memory_mb() -> int | None:
    """MemAvailable in MiB, or ``None`` where /proc/meminfo does not exist."""
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1]) // 1024
    return None


def verify_image_present(config: ContainmentConfig) -> list[str]:
    """The pinned digest must already be local. This module never pulls: a pull
    is a registry capability, and the contained principal must not need one."""
    proc = _host_run(
        [config.docker, "image", "inspect", config.image, "--format", "{{.Id}}"]
    )
    if isinstance(proc, str):
        # A missing docker binary used to escape as a bare FileNotFoundError,
        # leaving the CLI with a traceback and exit code 1 -- the same code as
        # "the tests failed". It is a precondition failure and is reported as
        # one.
        return [f"docker is not usable on this host: {proc}"]
    if proc.returncode != 0:
        return [
            f"pinned image is not present locally: {config.image} "
            f"(pre-pull it: docker pull {config.image})"
        ]
    return []


class _SerialLock:
    """Design §6 requires contained runs to be serial on the host."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._fh = None

    def __enter__(self) -> "_SerialLock":
        if self.path is None:
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._fh.close()
            self._fh = None
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise ContainmentError(
                    [f"another contained run holds {self.path}; runs are serial"]
                ) from exc
            raise
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._fh is not None:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------


def run(
    config: ContainmentConfig,
    targets: Sequence[str] = (),
    extra_args: Sequence[str] = (),
    *,
    mode: str = "run",
) -> ContainedResult:
    """Execute one contained pytest run and return the G2 judgement triple.

    Every precondition failure is returned as an ``infra_error`` verdict or
    raised, never as a pass: design §6 states that a host where the containment
    is unavailable does not start automatic integration.

    There is no way to skip the static check. The ``skip_static_check`` flag
    that used to be here removed the symlink check and the collection-config
    check together, with nothing underneath them, and this module is meant to be
    called as a library by the improvement lane -- an opt-out reachable by the
    caller is an opt-out of the containment.
    """
    report_token = new_report_token()
    argv = build_argv(config, targets, extra_args, mode=mode, report_token=report_token)

    blocking: list[str] = []
    blocking.extend(collection_static_check(config, targets))
    blocking.extend(verify_image_present(config))
    free_mb = available_memory_mb()
    if free_mb is not None and free_mb < config.min_free_mem_mb:
        blocking.append(
            f"available memory {free_mb}MiB is below the {config.min_free_mem_mb}MiB "
            "floor; the run is deferred"
        )
    if blocking:
        return ContainedResult(
            verdict="infra_error",
            exit_code=-1,
            collected=None,
            executed=None,
            failures=None,
            errors=None,
            skipped=None,
            duration_s=0.0,
            image=config.image,
            mode=mode,
            reasons=blocking,
            argv=argv,
        )

    started = time.monotonic()
    with _SerialLock(config.lock_path):
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=config.timeout_s,
                env=host_subprocess_env(),
            )
        except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
            return ContainedResult(
                verdict="infra_error",
                exit_code=-1,
                collected=None,
                executed=None,
                failures=None,
                errors=None,
                skipped=None,
                duration_s=time.monotonic() - started,
                image=config.image,
                mode=mode,
                reasons=[f"cannot execute {config.docker!r}: {exc}"],
                argv=argv,
            )
        except subprocess.TimeoutExpired as exc:
            return ContainedResult(
                verdict="infra_error",
                exit_code=-1,
                collected=None,
                executed=None,
                failures=None,
                errors=None,
                skipped=None,
                duration_s=time.monotonic() - started,
                image=config.image,
                mode=mode,
                reasons=[f"contained run exceeded {config.timeout_s}s"],
                argv=argv,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
            )
    return interpret(
        proc.returncode,
        proc.stdout,
        proc.stderr,
        mode=mode,
        duration_s=time.monotonic() - started,
        image=config.image,
        argv=argv,
        report_token=report_token,
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


# A caller that reads only the exit code has to be able to tell "the tests
# failed" from "the containment could not establish itself". Both used to be 1.
_EXIT_PASS = 0
_EXIT_FAIL = 1
_EXIT_REFUSED = 2
_EXIT_INFRA_ERROR = 3
_EXIT_CODES = {
    "pass": _EXIT_PASS,
    "fail": _EXIT_FAIL,
    "refused": _EXIT_REFUSED,
    "infra_error": _EXIT_INFRA_ERROR,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contained_runner",
        description=(
            "Run worker-authored tests in the design §6 containment and emit "
            "the G2 judgement triple as JSON."
        ),
    )
    parser.add_argument("--worktree", required=True)
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="collection root inside the worktree (repeatable)",
    )
    parser.add_argument("--mode", choices=("run", "collect"), default="run")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--interpreter", default=str(AGENT_NODE_INTERPRETER))
    parser.add_argument(
        "--runtime-mount",
        action="append",
        default=None,
        help="read-only runtime mount (repeatable); defaults to agent-node's",
    )
    parser.add_argument(
        "--secret-home",
        default="/home/user",
        help=(
            "literal home directory the deny-set enumerates against; this is "
            "the account whose secrets must not be reachable, not the account "
            "running the containment"
        ),
    )
    parser.add_argument(
        "--baseline-ref",
        default="origin/main",
        help="ref the collection surface is judged against",
    )
    parser.add_argument("--memory", default="4g")
    parser.add_argument("--cpus", default="2")
    parser.add_argument("--tmpfs-size", default="2g")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--min-free-mem-mb", type=int, default=2048)
    parser.add_argument("--lock-path", default=None)
    parser.add_argument("--check-image", action="store_true")
    parser.add_argument("--print-argv", action="store_true")
    parser.add_argument("--with-output", action="store_true")
    parser.add_argument(
        "--pytest-arg",
        action="append",
        default=[],
        help="extra pytest argument (repeatable); containment-reserved forms are refused",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help=(
            "additional container environment entry (repeatable); the name is "
            "checked against the allowlist, so no host value is ever forwarded"
        ),
    )
    return parser


def main(raw_args: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(raw_args)
    runtime_mounts = (
        tuple(Path(p) for p in args.runtime_mount)
        if args.runtime_mount
        else (
            AGENT_NODE_HERMES_CHECKOUT,
            AGENT_NODE_UV_PYTHON,
            AGENT_NODE_UV_PYTHON_ALIAS,
        )
    )
    extra_env: dict[str, str] = {}
    for entry in args.env:
        name, sep, value = entry.partition("=")
        if not sep:
            print(
                json.dumps(
                    {"verdict": "refused", "reasons": [f"--env needs NAME=VALUE: {entry}"]},
                    ensure_ascii=False,
                )
            )
            return _EXIT_REFUSED
        extra_env[name] = value

    uid, gid = os.getuid(), os.getgid()
    config = ContainmentConfig(
        worktree=Path(args.worktree),
        interpreter=Path(args.interpreter),
        runtime_mounts=runtime_mounts,
        secret_home=Path(args.secret_home),
        baseline_ref=args.baseline_ref,
        image=args.image,
        uid=uid,
        gid=gid,
        memory=args.memory,
        cpus=args.cpus,
        tmpfs_size=args.tmpfs_size,
        timeout_s=args.timeout,
        min_free_mem_mb=args.min_free_mem_mb,
        extra_env=extra_env,
        **({"lock_path": Path(args.lock_path)} if args.lock_path else {}),
    )

    if args.check_image:
        problems = verify_image_present(config)
        print(json.dumps({"image": config.image, "present": not problems,
                          "reasons": problems}, ensure_ascii=False))
        return _EXIT_PASS if not problems else _EXIT_INFRA_ERROR

    try:
        if args.print_argv:
            argv = build_argv(config, args.target, args.pytest_arg, mode=args.mode)
            print(json.dumps(argv, ensure_ascii=False, indent=2))
            return 0
        result = run(config, args.target, args.pytest_arg, mode=args.mode)
    except ContainmentError as exc:
        print(
            json.dumps(
                {"verdict": "refused", "reasons": exc.violations}, ensure_ascii=False
            )
        )
        return _EXIT_REFUSED
    print(json.dumps(result.to_dict(include_output=args.with_output),
                     ensure_ascii=False, indent=2))
    return _EXIT_CODES.get(result.verdict, _EXIT_INFRA_ERROR)


if __name__ == "__main__":
    sys.exit(main())

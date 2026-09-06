#!/usr/bin/env python3
"""Exercise real local shells and Kanban guards in a disposable home only."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile


MARKER = "HERMES_DELEGATED_CHILD_CONTEXT"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--scenario", choices=("sequential", "failed-command", "context-exception", "child-first", "concurrent"), default="sequential")
    args = parser.parse_args()
    source = args.source.resolve()
    # Never neutralize a real child's provenance to make this probe pass.
    assert not os.environ.get(MARKER), "Run from a genuine parent subprocess"
    with tempfile.TemporaryDirectory(prefix="pda-snapshot-safety-") as directory:
        scratch = Path(directory).resolve()
        home = scratch / "home"
        home.mkdir()
        os.environ.update({
            "HOME": str(home), "HERMES_HOME": str(home / ".hermes"),
            "HERMES_KANBAN_DB": str(scratch / "kanban.db"),
            "HERMES_KANBAN_BOARD": "default",
            "HERMES_KANBAN_ATTACHMENTS_ROOT": str(scratch / "attachments"),
            "TERMINAL_SHELL_INIT_FILES": "", "PYTHONDONTWRITEBYTECODE": "1",
        })
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(source))
        if args.overlay:
            module_name = "tools.environments.base"
            importlib.import_module("tools.environments")
            spec = importlib.util.spec_from_file_location(module_name, args.overlay / "tools/environments/base.py")
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        from agent.delegation_context import delegated_child_context, is_delegated_child_context
        from tools.environments.local import LocalEnvironment, _sanitize_subprocess_env

        payload = f'''
import os, sys, json
from pathlib import Path
sys.path.insert(0, {str(source)!r})
scratch = Path({str(scratch)!r})
assert Path(os.environ['HERMES_HOME']).resolve().is_relative_to(scratch)
# Child scrubbing removes the explicit DB override; its HOME is still temporary.
if os.environ.get('HERMES_KANBAN_DB'):
    assert Path(os.environ['HERMES_KANBAN_DB']).resolve().is_relative_to(scratch)
from hermes_cli import kanban_db as kb
try:
    kb.init_db()
    with kb.connect_closing() as conn:
        kb.create_task(conn, title='isolated snapshot safety probe')
    allowed, error = True, None
except PermissionError as exc:
    allowed, error = False, str(exc)
print(json.dumps({{'marker':os.environ.get({MARKER!r}), 'kanban_allowed':allowed, 'error':error, 'user_state':os.environ.get('PDA_PROBE_SHELL_STATE')}}))
'''
        command = shlex.join([sys.executable, "-B", "-c", payload])
        environment = LocalEnvironment(cwd=str(scratch), timeout=15)
        observations = []

        def check(label: str, child: bool, fail: bool = False) -> None:
            result = environment.execute(command + ("; (exit 7)" if fail else ""))
            expected_exit = 7 if fail else 0
            assert result.get("returncode") == expected_exit, result
            observed = json.loads(result["output"].strip())
            observations.append({"label": label, **observed})
            expected_marker = "1" if child else None
            assert observed["marker"] == expected_marker, (label, observed)
            assert observed["kanban_allowed"] is (not child), (label, observed)
            if child:
                assert "delegate_task child contexts cannot mutate" in observed["error"]
            assert observed["user_state"] == "preserved", observed

        try:
            if args.scenario == "child-first":
                with delegated_child_context("synthetic-child-first"):
                    environment.execute("export PDA_PROBE_SHELL_STATE=preserved")
                    check("child-first", True)
            else:
                environment.execute("export PDA_PROBE_SHELL_STATE=preserved")
                check("parent-before", False)
                if args.scenario == "concurrent":
                    # Seed the shared snapshot in a child, then overlap real
                    # parent and child shells. Every observer checks its role.
                    with delegated_child_context("synthetic-seed"):
                        check("child-seed", True)
                    def child_check(index: int) -> None:
                        with delegated_child_context(f"synthetic-{index}"):
                            check(f"child-{index}", True)
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        for index in range(8):
                            child_future = pool.submit(child_check, index)
                            check(f"parent-concurrent-{index}", False)
                            child_future.result(timeout=20)
                else:
                    try:
                        with delegated_child_context("synthetic-child"):
                            check("child", True, args.scenario == "failed-command")
                            if args.scenario == "context-exception":
                                raise ValueError("synthetic child exception")
                    except ValueError as exc:
                        assert str(exc) == "synthetic child exception"
            assert not is_delegated_child_context()
            assert not os.environ.get(MARKER)
            check("parent-after", False)
            # A fresh-process/background route must also keep genuine child
            # lineage; merely avoiding snapshots is not permission to bypass it.
            import subprocess
            with delegated_child_context("synthetic-background-child"):
                child_env = _sanitize_subprocess_env(dict(os.environ))
                result = subprocess.run([sys.executable, "-B", "-c", payload], env=child_env, text=True, capture_output=True, timeout=15)
            assert result.returncode == 0, result.stderr
            observed = json.loads(result.stdout)
            assert observed["marker"] == "1" and not observed["kanban_allowed"], observed
            print(json.dumps({"scenario": args.scenario, "observations": observations, "fresh_child_guard": "passed", "production_state_touched": False}))
        except Exception:
            print(json.dumps({"scenario": args.scenario, "observations": observations}), file=sys.stderr)
            raise
        finally:
            environment.cleanup()


if __name__ == "__main__":
    main()

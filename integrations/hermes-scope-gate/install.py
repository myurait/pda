#!/usr/bin/env python3
"""Transactional installer for the PDA Hermes scope gate."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

PLUGIN_ID = "pda-scope-gate"


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a YAML object")
    return value


def _read_allowlist(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"approvals": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("approvals"), list):
        raise TypeError(f"{path} must contain an approvals array")
    return value


def _desired_config(config: dict[str, Any], command: str) -> dict[str, Any]:
    result = copy.deepcopy(config)
    plugins = result.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        raise TypeError("config plugins must be an object")
    enabled = plugins.setdefault("enabled", [])
    if not isinstance(enabled, list) or not all(isinstance(item, str) for item in enabled):
        raise ValueError("config plugins.enabled must be an array of strings")
    if PLUGIN_ID not in enabled:
        enabled.append(PLUGIN_ID)

    hooks = result.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise TypeError("config hooks must be an object")
    pre_tool = hooks.setdefault("pre_tool_call", [])
    if not isinstance(pre_tool, list) or not all(isinstance(item, dict) for item in pre_tool):
        raise ValueError("config hooks.pre_tool_call must be an array of objects")
    desired_hook = {
        "matcher": ".*",
        "command": command,
        "timeout": 3,
        "fail_closed": True,
    }
    matches = [index for index, item in enumerate(pre_tool) if item.get("command") == command]
    if matches:
        pre_tool[matches[0]] = desired_hook
        for index in reversed(matches[1:]):
            del pre_tool[index]
    else:
        pre_tool.append(desired_hook)
    return result


def _desired_allowlist(value: dict[str, Any], command: str) -> dict[str, Any]:
    result = copy.deepcopy(value)
    approvals = result["approvals"]
    desired = {"event": "pre_tool_call", "command": command}
    if desired not in approvals:
        approvals.append(desired)
    return result


def _atomic_write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _current_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _restore_file_if_owned(
    path: Path,
    *,
    previous: bytes | None,
    applied: bytes,
    mode: int,
) -> None:
    current = _current_bytes(path)
    if current == previous:
        return
    if current != applied:
        raise RuntimeError(f"rollback conflict: {path} changed concurrently")
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        _atomic_write(path, previous, mode)


def install_scope_gate(
    *,
    home: str | Path,
    source: str | Path,
    write_fn: Any | None = None,
) -> dict[str, Any]:
    writer = write_fn or _atomic_write
    home_path = Path(home).expanduser().resolve()
    source_path = Path(source).expanduser().resolve()
    required = (
        "plugin.yaml",
        "__init__.py",
        "scope_gate.py",
        "plugin_runtime.py",
        "pda-scope-gate",
        "schemas/scope-contract-v1.schema.json",
    )
    missing = [name for name in required if not (source_path / name).is_file()]
    if missing:
        raise ValueError(f"scope gate source is incomplete: {', '.join(missing)}")

    plugin_path = home_path / "plugins" / PLUGIN_ID
    command = f"{shlex.quote(str(plugin_path / 'pda-scope-gate'))} validate-tool"
    config_path = home_path / "config.yaml"
    allowlist_path = home_path / "shell-hooks-allowlist.json"

    current_config = _read_yaml_mapping(config_path)
    current_allowlist = _read_allowlist(allowlist_path)
    desired_config = _desired_config(current_config, command)
    desired_allowlist = _desired_allowlist(current_allowlist, command)
    config_bytes = yaml.safe_dump(
        desired_config,
        allow_unicode=True,
        sort_keys=False,
    ).encode("utf-8")
    allowlist_bytes = (
        json.dumps(desired_allowlist, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    previous_config = config_path.read_bytes() if config_path.exists() else None
    previous_allowlist = allowlist_path.read_bytes() if allowlist_path.exists() else None
    plugin_was_correct = plugin_path.is_symlink() and plugin_path.resolve() == source_path
    config_changed = previous_config != config_bytes
    allowlist_changed = previous_allowlist != allowlist_bytes
    if plugin_was_correct and not config_changed and not allowlist_changed:
        return {"changed": False, "plugin": str(plugin_path), "command": command}

    home_path.mkdir(parents=True, exist_ok=True)
    plugin_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    created_link = False
    preserve_backup = False
    try:
        if not plugin_was_correct:
            if os.path.lexists(plugin_path):
                backup_path = Path(
                    tempfile.mkdtemp(prefix=f".{PLUGIN_ID}.backup.", dir=plugin_path.parent)
                ) / PLUGIN_ID
                shutil.move(str(plugin_path), str(backup_path))
            temporary_link = plugin_path.with_name(f".{PLUGIN_ID}.new.{os.getpid()}")
            temporary_link.unlink(missing_ok=True)
            temporary_link.symlink_to(source_path, target_is_directory=True)
            os.replace(temporary_link, plugin_path)
            created_link = True
        if config_changed:
            if _current_bytes(config_path) != previous_config:
                raise RuntimeError("config changed concurrently before scope-gate write")
            writer(config_path, config_bytes, 0o600)
        if allowlist_changed:
            if _current_bytes(allowlist_path) != previous_allowlist:
                raise RuntimeError("hook allowlist changed concurrently before scope-gate write")
            writer(allowlist_path, allowlist_bytes, 0o600)
    except Exception as original:
        rollback_errors: list[str] = []
        for path, previous, applied in (
            (config_path, previous_config, config_bytes),
            (allowlist_path, previous_allowlist, allowlist_bytes),
        ):
            try:
                _restore_file_if_owned(
                    path,
                    previous=previous,
                    applied=applied,
                    mode=0o600,
                )
            except Exception as exc:  # noqa: BLE001 -- aggregate rollback failures.
                rollback_errors.append(str(exc))
        if created_link or (backup_path is not None and backup_path.exists()):
            try:
                if created_link:
                    owns_link = plugin_path.is_symlink() and plugin_path.resolve() == source_path
                    if not owns_link:
                        raise RuntimeError(f"rollback conflict: {plugin_path} changed concurrently")
                    plugin_path.unlink()
                if backup_path is not None and backup_path.exists():
                    if os.path.lexists(plugin_path):
                        raise RuntimeError(f"rollback conflict: {plugin_path} is occupied")
                    shutil.move(str(backup_path), str(plugin_path))
            except Exception as exc:  # noqa: BLE001 -- aggregate rollback failures.
                rollback_errors.append(str(exc))
        if rollback_errors:
            preserve_backup = backup_path is not None and backup_path.exists()
            raise RuntimeError(
                f"scope-gate install failed ({original}); rollback conflict(s): "
                + "; ".join(rollback_errors)
            ) from original
        raise
    finally:
        if backup_path is not None and not preserve_backup:
            shutil.rmtree(backup_path.parent, ignore_errors=True)

    return {"changed": True, "plugin": str(plugin_path), "command": command}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default=os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes"))
    parser.add_argument("--source", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args()
    result = install_scope_gate(home=args.home, source=args.source)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Transactional installer for the PDA communication-quality guard."""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any

import yaml

PLUGIN_ID = "pda-communication-guard"
SKILL_IDS = ("pda-user-escalation", "pda-autonomous-improvement")
APPROVAL_ASSET_PATHS = (
    "plugin.yaml",
    "__init__.py",
    "dashboard/manifest.json",
    "dashboard/plugin_api.py",
    "dashboard/dist/index.js",
    "dashboard/dist/style.css",
)


def _read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a YAML object")
    return value


def _desired_config(config: dict[str, Any], *, enabled: bool) -> dict[str, Any]:
    result = copy.deepcopy(config)
    plugins = result.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        raise TypeError("config plugins must be an object")
    values = plugins.setdefault("enabled", [])
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise ValueError("config plugins.enabled must be an array of strings")
    plugins["enabled"] = [item for item in values if item != PLUGIN_ID]
    if enabled:
        plugins["enabled"].append(PLUGIN_ID)
    return result


def _open_managed_parent(
    root: Path,
    path: Path,
    *,
    create: bool,
) -> tuple[int, str]:
    root_absolute = Path(os.path.abspath(root))
    path_absolute = Path(os.path.abspath(path))
    try:
        parts = path_absolute.relative_to(root_absolute).parts
    except ValueError as exc:
        raise RuntimeError(f"managed path escapes Hermes home: {path}") from exc
    if not parts:
        raise RuntimeError("managed path cannot be the Hermes home itself")
    if create:
        root_absolute.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = os.open(root_absolute, flags)
    try:
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=directory_fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        return directory_fd, parts[-1]
    except Exception:
        os.close(directory_fd)
        raise


def _secure_current_bytes(root: Path, path: Path) -> bytes | None:
    try:
        directory_fd, name = _open_managed_parent(root, path, create=False)
    except FileNotFoundError:
        return None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            file_fd = os.open(name, flags, dir_fd=directory_fd)
        except FileNotFoundError:
            return None
        with os.fdopen(file_fd, "rb") as handle:
            return handle.read()
    finally:
        os.close(directory_fd)


def _secure_atomic_write(root: Path, path: Path, data: bytes, mode: int) -> None:
    directory_fd, name = _open_managed_parent(root, path, create=True)
    temporary_name = f".{name}.{os.getpid()}.{secrets.token_hex(8)}"
    file_fd: int | None = None
    try:
        try:
            target = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISLNK(target.st_mode):
                raise RuntimeError(f"managed target is a symlink: {path}")
        except FileNotFoundError:
            pass
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
        )
        file_fd = os.open(temporary_name, flags, mode, dir_fd=directory_fd)
        with os.fdopen(file_fd, "wb") as handle:
            file_fd = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), mode)
        os.replace(
            temporary_name,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        os.fsync(directory_fd)
    finally:
        if file_fd is not None:
            os.close(file_fd)
        try:
            os.unlink(temporary_name, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        os.close(directory_fd)


def _secure_unlink(root: Path, path: Path, *, allow_symlink: bool = False) -> None:
    try:
        directory_fd, name = _open_managed_parent(root, path, create=False)
    except FileNotFoundError:
        return
    try:
        try:
            target = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        if stat.S_ISLNK(target.st_mode) and not allow_symlink:
            raise RuntimeError(f"managed target is a symlink: {path}")
        os.unlink(name, dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _secure_symlink_target(root: Path, path: Path) -> Path | None:
    try:
        directory_fd, name = _open_managed_parent(root, path, create=False)
    except FileNotFoundError:
        return None
    try:
        try:
            target_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if not stat.S_ISLNK(target_stat.st_mode):
            raise RuntimeError(f"refusing to replace existing plugin path: {path}")
        target = Path(os.readlink(name, dir_fd=directory_fd))
        if not target.is_absolute():
            target = path.parent / target
        return target.resolve()
    finally:
        os.close(directory_fd)


def _secure_create_symlink(root: Path, path: Path, target: Path) -> None:
    directory_fd, name = _open_managed_parent(root, path, create=True)
    try:
        os.symlink(
            str(target),
            name,
            target_is_directory=True,
            dir_fd=directory_fd,
        )
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _config_bytes(config: dict[str, Any]) -> bytes:
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False).encode("utf-8")


def _current_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _skill_sources(source: Path) -> dict[str, Path]:
    root = source.parents[1] / "profiles" / "pda" / "skills"
    return {skill_id: root / skill_id / "SKILL.md" for skill_id in SKILL_IDS}


def _approval_sources(source: Path) -> dict[str, Path]:
    root = source.parents[1] / "integrations" / "hermes-pda-approvals"
    return {relative: root / relative for relative in APPROVAL_ASSET_PATHS}


def _state_path(home: Path) -> Path:
    return home / "plugin-data" / PLUGIN_ID / "install-state.json"


def _read_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 3:
        raise ValueError("communication-guard install state is invalid")
    if not isinstance(value.get("source"), str):
        raise ValueError("communication-guard install state source is invalid")
    skills = value.get("skills")
    if not isinstance(skills, dict) or set(skills) != set(SKILL_IDS):
        raise ValueError("communication-guard install state skills are invalid")
    for skill_id in SKILL_IDS:
        entry = skills.get(skill_id)
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("communication-guard install state skill path is invalid")
        previous = entry.get("previous_b64")
        if previous is not None and not isinstance(previous, str):
            raise ValueError("communication-guard prior skill snapshot is invalid")
        applied = entry.get("applied_sha256")
        if not isinstance(applied, str) or len(applied) != 64:
            raise ValueError("communication-guard applied skill digest is invalid")
    approval_assets = value.get("approval_assets")
    if not isinstance(approval_assets, dict) or set(approval_assets) != set(
        APPROVAL_ASSET_PATHS
    ):
        raise ValueError("communication-guard approval asset state is invalid")
    for relative in APPROVAL_ASSET_PATHS:
        entry = approval_assets.get(relative)
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("communication-guard approval asset path is invalid")
        previous = entry.get("previous_b64")
        if previous is not None and not isinstance(previous, str):
            raise ValueError("communication-guard prior approval asset is invalid")
        applied = entry.get("applied_sha256")
        if not isinstance(applied, str) or len(applied) != 64:
            raise ValueError("communication-guard approval asset digest is invalid")
    return value


def _decode_previous_file(entry: dict[str, Any]) -> bytes | None:
    encoded = entry.get("previous_b64")
    if encoded is None:
        return None
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("communication-guard prior skill snapshot is invalid") from exc


def _state_bytes(
    *,
    source: Path,
    skills: dict[str, tuple[Path, bytes | None, bytes]],
    approval_assets: dict[str, tuple[Path, bytes | None, bytes]],
) -> bytes:
    value = {
        "schema_version": 3,
        "source": str(source),
        "skills": {
            skill_id: {
                "path": str(path),
                "previous_b64": (
                    None
                    if previous is None
                    else base64.b64encode(previous).decode("ascii")
                ),
                "applied_sha256": _hash_bytes(applied),
            }
            for skill_id, (path, previous, applied) in skills.items()
        },
        "approval_assets": {
            relative: {
                "path": str(path),
                "previous_b64": (
                    None
                    if previous is None
                    else base64.b64encode(previous).decode("ascii")
                ),
                "applied_sha256": _hash_bytes(applied),
            }
            for relative, (path, previous, applied) in approval_assets.items()
        },
    }
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _restore_if_owned(
    path: Path,
    *,
    root: Path,
    previous: bytes | None,
    applied: bytes | None,
    mode: int,
) -> None:
    _assert_no_symlink_components(root, path)
    current = _secure_current_bytes(root, path)
    if current == previous:
        return
    if current != applied:
        raise RuntimeError(f"rollback conflict: {path} changed concurrently")
    if previous is None:
        _secure_unlink(root, path)
    else:
        _secure_atomic_write(root, path, previous, mode)


def _apply_file(
    path: Path,
    *,
    root: Path,
    previous: bytes | None,
    desired: bytes | None,
    mode: int,
    writer: Any,
) -> None:
    _assert_no_symlink_components(root, path)
    if _secure_current_bytes(root, path) != previous:
        raise RuntimeError(f"concurrent change before write: {path}")
    if desired is None:
        _secure_unlink(root, path)
    else:
        writer(path, desired, mode)


def _assert_no_symlink_components(root: Path, path: Path) -> None:
    root_absolute = Path(os.path.abspath(root))
    path_absolute = Path(os.path.abspath(path))
    try:
        relative = path_absolute.relative_to(root_absolute)
    except ValueError as exc:
        raise RuntimeError(f"managed path escapes Hermes home: {path}") from exc
    current = root_absolute
    for part in relative.parts:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise RuntimeError(f"managed path contains a symlink: {current}")


def install_guard(
    *,
    home: str | Path,
    source: str | Path,
    write_fn: Any | None = None,
) -> dict[str, Any]:
    home_path = Path(home).expanduser().resolve()
    home_path.mkdir(parents=True, exist_ok=True)
    writer = write_fn or (
        lambda path, data, mode: _secure_atomic_write(home_path, path, data, mode)
    )
    source_path = Path(source).expanduser().resolve()
    required = ("plugin.yaml", "__init__.py", "communication_guard.py")
    missing = [name for name in required if not (source_path / name).is_file()]
    if missing:
        raise ValueError(f"communication guard source is incomplete: {', '.join(missing)}")
    skill_sources = _skill_sources(source_path)
    missing_skills = [
        skill_id for skill_id, skill_source in skill_sources.items() if not skill_source.is_file()
    ]
    if missing_skills:
        raise ValueError(
            "canonical PDA skills are missing: " + ", ".join(missing_skills)
        )
    approval_sources = _approval_sources(source_path)
    missing_assets = [
        relative
        for relative, asset_source in approval_sources.items()
        if not asset_source.is_file()
    ]
    if missing_assets:
        raise ValueError(
            "canonical approval assets are missing: " + ", ".join(missing_assets)
        )

    plugin_path = home_path / "plugins" / PLUGIN_ID
    plugin_target = _secure_symlink_target(home_path, plugin_path)
    if plugin_target is not None and plugin_target != source_path:
        raise RuntimeError(f"refusing to replace existing plugin path: {plugin_path}")
    config_path = home_path / "config.yaml"
    _assert_no_symlink_components(home_path, config_path)
    previous_config = config_path.read_bytes() if config_path.exists() else None
    current = _read_config(config_path)
    desired_config = _config_bytes(_desired_config(current, enabled=True))
    skill_paths = {
        skill_id: home_path / "skills" / skill_id / "SKILL.md"
        for skill_id in SKILL_IDS
    }
    for skill_path in skill_paths.values():
        _assert_no_symlink_components(home_path, skill_path)
    current_skills = {
        skill_id: _current_bytes(skill_paths[skill_id]) for skill_id in SKILL_IDS
    }
    desired_skills = {
        skill_id: skill_sources[skill_id].read_bytes() for skill_id in SKILL_IDS
    }
    approval_root = home_path / "plugins" / "pda-approvals"
    if approval_root.is_symlink():
        raise RuntimeError("refusing to write approval assets through a symlink")
    approval_paths = {
        relative: approval_root / relative for relative in APPROVAL_ASSET_PATHS
    }
    for approval_path in approval_paths.values():
        _assert_no_symlink_components(home_path, approval_path)
    current_approval_assets = {
        relative: _current_bytes(approval_paths[relative])
        for relative in APPROVAL_ASSET_PATHS
    }
    desired_approval_assets = {
        relative: approval_sources[relative].read_bytes()
        for relative in APPROVAL_ASSET_PATHS
    }
    state_path = _state_path(home_path)
    _assert_no_symlink_components(home_path, state_path)
    previous_state = _current_bytes(state_path)
    state = _read_state(state_path)
    original_skills: dict[str, bytes | None] = {}
    if state is not None and state["source"] != str(source_path):
        raise RuntimeError("communication-guard install state belongs to another source")
    for skill_id in SKILL_IDS:
        current_skill = current_skills[skill_id]
        desired_skill = desired_skills[skill_id]
        if state is None:
            original_skills[skill_id] = current_skill
            continue
        entry = state["skills"][skill_id]
        if entry["path"] != str(skill_paths[skill_id]):
            raise RuntimeError("communication-guard install state belongs to another skill path")
        original_skills[skill_id] = _decode_previous_file(entry)
        if current_skill != desired_skill and (
            current_skill is None or _hash_bytes(current_skill) != entry["applied_sha256"]
        ):
            raise RuntimeError(f"installed {skill_id} skill changed concurrently")
    original_approval_assets: dict[str, bytes | None] = {}
    for relative in APPROVAL_ASSET_PATHS:
        current_asset = current_approval_assets[relative]
        desired_asset = desired_approval_assets[relative]
        if state is None:
            original_approval_assets[relative] = current_asset
            continue
        entry = state["approval_assets"][relative]
        if entry["path"] != str(approval_paths[relative]):
            raise RuntimeError(
                "communication-guard install state belongs to another approval asset path"
            )
        original_approval_assets[relative] = _decode_previous_file(entry)
        if current_asset != desired_asset and (
            current_asset is None or _hash_bytes(current_asset) != entry["applied_sha256"]
        ):
            raise RuntimeError(f"installed approval asset changed concurrently: {relative}")
    desired_state = _state_bytes(
        source=source_path,
        skills={
            skill_id: (
                skill_paths[skill_id],
                original_skills[skill_id],
                desired_skills[skill_id],
            )
            for skill_id in SKILL_IDS
        },
        approval_assets={
            relative: (
                approval_paths[relative],
                original_approval_assets[relative],
                desired_approval_assets[relative],
            )
            for relative in APPROVAL_ASSET_PATHS
        },
    )
    link_correct = plugin_target == source_path
    if (
        link_correct
        and previous_config == desired_config
        and all(
            current_skills[skill_id] == desired_skills[skill_id]
            for skill_id in SKILL_IDS
        )
        and all(
            current_approval_assets[relative] == desired_approval_assets[relative]
            for relative in APPROVAL_ASSET_PATHS
        )
        and previous_state == desired_state
    ):
        return {"changed": False, "plugin": str(plugin_path), "enabled": True}

    created_link = False
    written: list[tuple[Path, bytes | None, bytes | None, int]] = []
    try:
        if not link_correct:
            _secure_create_symlink(home_path, plugin_path, source_path)
            created_link = True
        file_updates: list[tuple[Path, bytes | None, bytes | None, int]] = [
            (
                skill_paths[skill_id],
                current_skills[skill_id],
                desired_skills[skill_id],
                0o644,
            )
            for skill_id in SKILL_IDS
        ]
        file_updates.extend(
            [
                (
                    approval_paths[relative],
                    current_approval_assets[relative],
                    desired_approval_assets[relative],
                    0o644,
                )
                for relative in APPROVAL_ASSET_PATHS
            ]
        )
        file_updates.extend(
            [
                (config_path, previous_config, desired_config, 0o600),
                (state_path, previous_state, desired_state, 0o600),
            ]
        )
        for path, previous, desired, mode in file_updates:
            if previous == desired:
                continue
            _apply_file(
                path,
                root=home_path,
                previous=previous,
                desired=desired,
                mode=mode,
                writer=writer,
            )
            written.append((path, previous, desired, mode))
    except Exception as original:
        rollback_errors: list[str] = []
        for path, previous, applied, mode in reversed(written):
            try:
                _restore_if_owned(
                    path,
                    root=home_path,
                    previous=previous,
                    applied=applied,
                    mode=mode,
                )
            except Exception as exc:  # noqa: BLE001 -- aggregate rollback conflicts.
                rollback_errors.append(str(exc))
        if created_link and _secure_symlink_target(home_path, plugin_path) == source_path:
            _secure_unlink(home_path, plugin_path, allow_symlink=True)
        if rollback_errors:
            raise RuntimeError(
                f"communication-guard install failed ({original}); rollback conflict(s): "
                + "; ".join(rollback_errors)
            ) from original
        raise
    return {"changed": True, "plugin": str(plugin_path), "enabled": True}


def disable_guard(
    *,
    home: str | Path,
    source: str | Path,
    write_fn: Any | None = None,
) -> dict[str, Any]:
    home_path = Path(home).expanduser().resolve()
    home_path.mkdir(parents=True, exist_ok=True)
    writer = write_fn or (
        lambda path, data, mode: _secure_atomic_write(home_path, path, data, mode)
    )
    source_path = Path(source).expanduser().resolve()
    plugin_path = home_path / "plugins" / PLUGIN_ID
    plugin_target = _secure_symlink_target(home_path, plugin_path)
    if plugin_target is not None and plugin_target != source_path:
        raise RuntimeError(f"plugin path is not owned by this source: {plugin_path}")
    config_path = home_path / "config.yaml"
    _assert_no_symlink_components(home_path, config_path)
    previous_config = _current_bytes(config_path)
    desired_config = _config_bytes(_desired_config(_read_config(config_path), enabled=False))
    state_path = _state_path(home_path)
    _assert_no_symlink_components(home_path, state_path)
    previous_state = _current_bytes(state_path)
    state = _read_state(state_path)
    skill_paths = {
        skill_id: home_path / "skills" / skill_id / "SKILL.md"
        for skill_id in SKILL_IDS
    }
    for skill_path in skill_paths.values():
        _assert_no_symlink_components(home_path, skill_path)
    current_skills = {
        skill_id: _current_bytes(skill_paths[skill_id]) for skill_id in SKILL_IDS
    }
    desired_skills = dict(current_skills)
    approval_root = home_path / "plugins" / "pda-approvals"
    if approval_root.is_symlink():
        raise RuntimeError("refusing to restore approval assets through a symlink")
    approval_paths = {
        relative: approval_root / relative for relative in APPROVAL_ASSET_PATHS
    }
    for approval_path in approval_paths.values():
        _assert_no_symlink_components(home_path, approval_path)
    current_approval_assets = {
        relative: _current_bytes(approval_paths[relative])
        for relative in APPROVAL_ASSET_PATHS
    }
    desired_approval_assets = dict(current_approval_assets)
    if state is not None:
        if state["source"] != str(source_path):
            raise RuntimeError("communication-guard install state belongs to another source")
        for skill_id in SKILL_IDS:
            entry = state["skills"][skill_id]
            current_skill = current_skills[skill_id]
            if entry["path"] != str(skill_paths[skill_id]):
                raise RuntimeError(
                    "communication-guard install state belongs to another skill path"
                )
            if current_skill is None or _hash_bytes(current_skill) != entry["applied_sha256"]:
                raise RuntimeError(f"cannot restore concurrently changed {skill_id} skill")
            desired_skills[skill_id] = _decode_previous_file(entry)
        for relative in APPROVAL_ASSET_PATHS:
            entry = state["approval_assets"][relative]
            current_asset = current_approval_assets[relative]
            if entry["path"] != str(approval_paths[relative]):
                raise RuntimeError(
                    "communication-guard install state belongs to another approval asset path"
                )
            if current_asset is None or _hash_bytes(current_asset) != entry["applied_sha256"]:
                raise RuntimeError(
                    f"cannot restore concurrently changed approval asset: {relative}"
                )
            desired_approval_assets[relative] = _decode_previous_file(entry)
    if previous_config == desired_config and state is None:
        return {"changed": False, "plugin": str(plugin_path), "enabled": False}
    written: list[tuple[Path, bytes | None, bytes | None, int]] = []
    try:
        file_updates: list[tuple[Path, bytes | None, bytes | None, int]] = [
            (config_path, previous_config, desired_config, 0o600)
        ]
        file_updates.extend(
            [
                (
                    skill_paths[skill_id],
                    current_skills[skill_id],
                    desired_skills[skill_id],
                    0o644,
                )
                for skill_id in SKILL_IDS
            ]
        )
        file_updates.extend(
            [
                (
                    approval_paths[relative],
                    current_approval_assets[relative],
                    desired_approval_assets[relative],
                    0o644,
                )
                for relative in APPROVAL_ASSET_PATHS
            ]
        )
        file_updates.append((state_path, previous_state, None, 0o600))
        for path, previous, desired, mode in file_updates:
            if previous == desired:
                continue
            _apply_file(
                path,
                root=home_path,
                previous=previous,
                desired=desired,
                mode=mode,
                writer=writer,
            )
            written.append((path, previous, desired, mode))
    except Exception as original:
        rollback_errors: list[str] = []
        for path, previous, applied, mode in reversed(written):
            try:
                _restore_if_owned(
                    path,
                    root=home_path,
                    previous=previous,
                    applied=applied,
                    mode=mode,
                )
            except Exception as exc:  # noqa: BLE001 -- aggregate rollback conflicts.
                rollback_errors.append(str(exc))
        if rollback_errors:
            raise RuntimeError(
                f"communication-guard disable failed ({original}); rollback conflict(s): "
                + "; ".join(rollback_errors)
            ) from original
        raise
    return {"changed": True, "plugin": str(plugin_path), "enabled": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--home",
        default=os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes"),
    )
    parser.add_argument("--source", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    operation = disable_guard if args.disable else install_guard
    result = operation(home=args.home, source=args.source)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

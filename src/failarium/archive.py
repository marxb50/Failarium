from __future__ import annotations

import fnmatch
import json
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import (
    DEFAULT_EXCLUDES,
    DETERMINISTIC_ENV,
    FIXED_ZIP_TIMESTAMP,
    FORMAT_VERSION,
)
from .errors import (
    ConflictError,
    ExecutionError,
    FormatError,
    IntegrityError,
    ValidationError,
)
from .utils import (
    canonical_json_bytes,
    deterministic_environment,
    normalize_process_output,
    output_preview,
    relative_to_posix,
    sha256_bytes,
    sha256_file,
    validate_relative_path,
)


@dataclass(frozen=True)
class SnapshotFile:
    path: str
    source: Path
    size: int
    sha256: str
    mode: int


@dataclass(frozen=True)
class LoadedCase:
    path: Path
    manifest: dict[str, Any]
    expected_stdout: bytes
    expected_stderr: bytes


def _case_identity(manifest: dict[str, Any]) -> str:
    identity_payload = dict(manifest)
    identity_payload["case_id"] = ""
    return sha256_bytes(canonical_json_bytes(identity_payload))


def _read_ignore_patterns(root: Path) -> tuple[str, ...]:
    ignore_file = root / ".failariumignore"
    if not ignore_file.exists():
        return ()
    patterns: list[str] = []
    for raw_line in ignore_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            patterns.append(line.replace("\\", "/"))
    return tuple(patterns)


def _matches_pattern(path: str, pattern: str) -> bool:
    normalized = pattern.lstrip("./").rstrip("/")
    if not normalized:
        return False
    if fnmatch.fnmatchcase(path, normalized):
        return True
    if fnmatch.fnmatchcase(Path(path).name, normalized):
        return True
    if normalized.endswith("/**"):
        prefix = normalized[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    return False


def _is_excluded(path: str, patterns: Iterable[str]) -> bool:
    return any(_matches_pattern(path, pattern) for pattern in patterns)


def _portable_mode(path: Path) -> int:
    mode = stat.S_IMODE(path.stat().st_mode)
    return 0o755 if mode & 0o111 else 0o644


def collect_snapshot(
    root: Path,
    *,
    extra_excludes: Iterable[str] = (),
    output_path: Path | None = None,
) -> list[SnapshotFile]:
    root = root.resolve()
    patterns = (
        *DEFAULT_EXCLUDES,
        *_read_ignore_patterns(root),
        *(pattern.replace("\\", "/") for pattern in extra_excludes),
    )
    files: list[SnapshotFile] = []

    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = relative_to_posix(candidate, root)
        if _is_excluded(relative, patterns):
            continue
        if output_path is not None and candidate.resolve() == output_path.resolve():
            continue
        if candidate.is_symlink():
            raise ValidationError(
                f"Symlinks are not supported in format v1: {relative}"
            )
        if not candidate.is_file():
            continue
        files.append(
            SnapshotFile(
                path=relative,
                source=candidate,
                size=candidate.stat().st_size,
                sha256=sha256_file(candidate),
                mode=_portable_mode(candidate),
            )
        )
    return files


def _zip_info(name: str, mode: int = 0o644) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (mode & 0xFFFF) << 16
    return info


def _write_archive(
    output_path: Path,
    manifest: dict[str, Any],
    expected_stdout: bytes,
    expected_stderr: bytes,
    snapshot_root: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)

    try:
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(_zip_info("case.json"), canonical_json_bytes(manifest))
            archive.writestr(_zip_info("expected/stdout.bin"), expected_stdout)
            archive.writestr(_zip_info("expected/stderr.bin"), expected_stderr)
            for entry in manifest["files"]:
                source = snapshot_root / Path(entry["path"])
                archive.writestr(
                    _zip_info(f"files/{entry['path']}", int(entry["mode"])),
                    source.read_bytes(),
                )
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _run_command(
    command: list[str],
    *,
    workspace: Path,
    cwd: str,
    timeout: float,
) -> dict[str, Any]:
    cwd_path = validate_relative_path(cwd, label="working directory")
    command_cwd = workspace.joinpath(*cwd_path.parts)
    if not command_cwd.is_dir():
        raise ValidationError(f"Working directory does not exist: {cwd}")
    try:
        completed = subprocess.run(
            command,
            cwd=command_cwd,
            env=deterministic_environment(workspace),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ExecutionError(f"Command was not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ExecutionError(
            f"Command exceeded the {timeout:g} second timeout"
        ) from exc

    stdout = normalize_process_output(completed.stdout, workspace)
    stderr = normalize_process_output(completed.stderr, workspace)
    return {
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def capture_case(
    *,
    root: Path,
    output_path: Path,
    command: list[str],
    name: str,
    description: str,
    cwd: str = ".",
    timeout: float = 60.0,
    extra_excludes: Iterable[str] = (),
    force: bool = False,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    if not root.is_dir():
        raise ValidationError(f"Capture root is not a directory: {root}")
    if not command:
        raise ValidationError("A replay command is required after --")
    if timeout <= 0:
        raise ValidationError("Timeout must be greater than zero")
    if output_path.exists() and not force:
        raise ConflictError(
            f"Output already exists: {output_path}. Use --force to replace it."
        )

    snapshot = collect_snapshot(
        root,
        extra_excludes=extra_excludes,
        output_path=output_path,
    )
    if not snapshot:
        raise ValidationError("Capture root contains no eligible files")

    with tempfile.TemporaryDirectory(prefix="failarium-capture-") as temporary:
        workspace = Path(temporary)
        for entry in snapshot:
            target = workspace / Path(entry.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry.source, target)
            target.chmod(entry.mode)

        execution = _run_command(
            command,
            workspace=workspace,
            cwd=cwd,
            timeout=timeout,
        )
        file_entries = [
            {
                "mode": entry.mode,
                "path": entry.path,
                "sha256": entry.sha256,
                "size": entry.size,
            }
            for entry in snapshot
        ]
        manifest: dict[str, Any] = {
            "case_id": "",
            "capture": {
                "platform": os.name,
                "source_date_epoch": 0,
            },
            "command": command,
            "cwd": cwd.replace("\\", "/"),
            "description": description,
            "environment": {
                "fixed": dict(sorted(DETERMINISTIC_ENV.items())),
                "workspace_variable": "FAILARIUM_CASE_ROOT",
            },
            "expected": {
                "exit_code": execution["exit_code"],
                "stderr_sha256": sha256_bytes(execution["stderr"]),
                "stderr_size": len(execution["stderr"]),
                "stdout_sha256": sha256_bytes(execution["stdout"]),
                "stdout_size": len(execution["stdout"]),
            },
            "files": file_entries,
            "format": "failarium",
            "format_version": FORMAT_VERSION,
            "name": name,
            "timeout_seconds": timeout,
        }
        manifest["case_id"] = _case_identity(manifest)
        _write_archive(
            output_path,
            manifest,
            execution["stdout"],
            execution["stderr"],
            workspace,
        )

    return {
        "case_id": manifest["case_id"],
        "command": command,
        "expected_exit_code": execution["exit_code"],
        "file_count": len(snapshot),
        "name": name,
        "output": str(output_path),
        "output_bytes": output_path.stat().st_size,
        "stderr_preview": output_preview(execution["stderr"]),
        "stdout_preview": output_preview(execution["stdout"]),
    }


def _read_archive(path: Path) -> LoadedCase:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValidationError(f"Case does not exist: {path}")
    try:
        with zipfile.ZipFile(path, mode="r") as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)):
                raise FormatError("Archive contains duplicate member names")
            for member in members:
                name = member.filename
                if "\\" in name:
                    raise FormatError(
                        f"Archive member must use forward slashes: {name!r}"
                    )
                validate_relative_path(name, label="archive member")
                mode = (member.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise FormatError(f"Archive contains a symlink: {name}")
                if name not in {
                    "case.json",
                    "expected/stdout.bin",
                    "expected/stderr.bin",
                } and not name.startswith("files/"):
                    raise FormatError(f"Archive contains an unknown member: {name}")
            required = {
                "case.json",
                "expected/stdout.bin",
                "expected/stderr.bin",
            }
            missing = sorted(required.difference(names))
            if missing:
                raise FormatError(
                    "Archive is missing required members: " + ", ".join(missing)
                )
            try:
                manifest = json.loads(archive.read("case.json").decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise FormatError("case.json is not valid UTF-8 JSON") from exc
            stdout = archive.read("expected/stdout.bin")
            stderr = archive.read("expected/stderr.bin")
    except zipfile.BadZipFile as exc:
        raise FormatError(f"Not a valid .failarium ZIP archive: {path}") from exc

    return LoadedCase(
        path=path,
        manifest=manifest,
        expected_stdout=stdout,
        expected_stderr=stderr,
    )


def verify_case(path: Path) -> dict[str, Any]:
    loaded = _read_archive(path)
    manifest = loaded.manifest
    if not isinstance(manifest, dict):
        raise FormatError("case.json root must be an object")
    if manifest.get("format") != "failarium":
        raise FormatError("case.json format must be 'failarium'")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise FormatError(
            f"Unsupported format version: {manifest.get('format_version')!r}"
        )
    if not isinstance(manifest.get("files"), list):
        raise FormatError("case.json files must be a list")
    if not isinstance(manifest.get("command"), list) or not manifest["command"]:
        raise FormatError("case.json command must be a non-empty list")
    if not all(isinstance(item, str) and item for item in manifest["command"]):
        raise FormatError("case.json command items must be non-empty strings")
    case_id = manifest.get("case_id")
    if not isinstance(case_id, str) or len(case_id) != 64:
        raise FormatError("case.json case_id must be a SHA-256 hex digest")
    try:
        int(case_id, 16)
    except ValueError as exc:
        raise FormatError("case.json case_id must be a SHA-256 hex digest") from exc
    if case_id != _case_identity(manifest):
        raise IntegrityError("case.json case_id does not match the manifest")

    expected = manifest.get("expected")
    if not isinstance(expected, dict):
        raise FormatError("case.json expected must be an object")
    if sha256_bytes(loaded.expected_stdout) != expected.get("stdout_sha256"):
        raise IntegrityError("Expected stdout hash does not match case.json")
    if sha256_bytes(loaded.expected_stderr) != expected.get("stderr_sha256"):
        raise IntegrityError("Expected stderr hash does not match case.json")
    if len(loaded.expected_stdout) != expected.get("stdout_size"):
        raise IntegrityError("Expected stdout size does not match case.json")
    if len(loaded.expected_stderr) != expected.get("stderr_size"):
        raise IntegrityError("Expected stderr size does not match case.json")

    with zipfile.ZipFile(loaded.path, mode="r") as archive:
        names = set(archive.namelist())
        seen_paths: set[str] = set()
        for entry in manifest["files"]:
            if not isinstance(entry, dict):
                raise FormatError("Each file entry must be an object")
            relative = str(validate_relative_path(entry.get("path", "")))
            if relative in seen_paths:
                raise FormatError(f"Duplicate file path in manifest: {relative}")
            seen_paths.add(relative)
            member = f"files/{relative}"
            if member not in names:
                raise IntegrityError(f"Archive is missing captured file: {relative}")
            payload = archive.read(member)
            if len(payload) != entry.get("size"):
                raise IntegrityError(f"Size mismatch for captured file: {relative}")
            if sha256_bytes(payload) != entry.get("sha256"):
                raise IntegrityError(f"Hash mismatch for captured file: {relative}")

        expected_members = {f"files/{path}" for path in seen_paths}
        actual_members = {name for name in names if name.startswith("files/")}
        unexpected = sorted(actual_members.difference(expected_members))
        if unexpected:
            raise FormatError(
                "Archive contains unlisted captured files: " + ", ".join(unexpected)
            )

    return {
        "case_id": manifest.get("case_id"),
        "file_count": len(manifest["files"]),
        "format_version": manifest["format_version"],
        "name": manifest.get("name"),
        "path": str(loaded.path),
        "valid": True,
    }


def extract_case(path: Path, destination: Path) -> LoadedCase:
    loaded = _read_archive(path)
    verify_case(path)
    destination = destination.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ConflictError(f"Replay workspace is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(loaded.path, mode="r") as archive:
        for entry in loaded.manifest["files"]:
            relative = validate_relative_path(entry["path"], label="captured file")
            target = destination.joinpath(*relative.parts)
            try:
                target.relative_to(destination)
            except ValueError as exc:
                raise FormatError(
                    f"Captured path escapes workspace: {relative}"
                ) from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = archive.read(f"files/{relative}")
            target.write_bytes(payload)
            try:
                target.chmod(int(entry.get("mode", 0o644)))
            except OSError:
                pass
    return loaded


def replay_case(
    path: Path,
    *,
    workspace: Path | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    managed_workspace: tempfile.TemporaryDirectory[str] | None = None
    if workspace is None:
        managed_workspace = tempfile.TemporaryDirectory(prefix="failarium-replay-")
        replay_root = Path(managed_workspace.name)
    else:
        replay_root = workspace.expanduser().resolve()

    try:
        loaded = extract_case(path, replay_root)
        manifest = loaded.manifest
        execution = _run_command(
            [str(item) for item in manifest["command"]],
            workspace=replay_root,
            cwd=str(manifest["cwd"]),
            timeout=float(timeout or manifest["timeout_seconds"]),
        )
        expected = manifest["expected"]
        comparisons = {
            "exit_code": execution["exit_code"] == expected["exit_code"],
            "stderr": sha256_bytes(execution["stderr"]) == expected["stderr_sha256"],
            "stdout": sha256_bytes(execution["stdout"]) == expected["stdout_sha256"],
        }
        mismatches = [name for name, matches in comparisons.items() if not matches]
        return {
            "actual": {
                "exit_code": execution["exit_code"],
                "stderr_preview": output_preview(execution["stderr"]),
                "stderr_sha256": sha256_bytes(execution["stderr"]),
                "stdout_preview": output_preview(execution["stdout"]),
                "stdout_sha256": sha256_bytes(execution["stdout"]),
            },
            "case_id": manifest["case_id"],
            "comparisons": comparisons,
            "expected_exit_code": expected["exit_code"],
            "matched": not mismatches,
            "mismatches": mismatches,
            "name": manifest["name"],
            "workspace": str(replay_root) if workspace is not None else None,
        }
    finally:
        if managed_workspace is not None:
            managed_workspace.cleanup()


def inspect_case(path: Path) -> dict[str, Any]:
    loaded = _read_archive(path)
    verify_case(path)
    manifest = loaded.manifest
    return {
        "case_id": manifest["case_id"],
        "command": manifest["command"],
        "cwd": manifest["cwd"],
        "description": manifest.get("description", ""),
        "expected": manifest["expected"],
        "file_count": len(manifest["files"]),
        "format_version": manifest["format_version"],
        "name": manifest["name"],
        "path": str(loaded.path),
        "stderr_preview": output_preview(loaded.expected_stderr),
        "stdout_preview": output_preview(loaded.expected_stdout),
    }


def dump_manifest(path: Path) -> dict[str, Any]:
    loaded = _read_archive(path)
    verify_case(path)
    return loaded.manifest


def list_cases(directory: Path, *, recursive: bool = False) -> list[dict[str, Any]]:
    directory = directory.expanduser().resolve()
    if not directory.is_dir():
        raise ValidationError(f"Cases directory does not exist: {directory}")
    iterator = (
        directory.rglob("*.failarium") if recursive else directory.glob("*.failarium")
    )
    results: list[dict[str, Any]] = []
    for path in sorted(iterator):
        try:
            info = inspect_case(path)
            results.append(
                {
                    "case_id": info["case_id"],
                    "name": info["name"],
                    "path": str(path.resolve()),
                    "valid": True,
                }
            )
        except (FormatError, IntegrityError) as exc:
            results.append(
                {
                    "error": str(exc),
                    "path": str(path.resolve()),
                    "valid": False,
                }
            )
    return results

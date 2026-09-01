from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any

from .constants import DETERMINISTIC_ENV
from .errors import FormatError, ValidationError


def canonical_json_bytes(value: Any) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (text + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_relative_path(value: str, *, label: str = "path") -> PurePosixPath:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise FormatError(f"Unsafe {label}: {value!r}")
    if any(part in ("", ".") for part in path.parts):
        raise FormatError(f"Invalid {label}: {value!r}")
    return path


def relative_to_posix(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValidationError(f"{path} is outside capture root {root}") from exc


def deterministic_environment(workspace: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(DETERMINISTIC_ENV)
    env["FAILARIUM_CASE_ROOT"] = str(workspace)
    return env


def normalize_process_output(value: bytes, workspace: Path) -> bytes:
    normalized = value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    candidates = {
        str(workspace),
        str(workspace.resolve()),
        str(workspace).replace("\\", "/"),
        str(workspace.resolve()).replace("\\", "/"),
    }
    for candidate in sorted(candidates, key=len, reverse=True):
        normalized = normalized.replace(
            candidate.encode("utf-8", errors="surrogateescape"),
            b"<FAILARIUM_CASE_ROOT>",
        )
    return normalized


def output_preview(value: bytes, limit: int = 400) -> str:
    text = value.decode("utf-8", errors="replace")
    if len(text) > limit:
        return text[:limit] + "..."
    return text

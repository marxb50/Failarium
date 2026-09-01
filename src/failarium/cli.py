from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from .archive import (
    capture_case,
    dump_manifest,
    inspect_case,
    list_cases,
    replay_case,
    verify_case,
)
from .constants import FORMAT_VERSION, VERSION
from .errors import FailariumError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="failarium",
        description=(
            "Capture, inspect, verify, and replay portable AI-agent failure cases."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a stable JSON envelope to stdout.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="Check runtime and local CLI capabilities.")

    init_parser = commands.add_parser(
        "init",
        help="Create a starter .failariumignore file.",
    )
    init_parser.add_argument("directory", nargs="?", default=".")

    capture_parser = commands.add_parser(
        "capture",
        help="Snapshot a directory and record the result of a command.",
    )
    capture_parser.add_argument("--root", default=".")
    capture_parser.add_argument("--out", required=True)
    capture_parser.add_argument("--name")
    capture_parser.add_argument("--description", default="")
    capture_parser.add_argument("--cwd", default=".")
    capture_parser.add_argument("--timeout", type=float, default=60.0)
    capture_parser.add_argument("--exclude", action="append", default=[])
    capture_parser.add_argument("--force", action="store_true")
    capture_parser.add_argument(
        "replay_command",
        nargs=argparse.REMAINDER,
        help="Command to record, placed after --.",
    )

    inspect_parser = commands.add_parser(
        "inspect",
        help="Show the public summary of a .failarium case.",
    )
    inspect_parser.add_argument("case")

    verify_parser = commands.add_parser(
        "verify",
        help="Validate format structure and all content hashes.",
    )
    verify_parser.add_argument("case")

    replay_parser = commands.add_parser(
        "replay",
        help="Restore a case and compare its command result byte-for-byte.",
    )
    replay_parser.add_argument("case")
    replay_parser.add_argument("--workspace")
    replay_parser.add_argument("--timeout", type=float)

    cases_parser = commands.add_parser("cases", help="Discover .failarium cases.")
    cases_commands = cases_parser.add_subparsers(dest="cases_command", required=True)
    cases_list = cases_commands.add_parser("list", help="List cases in a directory.")
    cases_list.add_argument("directory", nargs="?", default=".")
    cases_list.add_argument("--recursive", action="store_true")

    format_parser = commands.add_parser(
        "format",
        help="Low-level access to the open archive format.",
    )
    format_commands = format_parser.add_subparsers(
        dest="format_command",
        required=True,
    )
    format_dump = format_commands.add_parser(
        "dump",
        help="Print the complete case.json manifest.",
    )
    format_dump.add_argument("case")
    return parser


def _doctor() -> dict[str, Any]:
    return {
        "archive_format": f".failarium/v{FORMAT_VERSION}",
        "cwd": str(Path.cwd()),
        "executable": shutil.which("failarium"),
        "offline": True,
        "python": {
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "runtime_dependencies": [],
        "status": "ok",
        "version": VERSION,
    }


def _init(directory: str) -> dict[str, Any]:
    root = Path(directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    ignore_path = root / ".failariumignore"
    if ignore_path.exists():
        return {
            "created": False,
            "path": str(ignore_path),
            "reason": "already_exists",
        }
    content = (
        "# Project-specific exclusions for Failarium capture.\n"
        "# Built-in exclusions already cover Git metadata, virtual environments,\n"
        "# dependency folders, caches, and existing *.failarium archives.\n"
        "\n"
        "secrets/**\n"
        "*.pem\n"
        "*.key\n"
        ".env\n"
    )
    ignore_path.write_text(content, encoding="utf-8", newline="\n")
    return {
        "created": True,
        "path": str(ignore_path),
    }


def _strip_separator(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


def _execute(args: argparse.Namespace) -> Any:
    if args.command == "doctor":
        return _doctor()
    if args.command == "init":
        return _init(args.directory)
    if args.command == "capture":
        root = Path(args.root)
        name = args.name or Path(args.out).stem
        return capture_case(
            root=root,
            output_path=Path(args.out),
            command=_strip_separator(args.replay_command),
            name=name,
            description=args.description,
            cwd=args.cwd,
            timeout=args.timeout,
            extra_excludes=args.exclude,
            force=args.force,
        )
    if args.command == "inspect":
        return inspect_case(Path(args.case))
    if args.command == "verify":
        return verify_case(Path(args.case))
    if args.command == "replay":
        return replay_case(
            Path(args.case),
            workspace=Path(args.workspace) if args.workspace else None,
            timeout=args.timeout,
        )
    if args.command == "cases" and args.cases_command == "list":
        return {
            "cases": list_cases(
                Path(args.directory),
                recursive=args.recursive,
            )
        }
    if args.command == "format" and args.format_command == "dump":
        return dump_manifest(Path(args.case))
    raise AssertionError(f"Unhandled command: {args.command}")


def _human_output(command: str, result: Any) -> None:
    if command == "doctor":
        print(f"Failarium {result['version']}")
        print(f"Python: {result['python']['version']}")
        print(f"Format: {result['archive_format']}")
        print("Runtime dependencies: none")
        return
    if command == "capture":
        print(f"Captured {result['name']} -> {result['output']}")
        print(
            f"Case {result['case_id']}: {result['file_count']} files, "
            f"expected exit {result['expected_exit_code']}"
        )
        return
    if command == "replay":
        status = "MATCH" if result["matched"] else "MISMATCH"
        print(f"{status}: {result['name']} ({result['case_id']})")
        if result["mismatches"]:
            print("Differences: " + ", ".join(result["mismatches"]))
        return
    if command == "verify":
        print(
            f"VALID: {result['name']} ({result['case_id']}), "
            f"{result['file_count']} files"
        )
        return
    if command == "inspect":
        print(f"{result['name']} ({result['case_id']})")
        print("Command: " + " ".join(result["command"]))
        print(f"Files: {result['file_count']}")
        print(f"Expected exit: {result['expected']['exit_code']}")
        if result["description"]:
            print(result["description"])
        return
    if command == "init":
        action = "Created" if result["created"] else "Exists"
        print(f"{action}: {result['path']}")
        return
    if command == "cases":
        cases = result["cases"]
        if not cases:
            print("No .failarium cases found.")
            return
        for case in cases:
            if case["valid"]:
                print(f"{case['case_id']}  {case['name']}  {case['path']}")
            else:
                print(f"INVALID  {case['path']}  {case['error']}")
        return
    if command == "format":
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(result)


def _json_success(command: str, result: Any) -> None:
    print(
        json.dumps(
            {
                "command": command,
                "ok": True,
                "result": result,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _json_error(error: FailariumError) -> None:
    print(
        json.dumps(
            {
                "error": {
                    "code": error.code,
                    "message": str(error),
                },
                "ok": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        result = _execute(args)
        if args.json:
            _json_success(args.command, result)
        else:
            _human_output(args.command, result)
        if args.command == "replay" and not result["matched"]:
            return 3
        return 0
    except FailariumError as exc:
        if args.json:
            _json_error(exc)
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        if args.json:
            _json_error(FailariumError("Interrupted by user"))
        else:
            print("error: interrupted by user", file=sys.stderr)
        return 130
    except Exception as exc:
        if os.environ.get("FAILARIUM_DEBUG") == "1":
            raise
        wrapped = FailariumError(f"Unexpected failure: {exc}")
        if args.json:
            _json_error(wrapped)
        else:
            print(f"error: {wrapped}", file=sys.stderr)
        return 1

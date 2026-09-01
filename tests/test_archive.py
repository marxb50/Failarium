from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from failarium.archive import capture_case, inspect_case, replay_case, verify_case
from failarium.errors import ConflictError, FormatError, IntegrityError


class ArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="failarium-tests-")
        self.base = Path(self.temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / "input.txt").write_text("portable failure\n", encoding="utf-8")
        (self.project / "task.py").write_text(
            "from pathlib import Path\n"
            "print(Path('input.txt').read_text(encoding='utf-8').strip())\n"
            "print(Path.cwd())\n"
            "raise SystemExit(7)\n",
            encoding="utf-8",
        )
        (self.project / "__pycache__").mkdir()
        (self.project / "__pycache__" / "ignored.pyc").write_bytes(b"ignore")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def capture(self, name: str) -> Path:
        output = self.base / f"{name}.failarium"
        capture_case(
            root=self.project,
            output_path=output,
            command=[sys.executable, "task.py"],
            name="known-failure",
            description="A deterministic failing command.",
        )
        return output

    def test_capture_replay_preserves_expected_failure(self) -> None:
        case = self.capture("failure")
        info = inspect_case(case)
        result = replay_case(case)

        self.assertEqual(info["file_count"], 2)
        self.assertEqual(info["expected"]["exit_code"], 7)
        self.assertIn("<FAILARIUM_CASE_ROOT>", info["stdout_preview"])
        self.assertTrue(result["matched"])
        self.assertEqual(result["mismatches"], [])

    def test_repeated_capture_is_byte_identical(self) -> None:
        first = self.capture("first")
        second = self.capture("second")
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_verify_detects_modified_file_payload(self) -> None:
        original = self.capture("original")
        tampered = self.base / "tampered.failarium"

        with zipfile.ZipFile(original, "r") as source:
            members = [(info, source.read(info.filename)) for info in source.infolist()]
        with zipfile.ZipFile(tampered, "w") as target:
            for info, payload in members:
                if info.filename == "files/input.txt":
                    payload = b"changed\n"
                target.writestr(info, payload)

        with self.assertRaises(IntegrityError):
            verify_case(tampered)

    def test_verify_detects_modified_manifest(self) -> None:
        original = self.capture("original-manifest")
        tampered = self.base / "tampered-manifest.failarium"

        with zipfile.ZipFile(original, "r") as source:
            members = [(info, source.read(info.filename)) for info in source.infolist()]
        with zipfile.ZipFile(tampered, "w") as target:
            for info, payload in members:
                if info.filename == "case.json":
                    manifest = json.loads(payload)
                    manifest["name"] = "quietly-changed"
                    payload = json.dumps(manifest).encode("utf-8")
                target.writestr(info, payload)

        with self.assertRaises(IntegrityError):
            verify_case(tampered)

    def test_verify_rejects_unknown_archive_member(self) -> None:
        original = self.capture("original-extra")
        tampered = self.base / "unknown-member.failarium"

        with zipfile.ZipFile(original, "r") as source:
            members = [(info, source.read(info.filename)) for info in source.infolist()]
        with zipfile.ZipFile(tampered, "w") as target:
            for info, payload in members:
                target.writestr(info, payload)
            target.writestr("metadata/hidden.txt", b"not declared")

        with self.assertRaises(FormatError):
            verify_case(tampered)

    def test_archive_member_cannot_escape_workspace(self) -> None:
        malicious = self.base / "malicious.failarium"
        manifest = {
            "command": ["python", "task.py"],
            "expected": {
                "exit_code": 0,
                "stderr_sha256": "",
                "stderr_size": 0,
                "stdout_sha256": "",
                "stdout_size": 0,
            },
            "files": [],
            "format": "failarium",
            "format_version": 1,
        }
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr("case.json", json.dumps(manifest))
            archive.writestr("expected/stdout.bin", b"")
            archive.writestr("expected/stderr.bin", b"")
            archive.writestr("files/../escape.txt", b"unsafe")

        with self.assertRaises(FormatError):
            verify_case(malicious)

    def test_capture_refuses_to_overwrite_without_force(self) -> None:
        case = self.capture("existing")
        with self.assertRaises(ConflictError):
            capture_case(
                root=self.project,
                output_path=case,
                command=[sys.executable, "task.py"],
                name="known-failure",
                description="",
            )

    def test_replay_refuses_non_empty_workspace(self) -> None:
        case = self.capture("workspace")
        workspace = self.base / "not-empty"
        workspace.mkdir()
        (workspace / "keep.txt").write_text("do not overwrite", encoding="utf-8")
        with self.assertRaises(ConflictError):
            replay_case(case, workspace=workspace)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from failarium.cli import main


class CliTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(arguments)
        return code, output.getvalue()

    def test_doctor_json_has_stable_envelope(self) -> None:
        code, output = self.invoke(["--json", "doctor"])
        payload = json.loads(output)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "doctor")
        self.assertEqual(payload["result"]["archive_format"], ".failarium/v1")
        self.assertEqual(payload["result"]["runtime_dependencies"], [])

    def test_init_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="failarium-init-") as temporary:
            first_code, first_output = self.invoke(["--json", "init", temporary])
            second_code, second_output = self.invoke(["--json", "init", temporary])
            first = json.loads(first_output)
            second = json.loads(second_output)

            self.assertEqual(first_code, 0)
            self.assertEqual(second_code, 0)
            self.assertTrue(first["result"]["created"])
            self.assertFalse(second["result"]["created"])
            self.assertTrue(Path(first["result"]["path"]).is_file())

    def test_missing_case_returns_machine_readable_error(self) -> None:
        code, output = self.invoke(["--json", "verify", "does-not-exist.failarium"])
        payload = json.loads(output)
        self.assertEqual(code, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "validation_error")


if __name__ == "__main__":
    unittest.main()

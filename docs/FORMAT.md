# Failarium Format v1

## Status

This document defines version 1 of the open <code>.failarium</code> format.
Writers must emit the requirements below. Readers must reject unsupported major
versions.

## Container

A case is a ZIP file with the <code>.failarium</code> extension. The recommended
media type is <code>application/vnd.failarium+zip</code>.

Required members:

~~~text
case.json
expected/stdout.bin
expected/stderr.bin
~~~

Captured regular files are stored below <code>files/</code>. Member names use
forward slashes and paths relative to the capture root.

Readers must reject absolute paths, parent traversal, duplicate members,
backslash-separated names, symlinks, and members outside the defined roots.

## Manifest

<code>case.json</code> is UTF-8 JSON with this logical structure:

~~~json
{
  "format": "failarium",
  "format_version": 1,
  "case_id": "sha256 digest",
  "name": "case name",
  "command": ["python", "task.py"],
  "cwd": ".",
  "environment": {
    "fixed": {
      "LANG": "C.UTF-8",
      "LC_ALL": "C.UTF-8",
      "PYTHONHASHSEED": "0",
      "TZ": "UTC"
    },
    "workspace_variable": "FAILARIUM_CASE_ROOT"
  },
  "capture": {
    "platform": "posix",
    "source_date_epoch": 0
  },
  "timeout_seconds": 60,
  "files": [
    {
      "path": "task.py",
      "sha256": "hex digest",
      "size": 42
    }
  ],
  "expected": {
    "exit_code": 7,
    "stdout_sha256": "hex digest",
    "stdout_size": 13,
    "stderr_sha256": "hex digest",
    "stderr_size": 0
  }
}
~~~

The <code>case_id</code> is the SHA-256 digest of the canonical manifest with
<code>case_id</code> set to an empty string.

Unknown manifest fields must be ignored by v1 readers so compatible metadata
can be added. Missing required fields are an error.

## Canonical JSON

Writers serialize the manifest as UTF-8 with:

- object keys sorted lexicographically;
- separators <code>,</code> and <code>:</code> without insignificant spaces;
- Unicode represented directly, not ASCII-escaped;
- one trailing LF byte.

## Deterministic ZIP

Writers:

- sort member names lexicographically;
- use the DOS timestamp <code>1980-01-01 00:00:00</code>;
- set regular-file permissions to <code>0644</code>;
- use the deflate algorithm at level 9;
- omit filesystem-specific extra fields and comments.

Repeated capture of identical inputs and results by a compatible writer should
produce byte-identical archives.

## Output Normalization

Before storage and replay comparison, stdout and stderr:

1. convert CRLF and bare CR to LF;
2. replace the absolute execution workspace path with
   <code>&lt;FAILARIUM_CASE_ROOT&gt;</code>.

No other text or byte transformation is applied.

## Replay

A conforming reader verifies the full archive before execution. It extracts
captured files into a fresh directory, applies the recorded environment
overrides, runs the exact argument vector in the recorded relative working
directory, normalizes outputs, and independently compares:

- process exit code;
- stdout bytes;
- stderr bytes.

A matching non-zero exit code is a successful replay when it was the recorded
expected result.

## Security

The format intentionally stores an executable command. Replay is not a security
sandbox. Readers should clearly warn users, never execute during inspect or
verify operations, enforce archive path safety, and recommend isolation for
untrusted cases.

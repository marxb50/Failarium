# Failarium

[![CI](https://github.com/marxb50/Failarium/actions/workflows/ci.yml/badge.svg)](https://github.com/marxb50/Failarium/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-0B7285)](LICENSE)

**Grow the smallest world that reproduces an AI-agent failure.**

Failarium records a command, its input files, selected environment variables, and
expected outputs in one portable <code>.failarium</code> file. Anyone can verify
the artifact and replay the same failure without reconstructing the original
workspace by hand.

[Português](README.pt-BR.md) | [Format specification](docs/FORMAT.md)

## Why

AI-agent bugs often depend on a precise combination of prompt files, repository
state, command arguments, and environment values. A screenshot or log is not
enough to reproduce that state. Failarium turns it into a portable test case:

- one open, inspectable archive;
- deterministic archive bytes for the same captured state;
- cryptographic integrity checks;
- replay in a fresh temporary workspace;
- stable human-readable and JSON output.

## Quick Start

Requires Python 3.11 or newer.

~~~powershell
python -m pip install -e .
failarium --json doctor
failarium capture --root examples/known-failure --out failure.failarium -- python task.py
failarium inspect failure.failarium
failarium verify failure.failarium
failarium replay failure.failarium
~~~

The included example intentionally exits with code 7. Replay succeeds when that
same failure is reproduced, including its stdout, stderr, and exit code.

## Commands

~~~text
failarium init [directory]
failarium capture --root PATH --out CASE.failarium -- COMMAND...
failarium inspect CASE.failarium
failarium verify CASE.failarium
failarium replay CASE.failarium
failarium cases list [directory]
failarium format dump CASE.failarium
failarium --json doctor
~~~

Use <code>--json</code> before the command for a stable automation envelope.
Successful responses contain <code>{"ok": true, "data": ...}</code>; errors
contain <code>{"ok": false, "error": {"code": ..., "message": ...}}</code>.

## Open Format

A <code>.failarium</code> file is a deterministic ZIP archive:

~~~text
case.json
expected/stdout.bin
expected/stderr.bin
files/...
~~~

<code>case.json</code> contains the format version, command, relative working
directory, deterministic environment overrides, file hashes, expected result,
and capture metadata. The complete v1 contract is documented in
[docs/FORMAT.md](docs/FORMAT.md).

## Deterministic Boundary

Version 1 reproduces the captured filesystem, argument vector, working
directory, environment overrides, exit code, stdout, and stderr. It normalizes
line endings and replaces the temporary workspace path in output before
comparison.

Failarium does **not** yet virtualize the clock, network, operating system,
installed executables, or external services. Commands that depend on those
inputs should mock or pin them.

## Safety

Treat a <code>.failarium</code> file like source code from an unknown repository.
Verification and inspection do not execute the case. Replay executes the
recorded command and is not an operating-system sandbox. Only replay artifacts
you trust, preferably inside a container or disposable virtual machine.

The reader rejects duplicate members, unsafe paths, symlinks, missing payloads,
and hash mismatches before replay.

## Development

~~~powershell
python -m unittest discover -s tests -v
python -m compileall -q src
~~~

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and
[SECURITY.md](SECURITY.md) for private vulnerability reporting.

## Roadmap

- Week 1: open format, Python CLI, recording, integrity verification, replay.
- Week 2: minimization engine that removes irrelevant files and environment data.
- Week 3: adapters for popular coding agents and CI annotations.
- Week 4: searchable public specimen registry and browser viewer.

## License

MIT. See [LICENSE](LICENSE).

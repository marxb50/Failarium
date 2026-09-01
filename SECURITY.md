# Security Policy

## Reporting a Vulnerability

Please do not disclose exploitable archive handling or command execution issues
in a public issue. Use GitHub private vulnerability reporting for this
repository and include:

- affected Failarium version;
- a minimal proof of concept;
- expected and observed behavior;
- impact and suggested mitigation, if known.

You should receive an initial response within seven days.

## Trust Model

Inspect and verify operations never intentionally execute a recorded command.
Replay does execute it and is not an operating-system sandbox. Untrusted cases
should be replayed only in a disposable container or virtual machine.

Security-sensitive parser invariants include path traversal rejection, duplicate
member rejection, symlink rejection, bounded extraction destinations, and
SHA-256 verification before replay.

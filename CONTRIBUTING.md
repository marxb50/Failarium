# Contributing

Thank you for helping make AI-agent failures reproducible.

## Workflow

1. Open an issue describing the behavior or format change.
2. Keep format changes backward-compatible or propose a new major version.
3. Add tests for success, failure, and malicious input paths.
4. Run the complete local checks.
5. Submit a focused pull request explaining the observable behavior.

~~~powershell
python -m unittest discover -s tests -v
python -m compileall -q src
~~~

Code should use the Python standard library unless a dependency provides clear,
measurable value. Public CLI output and JSON fields are compatibility surfaces.

By contributing, you agree that your contribution is licensed under the MIT
License.

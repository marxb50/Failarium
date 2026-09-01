from __future__ import annotations

VERSION = "0.1.0"
FORMAT_VERSION = 1

DEFAULT_EXCLUDES = (
    ".git",
    ".git/**",
    ".hg",
    ".hg/**",
    ".svn",
    ".svn/**",
    ".venv",
    ".venv/**",
    "venv",
    "venv/**",
    "node_modules",
    "node_modules/**",
    "__pycache__",
    "**/__pycache__/**",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".pytest_cache/**",
    ".mypy_cache",
    ".mypy_cache/**",
    ".ruff_cache",
    ".ruff_cache/**",
    ".idea",
    ".idea/**",
    ".vscode",
    ".vscode/**",
    "*.failarium",
)

DETERMINISTIC_ENV = {
    "FAILARIUM_SEED": "0",
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONHASHSEED": "0",
    "SOURCE_DATE_EPOCH": "0",
    "TZ": "UTC",
}

FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

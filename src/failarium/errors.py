from __future__ import annotations


class FailariumError(Exception):
    code = "failarium_error"


class ValidationError(FailariumError):
    code = "validation_error"


class FormatError(FailariumError):
    code = "format_error"


class IntegrityError(FailariumError):
    code = "integrity_error"


class ExecutionError(FailariumError):
    code = "execution_error"


class ConflictError(FailariumError):
    code = "conflict_error"

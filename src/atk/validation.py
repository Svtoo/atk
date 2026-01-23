"""Validation result types for ATK.

Provides a simple dataclass for representing validation results with
specific error messages and optional exit codes.
"""

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of a validation operation.

    Attributes:
        is_valid: True if validation passed, False otherwise.
        errors: List of specific error messages if validation failed.
        error_code: Optional exit code when validation fails.
            The validation site knows best what error code to use.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    error_code: int | None = None


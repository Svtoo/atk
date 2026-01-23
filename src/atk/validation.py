"""Validation result types for ATK.

Provides a simple dataclass for representing validation results with
specific error messages.
"""

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of a validation operation.

    Attributes:
        is_valid: True if validation passed, False otherwise.
        errors: List of specific error messages if validation failed.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)


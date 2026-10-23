"""Shared application contracts; no HTTP dependencies."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, NoReturn


# PUBLIC_INTERFACE
class AppError(Exception):
    """Transport-independent failure with a stable machine-readable code."""

    # PUBLIC_INTERFACE
    def __init__(self, status: int, code: str, detail: str):
        """Describe the HTTP translation without exposing internal exceptions."""
        self.status, self.code, self.detail = status, code, detail
        super().__init__(detail)


# PUBLIC_INTERFACE
@dataclass(frozen=True)
class Identity:
    """Validated external subject and plant scope supplied by a trusted adapter."""

    subject: str
    plant_id: str
    role: Literal["Operator", "Engineer", "Manager"]
    active: bool = True


# PUBLIC_INTERFACE
def utcnow() -> str:
    """Return a fixed-width UTC ISO-8601 timestamp.

    Microseconds are always rendered so that stored timestamps sort lexically in
    chronological order (``isoformat`` otherwise omits a zero fraction).
    """
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


# PUBLIC_INTERFACE
def held(*questions: str) -> NoReturn:
    """Refuse execution of a use case that needs an unresolved product decision."""
    raise AppError(501, "rule_unresolved", "Awaiting decisions: " + ", ".join(questions))

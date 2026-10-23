"""Shared application contracts; no HTTP dependencies."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, NoReturn

# The three decided roles (DL-01 / US-2). The permission matrix is settled; how a
# request's role is determined without sign-in is not (D-35).
ROLES = ("Operator", "Engineer", "Manager")

# Open questions that block every business endpoint until a request-context
# mechanism is decided. Sign-in is out of MVP scope (DL-10), so no identity
# provider, sign-in flow, or token validation exists to supply these values.
CONTEXT_QUESTIONS = (
    "D-35: role and plant scope without sign-in",
    "D-36: record attribution without sign-in",
)


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
class RequestContext:
    """Role, plant scope and acting person a business operation needs.

    Sign-in is out of MVP scope (DL-10). This contract deliberately says nothing
    about where the values come from: role and plant-scope determination is held
    on D-35 and record attribution (``actor``) on D-36. No production source is
    implemented; see ``app.api.request_context``.
    """

    actor: str
    plant_id: str
    role: Literal["Operator", "Engineer", "Manager"]


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

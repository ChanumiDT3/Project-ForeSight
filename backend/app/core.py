"""Shared application contracts; no HTTP dependencies."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

# The three decided roles (DL-01 / US-2). A user's role comes from the users
# table, never from anything the client sends (Q1a).
ROLES = ("Operator", "Engineer", "Manager")

# Request header carrying the user chosen in the "Who are you?" popup (Q1a).
# It only selects an existing active user; it cannot change that user's role.
USER_ID_HEADER = "X-User-Id"

# Alert and work-order states that count as active / "open" (DL-06, Q5a).
ACTIVE_STATES = ("Open", "In Progress")


# PUBLIC_INTERFACE
class AppError(Exception):
    """Transport-independent failure with a stable machine-readable code."""

    # PUBLIC_INTERFACE
    def __init__(self, status: int, code: str, detail: str, extra: dict | None = None):
        """Describe the HTTP translation without exposing internal exceptions.

        ``extra`` carries small, safe, machine-readable fields (for example the
        identifier of an existing active work order) added to the problem body.
        """
        self.status, self.code, self.detail = status, code, detail
        self.extra = extra or {}
        super().__init__(detail)


# PUBLIC_INTERFACE
@dataclass(frozen=True)
class RequestContext:
    """Acting user, their role and the configured plant for one request.

    Built only by ``app.identity.get_current_user`` from the stored user record
    and the configured plant ID (Q1a, Q1b). ``actor`` is the user ID written to
    every audit field; ``name`` is for display only.
    """

    actor: str
    plant_id: str
    role: Literal["Operator", "Engineer", "Manager"]
    name: str = ""


# PUBLIC_INTERFACE
def utcnow() -> str:
    """Return a fixed-width UTC ISO-8601 timestamp.

    Microseconds are always rendered so that stored timestamps sort lexically in
    chronological order (``isoformat`` otherwise omits a zero fraction).
    """
    return to_utc_text(datetime.now(timezone.utc))


# PUBLIC_INTERFACE
def to_utc_text(moment: datetime) -> str:
    """Render an aware datetime as the fixed-width UTC text used in storage."""
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")

"""Identity without sign-in: the single "get current user" function (Q1a).

Sign-in is out of MVP scope (DL-10). The frontend's "Who are you?" popup stores
the chosen user ID and sends it in the ``X-User-Id`` header. This module looks
that user up and takes the name and role from the stored record and the plant
from configuration (Q1b), never from anything else the client sends. Editing the
header can only select another real, active user; it cannot change a role.

Known, accepted limitation (Q1a): anyone who can reach the app can pick any
user, so the audit shows who the app was set to, not proof of who was at the
keyboard. This is accepted for a trusted internal network with a small team.

All identity logic lives in ``get_current_user`` so a real login can replace it
later without touching business endpoints.
"""
from typing import Annotated

from fastapi import Header, Request
from sqlalchemy import select

from app.core import ROLES, USER_ID_HEADER, AppError, RequestContext
from app.models import User
from app.storage import transaction


# PUBLIC_INTERFACE
def configured_plant(request: Request) -> str:
    """Return the fixed plant ID stamped on every record (Q1b).

    Request FORESIGHT_PLANT_ID from the user through deployment configuration.
    """
    plant_id = request.app.state.plant_id
    if not plant_id:
        raise AppError(503, "plant_unconfigured", "FORESIGHT_PLANT_ID must be configured")
    return plant_id


# PUBLIC_INTERFACE
def get_current_user(
    request: Request,
    user_id: Annotated[str | None, Header(
        alias=USER_ID_HEADER,
        description="ID of the user chosen in the 'Who are you?' popup (from GET /v1/users)",
    )] = None,
) -> RequestContext:
    """Resolve the acting user from the X-User-Id header.

    Returns the user's ID, name and role from the users table and the configured
    plant. A missing, unknown, other-plant or deactivated user ID returns 401
    ``unknown_user``; the frontend then clears its stored choice and shows the
    popup again. Role permission checks (403) are applied by the endpoints.
    """
    plant_id = configured_plant(request)
    engine = request.app.state.engine
    if engine is None:
        raise AppError(503, "database_unconfigured", "FORESIGHT_DATABASE_URL must be configured")
    if not user_id or not user_id.strip():
        raise AppError(401, "unknown_user", "Select a user to continue")
    with transaction(engine) as session:
        user = session.scalar(select(User).where(
            User.id == user_id.strip(), User.plant_id == plant_id, User.active.is_(True)))
        if user is None or user.role not in ROLES:
            raise AppError(401, "unknown_user", "Unknown or deactivated user; select a user again")
        return RequestContext(actor=user.id, plant_id=plant_id, role=user.role, name=user.name)

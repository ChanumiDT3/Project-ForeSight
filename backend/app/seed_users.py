"""Load development-maintained users into the MVP user directory."""
import json
import os
import sys
from pathlib import Path

from sqlalchemy import func, inspect, select

from app.core import ROLES, utcnow
from app.models import User
from app.settings import load_environment
from app.storage import make_engine, transaction

DEFAULT_SEED = Path(__file__).resolve().parent.parent / "seed" / "users.json"
FIELDS = {"id", "name", "email", "role", "active"}


# PUBLIC_INTERFACE
def validate_records(records) -> list[dict]:
    """Validate all seed rows before any database write occurs."""
    if not isinstance(records, list):
        raise ValueError("Seed file must contain a JSON list of users")

    problems = []
    identifiers = set()
    emails = set()
    valid = []

    for index, record in enumerate(records, start=1):
        label = f"entry {index}"
        if not isinstance(record, dict) or set(record) != FIELDS:
            problems.append(f"{label}: needs exactly the fields {sorted(FIELDS)}")
            continue

        normalized = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in record.items()
        }
        for field in ("id", "name", "email"):
            if not isinstance(normalized[field], str) or not normalized[field]:
                problems.append(f"{label}: {field} must be a nonblank string")
        if normalized["role"] not in ROLES:
            problems.append(f"{label}: role must be one of {', '.join(ROLES)}")
        if not isinstance(normalized["active"], bool):
            problems.append(f"{label}: active must be true or false")
        if isinstance(normalized["email"], str) and "@" not in normalized["email"]:
            problems.append(f"{label}: email must be a work email address")
        if normalized["id"] in identifiers:
            problems.append(f"{label}: duplicate id {normalized['id']}")
        email_key = normalized["email"].lower() if isinstance(normalized["email"], str) else None
        if email_key in emails:
            problems.append(f"{label}: duplicate email")

        identifiers.add(normalized["id"])
        emails.add(email_key)
        valid.append(normalized)

    if problems:
        raise ValueError("Invalid seed file:\n" + "\n".join(problems))
    return valid


# PUBLIC_INTERFACE
def seed_users(engine, plant_id: str, records) -> dict:
    """Upsert users for a plant while leaving unlisted historical users untouched."""
    if not plant_id:
        raise ValueError("FORESIGHT_PLANT_ID must be configured")

    validated = validate_records(records)
    created = 0
    updated = 0

    with transaction(engine, write=True) as session:
        for values in validated:
            user = session.get(User, values["id"])
            timestamp = utcnow()
            if user is None:
                session.add(
                    User(
                        plant_id=plant_id,
                        created_at=timestamp,
                        updated_at=timestamp,
                        **values,
                    )
                )
                created += 1
                continue

            if user.plant_id != plant_id:
                raise ValueError(f"User {values['id']} belongs to another plant")
            if any(
                getattr(user, field) != values[field]
                for field in ("name", "email", "role", "active")
            ):
                for field in ("name", "email", "role", "active"):
                    setattr(user, field, values[field])
                user.updated_at = timestamp
                updated += 1

        session.flush()
        listed = {values["id"] for values in validated}
        unlisted = [
            user_id
            for user_id in session.scalars(select(User.id).where(User.plant_id == plant_id))
            if user_id not in listed
        ]

    return {"created": created, "updated": updated, "unlisted": sorted(unlisted)}


# PUBLIC_INTERFACE
def seed_users_if_empty(engine, plant_id: str, source: Path = DEFAULT_SEED) -> dict | None:
    """Populate the user list from the seed file only when the plant has no users.

    Used at application startup so a fresh local database is ready for the
    identity popup. Existing user directories are never modified here.

    Returns the ``seed_users`` summary when users were created, or ``None``
    when the plant already has users. Raises ``ValueError`` when the users
    table does not exist yet (migrations not applied) or the seed file is
    invalid, and ``OSError`` when the seed file cannot be read.
    """
    if not inspect(engine).has_table(User.__tablename__):
        raise ValueError("The users table does not exist; run 'alembic upgrade head' first")
    with transaction(engine) as session:
        existing = session.scalar(
            select(func.count()).select_from(User).where(User.plant_id == plant_id)
        )
    if existing:
        return None
    records = json.loads(source.read_text(encoding="utf-8"))
    return seed_users(engine, plant_id, records)


# PUBLIC_INTERFACE
def main(argv=None) -> int:
    """Execute the seed-file import and return a conventional process exit code."""
    arguments = sys.argv[1:] if argv is None else argv
    source = Path(arguments[0]) if arguments else DEFAULT_SEED
    # Real environment variables win; otherwise backend/.env (or .env.example).
    load_environment()
    database_url = os.getenv("FORESIGHT_DATABASE_URL")
    plant_id = os.getenv("FORESIGHT_PLANT_ID")

    if not database_url or not plant_id:
        print(
            "FORESIGHT_DATABASE_URL and FORESIGHT_PLANT_ID must be configured",
            file=sys.stderr,
        )
        return 2

    try:
        records = json.loads(source.read_text(encoding="utf-8"))
        engine = make_engine(database_url)
        try:
            summary = seed_users(engine, plant_id, records)
        finally:
            engine.dispose()
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"Users created: {summary['created']}, updated: {summary['updated']}")
    if summary["unlisted"]:
        print("Stored users not in seed file (unchanged): " + ", ".join(summary["unlisted"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

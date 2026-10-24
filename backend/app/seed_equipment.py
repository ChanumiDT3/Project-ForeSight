"""Load development-maintained equipment so reading entry has parameters to choose.

The Log Reading screen only offers parameters that are configured on registered
machines (UI Wireframes S3). On a fresh database no machine exists, so the
Parameter dropdown is empty. This module registers the machines listed in
``seed/equipment.json`` through the normal ``equipment.register`` use case, so
every seeded record passes the same validation as an Engineer's registration.

Seeding never modifies existing machines: machines whose Equipment ID already
exists are skipped, and startup seeding only runs when the plant has none.
"""
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import func, inspect, select

from app import equipment
from app.core import AppError, RequestContext
from app.models import Machine, User
from app.schemas import MachineInput
from app.settings import load_environment
from app.storage import make_engine, transaction

DEFAULT_SEED = Path(__file__).resolve().parent.parent / "seed" / "equipment.json"
RULES_FILE = Path(__file__).with_name("rules.json")

# Only Engineers register equipment (DL-01), so the seed is attributed to one.
REGISTERING_ROLE = "Engineer"


# PUBLIC_INTERFACE
def load_rules() -> dict:
    """Return the parameter rules the API uses for registration validation."""
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


# PUBLIC_INTERFACE
def validate_seed(document) -> tuple[str, list[MachineInput]]:
    """Validate the seed document shape before any database write occurs.

    Returns the registering user ID and the parsed machine inputs. Raises
    ``ValueError`` listing every problem when the document is invalid.
    """
    if not isinstance(document, dict):
        raise ValueError("Equipment seed must be a JSON object")
    registered_by = document.get("registered_by")
    machines = document.get("machines")
    problems = []
    if not isinstance(registered_by, str) or not registered_by.strip():
        problems.append("registered_by must be a nonblank user ID")
    if not isinstance(machines, list):
        problems.append("machines must be a JSON list")
        machines = []

    parsed, identifiers = [], set()
    for index, record in enumerate(machines, start=1):
        try:
            machine = MachineInput.model_validate(record)
        except ValidationError as error:
            problems.append(f"machine {index}: {error.errors()[0]['msg']}")
            continue
        if machine.equipment_id in identifiers:
            problems.append(f"machine {index}: duplicate equipment_id {machine.equipment_id}")
        identifiers.add(machine.equipment_id)
        parsed.append(machine)

    if problems:
        raise ValueError("Invalid equipment seed file:\n" + "\n".join(problems))
    return registered_by.strip(), parsed


def _registering_context(session, plant_id: str, user_id: str) -> RequestContext:
    """Attribute seeded records to an active Engineer of the configured plant."""
    user = session.get(User, user_id)
    if user is None or user.plant_id != plant_id or not user.active:
        raise ValueError(f"Seed user {user_id} is not an active user of plant {plant_id}")
    if user.role != REGISTERING_ROLE:
        raise ValueError(f"Seed user {user_id} must be an {REGISTERING_ROLE} to register equipment")
    return RequestContext(actor=user.id, plant_id=plant_id, role=user.role, name=user.name)


# PUBLIC_INTERFACE
def seed_equipment(engine, plant_id: str, document, rules: dict | None = None) -> dict:
    """Register seed machines that do not exist yet, atomically.

    Existing Equipment IDs are skipped and left untouched. Any validation
    failure rolls back the whole seed and raises ``ValueError``.
    """
    if not plant_id:
        raise ValueError("FORESIGHT_PLANT_ID must be configured")
    registered_by, machines = validate_seed(document)
    rules = rules or load_rules()
    created, skipped = [], []

    with transaction(engine, write=True) as session:
        context = _registering_context(session, plant_id, registered_by)
        for machine in machines:
            exists = session.scalar(
                select(Machine.id).where(
                    Machine.plant_id == plant_id,
                    Machine.equipment_id == machine.equipment_id,
                )
            )
            if exists:
                skipped.append(machine.equipment_id)
                continue
            try:
                equipment.register(session, context, machine, rules)
            except AppError as error:
                raise ValueError(f"{machine.equipment_id}: {error.detail}") from error
            created.append(machine.equipment_id)

    return {"created": created, "skipped": skipped}


# PUBLIC_INTERFACE
def seed_equipment_if_empty(engine, plant_id: str, source: Path = DEFAULT_SEED,
                            rules: dict | None = None) -> dict | None:
    """Populate equipment from the seed file only when the plant has no machines.

    Used at application startup so a fresh local database offers parameters on
    the Log Reading screen. Returns the ``seed_equipment`` summary, or ``None``
    when machines already exist. Raises ``ValueError`` when tables are missing
    or the seed is invalid, and ``OSError`` when the file cannot be read.
    """
    if not inspect(engine).has_table(Machine.__tablename__):
        raise ValueError("The machines table does not exist; run 'alembic upgrade head' first")
    with transaction(engine) as session:
        existing = session.scalar(
            select(func.count()).select_from(Machine).where(Machine.plant_id == plant_id)
        )
    if existing:
        return None
    document = json.loads(source.read_text(encoding="utf-8"))
    return seed_equipment(engine, plant_id, document, rules)


# PUBLIC_INTERFACE
def main(argv=None) -> int:
    """Register missing seed machines and return a conventional process exit code."""
    arguments = sys.argv[1:] if argv is None else argv
    source = Path(arguments[0]) if arguments else DEFAULT_SEED
    # Real environment variables win; otherwise backend/.env (or .env.example).
    load_environment()
    database_url = os.getenv("FORESIGHT_DATABASE_URL")
    plant_id = os.getenv("FORESIGHT_PLANT_ID")

    if not database_url or not plant_id:
        print("FORESIGHT_DATABASE_URL and FORESIGHT_PLANT_ID must be configured", file=sys.stderr)
        return 2

    try:
        document = json.loads(source.read_text(encoding="utf-8"))
        engine = make_engine(database_url)
        try:
            summary = seed_equipment(engine, plant_id, document)
        finally:
            engine.dispose()
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print("Machines created: " + (", ".join(summary["created"]) or "none"))
    if summary["skipped"]:
        print("Existing machines (unchanged): " + ", ".join(summary["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

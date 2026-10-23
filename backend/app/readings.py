"""Readings and Detection own validation, scoring, and breach persistence."""
from decimal import Decimal

from app.cases import accept_breach
from app.core import AppError
from app.domain import plain, score, validate_value
from app.equipment import latest_reading
from app.models import Breach, Machine, Parameter, Reading
from app.storage import Repository, attributes, serialize


# PUBLIC_INTERFACE
def log_reading(session, context, body, rules):
    """Validate and persist a reading, breach, and consolidated alert atomically."""
    repo = Repository(session, context.plant_id)
    parameter = repo.get(Parameter, body.parameter_id)
    machine = repo.get(Machine, parameter.machine_id)

    validate_value(body.value, parameter.minimum, parameter.maximum, parameter.precision, parameter.unit)
    latest = latest_reading(session, context, parameter.id)
    if parameter.cumulative and latest and body.value < Decimal(latest.value):
        raise AppError(
            422,
            "decreasing_reading",
            f"Cannot be lower than the latest reading ({latest.value})",
        )

    compared = body.value
    runtime_missing = parameter.kind == "runtime_hours" and machine.baseline is None
    if parameter.kind == "runtime_hours" and not runtime_missing:
        if body.value < Decimal(machine.baseline):
            raise AppError(422, "below_baseline", "Runtime reading cannot be below baseline")
        compared -= Decimal(machine.baseline)

    reading = Reading(
        **attributes(context),
        machine_id=machine.id,
        parameter_id=parameter.id,
        value=plain(body.value),
        source="manual",
    )
    session.add(reading)
    session.flush()

    alert = None
    if not runtime_missing and compared > Decimal(parameter.threshold):
        breakdown = score(
            compared,
            Decimal(parameter.threshold),
            machine.criticality,
            rules["exceedance_bands"],
        )
        alert = accept_breach(session, context, machine, parameter, compared, breakdown, reading.created_at)
        breach = Breach(
            **attributes(context),
            reading_id=reading.id,
            machine_id=machine.id,
            parameter_id=parameter.id,
            alert_id=alert.id,
            value=plain(compared),
            threshold=parameter.threshold,
            **breakdown,
        )
        breach.created_at = reading.created_at
        session.add(breach)
        session.flush()

    return {
        "reading": serialize(reading),
        "alert_id": alert.id if alert else None,
        "runtime_state": "Baseline missing" if runtime_missing else None,
    }

"""Readings and Detection own input validation and exact priority scoring."""
from decimal import Decimal

from sqlalchemy import select

from app.cases import accept_breach
from app.core import AppError, held
from app.domain import plain, score, validate_value
from app.models import Breach, Machine, Parameter, Reading
from app.storage import Repository, attributes, serialize


# PUBLIC_INTERFACE
def log_reading(session, context, body, rules):
    """Validate and save one immutable reading, breach and alert in one transaction."""
    repo = Repository(session, context.plant_id)
    parameter = repo.get(Parameter, body.parameter_id)
    machine = repo.get(Machine, parameter.machine_id)
    if parameter.kind == "custom":
        # Whether a custom stream may decrease depends on the cumulative marking.
        held("D-24: custom cumulative marking")

    validate_value(body.value, parameter.minimum, parameter.maximum, parameter.precision, parameter.unit)
    latest = session.scalar(select(Reading).where(
        Reading.parameter_id == parameter.id,
        Reading.plant_id == context.plant_id,
    ).order_by(Reading.created_at.desc(), Reading.id.desc()).limit(1))
    if parameter.cumulative and latest and body.value < Decimal(latest.value):
        raise AppError(422, "decreasing_reading", "Cumulative readings cannot decrease")

    compared = body.value
    runtime_missing = parameter.kind == "runtime_hours" and machine.baseline is None
    if parameter.kind == "runtime_hours" and not runtime_missing:
        if body.value < Decimal(machine.baseline):
            raise AppError(422, "below_baseline", "Runtime reading cannot be below baseline")
        # Runtime breach compares hours since service against the interval.
        compared -= Decimal(machine.baseline)

    reading = Reading(
        **attributes(context),
        machine_id=machine.id,
        parameter_id=parameter.id,
        value=plain(body.value),
    )
    session.add(reading)
    session.flush()

    alert = None
    # A missing baseline is bad data: never treated as zero, no runtime alert.
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
        # Reading and breach time are identical; the user never supplies either.
        breach.created_at = reading.created_at
        session.add(breach)
        session.flush()

    return dict(
        reading=serialize(reading),
        alert_id=alert.id if alert else None,
        runtime_state="Baseline missing" if runtime_missing else None,
    )

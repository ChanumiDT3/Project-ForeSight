"""Equipment Registry use cases; caller owns transaction."""
from decimal import Decimal

from sqlalchemy import select

from app.core import AppError, held, utcnow
from app.domain import plain, validate_value
from app.models import Alert, Machine, Parameter, Reading
from app.storage import Repository, attributes, serialize

ACTIVE_ALERT_STATES = ("Open", "In Progress")


def _check_threshold(threshold: Decimal, spec: dict):
    """Threshold must lie within the parameter's inclusive valid range (D-29)."""
    if not Decimal(spec["minimum"]) <= threshold <= Decimal(spec["maximum"]):
        raise AppError(422, "invalid_threshold", "Threshold must be within the inclusive valid range")


def _parameter_spec(item, rules) -> dict:
    """Resolve unit, valid range, precision and cumulative flag for one parameter."""
    if item.kind == "custom":
        if any(v is None for v in (item.unit, item.minimum, item.maximum, item.precision)):
            raise AppError(422, "custom_required", "Custom unit, precision and valid range required")
        if item.minimum > item.maximum:
            raise AppError(422, "invalid_range", "Minimum cannot exceed maximum")
        # How a custom parameter is marked cumulative is unresolved (D-24 residual).
        return dict(
            unit=item.unit,
            minimum=plain(item.minimum),
            maximum=plain(item.maximum),
            precision=item.precision,
            cumulative=None,
        )
    if any(v is not None for v in (item.unit, item.minimum, item.maximum, item.precision)):
        raise AppError(422, "fixed_rules", "Named parameter units and valid ranges come from configuration")
    return dict(rules["parameters"][item.kind])


# PUBLIC_INTERFACE
def register(session, identity, body, rules):
    """Register configured equipment atomically; held variants save nothing.

    All input is validated before the first write so a rejected request never
    depends on rollback to undo partial inserts.
    """
    if not body.parameters:
        held("D-15")

    runtime = any(p.kind == "runtime_hours" for p in body.parameters)
    if runtime:
        if body.baseline is None or body.current_meter is None:
            raise AppError(422, "runtime_required", "Runtime baseline and current meter are required")
        for value in (body.baseline, body.current_meter):
            validate_value(value, "0", "200000", 1, "hours")
        if body.baseline > body.current_meter:
            raise AppError(422, "invalid_baseline", "Baseline cannot exceed current meter")
    elif body.baseline is not None or body.current_meter is not None:
        raise AppError(422, "unexpected_runtime", "Runtime values require a runtime parameter")

    specs = []
    for item in body.parameters:
        spec = _parameter_spec(item, rules)
        _check_threshold(item.threshold, spec)
        specs.append(spec)

    if session.scalar(select(Machine.id).where(
        Machine.plant_id == identity.plant_id,
        Machine.equipment_id == body.equipment_id,
    )):
        raise AppError(409, "duplicate_id", "ID already exists")

    now = utcnow()
    machine = Machine(
        **attributes(identity),
        equipment_id=body.equipment_id,
        name=body.name,
        location=body.location,
        equipment_type=body.equipment_type,
        criticality=body.criticality,
        baseline=plain(body.baseline) if runtime else None,
        # The registration meter is captured but not saved as a reading (D-12 residual).
        registration_meter=plain(body.current_meter) if runtime else None,
        updated_by=identity.subject,
        updated_at=now,
    )
    session.add(machine)
    session.flush()

    parameters = []
    for item, spec in zip(body.parameters, specs):
        parameter = Parameter(
            **attributes(identity),
            machine_id=machine.id,
            kind=item.kind,
            name=item.name,
            threshold=plain(item.threshold),
            threshold_type="max",
            suggested_action=item.suggested_action,
            **spec,
            updated_by=identity.subject,
            updated_at=now,
        )
        session.add(parameter)
        parameters.append(parameter)
    session.flush()
    return dict(**serialize(machine), parameters=[serialize(parameter) for parameter in parameters])


# PUBLIC_INTERFACE
def machine_detail(session, identity, identifier):
    """Return equipment with derived alert status and nonpersistent runtime counter."""
    repo = Repository(session, identity.plant_id)
    machine = repo.get(Machine, identifier)
    parameters = session.scalars(select(Parameter).where(
        Parameter.machine_id == machine.id,
        Parameter.plant_id == identity.plant_id,
    ).order_by(Parameter.created_at, Parameter.id)).all()
    active = session.scalars(select(Alert.id).where(
        Alert.plant_id == identity.plant_id,
        Alert.machine_id == machine.id,
        Alert.status.in_(ACTIVE_ALERT_STATES),
    )).all()
    result = dict(
        **serialize(machine),
        parameters=[serialize(parameter) for parameter in parameters],
        status="At Risk" if active else "Healthy",
        active_alert_count=len(active),
    )
    for parameter in parameters:
        if parameter.kind == "runtime_hours":
            latest = session.scalar(select(Reading).where(
                Reading.parameter_id == parameter.id,
                Reading.plant_id == identity.plant_id,
            ).order_by(Reading.created_at.desc(), Reading.id.desc()).limit(1))
            result["runtime_state"] = "Baseline missing" if machine.baseline is None else "Ready"
            # Derived on read only; whether it is stored is unresolved (D-19).
            result["hours_since_service"] = None
            if machine.baseline is not None and latest:
                counter = Decimal(latest.value) - Decimal(machine.baseline)
                if counter < 0:
                    result["runtime_state"] = "Data error"
                else:
                    result["hours_since_service"] = plain(counter)
    return result


# PUBLIC_INTERFACE
def edit_criticality(session, identity, identifier, body):
    """Change only future criticality evaluations, recording actor and time."""
    machine = Repository(session, identity.plant_id).get(Machine, identifier)
    machine.criticality = body.criticality
    machine.updated_by, machine.updated_at = identity.subject, utcnow()
    session.flush()
    return serialize(machine)


# PUBLIC_INTERFACE
def edit_details(session, identity, identifier, body):
    """Edit equipment descriptions without mutating existing alert snapshots."""
    machine = Repository(session, identity.plant_id).get(Machine, identifier)
    machine.name, machine.location = body.name, body.location
    machine.equipment_type = body.equipment_type
    machine.updated_by, machine.updated_at = identity.subject, utcnow()
    session.flush()
    return serialize(machine)


# PUBLIC_INTERFACE
def edit_suggested_action(session, identity, identifier, body):
    """Edit parameter guidance for subsequently created alerts."""
    parameter = Repository(session, identity.plant_id).get(Parameter, identifier)
    parameter.suggested_action = body.suggested_action
    parameter.updated_by, parameter.updated_at = identity.subject, utcnow()
    session.flush()
    return serialize(parameter)


# PUBLIC_INTERFACE
def edit_threshold(session, identity, identifier, body):
    """Change only future threshold evaluations without rewriting existing breaches."""
    parameter = Repository(session, identity.plant_id).get(Parameter, identifier)
    _check_threshold(body.threshold, dict(minimum=parameter.minimum, maximum=parameter.maximum))
    parameter.threshold = plain(body.threshold)
    parameter.updated_by, parameter.updated_at = identity.subject, utcnow()
    session.flush()
    return serialize(parameter)

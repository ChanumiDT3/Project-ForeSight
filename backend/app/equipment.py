"""Equipment Registry use cases; callers own the active transaction."""
from decimal import Decimal

from sqlalchemy import func, select

from app.core import ACTIVE_STATES, AppError, utcnow
from app.domain import plain, validate_value
from app.models import Alert, BaselineHistory, Machine, Parameter, Reading
from app.storage import Repository, attributes, serialize

MONITORED = "Monitored"
NOT_MONITORED = "Not monitored"


def _check_threshold(threshold: Decimal, spec: dict):
    """Ensure a threshold is inside the configured inclusive valid range."""
    if not Decimal(spec["minimum"]) <= threshold <= Decimal(spec["maximum"]):
        raise AppError(422, "invalid_threshold", "Threshold must be within the inclusive valid range")


def _parameter_spec(item, rules) -> dict:
    """Resolve validation and cumulative behavior for a parameter input."""
    if item.kind == "custom":
        if any(value is None for value in (item.unit, item.minimum, item.maximum, item.precision)):
            raise AppError(422, "custom_required", "Custom unit, precision and valid range required")
        if item.minimum > item.maximum:
            raise AppError(422, "invalid_range", "Minimum cannot exceed maximum")
        return {
            "unit": item.unit,
            "minimum": plain(item.minimum),
            "maximum": plain(item.maximum),
            "precision": item.precision,
            "cumulative": bool(item.cumulative),
        }

    if any(value is not None for value in (item.unit, item.minimum, item.maximum, item.precision)):
        raise AppError(422, "fixed_rules", "Named parameter units and valid ranges come from configuration")

    spec = dict(rules["parameters"][item.kind])
    if item.cumulative is not None and item.cumulative != spec["cumulative"]:
        raise AppError(422, "fixed_rules", "Named parameter cumulative behavior comes from configuration")
    return spec


def _validate_runtime_values(baseline, current_meter, rules):
    """Validate required baseline/current runtime meters."""
    if baseline is None or current_meter is None:
        raise AppError(422, "runtime_required", "Runtime baseline and current meter are required")
    spec = rules["parameters"]["runtime_hours"]
    for value in (baseline, current_meter):
        validate_value(value, spec["minimum"], spec["maximum"], spec["precision"], spec["unit"])
    if baseline > current_meter:
        raise AppError(422, "invalid_baseline", "Baseline cannot exceed current meter")


def _new_parameter(context, machine, item, spec, now):
    """Create an unsaved attributed parameter row."""
    return Parameter(
        **attributes(context),
        machine_id=machine.id,
        kind=item.kind,
        name=item.name,
        threshold=plain(item.threshold),
        threshold_type="max",
        suggested_action=item.suggested_action,
        **spec,
        updated_by=context.actor,
        updated_at=now,
    )


# PUBLIC_INTERFACE
def latest_reading(session, context, parameter_id):
    """Return the latest stored reading for a parameter, if any."""
    return session.scalar(
        select(Reading)
        .where(
            Reading.parameter_id == parameter_id,
            Reading.plant_id == context.plant_id,
        )
        .order_by(Reading.created_at.desc(), Reading.id.desc())
        .limit(1)
    )


# PUBLIC_INTERFACE
def runtime_parameter(session, context, machine_id):
    """Return the machine runtime-hours parameter, if configured."""
    return session.scalar(
        select(Parameter).where(
            Parameter.machine_id == machine_id,
            Parameter.plant_id == context.plant_id,
            Parameter.kind == "runtime_hours",
        )
    )


def _parameters(session, context, machine_id):
    """Return a machine's parameters in durable creation order."""
    return session.scalars(
        select(Parameter)
        .where(Parameter.machine_id == machine_id, Parameter.plant_id == context.plant_id)
        .order_by(Parameter.created_at, Parameter.id)
    ).all()


def _parameter_view(session, context, parameter):
    """Serialize a parameter with the latest value for UI prefill."""
    latest = latest_reading(session, context, parameter.id)
    return {
        **serialize(parameter),
        "latest_value": latest.value if latest else None,
        "latest_reading_at": latest.created_at if latest else None,
    }


# PUBLIC_INTERFACE
def register(session, context, body, rules):
    """Register a machine atomically, allowing it to begin Not monitored."""
    runtime_count = sum(parameter.kind == "runtime_hours" for parameter in body.parameters)
    if runtime_count > 1:
        raise AppError(422, "duplicate_runtime", "A machine has at most one runtime-hours parameter")

    runtime = runtime_count == 1
    if runtime:
        _validate_runtime_values(body.baseline, body.current_meter, rules)
    elif body.baseline is not None or body.current_meter is not None:
        raise AppError(422, "unexpected_runtime", "Runtime values require a runtime parameter")

    specs = []
    for item in body.parameters:
        spec = _parameter_spec(item, rules)
        _check_threshold(item.threshold, spec)
        specs.append(spec)

    if session.scalar(
        select(Machine.id).where(
            Machine.plant_id == context.plant_id,
            Machine.equipment_id == body.equipment_id,
        )
    ):
        raise AppError(409, "duplicate_id", "ID already exists")

    now = utcnow()
    machine = Machine(
        **attributes(context),
        equipment_id=body.equipment_id,
        name=body.name,
        location=body.location,
        equipment_type=body.equipment_type,
        criticality=body.criticality,
        baseline=plain(body.baseline) if runtime else None,
        registration_meter=plain(body.current_meter) if runtime else None,
        updated_by=context.actor,
        updated_at=now,
    )
    session.add(machine)
    session.flush()

    parameters = [
        _new_parameter(context, machine, item, spec, now)
        for item, spec in zip(body.parameters, specs)
    ]
    session.add_all(parameters)
    session.flush()

    return {
        **serialize(machine),
        "parameters": [serialize(parameter) for parameter in parameters],
        "monitoring_state": MONITORED if parameters else NOT_MONITORED,
    }


# PUBLIC_INTERFACE
def add_parameter(session, context, identifier, body, rules):
    """Add a health parameter later to an existing plant-scoped machine."""
    machine = Repository(session, context.plant_id).get(Machine, identifier)
    spec = _parameter_spec(body, rules)
    _check_threshold(body.threshold, spec)
    now = utcnow()

    if body.kind == "runtime_hours":
        if runtime_parameter(session, context, machine.id):
            raise AppError(409, "duplicate_runtime", "A machine has at most one runtime-hours parameter")
        _validate_runtime_values(body.baseline, body.current_meter, rules)
        machine.baseline = plain(body.baseline)
        machine.registration_meter = plain(body.current_meter)
        machine.updated_by = context.actor
        machine.updated_at = now
    elif body.baseline is not None or body.current_meter is not None:
        raise AppError(422, "unexpected_runtime", "Runtime values require a runtime parameter")

    parameter = _new_parameter(context, machine, body, spec, now)
    session.add(parameter)
    session.flush()
    return serialize(parameter)


# PUBLIC_INTERFACE
def edit_cumulative(session, context, identifier, body):
    """Update a custom cumulative flag before any reading has been logged."""
    parameter = Repository(session, context.plant_id).get(Parameter, identifier)
    if parameter.kind != "custom":
        raise AppError(422, "fixed_rules", "Named parameter cumulative behavior comes from configuration")
    if latest_reading(session, context, parameter.id) is not None:
        raise AppError(409, "readings_exist", "The cumulative flag cannot change after a reading")
    parameter.cumulative = body.cumulative
    parameter.updated_by = context.actor
    parameter.updated_at = utcnow()
    session.flush()
    return serialize(parameter)


# PUBLIC_INTERFACE
def machine_page(session, context, offset, limit):
    """Return paginated machine records with derived monitoring and risk state."""
    rows, total = Repository(session, context.plant_id).page(
        Machine, offset, limit, order=(Machine.equipment_id,)
    )
    identifiers = [row.id for row in rows]
    parameter_counts = (
        dict(
            session.execute(
                select(Parameter.machine_id, func.count())
                .where(
                    Parameter.machine_id.in_(identifiers),
                    Parameter.plant_id == context.plant_id,
                )
                .group_by(Parameter.machine_id)
            ).all()
        )
        if identifiers
        else {}
    )
    alert_counts = (
        dict(
            session.execute(
                select(Alert.machine_id, func.count())
                .where(
                    Alert.machine_id.in_(identifiers),
                    Alert.plant_id == context.plant_id,
                    Alert.status.in_(ACTIVE_STATES),
                )
                .group_by(Alert.machine_id)
            ).all()
        )
        if identifiers
        else {}
    )
    return (
        [
            {
                **serialize(machine),
                "parameter_count": parameter_counts.get(machine.id, 0),
                "monitoring_state": (
                    MONITORED if parameter_counts.get(machine.id) else NOT_MONITORED
                ),
                "status": "At Risk" if alert_counts.get(machine.id) else "Healthy",
                "active_alert_count": alert_counts.get(machine.id, 0),
            }
            for machine in rows
        ],
        total,
    )


# PUBLIC_INTERFACE
def reading_targets(session, context, offset, limit):
    """Return machines, configured parameters, and latest values for reading entry."""
    rows, total = Repository(session, context.plant_id).page(
        Machine, offset, limit, order=(Machine.equipment_id,)
    )
    return (
        [
            {
                "id": machine.id,
                "equipment_id": machine.equipment_id,
                "name": machine.name,
                "location": machine.location,
                "baseline": machine.baseline,
                "parameters": [
                    _parameter_view(session, context, parameter)
                    for parameter in _parameters(session, context, machine.id)
                ],
            }
            for machine in rows
        ],
        total,
    )


# PUBLIC_INTERFACE
def machine_detail(session, context, identifier):
    """Return one machine with derived status, latest readings, and baseline history."""
    machine = Repository(session, context.plant_id).get(Machine, identifier)
    parameters = _parameters(session, context, machine.id)
    active_alert_count = session.scalar(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.plant_id == context.plant_id,
            Alert.machine_id == machine.id,
            Alert.status.in_(ACTIVE_STATES),
        )
    )
    history = session.scalars(
        select(BaselineHistory)
        .where(
            BaselineHistory.machine_id == machine.id,
            BaselineHistory.plant_id == context.plant_id,
        )
        .order_by(BaselineHistory.created_at.desc(), BaselineHistory.id)
    ).all()

    result = {
        **serialize(machine),
        "parameters": [_parameter_view(session, context, parameter) for parameter in parameters],
        "monitoring_state": MONITORED if parameters else NOT_MONITORED,
        "runtime_applicable": any(parameter.kind == "runtime_hours" for parameter in parameters),
        "status": "At Risk" if active_alert_count else "Healthy",
        "active_alert_count": active_alert_count,
        "baseline_history": [serialize(row) for row in history],
    }

    for parameter in parameters:
        if parameter.kind == "runtime_hours":
            latest = latest_reading(session, context, parameter.id)
            result["runtime_state"] = "Baseline missing" if machine.baseline is None else "Ready"
            result["hours_since_service"] = None
            if machine.baseline is not None and latest:
                counter = Decimal(latest.value) - Decimal(machine.baseline)
                if counter < 0:
                    result["runtime_state"] = "Data error"
                else:
                    result["hours_since_service"] = plain(counter)
    return result


# PUBLIC_INTERFACE
def edit_criticality(session, context, identifier, body):
    """Change only future criticality evaluations."""
    machine = Repository(session, context.plant_id).get(Machine, identifier)
    machine.criticality = body.criticality
    machine.updated_by = context.actor
    machine.updated_at = utcnow()
    session.flush()
    return serialize(machine)


# PUBLIC_INTERFACE
def edit_details(session, context, identifier, body):
    """Update descriptive fields without rewriting existing alert snapshots."""
    machine = Repository(session, context.plant_id).get(Machine, identifier)
    machine.name = body.name
    machine.location = body.location
    machine.equipment_type = body.equipment_type
    machine.updated_by = context.actor
    machine.updated_at = utcnow()
    session.flush()
    return serialize(machine)


# PUBLIC_INTERFACE
def edit_suggested_action(session, context, identifier, body):
    """Update future-alert guidance text for a parameter."""
    parameter = Repository(session, context.plant_id).get(Parameter, identifier)
    parameter.suggested_action = body.suggested_action
    parameter.updated_by = context.actor
    parameter.updated_at = utcnow()
    session.flush()
    return serialize(parameter)


# PUBLIC_INTERFACE
def edit_threshold(session, context, identifier, body):
    """Update a maximum threshold for future readings only."""
    parameter = Repository(session, context.plant_id).get(Parameter, identifier)
    _check_threshold(body.threshold, {"minimum": parameter.minimum, "maximum": parameter.maximum})
    parameter.threshold = plain(body.threshold)
    parameter.updated_by = context.actor
    parameter.updated_at = utcnow()
    session.flush()
    return serialize(parameter)

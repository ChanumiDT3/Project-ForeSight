"""Work-order lifecycle services; callers own the database transaction."""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core import ACTIVE_STATES, AppError, to_utc_text, utcnow
from app.domain import default_due_at, plain, priority_label, validate_value
from app.equipment import latest_reading, runtime_parameter
from app.models import (
    Alert,
    BaselineHistory,
    Machine,
    Parameter,
    Reading,
    User,
    WorkOrder,
    WorkOrderAddendum,
)
from app.storage import Repository, attributes, serialize

FINAL_STATES = ("Closed", "Cancelled")


def _load(session, context, identifier, version=None):
    """Load a work order and optionally validate its optimistic version."""
    work_order = Repository(session, context.plant_id).get(WorkOrder, identifier)
    if version is not None and work_order.version != version:
        raise AppError(409, "stale_version", "Work order version has changed; reload and retry")
    return work_order


def _require_editable(work_order):
    """Reject changes to final work orders."""
    if work_order.status == "Closed":
        raise AppError(409, "closed_read_only", "Closed work orders are read-only; add an addendum")
    if work_order.status not in ACTIVE_STATES:
        raise AppError(409, "invalid_transition", f"A {work_order.status} work order cannot be changed")


def _touch(work_order, context, timestamp):
    """Update mutation attribution and increment the version."""
    work_order.updated_by = context.actor
    work_order.updated_at = timestamp
    work_order.version += 1


def _reset_applies(work_order, runtime_applicable):
    """Determine whether closing this order must reset a runtime baseline."""
    return runtime_applicable and (
        work_order.raised_from_runtime_alert or work_order.scheduled_service
    )


# PUBLIC_INTERFACE
def work_order_view(session, context, work_order, include_addenda=False):
    """Serialize a work order with UI-required runtime and alert metadata."""
    alert_status = session.scalar(
        select(Alert.status).where(
            Alert.id == work_order.alert_id,
            Alert.plant_id == context.plant_id,
        )
    )
    runtime_applicable = runtime_parameter(session, context, work_order.machine_id) is not None
    result = {
        **serialize(work_order),
        "alert_status": alert_status,
        "runtime_applicable": runtime_applicable,
        "reset_applies": _reset_applies(work_order, runtime_applicable),
    }
    if include_addenda:
        addenda = session.scalars(
            select(WorkOrderAddendum)
            .where(
                WorkOrderAddendum.work_order_id == work_order.id,
                WorkOrderAddendum.plant_id == context.plant_id,
            )
            .order_by(WorkOrderAddendum.created_at, WorkOrderAddendum.id)
        ).all()
        result["addenda"] = [serialize(addendum) for addendum in addenda]
    return result


# PUBLIC_INTERFACE
def create(session, context, alert_id, rules):
    """Create an Open work order from an Open alert and move it In Progress."""
    alert = Repository(session, context.plant_id).get(Alert, alert_id)
    existing = session.scalar(
        select(WorkOrder.id).where(
            WorkOrder.plant_id == context.plant_id,
            WorkOrder.alert_id == alert.id,
            WorkOrder.status.in_(ACTIVE_STATES),
        )
    )
    if existing:
        raise AppError(
            409,
            "active_work_order_exists",
            "This alert already has an active work order",
            extra={"work_order_id": existing},
        )
    if alert.status != "Open":
        raise AppError(409, "invalid_transition", "A work order can be created only from an Open alert")

    machine = session.get(Machine, alert.machine_id)
    parameter = session.get(Parameter, alert.parameter_id)
    label = priority_label(alert.priority_score, rules)
    created = datetime.now(timezone.utc)
    timestamp = to_utc_text(created)
    record = attributes(context)
    record["created_at"] = timestamp

    work_order = WorkOrder(
        **record,
        alert_id=alert.id,
        machine_id=machine.id,
        status="Open",
        snapshot={
            "equipment_id": machine.equipment_id,
            "machine_name": machine.name,
            "machine_location": machine.location,
            "equipment_type": machine.equipment_type,
            "parameter_name": parameter.name,
            "parameter_kind": parameter.kind,
            "unit": parameter.unit,
            "fault_description": (
                f"{parameter.name} {alert.latest_value} {parameter.unit} "
                f"above safe limit {parameter.threshold} {parameter.unit}"
            ),
            "suggested_action": alert.suggested_action,
            "priority_score": alert.priority_score,
        },
        priority=label,
        assignee=None,
        due_at=default_due_at(created, label, rules),
        raised_from_runtime_alert=parameter.kind == "runtime_hours",
        scheduled_service=parameter.kind == "runtime_hours",
        parts_checklist=[],
        no_parts_used=False,
        version=1,
        updated_by=context.actor,
        updated_at=timestamp,
    )
    session.add(work_order)

    alert.status = "In Progress"
    alert.updated_by = context.actor
    alert.updated_at = timestamp
    alert.version += 1

    session.flush()
    return work_order_view(session, context, work_order)


# PUBLIC_INTERFACE
def edit(session, context, identifier, body, version):
    """Edit an active work order by any Engineer."""
    work_order = _load(session, context, identifier, version)
    _require_editable(work_order)

    changes = body.model_fields_set
    if not changes:
        raise AppError(422, "no_changes", "Send at least one editable work-order field")

    if "assignee" in changes and body.assignee is not None:
        assignee = session.scalar(
            select(User).where(
                User.id == body.assignee,
                User.plant_id == context.plant_id,
            )
        )
        if assignee is None or not assignee.active or assignee.role != "Engineer":
            raise AppError(422, "invalid_assignee", "Only active Engineers can be assigned")

    if "due_at" in changes:
        if body.due_at is None:
            raise AppError(422, "due_required", "A due date is required")
        if body.due_at < datetime.now(timezone.utc):
            raise AppError(422, "due_in_past", "Due date cannot be in the past")

    if "scheduled_service" in changes:
        if body.scheduled_service is None:
            raise AppError(422, "invalid_scheduled_service", "scheduled_service must be true or false")
        if work_order.raised_from_runtime_alert and not body.scheduled_service:
            raise AppError(
                422,
                "scheduled_service_locked",
                "Scheduled service is always performed for runtime-alert work",
            )

    if "assignee" in changes:
        work_order.assignee = body.assignee
    if "due_at" in changes:
        work_order.due_at = to_utc_text(body.due_at)
    if "scheduled_service" in changes:
        work_order.scheduled_service = body.scheduled_service

    _touch(work_order, context, utcnow())
    session.flush()
    return work_order_view(session, context, work_order)


# PUBLIC_INTERFACE
def start(session, context, identifier, version):
    """Move an Open work order to In Progress."""
    work_order = _load(session, context, identifier, version)
    if work_order.status != "Open":
        raise AppError(409, "invalid_transition", "Only an Open work order can be started")

    timestamp = utcnow()
    work_order.status = "In Progress"
    work_order.started_by = context.actor
    work_order.started_at = timestamp
    _touch(work_order, context, timestamp)
    session.flush()
    return work_order_view(session, context, work_order)


# PUBLIC_INTERFACE
def replace_checklist(session, context, identifier, body, version):
    """Replace the optional parts checklist on an active work order."""
    work_order = _load(session, context, identifier, version)
    _require_editable(work_order)
    work_order.parts_checklist = [item.model_dump(mode="json") for item in body.items]
    _touch(work_order, context, utcnow())
    session.flush()
    return work_order_view(session, context, work_order)


# PUBLIC_INTERFACE
def cancel(session, context, identifier, reason, version):
    """Cancel an active work order and return its linked alert to Open."""
    work_order = _load(session, context, identifier, version)
    if work_order.status not in ACTIVE_STATES:
        raise AppError(
            409,
            "invalid_transition",
            f"A {work_order.status} work order cannot be cancelled",
        )

    timestamp = utcnow()
    work_order.status = "Cancelled"
    work_order.cancellation_reason = reason
    work_order.cancelled_by = context.actor
    work_order.cancelled_at = timestamp
    _touch(work_order, context, timestamp)

    alert = session.get(Alert, work_order.alert_id)
    if alert.status == "In Progress":
        alert.status = "Open"
        alert.updated_by = context.actor
        alert.updated_at = timestamp
        alert.version += 1

    session.flush()
    return work_order_view(session, context, work_order)


def _closure_errors(body, reset, machine, runtime, latest):
    """Collect closure validation failures before the first state-changing write."""
    errors = []
    if not body.resolution_note.strip():
        errors.append("resolution_note: A resolution note is required")
    if bool(body.parts_used) == body.no_parts_used:
        errors.append("parts_used: List parts used or explicitly select no parts used")

    if not reset:
        if body.hour_meter_value is not None:
            errors.append("hour_meter_value: Not applicable because runtime does not reset")
        return errors

    if body.hour_meter_value is None:
        errors.append("hour_meter_value: The hour-meter reading at service is required")
        return errors

    try:
        validate_value(
            body.hour_meter_value,
            runtime.minimum,
            runtime.maximum,
            runtime.precision,
            runtime.unit,
        )
    except AppError as error:
        errors.append(f"hour_meter_value: {error.detail}")
        return errors

    for label, floor in (("previous baseline", machine.baseline),):
        if body.hour_meter_value < Decimal(floor):
            errors.append(f"hour_meter_value: Cannot be lower than the {label} ({floor})")

    if latest is not None and body.hour_meter_value < Decimal(latest.value):
        errors.append(
            f"hour_meter_value: Cannot be lower than the latest saved reading ({latest.value})"
        )
    return errors


# PUBLIC_INTERFACE
def close(session, context, identifier, body, version):
    """Close an In Progress order atomically, resetting runtime where applicable."""
    work_order = _load(session, context, identifier, version)
    if work_order.status in FINAL_STATES:
        raise AppError(409, "closed_read_only", f"The work order is already {work_order.status}")
    if work_order.status != "In Progress":
        raise AppError(409, "invalid_transition", "Start the work order before closing it")

    machine = session.get(Machine, work_order.machine_id)
    runtime = runtime_parameter(session, context, machine.id)
    reset = _reset_applies(work_order, runtime is not None)

    if reset and machine.baseline is None:
        raise AppError(422, "baseline_missing", "Baseline missing for this machine")

    latest = latest_reading(session, context, runtime.id) if reset else None
    errors = _closure_errors(body, reset, machine, runtime, latest)
    if errors:
        raise AppError(422, "closure_validation", "; ".join(errors))

    timestamp = utcnow()
    new_baseline = None

    if reset:
        reading = Reading(
            **attributes(context),
            machine_id=machine.id,
            parameter_id=runtime.id,
            value=plain(body.hour_meter_value),
            source="closure",
            work_order_id=work_order.id,
        )
        reading.created_at = timestamp
        session.add(reading)
        session.flush()

        new_baseline = reading.value
        history = BaselineHistory(
            **attributes(context),
            machine_id=machine.id,
            work_order_id=work_order.id,
            reading_id=reading.id,
            old_baseline=machine.baseline,
            new_baseline=new_baseline,
        )
        history.created_at = timestamp
        session.add(history)
        machine.baseline = new_baseline
        work_order.closure_reading_id = reading.id

    machine.last_service_at = timestamp
    machine.updated_by = context.actor
    machine.updated_at = timestamp

    work_order.status = "Closed"
    work_order.resolution_note = body.resolution_note.strip()
    work_order.parts_used = [item.model_dump(mode="json") for item in body.parts_used]
    work_order.no_parts_used = body.no_parts_used
    work_order.closed_by = context.actor
    work_order.closed_at = timestamp
    _touch(work_order, context, timestamp)

    alert = session.get(Alert, work_order.alert_id)
    alert.status = "Resolved"
    alert.updated_by = context.actor
    alert.updated_at = timestamp
    alert.version += 1

    session.flush()

    another_active_alert = session.scalar(
        select(Alert.id)
        .where(
            Alert.plant_id == context.plant_id,
            Alert.machine_id == machine.id,
            Alert.status.in_(ACTIVE_STATES),
        )
        .limit(1)
    )
    return {
        **work_order_view(session, context, work_order),
        "machine_status": "At Risk" if another_active_alert else "Healthy",
        "new_baseline": new_baseline,
        "last_service_at": timestamp,
    }


# PUBLIC_INTERFACE
def add_addendum(session, context, identifier, note):
    """Append an insert-only note to a Closed work order."""
    work_order = _load(session, context, identifier)
    if work_order.status != "Closed":
        raise AppError(409, "invalid_transition", "Addenda can be added only to Closed work orders")

    addendum = WorkOrderAddendum(
        **attributes(context),
        work_order_id=work_order.id,
        note=note,
    )
    session.add(addendum)
    session.flush()
    return serialize(addendum)

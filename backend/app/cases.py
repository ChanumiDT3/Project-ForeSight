"""Case Management owns alert consolidation, views, and dismissal."""
from sqlalchemy import select

from app.core import ACTIVE_STATES, AppError, utcnow
from app.domain import plain, priority_label
from app.models import Alert, Machine, Parameter, WorkOrder
from app.storage import Repository, attributes, serialize


# PUBLIC_INTERFACE
def accept_breach(session, context, machine, parameter, value, breakdown, timestamp):
    """Create or update one active alert while retaining its highest breakdown."""
    alert = session.scalar(
        select(Alert).where(
            Alert.plant_id == context.plant_id,
            Alert.machine_id == machine.id,
            Alert.parameter_id == parameter.id,
            Alert.status.in_(ACTIVE_STATES),
        )
    )
    if alert is None:
        alert = Alert(
            **attributes(context),
            machine_id=machine.id,
            parameter_id=parameter.id,
            status="Open",
            first_value=plain(value),
            latest_value=plain(value),
            first_breach_at=timestamp,
            latest_breach_at=timestamp,
            breach_count=1,
            priority_score=breakdown["priority_score"],
            breakdown=breakdown,
            suggested_action=parameter.suggested_action.strip()
            or f"Inspect {machine.name} – {parameter.name} above safe limit",
            version=1,
            updated_by=context.actor,
            updated_at=timestamp,
        )
        alert.created_at = timestamp
        session.add(alert)
    else:
        alert.latest_value = plain(value)
        alert.latest_breach_at = timestamp
        alert.breach_count += 1
        if breakdown["priority_score"] > alert.priority_score:
            alert.priority_score = breakdown["priority_score"]
            alert.breakdown = breakdown
        alert.version += 1
        alert.updated_by = context.actor
        alert.updated_at = timestamp
    session.flush()
    return alert


# PUBLIC_INTERFACE
def alert_views(session, context, alerts, rules):
    """Return queue/detail alert views enriched for the React UI."""
    machine_ids = {alert.machine_id for alert in alerts}
    parameter_ids = {alert.parameter_id for alert in alerts}
    alert_ids = [alert.id for alert in alerts]

    machines = (
        {
            machine.id: machine
            for machine in session.scalars(
                select(Machine).where(
                    Machine.id.in_(machine_ids),
                    Machine.plant_id == context.plant_id,
                )
            )
        }
        if alerts
        else {}
    )
    parameters = (
        {
            parameter.id: parameter
            for parameter in session.scalars(
                select(Parameter).where(
                    Parameter.id.in_(parameter_ids),
                    Parameter.plant_id == context.plant_id,
                )
            )
        }
        if alerts
        else {}
    )
    active_work = (
        dict(
            session.execute(
                select(WorkOrder.alert_id, WorkOrder.id).where(
                    WorkOrder.alert_id.in_(alert_ids),
                    WorkOrder.plant_id == context.plant_id,
                    WorkOrder.status.in_(ACTIVE_STATES),
                )
            )
        )
        if alerts
        else {}
    )

    return [
        {
            **serialize(alert),
            "priority_label": priority_label(alert.priority_score, rules),
            "machine": {
                "id": machines[alert.machine_id].id,
                "equipment_id": machines[alert.machine_id].equipment_id,
                "name": machines[alert.machine_id].name,
                "location": machines[alert.machine_id].location,
                "equipment_type": machines[alert.machine_id].equipment_type,
            },
            "parameter": {
                "id": parameters[alert.parameter_id].id,
                "name": parameters[alert.parameter_id].name,
                "kind": parameters[alert.parameter_id].kind,
                "unit": parameters[alert.parameter_id].unit,
                "threshold": parameters[alert.parameter_id].threshold,
            },
            "active_work_order_id": active_work.get(alert.id),
        }
        for alert in alerts
    ]


# PUBLIC_INTERFACE
def dismiss(session, context, identifier, reason, version, rules):
    """Dismiss an Open alert with no active work order using If-Match protection."""
    alert = Repository(session, context.plant_id).get(Alert, identifier)
    if alert.version != version:
        raise AppError(409, "stale_version", "Alert version has changed")

    active_work = session.scalar(
        select(WorkOrder.id).where(
            WorkOrder.plant_id == context.plant_id,
            WorkOrder.alert_id == identifier,
            WorkOrder.status.in_(ACTIVE_STATES),
        )
    )
    if alert.status != "Open" or active_work:
        raise AppError(
            409,
            "invalid_transition",
            "Only an Open alert without active work can be dismissed",
        )

    alert.status = "Dismissed"
    alert.dismissal_reason = reason
    alert.updated_by = context.actor
    alert.updated_at = utcnow()
    alert.version += 1
    session.flush()
    return alert_views(session, context, [alert], rules)[0]

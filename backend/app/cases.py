"""Case Management owns active alerts and guarded dismissal."""
from sqlalchemy import select

from app.core import AppError, utcnow
from app.domain import plain
from app.models import Alert, WorkOrder
from app.storage import Repository, attributes, serialize

# Alert and work-order states that count as active (DL-06).
ACTIVE_STATES = ("Open", "In Progress")


# PUBLIC_INTERFACE
def accept_breach(session, context, machine, parameter, value, breakdown, timestamp):
    """Consolidate synchronously inside the reading transaction; no lossy callbacks."""
    alert = session.scalar(select(Alert).where(
        Alert.plant_id == context.plant_id,
        Alert.machine_id == machine.id,
        Alert.parameter_id == parameter.id,
        Alert.status.in_(ACTIVE_STATES),
    ))
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
        # The alert is created at the same instant as the breaching reading.
        alert.created_at = timestamp
        session.add(alert)
    else:
        alert.latest_value, alert.latest_breach_at = plain(value), timestamp
        alert.breach_count += 1
        # Priority never decreases while active. On a lower repeat no choice of
        # highest/latest breakdown is made (CM-Q9); every original evaluation
        # remains queryable in breach history.
        alert.breakdown = breakdown if breakdown["priority_score"] >= alert.priority_score else None
        alert.priority_score = max(alert.priority_score, breakdown["priority_score"])
        alert.version += 1
        alert.updated_by, alert.updated_at = context.actor, timestamp
    session.flush()
    return alert


# PUBLIC_INTERFACE
def alert_view(alert):
    """Expose settled score state without assigning held score-to-label ownership."""
    result = serialize(alert)
    result["priority_label"] = None
    result["held_rules"] = ["CM-Q8"]
    if alert.breakdown is None:
        result["held_rules"].append("CM-Q9")
    return result


# PUBLIC_INTERFACE
def dismiss(session, context, identifier, reason, version):
    """Dismiss only an Open alert with no active work order using optimistic version."""
    repo = Repository(session, context.plant_id)
    alert = repo.get(Alert, identifier)
    if alert.version != version:
        raise AppError(409, "stale_version", "Alert version has changed")
    active_work = session.scalar(select(WorkOrder.id).where(
        WorkOrder.plant_id == context.plant_id,
        WorkOrder.alert_id == identifier,
        WorkOrder.status.in_(ACTIVE_STATES),
    ))
    if alert.status != "Open" or active_work:
        raise AppError(
            409,
            "invalid_transition",
            "Only an Open alert without active work can be dismissed",
        )
    alert.status, alert.dismissal_reason = "Dismissed", reason
    alert.updated_by, alert.updated_at = context.actor, utcnow()
    alert.version += 1
    session.flush()
    return alert_view(alert)

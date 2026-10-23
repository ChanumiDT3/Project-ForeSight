"""Read-only dashboard composition over authoritative alert and work-order rows."""
from sqlalchemy import func, select

from app.core import ACTIVE_STATES
from app.domain import priority_label
from app.models import Alert, Machine, WorkOrder


# PUBLIC_INTERFACE
def compose(session, context, rules, location=None, equipment_type=None, limit=100):
    """Return filtered at-risk machines, active alert counts, and active work orders."""
    conditions = [Machine.plant_id == context.plant_id]
    if location:
        conditions.append(Machine.location == location)
    if equipment_type:
        conditions.append(Machine.equipment_type == equipment_type)

    scoped_machine_ids = select(Machine.id).where(*conditions)

    active_counts = (
        select(Alert.machine_id, func.count().label("active_alert_count"))
        .where(
            Alert.plant_id == context.plant_id,
            Alert.status.in_(ACTIVE_STATES),
            Alert.machine_id.in_(scoped_machine_ids),
        )
        .group_by(Alert.machine_id)
        .subquery()
    )
    at_risk_total = session.scalar(select(func.count()).select_from(active_counts))
    at_risk_rows = session.execute(
        select(Machine, active_counts.c.active_alert_count)
        .join(active_counts, active_counts.c.machine_id == Machine.id)
        .order_by(Machine.equipment_id)
        .limit(limit)
    ).all()

    priority_counts = {label: 0 for label in ("Critical", "High", "Medium")}
    for score, count in session.execute(
        select(Alert.priority_score, func.count())
        .where(
            Alert.plant_id == context.plant_id,
            Alert.status.in_(ACTIVE_STATES),
            Alert.machine_id.in_(scoped_machine_ids),
        )
        .group_by(Alert.priority_score)
    ).all():
        priority_counts[priority_label(score, rules)] += count

    work_conditions = [
        WorkOrder.plant_id == context.plant_id,
        WorkOrder.status.in_(ACTIVE_STATES),
        WorkOrder.machine_id.in_(scoped_machine_ids),
    ]
    work_total = session.scalar(
        select(func.count()).select_from(WorkOrder).where(*work_conditions)
    )
    work_rows = session.execute(
        select(WorkOrder, Machine)
        .join(Machine, Machine.id == WorkOrder.machine_id)
        .where(*work_conditions)
        .order_by(WorkOrder.due_at, WorkOrder.id)
        .limit(limit)
    ).all()

    return {
        "filters": {
            "location": location,
            "equipment_type": equipment_type,
            "locations": list(
                session.scalars(
                    select(Machine.location)
                    .where(Machine.plant_id == context.plant_id)
                    .distinct()
                    .order_by(Machine.location)
                )
            ),
            "equipment_types": list(
                session.scalars(
                    select(Machine.equipment_type)
                    .where(Machine.plant_id == context.plant_id)
                    .distinct()
                    .order_by(Machine.equipment_type)
                )
            ),
        },
        "at_risk_machines": {
            "total": at_risk_total,
            "items": [
                {
                    "id": machine.id,
                    "equipment_id": machine.equipment_id,
                    "name": machine.name,
                    "location": machine.location,
                    "equipment_type": machine.equipment_type,
                    "active_alert_count": active_alert_count,
                }
                for machine, active_alert_count in at_risk_rows
            ],
        },
        "open_alerts_by_priority": priority_counts,
        "open_work_orders": {
            "total": work_total,
            "items": [
                {
                    "id": work_order.id,
                    "machine_id": machine.id,
                    "equipment_id": machine.equipment_id,
                    "machine_name": machine.name,
                    "priority": work_order.priority,
                    "status": work_order.status,
                    "assignee": work_order.assignee,
                    "due_at": work_order.due_at,
                    "alert_id": work_order.alert_id,
                }
                for work_order, machine in work_rows
            ],
        },
    }

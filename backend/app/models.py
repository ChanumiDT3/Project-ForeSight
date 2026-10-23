"""SQLAlchemy persistence entities. Operational records have no delete API."""
from sqlalchemy import (
    JSON, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core import utcnow


# PUBLIC_INTERFACE
class Base(DeclarativeBase):
    """Shared metadata for application migrations."""


# PUBLIC_INTERFACE
class Record:
    """Common identity, configured plant scope, and creation attribution."""

    id: Mapped[str] = mapped_column(String, primary_key=True)
    plant_id: Mapped[str] = mapped_column(String, index=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)


# PUBLIC_INTERFACE
class User(Base):
    """Person selectable from the MVP “Who are you?” popup."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    plant_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)
    updated_at: Mapped[str] = mapped_column(String, default=utcnow)

    __table_args__ = (UniqueConstraint("plant_id", "email"),)


# PUBLIC_INTERFACE
class Machine(Record, Base):
    """Equipment identity, criticality, runtime baseline, and service state."""

    __tablename__ = "machines"

    equipment_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text, index=True)
    equipment_type: Mapped[str] = mapped_column(Text, index=True)
    criticality: Mapped[int] = mapped_column(Integer)
    baseline: Mapped[str | None] = mapped_column(String)
    registration_meter: Mapped[str | None] = mapped_column(String)
    last_service_at: Mapped[str | None] = mapped_column(String)
    updated_by: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)

    __table_args__ = (UniqueConstraint("plant_id", "equipment_id"),)


# PUBLIC_INTERFACE
class Parameter(Record, Base):
    """Configured maximum-only health parameter with validation rules."""

    __tablename__ = "parameters"

    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    kind: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    minimum: Mapped[str] = mapped_column(String)
    maximum: Mapped[str] = mapped_column(String)
    precision: Mapped[int] = mapped_column(Integer)
    cumulative: Mapped[bool | None] = mapped_column(Boolean)
    threshold: Mapped[str] = mapped_column(String)
    threshold_type: Mapped[str] = mapped_column(String, default="max")
    suggested_action: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


# PUBLIC_INTERFACE
class Reading(Record, Base):
    """Immutable meter input including manual and closure-source readings."""

    __tablename__ = "readings"

    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"))
    parameter_id: Mapped[str] = mapped_column(ForeignKey("parameters.id"))
    value: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, default="manual", server_default="manual")
    work_order_id: Mapped[str | None] = mapped_column(String)

    __table_args__ = (Index("ix_reading_stream", "plant_id", "parameter_id", "created_at"),)


# PUBLIC_INTERFACE
class Breach(Record, Base):
    """Exactly one immutable evaluation snapshot per breaching reading."""

    __tablename__ = "breaches"

    reading_id: Mapped[str] = mapped_column(ForeignKey("readings.id"), unique=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    parameter_id: Mapped[str] = mapped_column(ForeignKey("parameters.id"))
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), index=True)
    value: Mapped[str] = mapped_column(String)
    threshold: Mapped[str] = mapped_column(String)
    exceedance_percent: Mapped[str] = mapped_column(String)
    exceedance_score: Mapped[int] = mapped_column(Integer)
    criticality: Mapped[int] = mapped_column(Integer)
    priority_score: Mapped[int] = mapped_column(Integer)


# PUBLIC_INTERFACE
class Alert(Record, Base):
    """Case alert whose breakdown always explains its stored priority."""

    __tablename__ = "alerts"

    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"))
    parameter_id: Mapped[str] = mapped_column(ForeignKey("parameters.id"))
    status: Mapped[str] = mapped_column(String, default="Open", index=True)
    first_value: Mapped[str] = mapped_column(String)
    latest_value: Mapped[str] = mapped_column(String)
    first_breach_at: Mapped[str] = mapped_column(String)
    latest_breach_at: Mapped[str] = mapped_column(String, index=True)
    breach_count: Mapped[int] = mapped_column(Integer, default=1)
    priority_score: Mapped[int] = mapped_column(Integer)
    breakdown: Mapped[dict | None] = mapped_column(JSON)
    suggested_action: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    dismissal_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "uq_active_alert",
            "plant_id",
            "machine_id",
            "parameter_id",
            unique=True,
            sqlite_where=text("status IN ('Open', 'In Progress')"),
        ),
        Index("ix_alert_queue", "plant_id", "priority_score", "first_breach_at"),
    )


# PUBLIC_INTERFACE
class WorkOrder(Record, Base):
    """Work-order lifecycle record from Open through Closed or Cancelled."""

    __tablename__ = "work_orders"

    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), index=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    priority: Mapped[str | None] = mapped_column(String)
    assignee: Mapped[str | None] = mapped_column(String, index=True)
    due_at: Mapped[str | None] = mapped_column(String)
    raised_from_runtime_alert: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("0")
    )
    scheduled_service: Mapped[bool] = mapped_column(Boolean, default=False)
    parts_checklist: Mapped[list | None] = mapped_column(JSON)
    started_by: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[str | None] = mapped_column(String)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_by: Mapped[str | None] = mapped_column(String)
    cancelled_at: Mapped[str | None] = mapped_column(String)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    parts_used: Mapped[list | None] = mapped_column(JSON)
    no_parts_used: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("0")
    )
    closure_reading_id: Mapped[str | None] = mapped_column(String)
    closed_by: Mapped[str | None] = mapped_column(String)
    closed_at: Mapped[str | None] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)

    __table_args__ = (
        Index(
            "uq_active_work_order",
            "plant_id",
            "alert_id",
            unique=True,
            sqlite_where=text("status IN ('Open', 'In Progress')"),
        ),
    )


# PUBLIC_INTERFACE
class WorkOrderAddendum(Record, Base):
    """Insert-only note appended after a work order is closed."""

    __tablename__ = "work_order_addenda"

    work_order_id: Mapped[str] = mapped_column(ForeignKey("work_orders.id"), index=True)
    note: Mapped[str] = mapped_column(Text)


# PUBLIC_INTERFACE
class BaselineHistory(Record, Base):
    """Recorded old/new runtime baselines produced by a closure reset."""

    __tablename__ = "baseline_history"

    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("work_orders.id"))
    reading_id: Mapped[str] = mapped_column(ForeignKey("readings.id"))
    old_baseline: Mapped[str] = mapped_column(String)
    new_baseline: Mapped[str] = mapped_column(String)


# PUBLIC_INTERFACE
class CommandReceipt(Base):
    """Durable idempotency result committed with the business transaction."""

    __tablename__ = "command_receipts"

    scope: Mapped[str] = mapped_column(String, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String)
    result: Mapped[dict] = mapped_column(JSON)
    plant_id: Mapped[str] = mapped_column(String, index=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)

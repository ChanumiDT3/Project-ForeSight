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
    """Common identity, plant, and creation attribution."""

    id: Mapped[str] = mapped_column(String, primary_key=True)
    plant_id: Mapped[str] = mapped_column(String, index=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)


# PUBLIC_INTERFACE
class Machine(Record, Base):
    """Equipment-owned identity, criticality and service baseline."""

    __tablename__ = "machines"
    name: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text, index=True)
    equipment_type: Mapped[str] = mapped_column(Text, index=True)
    criticality: Mapped[int] = mapped_column(Integer)
    baseline: Mapped[str | None] = mapped_column(String)
    registration_meter: Mapped[str | None] = mapped_column(String)
    last_service_at: Mapped[str | None] = mapped_column(String)
    updated_by: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    __table_args__ = (
        # Equipment identifiers are scoped by plant in the API; internal IDs are UUIDs.
        UniqueConstraint("plant_id", "equipment_id"),
    )
    equipment_id: Mapped[str] = mapped_column(String)


# PUBLIC_INTERFACE
class Parameter(Record, Base):
    """Configured maximum-only parameter with a snapshot of valid input rules."""

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
    """Immutable meter input; derived since-service counters are not persisted."""

    __tablename__ = "readings"
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"))
    parameter_id: Mapped[str] = mapped_column(ForeignKey("parameters.id"))
    value: Mapped[str] = mapped_column(String)
    __table_args__ = (Index("ix_reading_stream", "plant_id", "parameter_id", "created_at"),)


# PUBLIC_INTERFACE
class Breach(Record, Base):
    """Exactly one breach per reading, retaining the evaluation snapshot."""

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
    """Case-owned alert; lower-repeat display breakdown remains explicitly held."""

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
        Index("uq_active_alert", "plant_id", "machine_id", "parameter_id", unique=True,
              sqlite_where=text("status IN ('Open', 'In Progress')")),
        Index("ix_alert_queue", "plant_id", "priority_score", "first_breach_at"),
    )


# PUBLIC_INTERFACE
class WorkOrder(Record, Base):
    """Work-order storage prepared for the held creation and object policies."""

    __tablename__ = "work_orders"
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), index=True)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    assignee: Mapped[str | None] = mapped_column(String)
    due_at: Mapped[str | None] = mapped_column(String)
    scheduled_service: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    __table_args__ = (
        Index("uq_active_work_order", "plant_id", "alert_id", unique=True,
              sqlite_where=text("status IN ('Open', 'In Progress')")),
    )


# PUBLIC_INTERFACE
class CommandReceipt(Base):
    """Durable idempotency result committed with its business transaction."""

    __tablename__ = "command_receipts"
    scope: Mapped[str] = mapped_column(String, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String)
    result: Mapped[dict] = mapped_column(JSON)
    plant_id: Mapped[str] = mapped_column(String, index=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)

"""Initial retained operational schema.

Downgrading is intentionally refused: restoring a verified backup is an operational
decision, not an automatic deletion path for retained maintenance history.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _record():
    return [
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("plant_id", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    ]


def _text(name, nullable=False):
    return sa.Column(name, sa.String(), nullable=nullable)


def _fk(name, target):
    return sa.Column(name, sa.String(), sa.ForeignKey(target), nullable=False)


# PUBLIC_INTERFACE
def upgrade():
    """Create the initial relational schema and race-protection constraints."""
    op.create_table("machines", *_record(), _text("equipment_id"),
                    _text("name"), _text("location"), _text("equipment_type"),
                    sa.Column("criticality", sa.Integer(), nullable=False),
                    _text("baseline", True), _text("registration_meter", True),
                    _text("last_service_at", True), _text("updated_by"), _text("updated_at"),
                    sa.UniqueConstraint("plant_id", "equipment_id"))
    op.create_table("parameters", *_record(), _fk("machine_id", "machines.id"),
                    _text("kind"), _text("name"), _text("unit"), _text("minimum"),
                    _text("maximum"), sa.Column("precision", sa.Integer(), nullable=False),
                    sa.Column("cumulative", sa.Boolean(), nullable=True),
                    _text("threshold"), _text("threshold_type"), _text("suggested_action"),
                    _text("updated_by"), _text("updated_at"))
    op.create_table("readings", *_record(), _fk("machine_id", "machines.id"),
                    _fk("parameter_id", "parameters.id"), _text("value"))
    op.create_table("alerts", *_record(), _fk("machine_id", "machines.id"),
                    _fk("parameter_id", "parameters.id"), _text("status"),
                    _text("first_value"), _text("latest_value"), _text("first_breach_at"),
                    _text("latest_breach_at"),
                    sa.Column("breach_count", sa.Integer(), nullable=False),
                    sa.Column("priority_score", sa.Integer(), nullable=False),
                    sa.Column("breakdown", sa.JSON(), nullable=True),
                    _text("suggested_action"), sa.Column("version", sa.Integer(), nullable=False),
                    _text("updated_by"), _text("updated_at"), _text("dismissal_reason", True))
    op.create_table("breaches", *_record(), _fk("reading_id", "readings.id"),
                    _fk("machine_id", "machines.id"), _fk("parameter_id", "parameters.id"),
                    _fk("alert_id", "alerts.id"), _text("value"), _text("threshold"),
                    _text("exceedance_percent"),
                    sa.Column("exceedance_score", sa.Integer(), nullable=False),
                    sa.Column("criticality", sa.Integer(), nullable=False),
                    sa.Column("priority_score", sa.Integer(), nullable=False),
                    sa.UniqueConstraint("reading_id"))
    op.create_table("work_orders", *_record(), _fk("alert_id", "alerts.id"),
                    _fk("machine_id", "machines.id"), _text("status"),
                    sa.Column("snapshot", sa.JSON(), nullable=False),
                    _text("assignee", True), _text("due_at", True),
                    sa.Column("scheduled_service", sa.Boolean(), nullable=False),
                    sa.Column("version", sa.Integer(), nullable=False),
                    _text("updated_by"), _text("updated_at"))
    op.create_table("command_receipts",
                    sa.Column("scope", sa.String(), primary_key=True),
                    _text("fingerprint"), sa.Column("result", sa.JSON(), nullable=False),
                    _text("plant_id"), _text("created_by"), _text("created_at"))
    for table in ("machines", "parameters", "readings", "breaches", "alerts",
                  "work_orders", "command_receipts"):
        op.create_index(f"ix_{table}_plant_id", table, ["plant_id"])
    for table, columns in {
        "machines": ["location", "equipment_type"],
        "parameters": ["machine_id"],
        "breaches": ["machine_id", "alert_id"],
        "alerts": ["status", "latest_breach_at"],
        "work_orders": ["machine_id", "alert_id", "status"],
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index("ix_reading_stream", "readings", ["plant_id", "parameter_id", "created_at"])
    op.create_index("ix_alert_queue", "alerts", ["plant_id", "priority_score", "first_breach_at"])
    op.create_index("uq_active_alert", "alerts", ["plant_id", "machine_id", "parameter_id"],
                    unique=True, sqlite_where=sa.text("status IN ('Open', 'In Progress')"))
    op.create_index("uq_active_work_order", "work_orders", ["plant_id", "alert_id"],
                    unique=True, sqlite_where=sa.text("status IN ('Open', 'In Progress')"))


# PUBLIC_INTERFACE
def downgrade():
    """Refuse destructive removal of indefinitely retained operational records."""
    raise RuntimeError("Destructive downgrade refused; use an approved backup recovery procedure")

"""Users, expanded work orders, closure readings, and baseline history."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _record():
    """Return common retained-record columns."""
    return [
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("plant_id", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    ]


def _text(name, nullable=False):
    """Return a string column with the requested nullability."""
    return sa.Column(name, sa.String(), nullable=nullable)


# PUBLIC_INTERFACE
def upgrade():
    """Create identity and closure tables and add defaulted lifecycle columns."""
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        _text("plant_id"),
        _text("name"),
        _text("email"),
        _text("role"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _text("created_at"),
        _text("updated_at"),
        sa.UniqueConstraint("plant_id", "email"),
    )
    op.create_index("ix_users_plant_id", "users", ["plant_id"])

    op.add_column(
        "readings",
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
    )
    op.add_column("readings", _text("work_order_id", True))

    for name in (
        "priority",
        "started_by",
        "started_at",
        "cancellation_reason",
        "cancelled_by",
        "cancelled_at",
        "resolution_note",
        "closure_reading_id",
        "closed_by",
        "closed_at",
    ):
        op.add_column("work_orders", _text(name, True))

    op.add_column(
        "work_orders",
        sa.Column(
            "raised_from_runtime_alert",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "work_orders",
        sa.Column("no_parts_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("work_orders", sa.Column("parts_checklist", sa.JSON(), nullable=True))
    op.add_column("work_orders", sa.Column("parts_used", sa.JSON(), nullable=True))
    op.create_index("ix_work_orders_assignee", "work_orders", ["assignee"])

    op.create_table(
        "work_order_addenda",
        *_record(),
        sa.Column("work_order_id", sa.String(), sa.ForeignKey("work_orders.id"), nullable=False),
        _text("note"),
    )
    op.create_index("ix_work_order_addenda_plant_id", "work_order_addenda", ["plant_id"])
    op.create_index(
        "ix_work_order_addenda_work_order_id",
        "work_order_addenda",
        ["work_order_id"],
    )

    op.create_table(
        "baseline_history",
        *_record(),
        sa.Column("machine_id", sa.String(), sa.ForeignKey("machines.id"), nullable=False),
        sa.Column(
            "work_order_id",
            sa.String(),
            sa.ForeignKey("work_orders.id"),
            nullable=False,
        ),
        sa.Column("reading_id", sa.String(), sa.ForeignKey("readings.id"), nullable=False),
        _text("old_baseline"),
        _text("new_baseline"),
    )
    op.create_index("ix_baseline_history_plant_id", "baseline_history", ["plant_id"])
    op.create_index("ix_baseline_history_machine_id", "baseline_history", ["machine_id"])


# PUBLIC_INTERFACE
def downgrade():
    """Refuse destructive removal of indefinitely retained maintenance records."""
    raise RuntimeError("Destructive downgrade refused; use an approved backup recovery procedure")

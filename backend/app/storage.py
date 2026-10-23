"""SQLite resource management, record helpers and plant-scoped repository queries."""
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import create_engine, event, select, func
from sqlalchemy.orm import Session
from app.core import AppError, utcnow

# Connection execution option selecting the write lock protocol for a transaction.
_WRITE = "foresight_write"


# PUBLIC_INTERFACE
def make_engine(url: str):
    """Create the selected local SQLite engine; deployment storage is not provisioned."""
    if not url.startswith("sqlite:///"):
        raise ValueError("This scaffold supports SQLite only; configure sqlite:///path")
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _configure(dbapi_connection, _record):
        # Disable pysqlite's implicit transaction handling, which never begins a
        # transaction for SELECT statements. BEGIN is issued explicitly below.
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _begin(connection):
        # All writers use the same lock protocol. SQLite's database-wide writer
        # lock deliberately trades throughput for simple, correct MVP isolation.
        # Readers use a deferred transaction so multi-statement reads share one snapshot.
        immediate = connection.get_execution_options().get(_WRITE)
        connection.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")

    return engine


# PUBLIC_INTERFACE
@contextmanager
def transaction(engine, write=False):
    """Run one unit of work in a single SQLite transaction, committing on success.

    Reads (``write=False``) see one consistent snapshot; writes acquire the
    database writer lock before reading state they depend on.
    """
    with Session(engine, expire_on_commit=False) as session:
        try:
            session.connection(execution_options={_WRITE: write})
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


# PUBLIC_INTERFACE
def attributes(context):
    """Create common persisted record attribution (UUID, plant, actor, UTC time).

    The actor's source is held on D-36; this helper only copies what the
    request context supplies.
    """
    return dict(id=str(uuid4()), plant_id=context.plant_id, created_by=context.actor,
                created_at=utcnow())


# PUBLIC_INTERFACE
def serialize(row):
    """Serialize mapped scalar fields, never relationships or ORM internals."""
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


# PUBLIC_INTERFACE
class Repository:
    """Small explicit query helper, with mandatory plant isolation and no deletes."""

    # PUBLIC_INTERFACE
    def __init__(self, session: Session, plant_id: str):
        """Bind reads and writes to the caller's transaction and plant."""
        self.session, self.plant_id = session, plant_id

    # PUBLIC_INTERFACE
    def get(self, model, identifier):
        """Load a plant-scoped record or raise a non-enumerating not-found error."""
        row = self.session.scalar(select(model).where(
            model.id == identifier, model.plant_id == self.plant_id))
        if row is None:
            raise AppError(404, "not_found", "Record not found")
        return row

    # PUBLIC_INTERFACE
    def page(self, model, offset, limit, *conditions, order=()):
        """Return a bounded list and total from the same transaction snapshot."""
        query = select(model).where(model.plant_id == self.plant_id, *conditions)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        rows = self.session.scalars(query.order_by(*order).offset(offset).limit(limit)).all()
        return rows, total

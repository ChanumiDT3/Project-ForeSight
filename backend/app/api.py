"""HTTP controllers for the finalized ForeSight maintenance API."""
import hashlib
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select

from app import cases, dashboard as dashboard_service, equipment, readings, work_orders
from app.core import AppError, RequestContext
from app.identity import configured_plant, get_current_user
from app.models import Alert, Breach, CommandReceipt, Parameter, Reading, User, WorkOrder
from app.schemas import (
    AddendumInput,
    ClosureInput,
    CriticalityInput,
    CumulativeInput,
    EquipmentDetailsInput,
    MachineInput,
    NewParameterInput,
    Page,
    PartsChecklistInput,
    ReadingInput,
    ReasonInput,
    Result,
    SuggestedActionInput,
    ThresholdInput,
    WorkOrderEditInput,
)
from app.storage import Repository, serialize, transaction

router = APIRouter(prefix="/v1")
public_router = APIRouter()

Current = Annotated[RequestContext, Depends(get_current_user)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
WorkOrderStatus = Literal["Open", "In Progress", "Closed", "Cancelled"]


# PUBLIC_INTERFACE
def engineer(context: Current):
    """Require the Engineer role for mutations outside reading entry."""
    if context.role != "Engineer":
        raise AppError(403, "forbidden", "Engineer role required")
    return context


# PUBLIC_INTERFACE
def case_reader(context: Current):
    """Allow Engineers and Managers to read case, machine, and dashboard data."""
    if context.role not in {"Engineer", "Manager"}:
        raise AppError(403, "forbidden", "Requires Engineer or Manager")
    return context


# PUBLIC_INTERFACE
def reading_writer(context: Current):
    """Allow Operators and Engineers to log readings."""
    if context.role not in {"Operator", "Engineer"}:
        raise AppError(403, "forbidden", "Reading entry requires Operator or Engineer")
    return context


# PUBLIC_INTERFACE
def command_key(value: Annotated[str, Header(alias="Idempotency-Key")]):
    """Require a bounded retry key for every mutation."""
    if not value.strip() or len(value) > 200:
        raise AppError(422, "invalid_idempotency_key", "Use a nonblank key of at most 200 characters")
    return value


# PUBLIC_INTERFACE
def version(value: Annotated[str, Header(alias="If-Match")]):
    """Parse a quoted positive If-Match work-order or alert version."""
    if not (value.startswith('"') and value.endswith('"') and value[1:-1].isdigit()):
        raise AppError(422, "invalid_version", 'If-Match must be a quoted integer, for example "1"')
    parsed = int(value[1:-1])
    if parsed < 1:
        raise AppError(422, "invalid_version", "Version must be positive")
    return parsed


# PUBLIC_INTERFACE
def database(request: Request):
    """Return the configured database engine or a safe configuration problem."""
    if request.app.state.engine is None:
        raise AppError(503, "database_unconfigured", "FORESIGHT_DATABASE_URL must be configured")
    return request.app.state.engine


# PUBLIC_INTERFACE
def execute(request: Request, context: RequestContext, key: str, payload: dict, operation):
    """Run or replay one idempotent transactional command."""
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    scope = hashlib.sha256(
        json.dumps(
            [
                context.plant_id,
                context.actor,
                context.role,
                request.method,
                request.url.path,
                key,
            ]
        ).encode()
    ).hexdigest()

    with transaction(database(request), write=True) as session:
        receipt = session.get(CommandReceipt, scope)
        if receipt:
            if receipt.fingerprint != fingerprint:
                raise AppError(409, "idempotency_conflict", "Retry key was used with different input")
            return Result(data=receipt.result)

        result = operation(session)
        session.add(
            CommandReceipt(
                scope=scope,
                fingerprint=fingerprint,
                result=result,
                plant_id=context.plant_id,
                created_by=context.actor,
            )
        )
        session.flush()
        return Result(data=result)


# PUBLIC_INTERFACE
def collection(request: Request, context, model, offset, limit, *conditions, order=(), view=serialize):
    """Return a plant-scoped bounded collection from one consistent snapshot."""
    with transaction(database(request)) as session:
        rows, total = Repository(session, context.plant_id).page(
            model, offset, limit, *conditions, order=order
        )
        return Page(data=[view(row) for row in rows], total=total, offset=offset, limit=limit)


Reader = Annotated[RequestContext, Depends(case_reader)]
Engineer = Annotated[RequestContext, Depends(engineer)]
Key = Annotated[str, Depends(command_key)]
Version = Annotated[int, Depends(version)]


# PUBLIC_INTERFACE
@public_router.get("/health", tags=["Users"], summary="Health check")
def health():
    """Return a public liveness response without accessing storage."""
    return {"status": "ok"}


# PUBLIC_INTERFACE
@public_router.get("/v1/users", tags=["Users"], response_model=Page, summary="List active users")
def list_users(request: Request, offset: Offset = 0, limit: Limit = 100):
    """Return only ID, name, and role for active identity-popup choices."""
    plant_id = configured_plant(request)
    with transaction(database(request)) as session:
        rows, total = Repository(session, plant_id).page(
            User,
            offset,
            limit,
            User.active.is_(True),
            order=(User.name, User.id),
        )
        return Page(
            data=[{"id": user.id, "name": user.name, "role": user.role} for user in rows],
            total=total,
            offset=offset,
            limit=limit,
        )


# PUBLIC_INTERFACE
@router.get("/me", tags=["Users"], response_model=Result, summary="Get current user")
def me(user: Current):
    """Return the server-resolved identity, role, and configured plant."""
    return Result(
        data={
            "id": user.actor,
            "name": user.name,
            "role": user.role,
            "plant_id": user.plant_id,
        }
    )


# PUBLIC_INTERFACE
@router.get("/users/directory", tags=["Users"], response_model=Page, summary="Display user directory")
def user_directory(request: Request, user: Current, offset: Offset = 0, limit: Limit = 100):
    """Return all users for audit/assignee name resolution after identity validation."""
    return collection(
        request,
        user,
        User,
        offset,
        limit,
        order=(User.name, User.id),
        view=lambda row: {
            "id": row.id,
            "name": row.name,
            "role": row.role,
            "active": row.active,
        },
    )


# PUBLIC_INTERFACE
@router.post("/machines", tags=["Equipment"], response_model=Result, status_code=201)
def register_machine(request: Request, body: MachineInput, user: Engineer, key: Key):
    """Register equipment and zero or more configured parameters."""
    return execute(
        request,
        user,
        key,
        body.model_dump(mode="json"),
        lambda session: equipment.register(session, user, body, request.app.state.rules),
    )


# PUBLIC_INTERFACE
@router.get("/machines", tags=["Equipment"], response_model=Page)
def list_machines(request: Request, user: Reader, offset: Offset = 0, limit: Limit = 50):
    """List machine records with monitoring state and derived risk status."""
    with transaction(database(request)) as session:
        data, total = equipment.machine_page(session, user, offset, limit)
        return Page(data=data, total=total, offset=offset, limit=limit)


# PUBLIC_INTERFACE
@router.get("/machines/{identifier}", tags=["Equipment"], response_model=Result)
def get_machine(request: Request, identifier: str, user: Reader):
    """Return detailed machine information and reading/baseline context."""
    with transaction(database(request)) as session:
        return Result(data=equipment.machine_detail(session, user, identifier))


# PUBLIC_INTERFACE
@router.get("/machines/{identifier}/status", tags=["Cases"], response_model=Result)
def machine_status(request: Request, identifier: str, user: Reader):
    """Return a machine's derived health status and active alert count."""
    with transaction(database(request)) as session:
        detail = equipment.machine_detail(session, user, identifier)
        return Result(
            data={
                "status": detail["status"],
                "active_alert_count": detail["active_alert_count"],
            }
        )


# PUBLIC_INTERFACE
@router.patch("/machines/{identifier}", tags=["Equipment"], response_model=Result)
def equipment_details(
    request: Request,
    identifier: str,
    body: EquipmentDetailsInput,
    user: Engineer,
    key: Key,
):
    """Edit descriptive equipment fields."""
    return execute(
        request,
        user,
        key,
        body.model_dump(mode="json"),
        lambda session: equipment.edit_details(session, user, identifier, body),
    )


# PUBLIC_INTERFACE
@router.post("/machines/{identifier}/parameters", tags=["Equipment"], response_model=Result, status_code=201)
def add_parameter(
    request: Request,
    identifier: str,
    body: NewParameterInput,
    user: Engineer,
    key: Key,
):
    """Add a parameter to an already registered machine."""
    return execute(
        request,
        user,
        key,
        body.model_dump(mode="json"),
        lambda session: equipment.add_parameter(session, user, identifier, body, request.app.state.rules),
    )


# PUBLIC_INTERFACE
@router.patch("/parameters/{identifier}/cumulative", tags=["Equipment"], response_model=Result)
def cumulative(request: Request, identifier: str, body: CumulativeInput, user: Engineer, key: Key):
    """Change a custom parameter's cumulative flag before its first reading."""
    return execute(
        request,
        user,
        key,
        body.model_dump(mode="json"),
        lambda session: equipment.edit_cumulative(session, user, identifier, body),
    )


# PUBLIC_INTERFACE
@router.patch("/parameters/{identifier}/suggested-action", tags=["Equipment"], response_model=Result)
def suggested_action(
    request: Request,
    identifier: str,
    body: SuggestedActionInput,
    user: Engineer,
    key: Key,
):
    """Update a parameter's future alert suggested action."""
    return execute(
        request,
        user,
        key,
        body.model_dump(mode="json"),
        lambda session: equipment.edit_suggested_action(session, user, identifier, body),
    )


# PUBLIC_INTERFACE
@router.patch("/machines/{identifier}/criticality", tags=["Equipment"], response_model=Result)
def criticality(
    request: Request,
    identifier: str,
    body: CriticalityInput,
    user: Engineer,
    key: Key,
):
    """Update criticality for future alert calculation."""
    return execute(
        request,
        user,
        key,
        body.model_dump(mode="json"),
        lambda session: equipment.edit_criticality(session, user, identifier, body),
    )


# PUBLIC_INTERFACE
@router.patch("/parameters/{identifier}/threshold", tags=["Equipment"], response_model=Result)
def threshold(
    request: Request,
    identifier: str,
    body: ThresholdInput,
    user: Engineer,
    key: Key,
):
    """Update a maximum threshold for future readings."""
    return execute(
        request,
        user,
        key,
        body.model_dump(mode="json"),
        lambda session: equipment.edit_threshold(session, user, identifier, body),
    )


# PUBLIC_INTERFACE
@router.get("/readings/targets", tags=["Readings"], response_model=Page)
def reading_targets(
    request: Request,
    user: Annotated[RequestContext, Depends(reading_writer)],
    offset: Offset = 0,
    limit: Limit = 100,
):
    """Return validated reading-entry targets to Operators and Engineers."""
    with transaction(database(request)) as session:
        data, total = equipment.reading_targets(session, user, offset, limit)
        return Page(data=data, total=total, offset=offset, limit=limit)


# PUBLIC_INTERFACE
@router.post("/readings", tags=["Readings"], response_model=Result, status_code=201)
def log_reading(
    request: Request,
    body: ReadingInput,
    user: Annotated[RequestContext, Depends(reading_writer)],
    key: Key,
):
    """Log one reading and return its optional alert link."""
    return execute(
        request,
        user,
        key,
        body.model_dump(mode="json"),
        lambda session: readings.log_reading(session, user, body, request.app.state.rules),
    )


# PUBLIC_INTERFACE
@router.get("/parameters/{identifier}/readings", tags=["Readings"], response_model=Page)
def reading_history(
    request: Request,
    identifier: str,
    user: Reader,
    offset: Offset = 0,
    limit: Limit = 50,
):
    """Return immutable chronological readings for a parameter."""
    with transaction(database(request)) as session:
        repo = Repository(session, user.plant_id)
        repo.get(Parameter, identifier)
        rows, total = repo.page(
            Reading,
            offset,
            limit,
            Reading.parameter_id == identifier,
            order=(Reading.created_at, Reading.id),
        )
        return Page(data=[serialize(row) for row in rows], total=total, offset=offset, limit=limit)


# PUBLIC_INTERFACE
@router.get("/alerts", tags=["Cases"], response_model=Page)
def alert_queue(request: Request, user: Reader, offset: Offset = 0, limit: Limit = 50):
    """Return queue alerts ordered by priority then first breach time."""
    with transaction(database(request)) as session:
        rows, total = Repository(session, user.plant_id).page(
            Alert,
            offset,
            limit,
            order=(Alert.priority_score.desc(), Alert.first_breach_at, Alert.id),
        )
        return Page(
            data=cases.alert_views(session, user, rows, request.app.state.rules),
            total=total,
            offset=offset,
            limit=limit,
        )


# PUBLIC_INTERFACE
@router.get("/alerts/{identifier}", tags=["Cases"], response_model=Result)
def alert_detail(request: Request, identifier: str, user: Reader):
    """Return alert detail and linked work-order identifiers."""
    with transaction(database(request)) as session:
        alert = Repository(session, user.plant_id).get(Alert, identifier)
        work_order_ids = session.scalars(
            select(WorkOrder.id)
            .where(
                WorkOrder.alert_id == identifier,
                WorkOrder.plant_id == user.plant_id,
            )
            .order_by(WorkOrder.created_at)
        ).all()
        view = cases.alert_views(session, user, [alert], request.app.state.rules)[0]
        return Result(data={**view, "work_order_ids": list(work_order_ids)})


# PUBLIC_INTERFACE
@router.get("/alerts/{identifier}/breaches", tags=["Cases"], response_model=Page)
def breach_history(
    request: Request,
    identifier: str,
    user: Reader,
    offset: Offset = 0,
    limit: Limit = 50,
):
    """Return immutable breach snapshots for an alert."""
    with transaction(database(request)) as session:
        repo = Repository(session, user.plant_id)
        repo.get(Alert, identifier)
        rows, total = repo.page(
            Breach,
            offset,
            limit,
            Breach.alert_id == identifier,
            order=(Breach.created_at, Breach.id),
        )
        return Page(data=[serialize(row) for row in rows], total=total, offset=offset, limit=limit)


# PUBLIC_INTERFACE
@router.post("/alerts/{identifier}/dismissal", tags=["Cases"], response_model=Result)
def dismiss_alert(
    request: Request,
    identifier: str,
    body: ReasonInput,
    user: Engineer,
    key: Key,
    expected: Version,
):
    """Dismiss an Open alert without active work."""
    payload = {**body.model_dump(mode="json"), "version": expected}
    return execute(
        request,
        user,
        key,
        payload,
        lambda session: cases.dismiss(
            session,
            user,
            identifier,
            body.reason,
            expected,
            request.app.state.rules,
        ),
    )


# PUBLIC_INTERFACE
@router.post("/alerts/{identifier}/work-orders", tags=["Work orders"], response_model=Result, status_code=201)
def create_work_order(request: Request, identifier: str, user: Engineer, key: Key):
    """Create an Open work order from an Open alert."""
    return execute(
        request,
        user,
        key,
        {"alert_id": identifier},
        lambda session: work_orders.create(session, user, identifier, request.app.state.rules),
    )


# PUBLIC_INTERFACE
@router.get("/work-orders", tags=["Work orders"], response_model=Page)
def list_work_orders(
    request: Request,
    user: Reader,
    offset: Offset = 0,
    limit: Limit = 50,
    status: WorkOrderStatus | None = None,
    assignee: str | None = None,
):
    """List work orders with status and assignee filters for the React UI."""
    conditions = []
    if status:
        conditions.append(WorkOrder.status == status)
    if assignee:
        conditions.append(WorkOrder.assignee == assignee)
    return collection(
        request,
        user,
        WorkOrder,
        offset,
        limit,
        *conditions,
        order=(WorkOrder.created_at, WorkOrder.id),
    )


# PUBLIC_INTERFACE
@router.get("/work-orders/{identifier}", tags=["Work orders"], response_model=Result)
def get_work_order(request: Request, identifier: str, user: Reader):
    """Return one work order including closure/runtime information and addenda."""
    with transaction(database(request)) as session:
        work_order = Repository(session, user.plant_id).get(WorkOrder, identifier)
        return Result(data=work_orders.work_order_view(session, user, work_order, include_addenda=True))


# PUBLIC_INTERFACE
@router.patch("/work-orders/{identifier}", tags=["Work orders"], response_model=Result)
def edit_work_order(
    request: Request,
    identifier: str,
    body: WorkOrderEditInput,
    user: Engineer,
    key: Key,
    expected: Version,
):
    """Edit assignment, due date, or scheduled-service state."""
    payload = {**body.model_dump(mode="json", exclude_unset=True), "version": expected}
    return execute(
        request,
        user,
        key,
        payload,
        lambda session: work_orders.edit(session, user, identifier, body, expected),
    )


# PUBLIC_INTERFACE
@router.post("/work-orders/{identifier}/start", tags=["Work orders"], response_model=Result)
def start_work_order(
    request: Request,
    identifier: str,
    user: Engineer,
    key: Key,
    expected: Version,
):
    """Start an Open work order."""
    return execute(
        request,
        user,
        key,
        {"version": expected},
        lambda session: work_orders.start(session, user, identifier, expected),
    )


# PUBLIC_INTERFACE
@router.post("/work-orders/{identifier}/cancellation", tags=["Work orders"], response_model=Result)
def cancel_work_order(
    request: Request,
    identifier: str,
    body: ReasonInput,
    user: Engineer,
    key: Key,
    expected: Version,
):
    """Cancel an active work order and reopen its alert."""
    payload = {**body.model_dump(mode="json"), "version": expected}
    return execute(
        request,
        user,
        key,
        payload,
        lambda session: work_orders.cancel(session, user, identifier, body.reason, expected),
    )


# PUBLIC_INTERFACE
@router.put("/work-orders/{identifier}/parts-checklist", tags=["Work orders"], response_model=Result)
def parts_checklist(
    request: Request,
    identifier: str,
    body: PartsChecklistInput,
    user: Engineer,
    key: Key,
    expected: Version,
):
    """Replace an active work order's optional parts checklist."""
    payload = {**body.model_dump(mode="json"), "version": expected}
    return execute(
        request,
        user,
        key,
        payload,
        lambda session: work_orders.replace_checklist(session, user, identifier, body, expected),
    )


# PUBLIC_INTERFACE
@router.post("/work-orders/{identifier}/closure", tags=["Work orders"], response_model=Result)
def close_work_order(
    request: Request,
    identifier: str,
    body: ClosureInput,
    user: Engineer,
    key: Key,
    expected: Version,
):
    """Close an In Progress order and apply validated service effects atomically."""
    payload = {**body.model_dump(mode="json"), "version": expected}
    return execute(
        request,
        user,
        key,
        payload,
        lambda session: work_orders.close(session, user, identifier, body, expected),
    )


# PUBLIC_INTERFACE
@router.post("/work-orders/{identifier}/addenda", tags=["Work orders"], response_model=Result, status_code=201)
def addendum(
    request: Request,
    identifier: str,
    body: AddendumInput,
    user: Engineer,
    key: Key,
):
    """Append an insert-only note to a Closed work order."""
    return execute(
        request,
        user,
        key,
        body.model_dump(mode="json"),
        lambda session: work_orders.add_addendum(session, user, identifier, body.note),
    )


# PUBLIC_INTERFACE
@router.get("/dashboard", tags=["Dashboard"], response_model=Result)
def dashboard(
    request: Request,
    user: Reader,
    location: str | None = None,
    equipment_type: str | None = None,
    limit: Limit = 100,
):
    """Return the Manager/Engineer read-only dashboard."""
    with transaction(database(request)) as session:
        return Result(
            data=dashboard_service.compose(
                session,
                user,
                request.app.state.rules,
                location,
                equipment_type,
                limit,
            )
        )

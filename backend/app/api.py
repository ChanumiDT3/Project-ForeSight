"""HTTP controllers; business operations delegate to transaction-scoped services."""
import hashlib
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app import cases, equipment, readings
from app.core import AppError, Identity, held
from app.models import Alert, Breach, CommandReceipt, Machine, Parameter, Reading, WorkOrder
from app.schemas import (
    CriticalityInput, EquipmentDetailsInput, MachineInput, Page, ReadingInput,
    ReasonInput, Result, SuggestedActionInput, ThresholdInput,
)
from app.storage import Repository, serialize, transaction

router = APIRouter(prefix="/v1")
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger("foresight")


# PUBLIC_INTERFACE
def identity(request: Request, credential: Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer)
]) -> Identity:
    """Validate bearer credentials through the deployment's trusted provider adapter."""
    if credential is None:
        raise AppError(401, "authentication_required", "A valid bearer session is required")
    verifier = request.app.state.identity_verifier
    if verifier is None:
        raise AppError(503, "identity_unconfigured", "Identity provider integration is not configured")
    try:
        user = verifier(credential.credentials)
    except Exception as error:
        # Never log the credential itself; the error type is enough for diagnosis.
        logger.warning(json.dumps(dict(event="identity_rejected", error_type=type(error).__name__)))
        raise AppError(401, "invalid_session", "Invalid session") from None
    if (not isinstance(user, Identity) or not user.active or not user.subject or
            not user.plant_id or user.role not in {"Operator", "Engineer", "Manager"}):
        raise AppError(401, "invalid_session", "Invalid or inactive identity")
    return user


# PUBLIC_INTERFACE
def engineer(user: Annotated[Identity, Depends(identity)]):
    """Require the decided Engineer role before invoking a command."""
    if user.role != "Engineer":
        raise AppError(403, "forbidden", "Engineer role required")
    return user


# PUBLIC_INTERFACE
def case_reader(user: Annotated[Identity, Depends(identity)]):
    """Allow only Engineer and Manager case queries."""
    if user.role not in {"Engineer", "Manager"}:
        raise AppError(403, "forbidden", "Case access requires Engineer or Manager")
    return user


# PUBLIC_INTERFACE
def reading_writer(user: Annotated[Identity, Depends(identity)]):
    """Allow Operator and Engineer to log readings."""
    if user.role not in {"Operator", "Engineer"}:
        raise AppError(403, "forbidden", "Reading entry requires Operator or Engineer")
    return user


# PUBLIC_INTERFACE
def command_key(value: Annotated[str, Header(alias="Idempotency-Key")]):
    """Require a bounded, nonblank technical retry key on every mutation."""
    if not value.strip() or len(value) > 200:
        raise AppError(422, "invalid_idempotency_key", "Use a nonblank key of at most 200 characters")
    return value


# PUBLIC_INTERFACE
def version(value: Annotated[str, Header(alias="If-Match")]):
    """Parse a quoted positive entity version used for stale-write protection."""
    if not (value.startswith('"') and value.endswith('"') and value[1:-1].isdigit()):
        raise AppError(422, "invalid_version", 'If-Match must be a quoted integer, for example "1"')
    number = int(value[1:-1])
    if number < 1:
        raise AppError(422, "invalid_version", "Version must be positive")
    return number


# PUBLIC_INTERFACE
def database(request: Request):
    """Require explicit database configuration; never create an implicit database."""
    if request.app.state.engine is None:
        raise AppError(503, "database_unconfigured", "FORESIGHT_DATABASE_URL must be configured")
    return request.app.state.engine


# PUBLIC_INTERFACE
def execute(request: Request, user: Identity, key: str, payload: dict, operation):
    """Atomically replay or execute a command, detecting key/body mismatches."""
    fingerprint = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    scope = hashlib.sha256(json.dumps([
        user.plant_id, user.subject, user.role, request.method, request.url.path, key
    ]).encode()).hexdigest()
    with transaction(database(request), write=True) as session:
        receipt = session.get(CommandReceipt, scope)
        if receipt:
            if receipt.fingerprint != fingerprint:
                raise AppError(409, "idempotency_conflict", "Retry key was used with different input")
            return Result(data=receipt.result)
        result = operation(session)
        session.add(CommandReceipt(
            scope=scope, fingerprint=fingerprint, result=result,
            plant_id=user.plant_id, created_by=user.subject))
        session.flush()
        return Result(data=result)


# PUBLIC_INTERFACE
def collection(request: Request, user: Identity, model, offset: int, limit: int,
               *conditions, order=(), view=serialize):
    """Query a scoped page without giving repositories commit ownership."""
    with transaction(database(request)) as session:
        rows, total = Repository(session, user.plant_id).page(
            model, offset, limit, *conditions, order=order)
        return Page(data=[view(row) for row in rows], total=total, offset=offset, limit=limit)


Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
User = Annotated[Identity, Depends(case_reader)]
Engineer = Annotated[Identity, Depends(engineer)]
Key = Annotated[str, Depends(command_key)]


# PUBLIC_INTERFACE
@router.post("/machines", tags=["Equipment"], response_model=Result, status_code=201,
             summary="Register equipment", description="Save equipment and configured parameters atomically.")
def register_machine(request: Request, body: MachineInput, user: Engineer, key: Key):
    """Accept equipment configuration and return the new machine and parameters."""
    return execute(request, user, key, body.model_dump(mode="json"), lambda session:
                   equipment.register(session, user, body, request.app.state.rules))


# PUBLIC_INTERFACE
@router.get("/machines", tags=["Equipment"], response_model=Page,
            summary="List equipment", description="Return a plant-scoped, bounded equipment page.")
def list_machines(request: Request, user: User, offset: Offset = 0, limit: Limit = 50):
    """Return equipment ordered by plant equipment identifier."""
    return collection(request, user, Machine, offset, limit, order=(Machine.equipment_id,))


# PUBLIC_INTERFACE
@router.get("/machines/{identifier}", tags=["Equipment"], response_model=Result,
            summary="Equipment detail", description="Include derived status and nonpersisted runtime counter.")
def get_machine(request: Request, identifier: str, user: User):
    """Return one machine by internal UUID in the authenticated plant."""
    with transaction(database(request)) as session:
        return Result(data=equipment.machine_detail(session, user, identifier))


# PUBLIC_INTERFACE
@router.get("/machines/{identifier}/status", tags=["Cases"], response_model=Result,
            summary="Derived machine status", description="Read authoritative alerts; no persisted status projection.")
def machine_status(request: Request, identifier: str, user: User):
    """Return Healthy or At Risk and active alert count for one machine."""
    with transaction(database(request)) as session:
        detail = equipment.machine_detail(session, user, identifier)
        return Result(data={k: detail[k] for k in ("status", "active_alert_count")})


# PUBLIC_INTERFACE
@router.patch("/machines/{identifier}", tags=["Equipment"], response_model=Result,
              summary="Edit equipment details", description="Update descriptive fields with actor and UTC time.")
def equipment_details(request: Request, identifier: str, body: EquipmentDetailsInput,
                      user: Engineer, key: Key):
    """Accept descriptive equipment fields and return the updated plant-scoped record."""
    return execute(request, user, key, body.model_dump(mode="json"), lambda session:
                   equipment.edit_details(session, user, identifier, body))


# PUBLIC_INTERFACE
@router.patch("/parameters/{identifier}/suggested-action", tags=["Equipment"], response_model=Result,
              summary="Edit parameter action", description="Update guidance text for future alerts.")
def suggested_action(request: Request, identifier: str, body: SuggestedActionInput,
                     user: Engineer, key: Key):
    """Accept parameter action text and return the attributed parameter record."""
    return execute(request, user, key, body.model_dump(mode="json"), lambda session:
                   equipment.edit_suggested_action(session, user, identifier, body))


# PUBLIC_INTERFACE
@router.patch("/machines/{identifier}/criticality", tags=["Equipment"], response_model=Result,
              summary="Edit criticality", description="Affects future evaluations only.")
def criticality(request: Request, identifier: str, body: CriticalityInput, user: Engineer, key: Key):
    """Update machine criticality and return the attributed record."""
    return execute(request, user, key, body.model_dump(mode="json"), lambda session:
                   equipment.edit_criticality(session, user, identifier, body))


# PUBLIC_INTERFACE
@router.patch("/parameters/{identifier}/threshold", tags=["Equipment"], response_model=Result,
              summary="Edit maximum threshold", description="Existing alerts and breaches remain unchanged.")
def threshold(request: Request, identifier: str, body: ThresholdInput, user: Engineer, key: Key):
    """Update a configured parameter's safe maximum and return its record."""
    return execute(request, user, key, body.model_dump(mode="json"), lambda session:
                   equipment.edit_threshold(session, user, identifier, body))


# PUBLIC_INTERFACE
@router.post("/readings", tags=["Readings"], response_model=Result, status_code=201,
             summary="Log one reading", description="Validate, detect and consolidate alerts in one durable transaction.")
def log_reading(request: Request, body: ReadingInput,
                user: Annotated[Identity, Depends(reading_writer)], key: Key):
    """Accept one parameter value; return saved reading and associated alert ID."""
    return execute(request, user, key, body.model_dump(mode="json"), lambda session:
                   readings.log_reading(session, user, body, request.app.state.rules))


# PUBLIC_INTERFACE
@router.get("/parameters/{identifier}/readings", tags=["Readings"], response_model=Page,
            summary="Immutable reading history", description="List timestamped readings; no edit or delete interface exists.")
def reading_history(request: Request, identifier: str, user: User,
                    offset: Offset = 0, limit: Limit = 50):
    """Return ascending reading history for an existing plant-scoped parameter."""
    with transaction(database(request)) as session:
        repo = Repository(session, user.plant_id)
        repo.get(Parameter, identifier)
        rows, total = repo.page(
            Reading, offset, limit, Reading.parameter_id == identifier,
            order=(Reading.created_at, Reading.id))
        return Page(data=[serialize(row) for row in rows], total=total, offset=offset, limit=limit)


# PUBLIC_INTERFACE
@router.get("/alerts", tags=["Cases"], response_model=Page,
            summary="Alert queue", description="Fixed priority-score descending, earliest-breach ascending ordering.")
def alert_queue(request: Request, user: User, offset: Offset = 0, limit: Limit = 50):
    """Return all alerts including final alerts; optional filters are deferred."""
    return collection(request, user, Alert, offset, limit, order=(
        Alert.priority_score.desc(), Alert.first_breach_at, Alert.id), view=cases.alert_view)


# PUBLIC_INTERFACE
@router.get("/alerts/{identifier}", tags=["Cases"], response_model=Result,
            summary="Alert detail", description="Include stored score and explicit held display rules.")
def alert_detail(request: Request, identifier: str, user: User):
    """Return an alert and its existing linked work-order IDs."""
    with transaction(database(request)) as session:
        alert = Repository(session, user.plant_id).get(Alert, identifier)
        linked = session.scalars(select(WorkOrder.id).where(
            WorkOrder.alert_id == identifier, WorkOrder.plant_id == user.plant_id)).all()
        return Result(data=dict(**cases.alert_view(alert), work_order_ids=list(linked)))


# PUBLIC_INTERFACE
@router.get("/alerts/{identifier}/breaches", tags=["Cases"], response_model=Page,
            summary="Breach history", description="Every breaching reading retains its own evaluation snapshot.")
def breach_history(request: Request, identifier: str, user: User,
                   offset: Offset = 0, limit: Limit = 50):
    """Return the immutable chronological breach history of an existing alert."""
    with transaction(database(request)) as session:
        repo = Repository(session, user.plant_id)
        repo.get(Alert, identifier)
        rows, total = repo.page(
            Breach, offset, limit, Breach.alert_id == identifier,
            order=(Breach.created_at, Breach.id))
        return Page(data=[serialize(row) for row in rows], total=total, offset=offset, limit=limit)


# PUBLIC_INTERFACE
@router.post("/alerts/{identifier}/dismissal", tags=["Cases"], response_model=Result,
             summary="Dismiss an Open alert", description="Require Engineer, free-text reason, retry key and If-Match version.")
def dismiss_alert(request: Request, identifier: str, body: ReasonInput, user: Engineer, key: Key,
                  expected: Annotated[int, Depends(version)]):
    """Dismiss a plant-scoped alert and return its new state and version."""
    payload = dict(**body.model_dump(mode="json"), version=expected)
    return execute(request, user, key, payload, lambda session:
                   cases.dismiss(session, user, identifier, body.reason, expected))


# PUBLIC_INTERFACE
@router.post("/alerts/{identifier}/work-orders", tags=["Work orders"], response_model=Result,
             summary="Work-order creation (held)", description="No writes until due-day basis and label ownership are decided.")
def create_work_order(identifier: str, user: Engineer, key: Key):
    """Hold creation rather than invent calendar-day defaults or label ownership."""
    held("D-10: calendar versus working days", "CM-Q8")


# PUBLIC_INTERFACE
@router.get("/work-orders", tags=["Work orders"], response_model=Page,
            summary="Work-order list", description="Paginated plant-scoped persisted work orders.")
def work_orders(request: Request, user: User, offset: Offset = 0, limit: Limit = 50):
    """Return work-order records in creation order."""
    return collection(request, user, WorkOrder, offset, limit, order=(WorkOrder.created_at, WorkOrder.id))


# PUBLIC_INTERFACE
@router.get("/work-orders/{identifier}", tags=["Work orders"], response_model=Result,
            summary="Work-order detail", description="Read a plant-scoped work order without mutation.")
def work_order(request: Request, identifier: str, user: User):
    """Return one work order by UUID."""
    with transaction(database(request)) as session:
        return Result(data=serialize(Repository(session, user.plant_id).get(WorkOrder, identifier)))


# PUBLIC_INTERFACE
@router.patch("/work-orders/{identifier}", tags=["Work orders"], response_model=Result,
              summary="Edit work order (held)", description="Object-level authorization and assignee eligibility remain open.")
def edit_work_order(identifier: str, user: Engineer, key: Key):
    """Hold edits pending CM-Q4 and CM-Q7; do not infer any-Engineer permission."""
    held("CM-Q4", "CM-Q7")


# PUBLIC_INTERFACE
@router.post("/work-orders/{identifier}/start", tags=["Work orders"], response_model=Result,
             summary="Start work order (held)", description="Object-level mutation authorization is not settled.")
def start_work_order(identifier: str, user: Engineer, key: Key):
    """Hold mutation until work-order object policy is decided."""
    held("CM-Q4")


# PUBLIC_INTERFACE
@router.post("/work-orders/{identifier}/cancellation", tags=["Work orders"], response_model=Result,
             summary="Cancel work order (held)", description="Cancellation requires a reason; object policy remains held.")
def cancel_work_order(identifier: str, body: ReasonInput, user: Engineer, key: Key):
    """Validate nonblank reason without choosing the unresolved object policy."""
    held("CM-Q4")


# PUBLIC_INTERFACE
@router.put("/work-orders/{identifier}/parts-checklist", tags=["Work orders"], response_model=Result,
            summary="Parts checklist (held)", description="Quantity lower bound and object authorization are unresolved.")
def parts_checklist(identifier: str, user: Engineer, key: Key):
    """Hold checklist updates rather than invent a quantity lower bound."""
    held("CM-Q4", "CM-Q5")


# PUBLIC_INTERFACE
@router.post("/work-orders/{identifier}/closure", tags=["Work orders"], response_model=Result,
             summary="Close work order (held)", description="No partial closure writes are performed while policy is unresolved.")
def close_work_order(identifier: str, user: Engineer, key: Key):
    """Hold closure pending authorization and runtime closure decisions."""
    held("CM-Q4", "D-13", "D-26", "D-30")


# PUBLIC_INTERFACE
@router.post("/work-orders/{identifier}/addenda", tags=["Work orders"], response_model=Result,
             summary="Closed-work-order addendum (held)", description="Object-level write policy remains unresolved.")
def addendum(identifier: str, user: Engineer, key: Key):
    """Hold addendum writes pending work-order object authorization."""
    held("CM-Q4")


# PUBLIC_INTERFACE
@router.get("/dashboard", tags=["Dashboard"], response_model=Result,
            summary="Dashboard (held)", description="Location/type composition awaits definition of open work orders.")
def dashboard(user: Annotated[Identity, Depends(identity)],
              location: str | None = None, equipment_type: str | None = None):
    """Expose Manager prerequisite without granting undecided access to other roles."""
    if user.role != "Manager":
        held("D-17")
    held("D-31")

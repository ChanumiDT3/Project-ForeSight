"""FastAPI composition root. Run with ``uvicorn app.main:app``."""
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api import public_router, router
from app.core import USER_ID_HEADER, AppError
from app.schemas import Problem
from app.seed_users import seed_users_if_empty
from app.storage import make_engine

logger = logging.getLogger("foresight")

# Values of FORESIGHT_SEED_USERS_ON_STARTUP that disable startup seeding.
_DISABLED = {"0", "false", "no", "off"}


def _origins(value):
    """Parse a comma-separated CORS origin list, ignoring blank entries."""
    if not value:
        return []
    if isinstance(value, str):
        value = value.split(",")
    return [origin.strip().rstrip("/") for origin in value if origin and origin.strip()]


def _enabled(value, default=True) -> bool:
    """Interpret a boolean flag from an argument or environment string."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in _DISABLED


def _seed_initial_users(app: FastAPI) -> None:
    """Fill an empty user list from seed/users.json so the identity popup has choices.

    Failures (missing tables, unreadable seed file) are logged and never stop
    the API from starting; ``python -m app.seed_users`` remains available.
    """
    engine, plant_id = app.state.engine, app.state.plant_id
    if not app.state.seed_users_on_startup or engine is None:
        return
    if not isinstance(plant_id, str) or not plant_id:
        return
    try:
        summary = seed_users_if_empty(engine, plant_id)
    except (OSError, ValueError, SQLAlchemyError) as error:
        logger.warning(json.dumps({"event": "user_seed_skipped", "reason": str(error)}))
        return
    if summary:
        logger.warning(json.dumps({"event": "user_seed_loaded", "created": summary["created"]}))


# PUBLIC_INTERFACE
def create_app(database_url=None, plant_id=None, cors_origins=None, seed_users_on_startup=None):
    """Build the FastAPI application from explicit environment-backed configuration.

    ``seed_users_on_startup`` (env FORESIGHT_SEED_USERS_ON_STARTUP, default on)
    loads seed/users.json at startup when the configured plant has no users.
    """

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """Prepare startup data before serving requests."""
        _seed_initial_users(application)
        yield

    app = FastAPI(
        title="ForeSight Maintenance API",
        version="0.2.0",
        lifespan=lifespan,
        description=(
            "Predictive-maintenance MVP backend. There is no sign-in flow: the "
            "frontend selects an active user from public GET /v1/users and sends "
            f"that ID in {USER_ID_HEADER}. Name, role, and plant are resolved "
            "server-side. Unknown/deactivated users receive 401 and roles without "
            "permission receive 403. The known trusted-network limitation is that "
            "a reachable person can choose another real user."
        ),
        openapi_tags=[
            {"name": "Users", "description": "Identity-popup, current-user, and user-directory operations"},
            {"name": "Equipment", "description": "Machines and health parameter configuration"},
            {"name": "Readings", "description": "Immutable reading entry and history"},
            {"name": "Cases", "description": "Alert queue, detail, breaches, and dismissal"},
            {"name": "Work orders", "description": "Work-order lifecycle and closure"},
            {"name": "Dashboard", "description": "Read-only Engineer and Manager overview"},
        ],
    )

    url = database_url or os.getenv("FORESIGHT_DATABASE_URL")
    app.state.engine = make_engine(url) if url else None
    app.state.plant_id = plant_id or os.getenv("FORESIGHT_PLANT_ID")
    app.state.seed_users_on_startup = _enabled(
        seed_users_on_startup
        if seed_users_on_startup is not None
        else os.getenv("FORESIGHT_SEED_USERS_ON_STARTUP")
    )
    app.state.rules = json.loads(Path(__file__).with_name("rules.json").read_text())
    app.state.operational_recipient = os.getenv("FORESIGHT_OPERATIONAL_RECIPIENT")

    origins = _origins(
        cors_origins if cors_origins is not None else os.getenv("FORESIGHT_CORS_ORIGINS")
    )
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "PUT"],
            allow_headers=["Content-Type", USER_ID_HEADER, "Idempotency-Key", "If-Match"],
            expose_headers=["X-Correlation-ID"],
        )

    @app.middleware("http")
    async def correlation(request, call_next):
        """Attach a request correlation ID to all successful and failed responses."""
        request.state.correlation_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return response

    def problem(request, status, code, detail, extra=None):
        """Create a safe problem response with correlation and command metadata."""
        correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
        return JSONResponse(
            status_code=status,
            media_type="application/problem+json",
            headers={"X-Correlation-ID": correlation_id},
            content={
                "type": f"urn:foresight:problem:{code}",
                "title": code,
                "status": status,
                "detail": detail,
                "instance": request.url.path,
                "correlation_id": correlation_id,
                **(extra or {}),
            },
        )

    @app.exception_handler(AppError)
    async def application_error(request: Request, error: AppError):
        """Map application errors to stable RFC-style problem bodies."""
        return problem(request, error.status, error.code, error.detail, error.extra)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        """Map invalid request shapes to a safe validation problem."""
        fields = [f"{'.'.join(map(str, item['loc']))}: {item['type']}" for item in error.errors()]
        return problem(request, 422, "validation_failed", "; ".join(fields))

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        """Normalize framework routing errors into API problem responses."""
        if error.status_code == 404:
            return problem(request, 404, "not_found", "Requested resource was not found")
        if error.status_code == 405:
            return problem(request, 405, "method_not_allowed", "Request method is not allowed")
        return problem(request, error.status_code, "http_error", "Request could not be completed")

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, error: IntegrityError):
        """Hide low-level database conflict details from clients."""
        return problem(
            request,
            409,
            "integrity_conflict",
            "A concurrent or duplicate write conflicts with stored data",
        )

    @app.exception_handler(OperationalError)
    async def storage_error(request: Request, error: OperationalError):
        """Log safe storage-failure metadata and return a retry-safe response."""
        logger.error(
            json.dumps(
                {
                    "event": "storage_failure",
                    "correlation_id": request.state.correlation_id,
                    "recipient": app.state.operational_recipient,
                }
            )
        )
        return problem(
            request,
            503,
            "storage_unavailable",
            "Database unavailable; retry with the same idempotency key",
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        """Avoid leaking unexpected implementation details."""
        logger.error(
            json.dumps(
                {
                    "event": "processing_failure",
                    "correlation_id": getattr(request.state, "correlation_id", None),
                    "recipient": app.state.operational_recipient,
                    "error_type": type(error).__name__,
                }
            )
        )
        return problem(request, 500, "internal_error", "Request failed without partial writes")

    response = {"model": Problem, "content": {"application/problem+json": {}}}
    app.include_router(public_router, responses={503: response})
    app.include_router(
        router,
        responses={
            401: response,
            403: response,
            404: response,
            409: response,
            422: response,
            503: response,
        },
    )
    return app


app = create_app()

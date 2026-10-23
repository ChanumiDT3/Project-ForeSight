"""FastAPI composition root. Run with uvicorn app.main:app."""
import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException

from app.api import router
from app.core import AppError
from app.schemas import Problem
from app.storage import make_engine

logger = logging.getLogger("foresight")


# PUBLIC_INTERFACE
def create_app(database_url=None, identity_verifier=None):
    """Build an app with explicit storage and a trusted synchronous identity adapter.

    The adapter receives a bearer token and returns a validated Identity. No local
    passwords, caller-supplied roles, self-registration, or test bypass is exposed.
    Request FORESIGHT_DATABASE_URL and FORESIGHT_OPERATIONAL_RECIPIENT from the
    user through deployment configuration; this module never reads a .env file.
    """
    app = FastAPI(
        title="ForeSight Maintenance API", version="0.1.0",
        description="Settled MVP backend. 501 rule_unresolved denotes a documented held policy. "
                    "Identity provider integration is required before authenticated use.",
        openapi_tags=[{"name": name, "description": description} for name, description in [
            ("Equipment", "Equipment registry and maximum-only health parameters"),
            ("Readings", "Immutable readings, validation and atomic detection"),
            ("Cases", "Alerts and derived machine status"),
            ("Work orders", "Read interfaces and explicitly held lifecycle operations"),
            ("Dashboard", "Held composition interface"),
        ]],
    )
    url = database_url or os.getenv("FORESIGHT_DATABASE_URL")
    app.state.engine = make_engine(url) if url else None
    app.state.identity_verifier = identity_verifier
    app.state.rules = json.loads(Path(__file__).with_name("rules.json").read_text())
    app.state.operational_recipient = os.getenv("FORESIGHT_OPERATIONAL_RECIPIENT")

    @app.middleware("http")
    async def _correlation(request, call_next):
        request.state.correlation_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return response

    def _problem(request, status, code, detail):
        correlation = getattr(request.state, "correlation_id", str(uuid4()))
        return JSONResponse(
            status_code=status, media_type="application/problem+json",
            headers={"X-Correlation-ID": correlation,
                     **({"WWW-Authenticate": "Bearer"} if status == 401 else {})},
            content=dict(type=f"urn:foresight:problem:{code}", title=code, status=status,
                         detail=detail, instance=request.url.path, correlation_id=correlation),
        )

    @app.exception_handler(AppError)
    async def _application_error(request: Request, error: AppError):
        return _problem(request, error.status, error.code, error.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, error: RequestValidationError):
        # Do not echo input, request bodies, tokens, or arbitrary free text.
        fields = [f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in error.errors()]
        return _problem(request, 422, "validation_failed", "; ".join(fields))

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, error: HTTPException):
        if error.status_code == 404:
            return _problem(request, 404, "not_found", "Requested resource was not found")
        if error.status_code == 405:
            return _problem(request, 405, "method_not_allowed", "Request method is not allowed")
        return _problem(request, error.status_code, "http_error", "Request could not be completed")

    @app.exception_handler(IntegrityError)
    async def _integrity(request: Request, error: IntegrityError):
        return _problem(request, 409, "integrity_conflict", "A concurrent or duplicate write conflicts with stored data")

    @app.exception_handler(OperationalError)
    async def _storage_error(request: Request, error: OperationalError):
        logger.error(json.dumps(dict(event="storage_failure",
                                    correlation_id=request.state.correlation_id,
                                    recipient=app.state.operational_recipient)))
        return _problem(request, 503, "storage_unavailable", "Database unavailable; retry with the same idempotency key")

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, error: Exception):
        logger.error(json.dumps(dict(event="processing_failure",
                                    correlation_id=getattr(request.state, "correlation_id", None),
                                    recipient=app.state.operational_recipient,
                                    error_type=type(error).__name__)))
        return _problem(request, 500, "internal_error", "Request failed without partial writes")

    app.include_router(router, responses={
        code: {"model": Problem, "description": description,
               "content": {"application/problem+json": {}}}
        for code, description in {
            401: "Session missing or invalid", 403: "Role not permitted", 404: "Record not found",
            409: "State, version or retry conflict", 422: "Input rejected",
            501: "Business rule unresolved", 503: "Dependency unavailable",
        }.items()
    })
    return app


app = create_app()

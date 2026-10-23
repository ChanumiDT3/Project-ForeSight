"""Focused regression tests for settled MVP and held-rule boundaries."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core import RequestContext
from app.domain import plain, score
from app.main import create_app
from app.models import Alert, Base, Breach, CommandReceipt, Machine, Parameter, Reading
from app.storage import transaction

# Test-only header naming a predefined test context. It is not a product
# mechanism: how roles, plant scope and actors are supplied is held (D-35, D-36).
TEST_CONTEXT_HEADER = "X-Test-Context"


@pytest.fixture
def client(tmp_path):
    """Provide an isolated real SQLite database with a test-only request-context resolver."""
    contexts = {
        "engineer": RequestContext("e-1", "plant-1", "Engineer"),
        "operator": RequestContext("o-1", "plant-1", "Operator"),
        "manager": RequestContext("m-1", "plant-1", "Manager"),
        "other": RequestContext("e-2", "plant-2", "Engineer"),
    }
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}",
                     lambda request: contexts[request.headers[TEST_CONTEXT_HEADER]])
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.state.engine.dispose()


def _headers(role="engineer", key=None, version=None):
    headers = {TEST_CONTEXT_HEADER: role, "Idempotency-Key": key or str(uuid4())}
    if version is not None:
        headers["If-Match"] = f'"{version}"'
    return headers


def _machine(client, kind="temperature", **overrides):
    body = dict(equipment_id=str(uuid4()), name="Pump", location="North",
                equipment_type="Pump", criticality=2,
                parameters=[dict(kind=kind, name=kind, threshold="80")])
    if kind == "runtime_hours":
        body.update(baseline="1000", current_meter="1050")
    body.update(overrides)
    response = client.post("/v1/machines", json=body, headers=_headers())
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _reading(client, machine, value, **kwargs):
    return client.post("/v1/readings", json=dict(
        parameter_id=machine["parameters"][0]["id"], value=value), headers=_headers(**kwargs))


def _count(client, model):
    with transaction(client.app.state.engine) as session:
        return session.scalar(select(func.count()).select_from(model))


# PUBLIC_INTERFACE
def test_roles_and_plant_isolation(client):
    """Decided three-role permissions and plant isolation apply to the supplied context."""
    assert client.get("/v1/alerts", headers=_headers("operator")).status_code == 403
    machine = _machine(client)
    assert client.get(f"/v1/machines/{machine['id']}", headers=_headers("other")).status_code == 404
    assert client.post("/v1/readings", json=dict(
        parameter_id=machine["parameters"][0]["id"], value=85),
        headers=_headers("manager")).status_code == 403
    assert _reading(client, machine, "85", role="operator").status_code == 201
    with transaction(client.app.state.engine) as session:
        reading = session.scalars(select(Reading)).one()
    assert reading.created_by == "o-1" and reading.plant_id == "plant-1"


# PUBLIC_INTERFACE
def test_no_sign_in_holds_on_request_context(tmp_path):
    """Without sign-in (DL-10) and with no decided context source, nothing is invented.

    No 401 or bearer challenge is produced, a bearer token grants nothing, and
    business endpoints hold on D-35/D-36 without writing anything.
    """
    app = create_app(f"sqlite:///{tmp_path / 'held.db'}")
    Base.metadata.create_all(app.state.engine)
    with TestClient(app, raise_server_exceptions=False) as held_client:
        for headers in ({}, {"Authorization": "Bearer anything"}):
            response = held_client.get("/v1/machines", headers=headers)
            assert response.status_code == 501
            assert response.json()["title"] == "rule_unresolved"
            assert "D-35" in response.json()["detail"] and "D-36" in response.json()["detail"]
            assert "WWW-Authenticate" not in response.headers
        response = held_client.post("/v1/readings", json=dict(parameter_id="x", value="1"),
                                    headers={"Idempotency-Key": "k"})
        assert response.status_code == 501
        assert held_client.get("/v1/dashboard").status_code == 501
        assert held_client.get("/openapi.json").status_code == 200
        assert _count(held_client, CommandReceipt) == _count(held_client, Machine) == 0
    app.state.engine.dispose()


# PUBLIC_INTERFACE
def test_invalid_resolver_output_is_server_error(tmp_path):
    """A resolver violating the RequestContext contract never yields an unscoped request."""
    app = create_app(f"sqlite:///{tmp_path / 'bad.db'}",
                     lambda request: RequestContext("a", "plant-1", "Admin"))
    with TestClient(app, raise_server_exceptions=False) as bad_client:
        response = bad_client.get("/v1/machines")
        assert response.status_code == 500
        assert response.json()["title"] == "request_context_invalid"
    app.state.engine.dispose()


# PUBLIC_INTERFACE
def test_atomic_detection_and_idempotency(client):
    """Retries never duplicate readings, breaches or alert counts."""
    machine = _machine(client)
    first = _reading(client, machine, "85", key="reading-one")
    again = _reading(client, machine, "85", key="reading-one")
    assert first.status_code == again.status_code == 201
    assert first.json() == again.json()
    assert _reading(client, machine, "86", key="reading-one").status_code == 409
    assert _count(client, Reading) == _count(client, Breach) == _count(client, Alert) == 1
    assert _reading(client, machine, "101").status_code == 201
    assert _reading(client, machine, "89").status_code == 201
    queue = client.get("/v1/alerts", headers=_headers()).json()["data"]
    assert len(queue) == 1
    alert = queue[0]
    assert alert["breach_count"] == 3 and alert["priority_score"] == 5
    assert alert["first_value"] == "85" and alert["latest_value"] == "89"
    assert alert["breakdown"] is None and "CM-Q9" in alert["held_rules"]
    history = client.get(f"/v1/alerts/{alert['id']}/breaches", headers=_headers()).json()
    assert history["total"] == 3


# PUBLIC_INTERFACE
@pytest.mark.parametrize("value", ["-0.1", "1000.1", "85.11", "NaN", "Infinity", "text"])
def test_rejected_reading_has_no_side_effects(client, value):
    """Invalid range, precision or syntax leaves the entire signal chain unchanged."""
    machine = _machine(client)
    before = _count(client, CommandReceipt)
    assert _reading(client, machine, value).status_code == 422
    assert _count(client, Reading) == _count(client, Breach) == _count(client, Alert) == 0
    assert _count(client, CommandReceipt) == before


# PUBLIC_INTERFACE
def test_threshold_equality_dismissal_and_new_alert(client):
    """Equality is not a breach; dismissal is versioned, reasoned and final."""
    machine = _machine(client)
    assert _reading(client, machine, "80").status_code == 201
    assert _count(client, Breach) == 0
    _reading(client, machine, "85")
    alert = client.get("/v1/alerts", headers=_headers()).json()["data"][0]
    url = f"/v1/alerts/{alert['id']}/dismissal"
    assert client.post(url, json={"reason": " "},
                       headers=_headers(version=1)).status_code == 422
    assert client.post(url, json={"reason": "False alarm"},
                       headers=_headers(version=9)).status_code == 409
    response = client.post(url, json={"reason": "False alarm"},
                           headers=_headers(key="dismiss", version=1))
    assert response.status_code == 200
    assert client.post(url, json={"reason": "False alarm"},
                       headers=_headers(key="dismiss", version=1)).json() == response.json()
    status = client.get(f"/v1/machines/{machine['id']}/status", headers=_headers()).json()["data"]
    assert status["status"] == "Healthy"
    assert client.post(url, json={"reason": "Again"},
                       headers=_headers(version=2)).status_code == 409
    _reading(client, machine, "85")
    assert _count(client, Alert) == 2


# PUBLIC_INTERFACE
def test_runtime_and_immutable_history(client):
    """Compare runtime against baseline, reject decreasing input, never save registration as reading."""
    machine = _machine(client, "runtime_hours")
    assert _count(client, Reading) == 0
    assert _reading(client, machine, "1080").status_code == 201
    assert _count(client, Breach) == 0
    assert _reading(client, machine, "1080.1").status_code == 201
    assert _count(client, Breach) == 1
    assert _reading(client, machine, "1080").status_code == 422
    assert _reading(client, machine, "999").status_code == 422
    detail = client.get(f"/v1/machines/{machine['id']}", headers=_headers()).json()["data"]
    assert detail["hours_since_service"] == "80.1"
    history = client.get(f"/v1/parameters/{machine['parameters'][0]['id']}/readings",
                         headers=_headers()).json()
    assert history["total"] == 2
    assert client.delete(f"/v1/readings/{history['data'][0]['id']}").status_code in (404, 405)


# PUBLIC_INTERFACE
def test_missing_baseline_never_treated_as_zero(client):
    """Bad legacy data produces no runtime alert and explicitly reports missing baseline."""
    machine = _machine(client, "runtime_hours")
    with transaction(client.app.state.engine, write=True) as session:
        session.get(Machine, machine["id"]).baseline = None
    result = _reading(client, machine, "2000")
    assert result.status_code == 201 and result.json()["data"]["runtime_state"] == "Baseline missing"
    assert _count(client, Breach) == 0


# PUBLIC_INTERFACE
def test_rule_holds_and_input_shape(client):
    """Unresolved variants return question IDs without partial persistence."""
    assert client.post("/v1/machines", json=dict(
        equipment_id="empty", name="Empty", location="A", equipment_type="B",
        criticality=1, parameters=[]), headers=_headers()).status_code == 501
    assert _count(client, Machine) == 0
    machine = _machine(client)
    _reading(client, machine, "85")
    alert = client.get("/v1/alerts", headers=_headers()).json()["data"][0]
    held = client.post(f"/v1/alerts/{alert['id']}/work-orders", headers=_headers())
    assert held.status_code == 501 and "D-10" in held.json()["detail"]
    assert client.post("/v1/work-orders/x/closure", headers=_headers()).status_code == 501
    assert client.get("/v1/dashboard", headers=_headers("manager")).status_code == 501
    result = client.post("/v1/readings", json=dict(
        parameter_id=machine["parameters"][0]["id"], value="1", timestamp="yesterday"),
        headers=_headers())
    assert result.status_code == 422
    assert result.headers["content-type"].startswith("application/problem+json")


# PUBLIC_INTERFACE
def test_transaction_failure_rolls_back_chain(client, monkeypatch):
    """A failure after inserting a reading cannot leave it durably saved alone."""
    machine = _machine(client)
    import app.readings as module

    def fail(*args, **kwargs):
        raise RuntimeError("injected detection handoff failure")

    monkeypatch.setattr(module, "accept_breach", fail)
    response = _reading(client, machine, "85")
    assert response.status_code == 500
    assert _count(client, Reading) == _count(client, Breach) == _count(client, Alert) == 0


# PUBLIC_INTERFACE
def test_concurrent_retry_has_one_effect(client):
    """Serialized command receipt writes de-duplicate concurrent retries."""
    machine = _machine(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _reading(client, machine, "85", key="parallel"), range(2)))
    assert [r.status_code for r in results] == [201, 201]
    assert results[0].json() == results[1].json()
    assert _count(client, Reading) == _count(client, Breach) == _count(client, Alert) == 1


# PUBLIC_INTERFACE
def test_equipment_edits_preserve_existing_evaluation(client):
    """Settled edits are attributed and do not rewrite already evaluated alerts."""
    machine = _machine(client)
    parameter = machine["parameters"][0]["id"]
    _reading(client, machine, "85")
    alert_before = client.get("/v1/alerts", headers=_headers()).json()["data"][0]
    assert client.patch(f"/v1/machines/{machine['id']}", json=dict(
        name="New Pump", location="South", equipment_type="Compressor"),
        headers=_headers()).status_code == 200
    assert client.patch(f"/v1/machines/{machine['id']}/criticality",
                        json={"criticality": 3}, headers=_headers()).status_code == 200
    assert client.patch(f"/v1/parameters/{parameter}/threshold",
                        json={"threshold": "1000"}, headers=_headers()).status_code == 200
    assert client.patch(f"/v1/parameters/{parameter}/suggested-action",
                        json={"suggested_action": "Inspect bearing"},
                        headers=_headers()).status_code == 200
    assert client.get("/v1/alerts", headers=_headers()).json()["data"][0] == alert_before
    assert _reading(client, machine, "1000").status_code == 201
    assert _count(client, Breach) == 1
    for role in ("operator", "manager"):
        assert client.patch(f"/v1/machines/{machine['id']}/criticality",
                            json={"criticality": 1}, headers=_headers(role)).status_code == 403


# PUBLIC_INTERFACE
@pytest.mark.parametrize("value, expected", [("85", 1), ("88", 1), ("89", 2), ("100", 2), ("101", 3)])
def test_score_boundaries(value, expected):
    """Band exact exceedance rather than a rounded display percentage."""
    result = score(Decimal(value), Decimal("80"), 2, ["10", "25"])
    assert result["exceedance_score"] == expected
    for criticality in (1, 2, 3):
        assert score(Decimal(value), Decimal("80"), criticality, ["10", "25"])["priority_score"] == criticality + expected


# PUBLIC_INTERFACE
def test_openapi_and_pagination(client):
    """Composition root exposes documented routes and bounds every collection."""
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "ForeSight Maintenance API"
    assert "/v1/readings" in spec["paths"] and "/v1/work-orders/{identifier}/closure" in spec["paths"]
    # Sign-in is out of MVP scope (DL-10): no security scheme and no 401 response.
    assert "securitySchemes" not in spec.get("components", {})
    assert all("401" not in operation["responses"]
               for path in spec["paths"].values() for operation in path.values())
    assert client.get("/v1/alerts?limit=101", headers=_headers()).status_code == 422
    assert client.get("/v1/alerts?offset=-1", headers=_headers()).status_code == 422


# PUBLIC_INTERFACE
def test_migration_upgrade_and_retention_guard(tmp_path, monkeypatch):
    """Initial migration is repeatable; destructive downgrade is intentionally refused."""
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("FORESIGHT_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    app = create_app(url, lambda request: RequestContext("e", "p", "Engineer"))
    with TestClient(app) as migrated:
        _machine(migrated)
    with pytest.raises(RuntimeError, match="Destructive downgrade"):
        command.downgrade(config, "base")
    app.state.engine.dispose()


# PUBLIC_INTERFACE
def test_reads_and_writes_run_in_explicit_transactions(client):
    """Read pages (count plus rows) share one snapshot; writes hold the writer lock."""
    for write in (False, True):
        with transaction(client.app.state.engine, write=write) as session:
            assert session.connection().connection.dbapi_connection.in_transaction


# PUBLIC_INTERFACE
def test_canonical_decimal_and_timestamp_storage(client):
    """Values never persist in exponent notation; UTC timestamps are fixed width."""
    assert plain(Decimal("1E+2")) == "100" and plain(Decimal("-0")) == "0"
    assert plain(Decimal("85.10")) == "85.10"
    machine = _machine(client)
    reading = _reading(client, machine, "1E+1").json()["data"]["reading"]
    assert reading["value"] == "10"
    assert reading["created_at"].endswith("+00:00") and len(reading["created_at"]) == 32
    assert _reading(client, machine, "16E+1").status_code == 201
    alert = client.get("/v1/alerts", headers=_headers()).json()["data"][0]
    assert alert["first_value"] == "160" and alert["breakdown"]["exceedance_percent"] == "100"
    assert alert["created_at"] == alert["first_breach_at"]


# PUBLIC_INTERFACE
def test_registration_validates_before_any_write(client):
    """An invalid later parameter rejects the whole registration with nothing saved."""
    response = client.post("/v1/machines", json=dict(
        equipment_id="M-1", name="Press", location="A", equipment_type="Press", criticality=1,
        parameters=[dict(kind="temperature", name="Temp", threshold="80"),
                    dict(kind="custom", name="Flow", threshold="5")]), headers=_headers())
    assert response.status_code == 422 and response.json()["title"] == "custom_required"
    assert _count(client, Machine) == _count(client, Parameter) == 0
    unknown = client.get("/v1/unknown", headers=_headers())
    assert unknown.status_code == 404 and unknown.json()["title"] == "not_found"

"""Startup seeding of equipment so the Log reading Parameter dropdown has choices."""
import json

import pytest
from fastapi.testclient import TestClient

from app.core import USER_ID_HEADER, RequestContext
from app.equipment import register
from app.main import create_app
from app.models import Base
from app.schemas import MachineInput
from app.seed_equipment import DEFAULT_SEED, seed_equipment, validate_seed
from app.storage import transaction

OPERATOR = {USER_ID_HEADER: "u-ana"}
# Documented M-100 Press 1 parameters (UI Wireframes S2/S3).
SEEDED_PARAMETERS = [
    ("Temperature", "degrees C", "80"),
    ("Vibration", "mm/s", "12"),
    ("Runtime hours", "hours", "100"),
]


@pytest.fixture
def make_app(tmp_path):
    """Build apps on an isolated SQLite file and dispose their engines afterwards."""
    apps = []

    def build(**kwargs):
        app = create_app(f"sqlite:///{tmp_path / 'seed.db'}", "plant-1",
                         seed_users_on_startup=True, **kwargs)
        Base.metadata.create_all(app.state.engine)
        apps.append(app)
        return app

    yield build
    for app in apps:
        app.state.engine.dispose()


def _targets(client):
    response = client.get("/v1/readings/targets", headers=OPERATOR)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_empty_database_offers_seeded_parameters_for_reading_entry(make_app):
    with TestClient(make_app(seed_equipment_on_startup=True)) as client:
        targets = _targets(client)
    assert [(t["equipment_id"], t["name"]) for t in targets] == [("M-100", "Press 1")]
    assert [(p["name"], p["unit"], p["threshold"]) for p in targets[0]["parameters"]] == SEEDED_PARAMETERS
    assert targets[0]["baseline"] == "5000.0"
    assert targets[0]["parameters"][0]["created_by"] == "u-raj"


def test_seeded_parameter_accepts_a_reading(make_app):
    with TestClient(make_app(seed_equipment_on_startup=True)) as client:
        parameter_id = _targets(client)[0]["parameters"][0]["id"]
        response = client.post("/v1/readings", headers={**OPERATOR, "Idempotency-Key": "k-1"},
                               json={"parameter_id": parameter_id, "value": "25.0"})
    assert response.status_code == 201, response.text


def test_existing_machines_are_left_untouched(make_app):
    app = make_app(seed_equipment_on_startup=False)
    with TestClient(app):  # seeds users only
        pass
    with transaction(app.state.engine, write=True) as session:
        context = RequestContext(actor="u-raj", plant_id="plant-1", role="Engineer")
        register(session, context, MachineInput(equipment_id="L-1", name="Local", location="Bay",
                                                equipment_type="Conveyor", criticality=1), app.state.rules)
    with TestClient(make_app(seed_equipment_on_startup=True)) as client:
        assert [t["equipment_id"] for t in _targets(client)] == ["L-1"]


def test_startup_seeding_can_be_disabled(make_app):
    with TestClient(make_app(seed_equipment_on_startup=False)) as client:
        assert _targets(client) == []


def test_rerunning_seed_skips_existing_equipment(make_app):
    app = make_app(seed_equipment_on_startup=True)
    with TestClient(app):
        pass
    summary = seed_equipment(app.state.engine, "plant-1", json.loads(DEFAULT_SEED.read_text("utf-8")))
    assert summary == {"created": [], "skipped": ["M-100"]}


def test_seed_must_be_registered_by_an_engineer(make_app):
    app = make_app(seed_equipment_on_startup=False)
    with TestClient(app):
        pass
    document = {**json.loads(DEFAULT_SEED.read_text("utf-8")), "registered_by": "u-ana"}
    with pytest.raises(ValueError, match="Engineer"):
        seed_equipment(app.state.engine, "plant-1", document)


def test_invalid_seed_is_rejected_before_writing():
    with pytest.raises(ValueError, match="machines must be a JSON list"):
        validate_seed({"registered_by": "u-raj", "machines": {}})

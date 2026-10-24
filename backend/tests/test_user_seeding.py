"""Startup seeding of the identity-popup user list (GET /v1/users)."""
import pytest
from fastapi.testclient import TestClient

from app.core import utcnow
from app.main import create_app
from app.models import Base, User
from app.storage import transaction

SEEDED_NAMES = ["Ana Silva", "Mei Chen", "Priya Sharma", "Raj Patel"]


@pytest.fixture
def make_app(tmp_path):
    """Build apps on an isolated SQLite file and dispose their engines afterwards."""
    apps = []

    def build(create_tables=True, **kwargs):
        app = create_app(f"sqlite:///{tmp_path / 'seed.db'}", "plant-1", **kwargs)
        if create_tables:
            Base.metadata.create_all(app.state.engine)
        apps.append(app)
        return app

    yield build
    for app in apps:
        app.state.engine.dispose()


def _user_names(app):
    with TestClient(app) as client:
        response = client.get("/v1/users")
    assert response.status_code == 200, response.text
    return [row["name"] for row in response.json()["data"]]


def test_empty_database_is_populated_on_startup(make_app):
    assert _user_names(make_app(seed_users_on_startup=True)) == SEEDED_NAMES


def test_existing_users_are_left_untouched(make_app):
    app = make_app(seed_users_on_startup=True)
    with transaction(app.state.engine, write=True) as session:
        now = utcnow()
        session.add(User(id="u-local", plant_id="plant-1", name="Local Person",
                         email="local@example.com", role="Engineer", active=True,
                         created_at=now, updated_at=now))
    assert _user_names(app) == ["Local Person"]


def test_startup_seeding_can_be_disabled(make_app):
    assert _user_names(make_app(seed_users_on_startup=False)) == []


def test_missing_tables_do_not_block_startup(make_app):
    app = make_app(create_tables=False, seed_users_on_startup=True)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

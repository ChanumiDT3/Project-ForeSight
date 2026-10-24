"""Backend configuration loading without shell-exported variables."""
import os

import pytest

from app.settings import BACKEND_DIR, load_environment, parse_env_file, resolve_sqlite_url

KEYS = ("FORESIGHT_DATABASE_URL", "FORESIGHT_PLANT_ID", "FORESIGHT_EXTRA")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Start every test without the variables the loader may set."""
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    yield
    # monkeypatch restores originals; also remove anything setdefault() added.
    for key in KEYS:
        os.environ.pop(key, None)


# PUBLIC_INTERFACE
def test_env_file_is_loaded_and_relative_sqlite_path_resolved(tmp_path):
    """Values from .env fill the environment; ./db paths are relative to the file."""
    env = tmp_path / ".env"
    env.write_text("# comment\nFORESIGHT_DATABASE_URL=sqlite:///./foresight.db\n"
                   "export FORESIGHT_PLANT_ID='plant-9'\n\nnot a pair\n", encoding="utf-8")
    assert load_environment(env, tmp_path / ".env.example") == env
    assert os.environ["FORESIGHT_DATABASE_URL"] == "sqlite:///" + (tmp_path / "foresight.db").resolve().as_posix()
    assert os.environ["FORESIGHT_PLANT_ID"] == "plant-9"


# PUBLIC_INTERFACE
def test_real_environment_wins(tmp_path, monkeypatch):
    """Deployment-provided variables are never overridden by files."""
    env = tmp_path / ".env"
    env.write_text("FORESIGHT_PLANT_ID=from-file\nFORESIGHT_EXTRA=x\n", encoding="utf-8")
    monkeypatch.setenv("FORESIGHT_PLANT_ID", "from-shell")
    load_environment(env, tmp_path / ".env.example")
    assert os.environ["FORESIGHT_PLANT_ID"] == "from-shell"
    assert os.environ["FORESIGHT_EXTRA"] == "x"


# PUBLIC_INTERFACE
def test_example_file_is_fallback_and_missing_files_are_ignored(tmp_path):
    """Without .env the committed example supplies values; with neither nothing changes."""
    example = tmp_path / ".env.example"
    assert load_environment(tmp_path / ".env", example) is None
    assert "FORESIGHT_PLANT_ID" not in os.environ
    example.write_text('FORESIGHT_PLANT_ID="plant-1"\n', encoding="utf-8")
    assert load_environment(tmp_path / ".env", example) == example
    assert os.environ["FORESIGHT_PLANT_ID"] == "plant-1"


# PUBLIC_INTERFACE
def test_committed_example_configures_database_and_plant():
    """The repository's .env.example is enough for a fresh checkout to start."""
    values = parse_env_file(BACKEND_DIR / ".env.example")
    assert values["FORESIGHT_DATABASE_URL"].startswith("sqlite:///")
    assert values["FORESIGHT_PLANT_ID"]


# PUBLIC_INTERFACE
@pytest.mark.parametrize("url", ["sqlite:////abs/path.db", "sqlite:///:memory:", "sqlite:///", "postgresql://x/y"])
def test_non_relative_urls_are_unchanged(url, tmp_path):
    """Only relative SQLite file paths are rewritten."""
    assert resolve_sqlite_url(url, tmp_path) == url

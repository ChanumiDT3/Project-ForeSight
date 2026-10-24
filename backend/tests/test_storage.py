"""SQLite engine creation must not fail when the database directory is missing."""
from pathlib import Path

from sqlalchemy import text

from app.storage import ensure_sqlite_directory, make_engine


# PUBLIC_INTERFACE
def test_missing_database_directory_is_created_and_usable(tmp_path):
    """A sqlite:/// URL under a not-yet-existing directory connects successfully."""
    database = tmp_path / "missing" / "nested" / "foresight.db"
    engine = make_engine("sqlite:///" + database.as_posix())
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar() == 1
    finally:
        engine.dispose()
    assert database.parent.is_dir()
    assert database.is_file()


# PUBLIC_INTERFACE
def test_in_memory_and_query_string_urls_are_handled(tmp_path):
    """In-memory URLs need no directory; query strings are not part of the path."""
    assert ensure_sqlite_directory("sqlite:///:memory:") is None
    assert ensure_sqlite_directory("sqlite:///") is None
    target = tmp_path / "with-query"
    assert ensure_sqlite_directory(f"sqlite:///{target.as_posix()}/db.sqlite?timeout=5") == target
    assert target.is_dir()


# PUBLIC_INTERFACE
def test_uncreatable_directory_is_logged_not_raised(tmp_path):
    """A blocked path (a file where the directory should be) does not raise."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    assert ensure_sqlite_directory("sqlite:///" + (blocker / "foresight.db").as_posix()) is None
    assert Path(blocker).is_file()

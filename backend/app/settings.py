"""Load backend configuration files into the process environment.

The backend reads its configuration (FORESIGHT_DATABASE_URL, FORESIGHT_PLANT_ID,
...) from environment variables. Previously those variables had to be exported
by the shell first (``set -a; . ./.env; set +a``). That failed whenever
``backend/.env`` was missing (it is gitignored, so fresh checkouts and workspace
resets do not have it) and does not work on Windows at all, so the API never
started and the frontend could not load the user list.

``load_environment`` makes the API, the Alembic migrations and the user seeding
command read the configuration themselves:

1. Variables already set in the real environment always win (deployments and
   CI keep full control).
2. Otherwise values come from ``backend/.env`` when it exists.
3. Otherwise the committed ``backend/.env.example`` supplies the documented
   local-development values, so a fresh checkout starts without manual setup.

Relative SQLite paths in a file (for example ``sqlite:///./foresight.db``) are
resolved against the ``backend/`` directory so that migrations, seeding and the
API always use the same database file regardless of the working directory.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger("foresight")

# The backend/ directory that holds .env, .env.example, alembic.ini and seed/.
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Configuration files checked in order; only the first existing file is used.
ENV_FILE = BACKEND_DIR / ".env"
EXAMPLE_ENV_FILE = BACKEND_DIR / ".env.example"

DATABASE_URL_VARIABLE = "FORESIGHT_DATABASE_URL"
_SQLITE_PREFIX = "sqlite:///"


# PUBLIC_INTERFACE
def parse_env_file(path: Path) -> dict[str, str]:
    """Parse simple ``KEY=VALUE`` lines from a dotenv-style file.

    Blank lines and ``#`` comment lines are ignored, an optional leading
    ``export`` is accepted, and one pair of matching surrounding quotes is
    removed from a value. Lines without ``=`` or with an invalid key are skipped.
    """
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not key.isidentifier():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


# PUBLIC_INTERFACE
def resolve_sqlite_url(url: str, base_dir: Path = BACKEND_DIR) -> str:
    """Make a relative ``sqlite:///`` file path absolute against ``base_dir``.

    Absolute paths, in-memory databases and non-SQLite URLs are returned
    unchanged (non-SQLite URLs are rejected later by ``make_engine``).
    """
    if not url.startswith(_SQLITE_PREFIX):
        return url
    location = url[len(_SQLITE_PREFIX):]
    if not location or location.startswith(":memory:") or Path(location).is_absolute():
        return url
    return _SQLITE_PREFIX + (base_dir / location).resolve().as_posix()


# PUBLIC_INTERFACE
def load_environment(env_file: Path = ENV_FILE, example_file: Path = EXAMPLE_ENV_FILE) -> Path | None:
    """Fill unset configuration variables from ``.env`` (or ``.env.example``).

    Existing environment variables are never overridden. Returns the file that
    supplied values, or ``None`` when neither file exists.
    """
    source = env_file if env_file.is_file() else example_file if example_file.is_file() else None
    if source is None:
        return None
    if source == example_file:
        logger.warning(
            "%s not found; using local-development defaults from %s",
            env_file.name,
            example_file.name,
        )
    for key, value in parse_env_file(source).items():
        if key == DATABASE_URL_VARIABLE:
            # Relative paths are relative to the file's directory, not the cwd.
            value = resolve_sqlite_url(value, source.parent)
        os.environ.setdefault(key, value)
    return source

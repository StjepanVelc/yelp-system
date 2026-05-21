import os
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text


def find_repo_root(start: Path) -> Optional[Path]:
    """Walk upward to locate repository root by known project files."""
    markers = {"docker-compose.yml", "README.md"}
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if all((candidate / marker).exists() for marker in markers):
            return candidate
    return None

def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_database_url() -> str:
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    has_postgres_vars = any(
        os.getenv(name)
        for name in ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    )
    if has_postgres_vars:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5432")
        database = os.getenv("POSTGRES_DB", "yelp")
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "change_me")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    return "postgresql://postgres:change_me@localhost:5432/yelp"


repo_root = find_repo_root(Path(__file__).resolve().parent)
if repo_root:
    load_dotenv(repo_root / ".env")
    load_dotenv(repo_root / ".env.local")

database_url = resolve_database_url()
e = create_engine(database_url)

if "--count-only" in sys.argv:
    with e.connect() as c:
        count = c.execute(text("SELECT COUNT(*) FROM reviews")).scalar() or 0
        print(int(count))
    raise SystemExit(0)

print(f"Using DATABASE_URL: {database_url}")

with e.connect() as c:
    cols = c.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='reviews' ORDER BY ordinal_position")).fetchall()
    for col in cols:
        print(col[0], col[1])
    print()
    rows = c.execute(text("SELECT * FROM reviews WHERE business_id='ROeacJQwBeh05Rqg7F6TCg' ORDER BY date DESC LIMIT 3")).fetchall()
    for row in rows:
        print(dict(row._mapping))

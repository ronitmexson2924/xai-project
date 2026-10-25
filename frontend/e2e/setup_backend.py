"""Prepare a fresh database for the browser tests and start the API (run from backend/).

    python ../frontend/e2e/setup_backend.py

Drops and recreates the E2E database, migrates it, loads content/, creates the E2E admin, then
execs uvicorn. Never point E2E_DATABASE_URL at a database you want to keep.
"""

import os
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

url = make_url(os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://pcg:pcg@localhost:5432/pcg_e2e"
))
if not url.database or not url.database.endswith("_e2e"):
    sys.exit(f"refusing to reset {url.database!r}: the E2E database name must end in _e2e")
os.environ.setdefault("JWT_SECRET", "e2e-only-secret-" + "x" * 32)
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3005")
os.environ.setdefault("ANALYSIS_SALT", "e2e-salt-0123456789")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("INCLUDE_DRAFT_ITEMS", "true")  # the item bank awaits review (S3)

admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with admin.connect() as conn:
    conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
    conn.execute(text(f'CREATE DATABASE "{url.database}"'))
admin.dispose()

subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
subprocess.run([sys.executable, "-m", "app.graph.seed", "../content"], check=True)

from app.auth.onboard import create_admin  # noqa: E402 (needs DATABASE_URL set first)
from app.db.session import SessionLocal  # noqa: E402

with SessionLocal() as session:
    create_admin(session, "e2e-admin@example.com", "E2e-admin-pass-1", "E2E Admin")
    session.commit()

os.execvp(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"])

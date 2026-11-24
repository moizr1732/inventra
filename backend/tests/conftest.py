"""Test configuration.

Tests run against a dedicated PostgreSQL database. The fixture refuses to
run unless the database name contains "test", and it rebuilds the schema
from Alembic migrations once per session, so the migrations are exercised
on every run.
"""
import os

os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "testpass")
os.environ.setdefault("POSTGRES_HOST", "127.0.0.1")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "inventra_test")
os.environ["GROQ_API_KEY"] = ""

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import BACKEND_DIR, settings  # noqa: E402
from app.database.connection import engine  # noqa: E402
from app.main import app  # noqa: E402

assert "test" in settings.POSTGRES_DB.lower(), (
    "Refusing to run tests against a non-test database: " + settings.POSTGRES_DB
)


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(_alembic_config(), "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE assistant_messages, assistant_conversations, forecast_overrides, "
                "inventory_consumption, purchase_orders, inventory_items RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def alembic_cfg():
    return _alembic_config()

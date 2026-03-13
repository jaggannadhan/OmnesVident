"""
Shared pytest fixtures for api_storage tests.

All tests use an in-memory SQLite database to stay isolated and fast.
The FastAPI dependency `get_db_session` is overridden so no test ever
touches the real on-disk database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, StaticPool

import api_storage.database as db_module
from api_storage.routes import app
from api_storage.database import get_db_session


@pytest.fixture(name="engine", scope="function")
def engine_fixture():
    """In-memory SQLite engine — fresh for every test function."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(name="session", scope="function")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client", scope="function")
def client_fixture(engine):
    """TestClient with the DB dependency overridden to use the test engine."""

    def override_get_db_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    # Also patch the module-level engine used by the lifespan & background tasks
    original_engine = db_module.engine
    db_module.engine = engine

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    app.dependency_overrides.clear()
    db_module.engine = original_engine

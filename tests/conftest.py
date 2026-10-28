"""Fixtures compartidos de Pytest según el estándar de la Guía del Dojo."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.db.session import Base, get_db
from app.main import app

# Motor SQLite en memoria para tests ultra-rápidos sin necesidad de Docker
ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Crea y destruye las tablas para cada test unitario.
    Garantiza que cada test parte de una base de datos limpia y aislada.
    """
    Base.metadata.create_all(bind=ENGINE)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=ENGINE)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    Cliente HTTP de prueba con la base de datos en memoria inyectada.
    Equivalente al TestRestTemplate de Spring Boot según la guía académica.
    """

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

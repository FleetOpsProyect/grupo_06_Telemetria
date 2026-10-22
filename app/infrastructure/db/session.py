"""Configuración de base de datos relacional y gestión de sesiones con SQLAlchemy."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Conexión relacional con pool de conexiones configurado
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size if "sqlite" not in settings.database_url else 5,
    max_overflow=settings.db_max_overflow if "sqlite" not in settings.database_url else 10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Clase base declarativa para modelos ORM de SQLAlchemy 2.0."""


def get_db() -> Generator[Session, None, None]:
    """
    Dependencia FastAPI para inyectar una sesión de base de datos por petición.

    Asegura el cierre automático al finalizar el ciclo de vida del request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

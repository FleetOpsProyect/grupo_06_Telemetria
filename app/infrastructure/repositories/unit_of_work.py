"""Unidad de trabajo sobre una sesion de SQLAlchemy (ruta + outbox)"""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError, DuplicateEntityError
from app.domain.ports.repositories import IUnitOfWork


class SqlAlchemyUnitOfWork(IUnitOfWork):
    """Unidad de trabajo que coordina la persistencia de rutas y eventos outbox."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def commit(self) -> None:
        """Confirma la transacción actual."""
        try:
            self.session.commit()
        except IntegrityError as e:
            self.session.rollback()
            raise DuplicateEntityError("Ya existe una ruta con el mismo ID o asignación.") from e
        except SQLAlchemyError as e:
            self.session.rollback()
            raise DatabaseUnavailableError("La base de datos no está disponible.") from e

    def rollback(self) -> None:
        try:
            self.session.rollback()
        except SQLAlchemyError:
            pass

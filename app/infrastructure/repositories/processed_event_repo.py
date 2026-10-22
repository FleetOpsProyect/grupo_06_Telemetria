"""Implementación del repositorio de deduplicación para Idempotent Consumer."""

from sqlalchemy.orm import Session

from app.domain.ports.repositories import IProcessedEventRepository
from app.infrastructure.db.orm_models import ProcessedEventModel


class SqlAlchemyProcessedEventRepository(IProcessedEventRepository):
    """Adaptador de persistencia para la tabla eventos_procesados."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def is_processed(self, evento_id: str) -> bool:
        """Verifica si el evento_id ya fue registrado."""
        model = self.session.get(ProcessedEventModel, evento_id)
        return model is not None

    def mark_processed(self, evento_id: str, tipo_evento: str) -> None:
        """Inserta el evento_id para evitar futuros reprocesamientos."""
        if not self.is_processed(evento_id):
            model = ProcessedEventModel(evento_id=evento_id, tipo_evento=tipo_evento)
            self.session.add(model)
            self.session.commit()

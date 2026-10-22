"""Implementación del repositorio para el patrón Transactional Outbox."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.ports.repositories import IOutboxRepository, OutboxRecord
from app.infrastructure.db.orm_models import OutboxModel


class SqlAlchemyOutboxRepository(IOutboxRepository):
    """Adaptador de persistencia para outbox_eventos."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, record: OutboxRecord) -> OutboxRecord:
        """Inserta un evento outbox en la transacción de base de datos."""
        model = OutboxModel(
            id=record.id,
            evento_id=record.evento_id,
            tipo_evento=record.tipo_evento,
            routing_key=record.routing_key,
            payload_json=record.payload_json,
            estado=record.estado,
            intentos=record.intentos,
        )
        self.session.add(model)
        self.session.commit()
        return record

    def get_pending(self, limit: int = 50) -> list[OutboxRecord]:
        """Obtiene los eventos pendientes de despacho."""
        stmt = (
            select(OutboxModel)
            .where(OutboxModel.estado == "PENDIENTE")
            .order_by(OutboxModel.created_at)
            .limit(limit)
        )
        models = self.session.execute(stmt).scalars().all()
        return [
            OutboxRecord(
                id=m.id,
                evento_id=m.evento_id,
                tipo_evento=m.tipo_evento,
                routing_key=m.routing_key,
                payload_json=m.payload_json,
                estado=m.estado,
                intentos=m.intentos,
                created_at=m.created_at,
                sent_at=m.sent_at,
            )
            for m in models
        ]

    def mark_published(self, record_id: str) -> None:
        """Marca el evento outbox como PUBLICADO."""
        model = self.session.get(OutboxModel, record_id)
        if model:
            model.estado = "PUBLICADO"
            model.sent_at = datetime.now(UTC)
            self.session.commit()

    def mark_failed(self, record_id: str) -> None:
        """Incrementa los intentos de despacho ante fallo transitorio."""
        model = self.session.get(OutboxModel, record_id)
        if model:
            model.intentos += 1
            if model.intentos >= 5:
                model.estado = "FALLIDO"
            self.session.commit()

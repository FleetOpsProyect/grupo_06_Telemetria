"""Publicador de eventos en AWS SNS y worker de despacho de Outbox."""

import json
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.domain.ports.event_publisher import IEventPublisher
from app.domain.ports.repositories import IOutboxRepository
from app.infrastructure.messaging.connection import get_sns_client


def _tipo_evento(payload_json: str, default: str) -> str:
    """Lee tipo_evento del JSON para usarlo como atributo de filtrado en SNS."""
    try:
        data = json.loads(payload_json)
    except ValueError:
        return default
    value = data.get("tipo_evento") if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else default


class SnsEventPublisher(IEventPublisher):
    """Adaptador que publica los eventos del outbox en el tópico SNS de FleetOps."""

    def __init__(self, topic_arn: str | None = None, client: Any | None = None) -> None:
        self.topic_arn = topic_arn or settings.sns_topic_arn
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = get_sns_client()
        return self._client

    def publish(self, routing_key: str, payload_json: str) -> bool:
        """
        Publica el JSON en SNS con los atributos tipo_evento y routing_key.

        Las suscripciones SQS de otros servicios filtran por esos atributos.
        """
        if not self.topic_arn:
            logger.warning("SNS_TOPIC_ARN no está configurado; el evento queda pendiente.")
            return False
        try:
            self.client.publish(
                TopicArn=self.topic_arn,
                Message=payload_json,
                MessageAttributes={
                    "tipo_evento": {
                        "DataType": "String",
                        "StringValue": _tipo_evento(payload_json, routing_key),
                    },
                    "routing_key": {"DataType": "String", "StringValue": routing_key},
                },
            )
            return True
        except Exception as e:
            logger.error(f"Error al publicar mensaje en SNS: {e}")
            return False


def dispatch_pending_outbox_events(
    outbox_repo: IOutboxRepository, publisher: IEventPublisher
) -> int:
    """Worker que despacha los eventos pendientes acumulados en la tabla outbox_eventos."""
    pending = outbox_repo.get_pending(limit=20)
    dispatched_count = 0

    for item in pending:
        try:
            success = publisher.publish(item.routing_key, item.payload_json)
            if success:
                outbox_repo.mark_published(item.id)
                dispatched_count += 1
            else:
                outbox_repo.mark_failed(item.id)
        except Exception as e:
            logger.error(f"Fallo al despachar outbox {item.id}: {e}")
            outbox_repo.mark_failed(item.id)

    return dispatched_count

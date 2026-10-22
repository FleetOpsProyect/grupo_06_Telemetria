"""Publicador de eventos en RabbitMQ y worker de despacho de Outbox."""

import pika

from app.core.config import settings
from app.core.logging import logger
from app.domain.ports.event_publisher import IEventPublisher
from app.domain.ports.repositories import IOutboxRepository
from app.infrastructure.messaging.connection import get_rabbitmq_connection


class RabbitMQEventPublisher(IEventPublisher):
    """Adaptador de publicación de eventos hacia el exchange topic fleetops.events."""

    def __init__(self, exchange: str | None = None) -> None:
        self.exchange = exchange or settings.rabbitmq_exchange

    def publish(self, routing_key: str, payload_json: str) -> bool:
        """Publica un mensaje persistente en RabbitMQ."""
        conn = get_rabbitmq_connection()
        if not conn:
            return False

        try:
            channel = conn.channel()
            # Declarar exchange topic durable
            channel.exchange_declare(exchange=self.exchange, exchange_type="topic", durable=True)

            channel.basic_publish(
                exchange=self.exchange,
                routing_key=routing_key,
                body=payload_json.encode("utf-8"),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Mensaje persistente en disco
                    content_type="application/json",
                ),
            )
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error al publicar mensaje en RabbitMQ: {e}")
            if conn and not conn.is_closed:
                conn.close()
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

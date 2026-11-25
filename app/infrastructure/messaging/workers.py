"""Hilos en segundo plano: despacho del outbox a SNS y consumo de la cola SQS."""

import threading
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.messaging.consumers.sqs_consumer import SqsAssignmentConsumer
from app.infrastructure.messaging.publisher import (
    SnsEventPublisher,
    dispatch_pending_outbox_events,
)
from app.infrastructure.repositories.outbox_repository import SqlAlchemyOutboxRepository


class MessagingWorkers:
    """Arranca y detiene los dos workers de mensajería junto con la aplicación."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        for name, target in (
            ("outbox-sns", self._outbox_loop),
            ("sqs-consumer", self._consumer_loop),
        ):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._threads.append(thread)
        logger.info("Workers de mensajería SNS/SQS iniciados.")

    def stop(self, timeout: float = 25.0) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=timeout)
        logger.info("Workers de mensajería SNS/SQS detenidos.")

    def _outbox_loop(self) -> None:
        publisher = SnsEventPublisher()
        while not self._stop.is_set():
            try:
                with self.session_factory() as session:
                    sent = dispatch_pending_outbox_events(
                        SqlAlchemyOutboxRepository(session), publisher
                    )
                if sent:
                    logger.info(f"Outbox: {sent} evento(s) publicados en SNS.")
            except Exception as e:
                logger.error(f"Fallo en el ciclo del outbox: {e}")
            self._stop.wait(settings.outbox_dispatch_interval_seconds)

    def _consumer_loop(self) -> None:
        consumer = SqsAssignmentConsumer(self.session_factory)
        while not self._stop.is_set():
            try:
                consumer.poll_once()
            except Exception as e:
                logger.error(f"Fallo leyendo la cola SQS: {e}")
                self._stop.wait(5)

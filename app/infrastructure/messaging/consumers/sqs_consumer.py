"""Consumidor de la cola SQS de Telemetría (eventos de Asignaciones vía SNS)."""

import json
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.messaging.assignment_handler import handle_assignment_message
from app.infrastructure.messaging.connection import get_sqs_client


def unwrap_sns_envelope(body: str) -> str:
    """
    Devuelve el JSON de dominio.

    Si la suscripción SNS→SQS no usa "raw message delivery", SNS envuelve el evento
    en {"Type": "Notification", "Message": "<json>"}; aquí se extrae ese Message.
    """
    try:
        data = json.loads(body)
    except ValueError:
        return body
    if isinstance(data, dict) and data.get("Type") == "Notification" and "Message" in data:
        return str(data["Message"])
    return body


class SqsAssignmentConsumer:
    """Lee la cola, procesa cada mensaje y lo borra solo si el commit fue exitoso."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        queue_url: str | None = None,
        client: Any | None = None,
        handler: Callable[[Callable[[], Session], str], None] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.queue_url = queue_url or settings.sqs_queue_url
        self._client = client
        self.handler = handler or (lambda factory, body: handle_assignment_message(factory, body))

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = get_sqs_client()
        return self._client

    def poll_once(self, wait_time_seconds: int | None = None) -> int:
        """
        Hace una lectura (long polling) y procesa los mensajes recibidos.

        Si un mensaje falla NO se borra: SQS lo vuelve a entregar al vencer el
        visibility timeout y, tras maxReceiveCount intentos, lo mueve a la DLQ.
        Retorna cuántos mensajes se procesaron y borraron.
        """
        response = self.client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=settings.sqs_max_messages,
            WaitTimeSeconds=(
                settings.sqs_wait_time_seconds if wait_time_seconds is None else wait_time_seconds
            ),
            MessageAttributeNames=["All"],
        )
        processed = 0
        for message in response.get("Messages", []):
            message_id = message.get("MessageId", "?")
            try:
                self.handler(self.session_factory, unwrap_sns_envelope(message["Body"]))
            except Exception as e:
                logger.error(
                    f"No se pudo procesar el mensaje SQS {message_id}; se reintentará: {e}"
                )
                continue
            self.client.delete_message(
                QueueUrl=self.queue_url, ReceiptHandle=message["ReceiptHandle"]
            )
            processed += 1
        return processed

"""Puerto abstracto para publicación de eventos en el broker de mensajería."""

from abc import ABC, abstractmethod


class IEventPublisher(ABC):
    """Puerto de salida para emitir eventos hacia RabbitMQ (fleetops.events)."""

    @abstractmethod
    def publish(self, routing_key: str, payload_json: str) -> bool:
        """
        Publica un mensaje JSON en el exchange topic con la routing key especificada.

        Retorna True si la publicación fue confirmada por el broker, False en caso de fallo.
        """

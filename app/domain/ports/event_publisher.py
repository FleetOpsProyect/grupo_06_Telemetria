"""Puerto abstracto para publicación de eventos en el broker de mensajería."""

from abc import ABC, abstractmethod


class IEventPublisher(ABC):
    """Puerto de salida para emitir eventos hacia el bus de eventos (AWS SNS)."""

    @abstractmethod
    def publish(self, routing_key: str, payload_json: str) -> bool:
        """
        Publica un mensaje JSON en el tópico, identificado por la routing key.

        Retorna True si la publicación fue confirmada por el broker, False en caso de fallo.
        """

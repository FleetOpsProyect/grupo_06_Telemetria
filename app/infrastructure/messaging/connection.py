"""Gestión de conexión con RabbitMQ y sondeo de salud del socket TCP."""

import socket
from urllib.parse import urlparse

import pika

from app.core.config import settings
from app.core.logging import logger


def check_rabbitmq_socket(timeout: float = 1.0) -> bool:
    """
    Sondeo activo del socket TCP contra el broker RabbitMQ.

    Verifica conectividad en menos de 1.0 segundo sin dejar sockets colgados.
    """
    try:
        parsed = urlparse(settings.rabbitmq_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5672

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        logger.warning(f"Sondeo de salud a RabbitMQ falló: {e}")
        return False


def get_rabbitmq_connection() -> pika.BlockingConnection | None:
    """Abre una conexión bloqueante con el broker RabbitMQ."""
    try:
        parameters = pika.URLParameters(settings.rabbitmq_url)
        parameters.socket_timeout = 2.0
        return pika.BlockingConnection(parameters)
    except Exception as e:
        logger.error(f"No fue posible conectar con RabbitMQ ({settings.rabbitmq_url}): {e}")
        return None

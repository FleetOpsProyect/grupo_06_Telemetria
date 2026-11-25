"""Clientes de AWS SNS/SQS y sondeo de salud de la mensajería."""

import time
from threading import Lock
from typing import Any

import boto3
from botocore.config import Config

from app.core.config import settings
from app.core.logging import logger

# Timeouts cortos: el /health no debe quedarse colgado si AWS no responde
_HEALTH_CONFIG = Config(connect_timeout=1, read_timeout=2, retries={"max_attempts": 1})
# Los workers usan long polling de hasta 20 s, así que el read_timeout debe ser mayor
_WORKER_CONFIG = Config(connect_timeout=3, read_timeout=30, retries={"max_attempts": 3})

_HEALTH_CACHE_SECONDS = 30.0
_health_cache: dict[str, Any] = {"value": None, "checked_at": 0.0}
_health_lock = Lock()


def _client(service: str, config: Config) -> Any:
    """Crea un cliente boto3; las credenciales salen del rol IAM de la EC2 o del entorno."""
    return boto3.client(
        service,
        region_name=settings.aws_region,
        endpoint_url=settings.aws_endpoint_url or None,
        config=config,
    )


def get_sns_client(*, for_health: bool = False) -> Any:
    """Cliente SNS para publicar eventos de Telemetría."""
    return _client("sns", _HEALTH_CONFIG if for_health else _WORKER_CONFIG)


def get_sqs_client(*, for_health: bool = False) -> Any:
    """Cliente SQS para consumir eventos dirigidos a Telemetría."""
    return _client("sqs", _HEALTH_CONFIG if for_health else _WORKER_CONFIG)


def _probe_messaging() -> str:
    try:
        get_sns_client(for_health=True).get_topic_attributes(TopicArn=settings.sns_topic_arn)
        get_sqs_client(for_health=True).get_queue_attributes(
            QueueUrl=settings.sqs_queue_url, AttributeNames=["QueueArn"]
        )
        return "UP"
    except Exception as e:
        logger.warning(f"Sondeo de salud a SNS/SQS falló: {e}")
        return "DOWN"


def check_messaging() -> str:
    """
    Estado de la mensajería: UP, DOWN o DISABLED (sin tópico/cola configurados).

    El resultado se guarda 30 s para no llamar a AWS en cada healthcheck de Docker.
    """
    if not settings.messaging_configured:
        return "DISABLED"
    with _health_lock:
        now = time.monotonic()
        cached = _health_cache["value"]
        if cached is not None and now - float(_health_cache["checked_at"]) < _HEALTH_CACHE_SECONDS:
            return str(cached)
        value = _probe_messaging()
        _health_cache.update(value=value, checked_at=now)
        return value


def reset_messaging_health_cache() -> None:
    """Limpia el caché del sondeo (usado por las pruebas)."""
    with _health_lock:
        _health_cache.update(value=None, checked_at=0.0)

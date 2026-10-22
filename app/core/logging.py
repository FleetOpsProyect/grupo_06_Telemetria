"""Configuración de logging estructurado con identificador de correlación."""

import logging
import sys
from contextvars import ContextVar
from typing import Any

# ContextVar para propagar el correlation_id a través de llamadas asíncronas
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="system")


class CorrelationFilter(logging.Filter):
    """Filtro de logging para inyectar correlation_id en cada registro."""

    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, "correlation_id", correlation_id_ctx.get())  # noqa: B010
        return True


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configura el logger raíz con formato consistente y trazabilidad."""
    log_level = logging.DEBUG if debug else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [corr=%(correlation_id)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationFilter())

    logger = logging.getLogger("fleetops.telemetria")
    logger.setLevel(log_level)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False

    return logger


logger = setup_logging()


def log_event(level: int, message: str, extra: dict[str, Any] | None = None) -> None:
    """Helper para escribir logs estructurados con metadatos contextuales."""
    if extra:
        extra_str = " | ".join(f"{k}={v}" for k, v in extra.items())
        logger.log(level, f"{message} [{extra_str}]")
    else:
        logger.log(level, message)

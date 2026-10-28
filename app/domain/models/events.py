"""Modelos base y estructuras de sobre estándar para mensajería y eventos de dominio."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generic, TypeVar
from uuid import uuid4

T = TypeVar("T")


@dataclass(frozen=True)
class EventEnvelope(Generic[T]):
    """Sobre estándar obligatorio para intercambio de eventos entre microservicios."""

    evento_id: str
    tipo_evento: str
    version: str
    fecha_evento: str
    origen: str
    datos: T

    @classmethod
    def create(cls, tipo_evento: str, datos: T, origen: str = "telemetria") -> "EventEnvelope[T]":
        """Construye un sobre de evento con identificador UUID y timestamp UTC actual."""
        return cls(
            evento_id=str(uuid4()),
            tipo_evento=tipo_evento,
            version="1.0",
            fecha_evento=datetime.now(UTC).isoformat(),
            origen=origen,
            datos=datos,
        )

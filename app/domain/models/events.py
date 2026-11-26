"""Modelos base y estructuras de sobre estándar para mensajería y eventos de dominio."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generic, TypeVar
from uuid import uuid4

from app.domain.models.route import Route

T = TypeVar("T")
# HU-01: evento de inicio de ruta (consumido por Asignaciones para pasar a EN_CURSO)
ROUTE_STARTED_EVENT = "RutaIniciadaEvent"
ROUTE_STARTED_ROUTING_KEY = "telemetria.ruta.iniciada"
# HU-03: evento de cierre de ruta según el contrato del DAS V2 (sección 10.1)
ROUTE_COMPLETED_EVENT = "route_completed_event"
ROUTE_COMPLETED_ROUTING_KEY = "telemetria.ruta.finalizada"
EVENT_SOURCE = "fleetops-telemetria"


def route_started_data(route: Route) -> dict[str, object]:
    """Construye el bloque de datos de RutaIniciadaEvent a partir de la entidad de Route."""
    return {
        "ruta_id": route.id,
        "asignacion_id": route.asignacion_id,
        "vehiculo_id": route.vehiculo_id,
        "conductor_id": route.conductor_id,
        "estado": route.estado.value,
        "coordenada_origen": {"latitud": route.origen.latitud, "longitud": route.origen.longitud},
        "hora_inicio": route.hora_inicio.isoformat(),
        "hora_fin": route.hora_fin.isoformat() if route.hora_fin else None,
    }


def route_completed_event(route: Route) -> dict[str, object]:
    """
    Sobre de route_completed_event tal como lo define el DAS V2:
    evento_id, tipo_evento, origen, timestamp, version y payload.
    """
    if route.hora_fin is None or route.distancia_recorrida_km is None:
        raise ValueError("La ruta debe estar finalizada para emitir route_completed_event")
    return {
        "evento_id": str(uuid4()),
        "tipo_evento": ROUTE_COMPLETED_EVENT,
        "origen": EVENT_SOURCE,
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0",
        "payload": {
            "ruta_id": route.id,
            "asignacion_id": route.asignacion_id,
            "vehiculo_id": route.vehiculo_id,
            "conductor_id": route.conductor_id,
            "estado": route.estado.value,
            "hora_inicio": route.hora_inicio.isoformat(),
            "hora_fin": route.hora_fin.isoformat(),
            "distancia_recorrida_km": route.distancia_recorrida_km,
        },
    }


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

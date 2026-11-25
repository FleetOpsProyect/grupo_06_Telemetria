"""Procesa el plan y la interrupción sin depender de AWS ni de SQLAlchemy."""

import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from app.application.dtos.assignment_interrupted import AssignmentInterruptedEventDTO
from app.application.dtos.travel_plan import TravelPlanEventDTO
from app.core.logging import logger
from app.domain.models.events import EventEnvelope
from app.domain.models.route import Route, RouteStatus
from app.domain.models.travel_plan import Coordinate, TravelPlan
from app.domain.ports.repositories import OutboxRecord


class TravelPlanNotAvailableError(Exception):
    """El consumidor puede reintentar cuando llegue el plan de viaje."""


class AssignmentMessageStore(Protocol):
    """Persistencia coordinada por una sola transacción, sin commits internos."""

    def claim_event(self, event_id: str, kind: str) -> bool: ...

    def save_plan(self, assignment_id: str, plan: TravelPlan) -> None: ...

    def get_plan(self, assignment_id: str) -> TravelPlan | None: ...

    def get_active_route(self, assignment_id: str) -> Route | None: ...

    def close_active_route(self, route_id: str, finished_at: datetime) -> bool: ...

    def add_outbox(self, record: OutboxRecord) -> None: ...


def utc(value: datetime) -> datetime:
    # SQLite quita tzinfo al recuperar DateTime; los timestamps almacenados son UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def process_assignment_event(
    event: TravelPlanEventDTO | AssignmentInterruptedEventDTO,
    store: AssignmentMessageStore,
    clock: Callable[[], datetime],
) -> None:
    if not store.claim_event(str(event.evento_id), event.tipo_evento):
        return

    assignment_id = event.datos.asignacion_id
    if isinstance(event, TravelPlanEventDTO):
        data = event.datos
        store.save_plan(
            assignment_id,
            TravelPlan(
                origin=Coordinate(data.coordenada_origen.latitud, data.coordenada_origen.longitud),
                destination=Coordinate(
                    data.coordenada_destino.latitud, data.coordenada_destino.longitud
                ),
                duration_seconds=data.duracion_estimada_segundos,
            ),
        )
        return

    route = store.get_active_route(assignment_id)
    if route is None:
        logger.info("No había ruta activa por cerrar; asignacion_id=%s", assignment_id)
        return

    plan = store.get_plan(assignment_id)
    if plan is None:
        raise TravelPlanNotAvailableError(f"Plan de viaje pendiente: {assignment_id}")

    started_at = utc(route.hora_inicio)
    finished_at = max(started_at, utc(clock()))
    distance = plan.distance_at((finished_at - started_at).total_seconds())
    if not store.close_active_route(route.id, finished_at):
        return

    envelope = EventEnvelope.create(
        tipo_evento="RutaFinalizadaEvent",
        datos={
            "asignacion_id": assignment_id,
            "vehiculo_id": route.vehiculo_id,
            "distancia_recorrida_km": round(distance, 2),
            "estado_ruta": RouteStatus.INTERRUMPIDA.value,
            "hora_inicio": started_at.isoformat(),
            "hora_fin": finished_at.isoformat(),
        },
    )
    store.add_outbox(
        OutboxRecord(
            id=str(uuid4()),
            evento_id=envelope.evento_id,
            tipo_evento=envelope.tipo_evento,
            routing_key="telemetria.ruta.finalizada",
            payload_json=json.dumps(asdict(envelope)),
        )
    )

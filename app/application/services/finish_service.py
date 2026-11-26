"""Caso de uso HU-03: finalizar la ruta activa y calcular la distancia recorrida."""

import json
import random
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from app.application.dtos.route_finish import RouteFinishDTO, RouteFinishedResponseDTO
from app.core.exceptions import (
    DatabaseUnavailableError,
    EntityNotFoundError,
    InvalidStateTransitionError,
)
from app.core.logging import logger
from app.domain.models.events import (
    ROUTE_COMPLETED_EVENT,
    ROUTE_COMPLETED_ROUTING_KEY,
    route_completed_event,
)
from app.domain.models.route import Coordinate, Route
from app.domain.models.trip_simulation import random_destination, trip_distance_km
from app.domain.ports.repositories import (
    IOutboxRepository,
    IRouteRepository,
    IUnitOfWork,
    OutboxRecord,
)

ESTADO_INVALIDO_MSG = "La ruta no se encuentra en estado EN_CURSO para ser finalizada"


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class FinishRouteService:
    """
    Orquesta el cierre de la ruta.

    1. Busca la ruta de la asignación (404 RUTA_NO_ENCONTRADA) y valida EN_CURSO (409).
    2. Usa el destino enviado o lo simula a 5-25 km; calcula la distancia con Haversine.
    3. Guarda el cierre y route_completed_event en outbox_eventos en la MISMA transacción.
       El UPDATE condicional garantiza que de dos cierres simultáneos solo uno gane (409).
    """

    def __init__(
        self,
        route_repo: IRouteRepository,
        outbox_repo: IOutboxRepository,
        unit_of_work: IUnitOfWork,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        rng: random.Random | None = None,
    ) -> None:
        self.route_repo = route_repo
        self.outbox_repo = outbox_repo
        self.unit_of_work = unit_of_work
        self.clock = clock
        self.rng = rng or random.SystemRandom()

    def finish_route(self, dto: RouteFinishDTO) -> RouteFinishedResponseDTO:
        asignacion_id = dto.asignacion_id
        logger.info(f"Solicitud de finalización de ruta; asignacion_id={asignacion_id}")

        try:
            route = self.route_repo.get_by_asignacion_id(asignacion_id)
            if route is None:
                raise EntityNotFoundError(
                    f"No existe una ruta asociada a la asignación {asignacion_id}",
                    code="RUTA_NO_ENCONTRADA",
                )
            if not route.en_curso:
                logger.info(f"Ruta {route.id} en estado {route.estado}; no se finaliza")
                raise InvalidStateTransitionError(ESTADO_INVALIDO_MSG)

            self._close(route, dto)
            self._persist_with_event(route)
        except DatabaseUnavailableError as e:
            logger.error(f"Fallo de persistencia al finalizar ruta {asignacion_id}: {e.message}")
            raise DatabaseUnavailableError() from e

        logger.info(
            f"Ruta {route.id} FINALIZADA; distancia={route.distancia_recorrida_km} km "
            f"asignacion_id={asignacion_id}"
        )
        return RouteFinishedResponseDTO.from_domain(route)

    def _close(self, route: Route, dto: RouteFinishDTO) -> None:
        hora_inicio = _utc(route.hora_inicio)
        hora_fin = max(hora_inicio, _utc(self.clock()))
        if dto.destino_latitud is not None and dto.destino_longitud is not None:
            destino = Coordinate(latitud=dto.destino_latitud, longitud=dto.destino_longitud)
        else:
            destino = random_destination(route.origen, self.rng)
        distancia = trip_distance_km(route.origen, destino, hora_inicio, hora_fin)
        route.hora_inicio = hora_inicio
        route.finish(hora_fin=hora_fin, destino=destino, distancia_km=distancia)

    def _persist_with_event(self, route: Route) -> None:
        """Transactional Outbox: el cierre y su evento se confirman juntos o no se confirma nada."""
        event = route_completed_event(route)
        record = OutboxRecord(
            id=str(uuid4()),
            evento_id=str(event["evento_id"]),
            tipo_evento=ROUTE_COMPLETED_EVENT,
            routing_key=ROUTE_COMPLETED_ROUTING_KEY,
            payload_json=json.dumps(event, ensure_ascii=False),
        )
        try:
            if not self.route_repo.finish(route):
                # Carrera: otra petición finalizó (o se interrumpió) la ruta primero.
                self.unit_of_work.rollback()
                logger.warning(f"Finalización concurrente rechazada para ruta {route.id}")
                raise InvalidStateTransitionError(ESTADO_INVALIDO_MSG)
            self.outbox_repo.add(record)
            self.unit_of_work.commit()
        except DatabaseUnavailableError:
            self.unit_of_work.rollback()
            raise

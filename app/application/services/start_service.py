"""Caso de uso HU-01: iniciar la ruta asociada a una asignación PENDIENTE."""

import json
from dataclasses import asdict
from uuid import uuid4

from app.application.dtos.route import RouteResponseDTO
from app.application.dtos.route_start import RouteStartDTO
from app.core.exceptions import (
    DatabaseUnavailableError,
    DuplicateEntityError,
    EntityNotFoundError,
    InvalidStateTransitionError,
)
from app.core.logging import logger
from app.domain.models.events import (
    ROUTE_STARTED_EVENT,
    ROUTE_STARTED_ROUTING_KEY,
    EventEnvelope,
    route_started_data,
)
from app.domain.models.route import Route
from app.domain.ports.external_services import IAssignmentsClient
from app.domain.ports.repositories import (
    IOutboxRepository,
    IRouteRepository,
    IUnitOfWork,
    OutboxRecord,
)


def _duplicate_route_message(asignacion_id: str) -> str:
    return f"Ya existe una ruta registrada para la asignación {asignacion_id}"


class StartRouteService:
    """
    Orquesta el inicio de ruta.

    1. Unicidad local: una asignación tiene una sola ruta (409 RUTA_DUPLICADA).
    2. Validación síncrona con Asignaciones (404 / 409 ASIGNACION_NO_PENDIENTE / 503).
    3. Guarda la ruta EN_CURSO y RutaIniciadaEvent en outbox_eventos en la MISMA transacción.
    """

    def __init__(
        self,
        route_repo: IRouteRepository,
        outbox_repo: IOutboxRepository,
        assignments_client: IAssignmentsClient,
        unit_of_work: IUnitOfWork,
    ) -> None:
        self.route_repo = route_repo
        self.outbox_repo = outbox_repo
        self.assignments_client = assignments_client
        self.unit_of_work = unit_of_work

    def start_route(self, dto: RouteStartDTO) -> RouteResponseDTO:
        asignacion_id = dto.asignacion_id
        logger.info(f"Solicitud de inicio de ruta; asignacion_id={asignacion_id}")

        try:
            if self.route_repo.get_by_asignacion_id(asignacion_id) is not None:
                raise DuplicateEntityError(_duplicate_route_message(asignacion_id))

            assignment = self.assignments_client.get_assignment(asignacion_id)
            if assignment is None:
                raise EntityNotFoundError(
                    f"No existe una asignación con id {asignacion_id}",
                    code="ASIGNACION_NO_ENCONTRADA",
                )
            if assignment.estado != "PENDIENTE":
                logger.info(
                    f"Asignación {asignacion_id} en estado {assignment.estado}; no se inicia ruta"
                )
                raise InvalidStateTransitionError(
                    "La asignación no se encuentra en estado PENDIENTE para iniciar ruta",
                    code="ASIGNACION_NO_PENDIENTE",
                )

            route = Route.start_new(
                id=str(uuid4()),
                asignacion_id=asignacion_id,
                vehiculo_id=assignment.vehiculo_id,
                conductor_id=assignment.conductor_id,
            )
            self._persist_with_event(route)
        except DatabaseUnavailableError as e:
            logger.error(f"Fallo de persistencia al iniciar ruta {asignacion_id}: {e.message}")
            raise DatabaseUnavailableError() from e

        logger.info(f"Ruta {route.id} iniciada (EN_CURSO) para asignación {asignacion_id}")
        return RouteResponseDTO.from_domain(route)

    def _persist_with_event(self, route: Route) -> None:
        """Transactional Outbox: la ruta y su evento se confirman juntos o no se confirma nada."""
        envelope = EventEnvelope.create(
            tipo_evento=ROUTE_STARTED_EVENT, datos=route_started_data(route)
        )
        record = OutboxRecord(
            id=str(uuid4()),
            evento_id=envelope.evento_id,
            tipo_evento=envelope.tipo_evento,
            routing_key=ROUTE_STARTED_ROUTING_KEY,
            payload_json=json.dumps(asdict(envelope), ensure_ascii=False),
        )
        try:
            self.route_repo.add(route)
            self.outbox_repo.add(record)
            self.unit_of_work.commit()
        except DuplicateEntityError as e:
            # Carrera: otra petición con la misma asignación confirmó primero (UNIQUE en BD).
            self.unit_of_work.rollback()
            logger.warning(f"Inicio concurrente rechazado para asignación {route.asignacion_id}")
            raise DuplicateEntityError(_duplicate_route_message(route.asignacion_id)) from e
        except DatabaseUnavailableError:
            self.unit_of_work.rollback()
            raise

"""Servicio de aplicación transaccional de ejemplo para el arquetipo Clean Architecture."""

from uuid import uuid4

from app.application.dtos.route import RouteCreateDTO, RouteResponseDTO
from app.core.exceptions import DuplicateEntityError, EntityNotFoundError
from app.core.logging import logger
from app.domain.models.route import Route
from app.domain.ports.repositories import IRouteRepository


class RouteService:
    """
    Servicio de aplicación que orquesta el flujo transaccional de ejemplo del arquetipo.

    Conecta: Controlador HTTP -> DTO -> Entidad de Dominio -> Puerto de Repositorio -> BD.
    """

    def __init__(self, route_repo: IRouteRepository) -> None:
        self.route_repo = route_repo

    def create_route(self, dto: RouteCreateDTO) -> RouteResponseDTO:
        """
        Flujo transaccional de escritura: crea y persiste una nueva ruta.

        - Valida unicidad de la asignación.
        - Instancia la entidad de dominio Route.
        - Persiste a través del puerto IRouteRepository.
        - Retorna el DTO de respuesta.
        """
        logger.info(f"Creando ruta para asignación: {dto.asignacion_id}")

        existing = self.route_repo.get_by_asignacion_id(dto.asignacion_id)
        if existing:
            raise DuplicateEntityError(
                f"Ya existe una ruta registrada para la asignación {dto.asignacion_id}"
            )

        route_id = f"ruta-{uuid4().hex[:8]}"
        route = Route.start_new(
            id=route_id,
            asignacion_id=dto.asignacion_id,
            vehiculo_id=dto.vehiculo_id,
            conductor_id=dto.conductor_id,
        )

        saved = self.route_repo.save(route)
        logger.info(f"Ruta creada exitosamente en arquetipo: {saved.id}")

        return RouteResponseDTO(
            id=saved.id,
            asignacion_id=saved.asignacion_id,
            vehiculo_id=saved.vehiculo_id,
            conductor_id=saved.conductor_id,
            estado=saved.estado.value,
            hora_inicio=saved.hora_inicio.isoformat(),
        )

    def get_route_by_id(self, route_id: str) -> RouteResponseDTO:
        """
        Flujo transaccional de lectura: consulta una ruta por su identificador.

        Lanza EntityNotFoundError si no existe.
        """
        route = self.route_repo.get_by_id(route_id)
        if not route:
            raise EntityNotFoundError(
                f"No existe una ruta con id {route_id}", code="RUTA_NO_ENCONTRADA"
            )

        return RouteResponseDTO(
            id=route.id,
            asignacion_id=route.asignacion_id,
            vehiculo_id=route.vehiculo_id,
            conductor_id=route.conductor_id,
            estado=route.estado.value,
            hora_inicio=route.hora_inicio.isoformat(),
        )

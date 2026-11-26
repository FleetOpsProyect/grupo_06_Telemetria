"""Servicio de aplicación transaccional de ejemplo para el arquetipo Clean Architecture."""

from uuid import uuid4

from app.application.dtos.common import PaginatedResponse
from app.application.dtos.route import RouteCreateDTO, RouteResponseDTO
from app.application.dtos.route_query import RouteDetailDTO, RouteSummaryDTO
from app.core.exceptions import DuplicateEntityError, EntityNotFoundError, ValidationError
from app.core.logging import logger
from app.domain.models.route import Route, RouteStatus
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

        return RouteResponseDTO.from_domain(saved)

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

        return RouteResponseDTO.from_domain(route)

    def list_routes(
        self,
        asignacion_id: str | None = None,
        vehiculo_id: str | None = None,
        estado: RouteStatus | None = None,
        fecha_desde: str | None = None,
        fecha_hasta: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> PaginatedResponse[RouteSummaryDTO]:
        """Lista rutas paginadas con filtros opcionales y orden descendente."""
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise ValidationError(
                message="La fecha_desde no puede ser mayor que fecha_hasta",
                details=[
                    {"campo": "fecha_desde", "detalle": "Debe ser menor o igual a fecha_hasta"}
                ],
            )
        routes, total = self.route_repo.list_routes(
            asignacion_id=asignacion_id,
            vehiculo_id=vehiculo_id,
            estado=estado,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            page=page,
            size=size,
        )
        return PaginatedResponse[RouteSummaryDTO](
            contenido=[RouteSummaryDTO.from_domain(r) for r in routes],
            page=page,
            size=size,
            total=total,
        )
    def get_route_detail(self,route_id: str)-> RouteDetailDTO:
        """consulta el detalle completo de una ruta """
        route = self.route_repo.get_by_id(route_id)
        if not route:
            raise EntityNotFoundError(
                f"No existe una ruta con id {route_id}", code="RUTA_NO_ENCONTRADA"
            )
        return RouteDetailDTO.from_domain(route)
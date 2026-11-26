from datetime import date
from typing import Any
from fastapi import APIRouter, Depends, Query, status
from app.application.dtos.common import ErrorResponse, PaginatedResponse
from app.application.dtos.route_query import RouteDetailDTO, RouteSummaryDTO
from app.application.services.route_service import RouteService
from app.core.security import verify_authorization
from app.domain.models.route import RouteStatus
from app.presentation.dependencies import get_route_service

router = APIRouter(prefix="/route", tags=["Rutas"])

@router.get(
    "",
    response_model=PaginatedResponse[RouteSummaryDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar rutas con filtros y paginación",
    responses={
        200: {"model": PaginatedResponse[RouteSummaryDTO], "description": "Listado paginado"},
        400: {"model": ErrorResponse, "description": "DATOS_INVALIDOS"},
        503: {"model": ErrorResponse, "description": "SERVICIO_NO_DISPONIBLE"},
    },
    )
def listar_rutas(
    asignacion_id: str|None = Query(default=None,min_length=1),
    vehiculo_id: str | None = Query(default=None, min_length=1),
    estado: RouteStatus | None = Query(default=None),
    fecha_desde: date | None = Query(default=None),
    fecha_hasta: date | None = Query(default=None),
    page: int = Query(default=0, ge=0),
    size: int = Query(default=20, ge=1, le=100),
    service: RouteService = Depends(get_route_service),
    _auth: dict[str, Any] = Depends(verify_authorization),
) -> PaginatedResponse[RouteSummaryDTO]:
    return service.list_routes(
        asignacion_id=asignacion_id,
            vehiculo_id=vehiculo_id,
            estado=estado,
            fecha_desde=fecha_desde.isoformat() if fecha_desde else None,
            fecha_hasta=fecha_hasta.isoformat() if fecha_hasta else None,
            page=page,
            size=size,
    )

@router.get(
    "/{route_id}",
    response_model=RouteDetailDTO,
    status_code=status.HTTP_200_OK,
    summary="Consultar detalle completo de una ruta por ID (HU-05)",
    responses={
        200: {"model": RouteDetailDTO, "description": "Detalle de la ruta"},
        404: {"model": ErrorResponse, "description": "RUTA_NO_ENCONTRADA"},
        503: {"model": ErrorResponse, "description": "SERVICIO_NO_DISPONIBLE"},
    },
)
def obtener_ruta_detalle(
    route_id: str,
    service: RouteService = Depends(get_route_service),
    _auth: dict[str, Any] = Depends(verify_authorization),
) -> RouteDetailDTO:
    """Retorna ruta incluyendo origen y destino."""
    return service.get_route_detail(route_id)
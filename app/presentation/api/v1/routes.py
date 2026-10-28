"""Endpoints REST de ejemplo transaccional para el arquetipo."""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.application.dtos.common import ErrorResponse
from app.application.dtos.route import RouteCreateDTO, RouteResponseDTO
from app.application.services.route_service import RouteService
from app.core.security import verify_authorization
from app.presentation.dependencies import get_route_service

router = APIRouter(prefix="/rutas", tags=["Rutas (Arquetipo)"])


@router.post(
    "",
    response_model=RouteResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear ruta (Ejemplo transaccional del arquetipo)",
    responses={
        201: {"model": RouteResponseDTO, "description": "Ruta creada exitosamente"},
        400: {"model": ErrorResponse, "description": "Datos de entrada inválidos"},
        409: {"model": ErrorResponse, "description": "Ruta duplicada para la asignación"},
        503: {"model": ErrorResponse, "description": "Servicio de persistencia no disponible"},
    },
)
def crear_ruta(
    dto: RouteCreateDTO,
    service: RouteService = Depends(get_route_service),
    _auth: dict[str, Any] = Depends(verify_authorization),
) -> RouteResponseDTO:
    """
    Ejemplo transaccional de escritura del arquetipo.

    Conecta: Presentation -> Application (RouteService) ->
    Domain (Route) -> Infrastructure (PostgreSQL).
    """
    return service.create_route(dto)


@router.get(
    "/{route_id}",
    response_model=RouteResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Consultar ruta por ID (Ejemplo transaccional de lectura)",
    responses={
        200: {"model": RouteResponseDTO, "description": "Ruta encontrada"},
        404: {"model": ErrorResponse, "description": "Ruta no encontrada"},
        503: {"model": ErrorResponse, "description": "Servicio de persistencia no disponible"},
    },
)
def obtener_ruta(
    route_id: str,
    service: RouteService = Depends(get_route_service),
    _auth: dict[str, Any] = Depends(verify_authorization),
) -> RouteResponseDTO:
    """Ejemplo transaccional de lectura del arquetipo."""
    return service.get_route_by_id(route_id)

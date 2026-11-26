"""Endpoint HU-01: el conductor inicia la ruta de su asignación."""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.application.dtos.common import ErrorResponse
from app.application.dtos.route import RouteResponseDTO
from app.application.dtos.route_start import RouteStartDTO
from app.application.services.start_service import StartRouteService
from app.core.security import verify_authorization
from app.presentation.dependencies import get_start_route_service

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.post(
    "/start",
    response_model=RouteResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar ruta asociada a una asignación (HU-01)",
    responses={
        201: {"model": RouteResponseDTO, "description": "Ruta iniciada en estado EN_CURSO"},
        400: {"model": ErrorResponse, "description": "DATOS_INVALIDOS o JSON_INVALIDO"},
        404: {"model": ErrorResponse, "description": "ASIGNACION_NO_ENCONTRADA"},
        409: {"model": ErrorResponse, "description": "ASIGNACION_NO_PENDIENTE o RUTA_DUPLICADA"},
        503: {
            "model": ErrorResponse,
            "description": "DEPENDENCIA_NO_DISPONIBLE (Asignaciones) o SERVICIO_NO_DISPONIBLE (BD)",
        },
    },
)
def start_route(
    dto: RouteStartDTO,
    service: StartRouteService = Depends(get_start_route_service),
    _auth: dict[str, Any] = Depends(verify_authorization),
) -> RouteResponseDTO:
    """
    Valida la asignación contra el MS de Asignaciones, registra la ruta EN_CURSO con origen
    en el Centro de Operaciones y deja RutaIniciadaEvent en outbox_eventos.
    """
    return service.start_route(dto)

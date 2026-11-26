"""Endpoint HU-03: el conductor finaliza su ruta activa (POST /route, DAS V2)."""

from typing import Any

from fastapi import APIRouter, Depends, status

from app.application.dtos.common import ErrorResponse
from app.application.dtos.route_finish import RouteFinishDTO, RouteFinishedResponseDTO
from app.application.services.finish_service import FinishRouteService
from app.core.security import verify_authorization
from app.presentation.dependencies import get_finish_route_service

router = APIRouter(prefix="/route", tags=["Rutas"])


@router.post(
    "",
    response_model=RouteFinishedResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Finalizar ruta activa y calcular distancia recorrida (HU-03)",
    responses={
        200: {"model": RouteFinishedResponseDTO, "description": "Ruta FINALIZADA"},
        400: {"model": ErrorResponse, "description": "DATOS_INVALIDOS o JSON_INVALIDO"},
        404: {"model": ErrorResponse, "description": "RUTA_NO_ENCONTRADA"},
        409: {"model": ErrorResponse, "description": "ESTADO_RUTA_INVALIDO"},
        503: {"model": ErrorResponse, "description": "SERVICIO_NO_DISPONIBLE"},
    },
)
def finalizar_ruta(
    dto: RouteFinishDTO,
    service: FinishRouteService = Depends(get_finish_route_service),
    _auth: dict[str, Any] = Depends(verify_authorization),
) -> RouteFinishedResponseDTO:
    """
    Cierra la ruta EN_CURSO de la asignación, calcula la distancia con Haversine
    (destino enviado o simulado a 5-25 km) y deja route_completed_event en outbox_eventos.
    """
    return service.finish_route(dto)

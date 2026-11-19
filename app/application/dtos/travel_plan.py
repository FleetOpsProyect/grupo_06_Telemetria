"""Contrato provisional para el plan publicado por Asignaciones."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from app.application.dtos.assignment_interrupted import (
    AssignmentEventDTO,
    AssignmentInterruptedDataDTO,
)


class CoordinateDTO(BaseModel):
    """Coordenadas en grados decimales."""

    model_config = ConfigDict(strict=True)

    latitud: Annotated[float, Field(ge=-90, le=90)]
    longitud: Annotated[float, Field(ge=-180, le=180)]


class TravelPlanDataDTO(AssignmentInterruptedDataDTO):
    """Datos mínimos para estimar el avance de una ruta."""

    coordenada_origen: CoordinateDTO
    coordenada_destino: CoordinateDTO
    duracion_estimada_segundos: PositiveInt


class TravelPlanEventDTO(AssignmentEventDTO):
    """Plan inicial asociado a una asignación."""

    tipo_evento: Literal["PlanViajeAsignacionEvent"]
    datos: TravelPlanDataDTO

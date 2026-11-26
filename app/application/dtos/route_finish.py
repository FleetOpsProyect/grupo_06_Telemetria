"""DTOs de la HU-03: finalizar ruta (POST /route) según el contrato del DAS V2."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.dtos.route import CoordinateDTO
from app.domain.models.route import Route

Latitud = Annotated[float, Field(ge=-90, le=90)]
Longitud = Annotated[float, Field(ge=-180, le=180)]


class RouteFinishDTO(BaseModel):
    """
    Orden de término enviada por el conductor.

    destino_latitud y destino_longitud son opcionales: si no vienen, el sistema simula el
    destino a 5-25 km del origen (HU-03, criterio 3). Si viene uno, debe venir el otro.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    asignacion_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Identificador de la asignación cuya ruta se va a finalizar",
        examples=["f47ac10b-58cc-4372-a567-0e02b2c3d479"],
    )
    destino_latitud: Latitud | None = Field(default=None, examples=[3.4372])
    destino_longitud: Longitud | None = Field(default=None, examples=[-76.5225])

    @model_validator(mode="after")
    def destino_completo(self) -> Self:
        if (self.destino_latitud is None) != (self.destino_longitud is None):
            raise ValueError("destino_latitud y destino_longitud deben enviarse juntos")
        return self


class RouteFinishedResponseDTO(BaseModel):
    """Resumen del viaje finalizado (DAS V2, respuesta 200 de POST /route)."""

    id: str
    asignacion_id: str
    vehiculo_id: str
    estado: str
    hora_inicio: str
    hora_fin: str
    distancia_recorrida_km: float
    origen: CoordinateDTO
    destino: CoordinateDTO

    @classmethod
    def from_domain(cls, route: Route) -> "RouteFinishedResponseDTO":
        if route.hora_fin is None or route.destino is None or route.distancia_recorrida_km is None:
            raise ValueError("La ruta no está finalizada")
        return cls(
            id=route.id,
            asignacion_id=route.asignacion_id,
            vehiculo_id=route.vehiculo_id,
            estado=route.estado.value,
            hora_inicio=route.hora_inicio.isoformat(),
            hora_fin=route.hora_fin.isoformat(),
            distancia_recorrida_km=route.distancia_recorrida_km,
            origen=CoordinateDTO(latitud=route.origen.latitud, longitud=route.origen.longitud),
            destino=CoordinateDTO(latitud=route.destino.latitud, longitud=route.destino.longitud),
        )

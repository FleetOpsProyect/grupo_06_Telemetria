"""DTOs de ejemplo transaccional para el arquetipo (Creación y Consulta de Rutas)."""

from pydantic import BaseModel, Field, field_validator
from app.domain.models.route import Route

from app.core.exceptions import ValidationError


class RouteCreateDTO(BaseModel):
    """Schema de entrada para crear una ruta en el arquetipo."""

    asignacion_id: str = Field(..., min_length=1, description="Identificador de la asignación")
    vehiculo_id: str = Field(..., min_length=1, description="Identificador del vehículo")
    conductor_id: str = Field(..., min_length=1, description="Identificador del conductor")

    @field_validator("asignacion_id", "vehiculo_id", "conductor_id")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValidationError(
                message="Los campos de identificación no pueden estar vacíos",
                details=[{"campo": "identificador", "detalle": "Cadena vacía no permitida"}],
            )
        return stripped


class CoordinateDTO(BaseModel):
    """Coordenada geografica en grados decimales"""

    latitud: float
    longitud: float


class RouteResponseDTO(BaseModel):
    """Schema de salida con los datos de la ruta."""

    id: str
    asignacion_id: str
    vehiculo_id: str
    conductor_id: str
    estado: str
    hora_inicio: str
    coordenada_origen: CoordinateDTO

    model_config = {"from_attributes": True}

    @classmethod
    def from_domain(cls, route: Route) -> "RouteResponseDTO":
        """Mapea la entidad de dominio a la respuesta HTTP (misma forma en POST y GET)"""
        return cls(
            id=route.id,
            asignacion_id=route.asignacion_id,
            vehiculo_id=route.vehiculo_id,
            conductor_id=route.conductor_id,
            estado=route.estado,
            hora_inicio=route.hora_inicio.isoformat(),
            coordenada_origen=CoordinateDTO(
                latitud=route.origen.latitud, longitud=route.origen.longitud
            ),
        )

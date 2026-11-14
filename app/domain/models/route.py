"""Entidad de dominio agregada Ruta para el arquetipo de microservicio."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class RouteStatus(StrEnum):
    """Catálogo de estados de una ruta."""

    EN_CURSO = "EN_CURSO"
    FINALIZADA = "FINALIZADA"
    INTERRUMPIDA = "INTERRUMPIDA"


@dataclass(
    frozen=True
)  # frozen=True hace que la coordenada sea inmutable, es decir, no se puede cambiar una vez creada.
class Coordinate:
    """Es el tipo de valor inmutable que representa una coordenada geográfica (grados decimales)."""

    latitud: float
    longitud: float


# HU-01: Mientras no exista el GPS fisico, la ruta sale del centro de operaciones de FleetCorp
CENTRO_OPERACIONES = Coordinate(latitud=-34.6037, longitud=-76.5320)


class Route:
    """
    Entidad de dominio representativa del arquetipo.

    Define el ciclo de vida y atributos esenciales de una ruta operativa.
    """

    def __init__(
        self,
        id: str,
        asignacion_id: str,
        vehiculo_id: str,
        conductor_id: str,
        estado: RouteStatus = RouteStatus.EN_CURSO,
        origen: Coordinate | None = None,
        hora_inicio: datetime | None = None,
        hora_fin: datetime | None = None,
    ) -> None:
        self.id = id
        self.asignacion_id = asignacion_id
        self.vehiculo_id = vehiculo_id
        self.conductor_id = conductor_id
        self.estado = estado
        self.origen = origen or CENTRO_OPERACIONES
        self.hora_inicio = hora_inicio or datetime.now(UTC)
        self.hora_fin = hora_fin

    @classmethod
    def start_new(
        cls,
        id: str,
        asignacion_id: str,
        vehiculo_id: str,
        conductor_id: str,
        origen: Coordinate = CENTRO_OPERACIONES,
    ) -> "Route":
        """Fabrica una nueva instancia de ruta en estado EN_CURSO."""
        return cls(
            id=id,
            asignacion_id=asignacion_id,
            vehiculo_id=vehiculo_id,
            conductor_id=conductor_id,
            estado=RouteStatus.EN_CURSO,
            hora_inicio=datetime.now(UTC),
            origen=origen,
        )

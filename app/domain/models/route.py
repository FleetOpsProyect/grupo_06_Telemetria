"""Entidad de dominio agregada Ruta para el arquetipo de microservicio."""

from datetime import UTC, datetime
from enum import Enum


class RouteStatus(str, Enum):
    """Catálogo de estados de una ruta."""

    EN_CURSO = "EN_CURSO"
    FINALIZADA = "FINALIZADA"
    INTERRUMPIDA = "INTERRUMPIDA"


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
        hora_inicio: datetime | None = None,
        hora_fin: datetime | None = None,
    ) -> None:
        self.id = id
        self.asignacion_id = asignacion_id
        self.vehiculo_id = vehiculo_id
        self.conductor_id = conductor_id
        self.estado = estado
        self.hora_inicio = hora_inicio or datetime.now(UTC)
        self.hora_fin = hora_fin

    @classmethod
    def start_new(
        cls,
        id: str,
        asignacion_id: str,
        vehiculo_id: str,
        conductor_id: str,
    ) -> "Route":
        """Fabrica una nueva instancia de ruta en estado EN_CURSO."""
        return cls(
            id=id,
            asignacion_id=asignacion_id,
            vehiculo_id=vehiculo_id,
            conductor_id=conductor_id,
            estado=RouteStatus.EN_CURSO,
            hora_inicio=datetime.now(UTC),
        )

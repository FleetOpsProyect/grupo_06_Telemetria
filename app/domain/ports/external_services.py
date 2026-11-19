"""Puertos abstractos para clientes hacia servicios externos del ecosistema."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssignmentSnapshot:
    """Datos mínimos de una asignación consultada en el servicio externo."""

    asignacion_id: str
    estado: str
    vehiculo_id: str
    conductor_id: str


class IAssignmentsClient(ABC):
    """Puerto para consultar asignaciones en el servicio externo."""

    @abstractmethod
    def get_assignment(self, asignacion_id: str) -> AssignmentSnapshot | None:
        """Retorna la asignación o None si no existe."""


class IExternalServiceClient(ABC):
    """Puerto de salida de ejemplo para comunicación HTTP con servicios externos."""

    @abstractmethod
    def fetch_resource(self, resource_id: str) -> dict[str, Any]:
        """Obtiene un recurso de un servicio externo."""

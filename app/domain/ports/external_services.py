"""Puertos abstractos para clientes hacia servicios externos del ecosistema."""

from abc import ABC, abstractmethod
from typing import Any


class IExternalServiceClient(ABC):
    """Puerto de salida de ejemplo para comunicación HTTP con servicios externos."""

    @abstractmethod
    def fetch_resource(self, resource_id: str) -> dict[str, Any]:
        """Obtiene un recurso de un servicio externo."""

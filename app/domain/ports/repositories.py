"""Puertos e interfaces abstractas para la persistencia del dominio."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.domain.models.route import Route, RouteStatus


@dataclass
class OutboxRecord:
    """Registro de evento transaccional en outbox_eventos."""

    id: str
    evento_id: str
    tipo_evento: str
    routing_key: str
    payload_json: str
    estado: str = "PENDIENTE"
    intentos: int = 0
    created_at: datetime | None = None
    sent_at: datetime | None = None


class IRouteRepository(ABC):
    """Puerto para el repositorio de rutas operativas."""

    @abstractmethod
    def save(self, route: Route) -> Route:
        """Persiste o actualiza una ruta en la base de datos."""

    @abstractmethod
    def get_by_id(self, route_id: str) -> Route | None:
        """Busca una ruta por su identificador único."""

    @abstractmethod
    def get_by_asignacion_id(self, asignacion_id: str) -> Route | None:
        """Busca una ruta asociada a una asignación."""

    @abstractmethod
    def get_active_route_by_asignacion(self, asignacion_id: str) -> Route | None:
        """Busca la ruta activa (EN_CURSO) de una asignación."""

    @abstractmethod
    def list_routes(
        self,
        asignacion_id: str | None = None,
        vehiculo_id: str | None = None,
        estado: RouteStatus | None = None,
        fecha_desde: str | None = None,
        fecha_hasta: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> tuple[list[Route], int]:
        """Consulta rutas históricas con filtros y paginación ordenada descendente."""


class IOutboxRepository(ABC):
    """Puerto para el repositorio del patrón Transactional Outbox."""

    @abstractmethod
    def save(self, record: OutboxRecord) -> OutboxRecord:
        """Guarda un evento en la tabla outbox dentro de la transacción activa."""

    @abstractmethod
    def get_pending(self, limit: int = 50) -> list[OutboxRecord]:
        """Obtiene eventos pendientes para su publicación en el broker."""

    @abstractmethod
    def mark_published(self, record_id: str) -> None:
        """Marca un evento como publicado exitosamente."""

    @abstractmethod
    def mark_failed(self, record_id: str) -> None:
        """Incrementa el contador de fallos de un evento outbox."""


class IProcessedEventRepository(ABC):
    """Puerto para el control de deduplicación de eventos (Idempotent Consumer)."""

    @abstractmethod
    def is_processed(self, evento_id: str) -> bool:
        """Verifica si un evento ya fue procesado con anterioridad."""

    @abstractmethod
    def mark_processed(self, evento_id: str, tipo_evento: str) -> None:
        """Registra un evento_id en la base de datos para garantizar idempotencia."""

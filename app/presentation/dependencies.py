"""Inversión de control y contenedor de inyección de dependencias para FastAPI."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.services.route_service import RouteService
from app.domain.ports.event_publisher import IEventPublisher
from app.domain.ports.repositories import (
    IOutboxRepository,
    IProcessedEventRepository,
    IRouteRepository,
)
from app.infrastructure.db.session import get_db
from app.infrastructure.messaging.publisher import RabbitMQEventPublisher
from app.infrastructure.repositories.outbox_repository import SqlAlchemyOutboxRepository
from app.infrastructure.repositories.processed_event_repo import SqlAlchemyProcessedEventRepository
from app.infrastructure.repositories.route_repository import SqlAlchemyRouteRepository


def get_route_repository(db: Session = Depends(get_db)) -> IRouteRepository:
    """Provee la implementación del repositorio de rutas."""
    return SqlAlchemyRouteRepository(db)


def get_outbox_repository(db: Session = Depends(get_db)) -> IOutboxRepository:
    """Provee la implementación del repositorio de outbox."""
    return SqlAlchemyOutboxRepository(db)


def get_processed_event_repository(db: Session = Depends(get_db)) -> IProcessedEventRepository:
    """Provee la implementación del repositorio de eventos procesados."""
    return SqlAlchemyProcessedEventRepository(db)


def get_event_publisher() -> IEventPublisher:
    """Provee el publicador de eventos a RabbitMQ."""
    return RabbitMQEventPublisher()


def get_route_service(
    route_repo: IRouteRepository = Depends(get_route_repository),
) -> RouteService:
    """Instancia el servicio transaccional de ejemplo del arquetipo."""
    return RouteService(route_repo=route_repo)

"""Inversión de control y contenedor de inyección de dependencias para FastAPI."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.services.finish_service import FinishRouteService
from app.application.services.route_service import RouteService
from app.application.services.start_service import StartRouteService
from app.domain.ports.event_publisher import IEventPublisher
from app.domain.ports.external_services import IAssignmentsClient
from app.domain.ports.repositories import (
    IOutboxRepository,
    IProcessedEventRepository,
    IRouteRepository,
    IUnitOfWork,
)
from app.infrastructure.db.session import get_db
from app.infrastructure.http_clients.assignments_clients import HttpAssignmentsClient
from app.infrastructure.messaging.publisher import SnsEventPublisher
from app.infrastructure.repositories.outbox_repository import SqlAlchemyOutboxRepository
from app.infrastructure.repositories.processed_event_repo import SqlAlchemyProcessedEventRepository
from app.infrastructure.repositories.route_repository import SqlAlchemyRouteRepository
from app.infrastructure.repositories.unit_of_work import SqlAlchemyUnitOfWork


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
    """Provee el publicador de eventos a AWS SNS."""
    return SnsEventPublisher()


def get_route_service(
    route_repo: IRouteRepository = Depends(get_route_repository),
) -> RouteService:
    """Instancia el servicio transaccional de ejemplo del arquetipo."""
    return RouteService(route_repo=route_repo)


def get_unit_of_work(db: Session = Depends(get_db)) -> IUnitOfWork:
    """Provee la unidad sobre la misma sesion que usan los repositorios."""
    return SqlAlchemyUnitOfWork(db)


def get_assignments_client() -> IAssignmentsClient:
    """Provee el cliente HTTP para el microservicio de Asignaciones."""
    return HttpAssignmentsClient()


def get_start_route_service(
    route_repo: IRouteRepository = Depends(get_route_repository),
    outbox_repo: IOutboxRepository = Depends(get_outbox_repository),
    assignments_client: IAssignmentsClient = Depends(get_assignments_client),
    unit_of_work: IUnitOfWork = Depends(get_unit_of_work),
) -> StartRouteService:
    """Instancia el servicio transaccional de inicio de ruta."""
    return StartRouteService(
        route_repo=route_repo,
        outbox_repo=outbox_repo,
        assignments_client=assignments_client,
        unit_of_work=unit_of_work,
    )


def get_finish_route_service(
    route_repo: IRouteRepository = Depends(get_route_repository),
    outbox_repo: IOutboxRepository = Depends(get_outbox_repository),
    unit_of_work: IUnitOfWork = Depends(get_unit_of_work),
) -> FinishRouteService:
    """Instancia el servicio transaccional de finalización de ruta (HU-03)."""
    return FinishRouteService(
        route_repo=route_repo,
        outbox_repo=outbox_repo,
        unit_of_work=unit_of_work,
    )

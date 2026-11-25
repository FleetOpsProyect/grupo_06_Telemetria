"""Persistencia del flujo de mensajes de Asignaciones en una sesión compartida."""

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import Insert as PostgresInsert
from sqlalchemy.dialects.sqlite import Insert as SQLiteInsert
from sqlalchemy.orm import Session

from app.domain.models.route import Route, RouteStatus
from app.domain.models.travel_plan import Coordinate, TravelPlan
from app.domain.ports.repositories import OutboxRecord
from app.infrastructure.db.orm_models import (
    OutboxModel,
    ProcessedEventModel,
    RouteModel,
    TravelPlanModel,
)
from app.infrastructure.repositories.route_repository import SqlAlchemyRouteRepository


class SqlAlchemyAssignmentMessageStore:
    """Almacena planes, deduplicación, cierre y outbox sin confirmar por su cuenta."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _insert(
        self, model: type[ProcessedEventModel] | type[TravelPlanModel]
    ) -> PostgresInsert | SQLiteInsert:
        dialect = self.session.get_bind().dialect.name
        if dialect == "postgresql":
            return PostgresInsert(model)
        if dialect == "sqlite":
            return SQLiteInsert(model)
        raise RuntimeError(f"Dialecto no soportado para procesar asignaciones: {dialect}")

    def claim_event(self, event_id: str, kind: str) -> bool:
        stmt = (
            self._insert(ProcessedEventModel)
            .values(evento_id=event_id, tipo_evento=kind)
            .on_conflict_do_nothing(index_elements=[ProcessedEventModel.evento_id])
            .returning(ProcessedEventModel.evento_id)
        )
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def save_plan(self, assignment_id: str, plan: TravelPlan) -> None:
        stmt = (
            self._insert(TravelPlanModel)
            .values(
                asignacion_id=assignment_id,
                latitud_origen=plan.origin.latitude,
                longitud_origen=plan.origin.longitude,
                latitud_destino=plan.destination.latitude,
                longitud_destino=plan.destination.longitude,
                duracion_estimada_segundos=plan.duration_seconds,
            )
            .on_conflict_do_nothing(index_elements=[TravelPlanModel.asignacion_id])
        )
        self.session.execute(stmt)

    def get_plan(self, assignment_id: str) -> TravelPlan | None:
        model = self.session.get(TravelPlanModel, assignment_id)
        if model is None:
            return None
        return TravelPlan(
            Coordinate(model.latitud_origen, model.longitud_origen),
            Coordinate(model.latitud_destino, model.longitud_destino),
            model.duracion_estimada_segundos,
        )

    def get_active_route(self, assignment_id: str) -> Route | None:
        return SqlAlchemyRouteRepository(self.session).get_active_route_by_asignacion(assignment_id)

    def close_active_route(self, route_id: str, finished_at: datetime) -> bool:
        stmt = (
            update(RouteModel)
            .where(RouteModel.id == route_id, RouteModel.estado == RouteStatus.EN_CURSO.value)
            .values(estado=RouteStatus.INTERRUMPIDA.value, hora_fin=finished_at)
            .returning(RouteModel.id)
        )
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def add_outbox(self, record: OutboxRecord) -> None:
        self.session.add(
            OutboxModel(
                id=record.id,
                evento_id=record.evento_id,
                tipo_evento=record.tipo_evento,
                routing_key=record.routing_key,
                payload_json=record.payload_json,
                estado=record.estado,
                intentos=record.intentos,
            )
        )

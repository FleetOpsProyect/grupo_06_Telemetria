"""Simulación del flujo HU-04: el productor entrega sobres JSON sin usar AWS."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.application.services.assignment_message_service import TravelPlanNotAvailableError
from app.domain.models.route import Route, RouteStatus
from app.infrastructure.messaging.assignment_handler import handle_assignment_message
from app.infrastructure.repositories.assignment_message_store import (
    SqlAlchemyAssignmentMessageStore,
)
from app.infrastructure.repositories.outbox_repository import SqlAlchemyOutboxRepository
from app.infrastructure.repositories.processed_event_repo import SqlAlchemyProcessedEventRepository
from app.infrastructure.repositories.route_repository import SqlAlchemyRouteRepository

START = datetime(2026, 10, 5, 8, tzinfo=UTC)
FINISH = datetime(2026, 10, 5, 8, 15, tzinfo=UTC)


def message(kind: str, **data: object) -> bytes:
    return json.dumps(
        {
            "evento_id": str(uuid4()),
            "tipo_evento": kind,
            "version": "1.0",
            "fecha_evento": START.isoformat(),
            "origen": "asignaciones",
            "datos": {"asignacion_id": "asig-8472", **data},
        }
    ).encode()


def plan_message() -> bytes:
    return message(
        "PlanViajeAsignacionEvent",
        coordenada_origen={"latitud": 0, "longitud": 0},
        coordenada_destino={"latitud": 0, "longitud": 0.2},
        duracion_estimada_segundos=1800,
    )


def save_active_route(db: Session) -> None:
    with Session(bind=db.get_bind()) as seed_session:
        SqlAlchemyRouteRepository(seed_session).save(
            Route("ruta-1", "asig-8472", "veh-1", "cond-1", hora_inicio=START)
        )


def deliver(db: Session, body: bytes) -> None:
    handle_assignment_message(sessionmaker(bind=db.get_bind()), body, clock=lambda: FINISH)


def test_plan_from_message_is_used_to_close_route_once(db_session: Session) -> None:
    deliver(db_session, plan_message())
    save_active_route(db_session)
    interrupted = message("AsignacionInterrumpidaEvent", incidente_id="inc-302")

    deliver(db_session, interrupted)
    deliver(db_session, interrupted)
    deliver(db_session, message("AsignacionInterrumpidaEvent"))

    route = SqlAlchemyRouteRepository(db_session).get_by_id("ruta-1")
    assert route is not None and route.estado == RouteStatus.INTERRUMPIDA
    events = SqlAlchemyOutboxRepository(db_session).get_pending()
    assert len(events) == 1
    assert events[0].routing_key == "telemetria.ruta.finalizada"
    event = json.loads(events[0].payload_json)
    assert event["tipo_evento"] == "RutaFinalizadaEvent"
    assert event["datos"] == {
        "asignacion_id": "asig-8472",
        "vehiculo_id": "veh-1",
        "distancia_recorrida_km": pytest.approx(11.12, abs=0.01),
        "estado_ruta": "INTERRUMPIDA",
        "hora_inicio": START.isoformat(),
        "hora_fin": FINISH.isoformat(),
    }


def test_missing_plan_leaves_route_and_event_available_for_retry(db_session: Session) -> None:
    save_active_route(db_session)
    interrupted = message("AsignacionInterrumpidaEvent")
    with pytest.raises(TravelPlanNotAvailableError):
        deliver(db_session, interrupted)

    route = SqlAlchemyRouteRepository(db_session).get_by_id("ruta-1")
    assert route is not None and route.estado == RouteStatus.EN_CURSO
    assert not SqlAlchemyProcessedEventRepository(db_session).is_processed(
        json.loads(interrupted)["evento_id"]
    )
    assert SqlAlchemyOutboxRepository(db_session).get_pending() == []
    db_session.rollback()

    deliver(db_session, plan_message())
    deliver(db_session, interrupted)
    assert len(SqlAlchemyOutboxRepository(db_session).get_pending()) == 1


def test_outbox_failure_rolls_back_route_and_event_id(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_active_route(db_session)
    deliver(db_session, plan_message())
    interrupted = message("AsignacionInterrumpidaEvent")

    with monkeypatch.context() as patch:

        def fail(*_: object) -> None:
            raise RuntimeError("outbox no disponible")

        patch.setattr(SqlAlchemyAssignmentMessageStore, "add_outbox", fail)
        with pytest.raises(RuntimeError, match="outbox no disponible"):
            deliver(db_session, interrupted)

    route = SqlAlchemyRouteRepository(db_session).get_by_id("ruta-1")
    assert route is not None and route.estado == RouteStatus.EN_CURSO
    assert not SqlAlchemyProcessedEventRepository(db_session).is_processed(
        json.loads(interrupted)["evento_id"]
    )
    db_session.rollback()

    deliver(db_session, interrupted)
    assert len(SqlAlchemyOutboxRepository(db_session).get_pending()) == 1

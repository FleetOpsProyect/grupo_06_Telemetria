"""Tests de repositorios y unidad de trabajo contra SQLite en memoria (HU-01)."""

import pytest
from app.infrastructure.repositories.unit_of_work import SqlAlchemyUnitOfWork
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateEntityError
from app.domain.models.route import CENTRO_OPERACIONES, Route
from app.domain.ports.repositories import OutboxRecord
from app.infrastructure.db.orm_models import OutboxModel, RouteModel
from app.infrastructure.repositories.outbox_repository import SqlAlchemyOutboxRepository
from app.infrastructure.repositories.route_repository import SqlAlchemyRouteRepository


def _route(asignacion_id: str, route_id: str = "r1") -> Route:
    return Route.start_new(
        id=route_id, asignacion_id=asignacion_id, vehiculo_id="v1", conductor_id="c1"
    )


def _outbox_record() -> OutboxRecord:
    return OutboxRecord(
        id="o1",
        evento_id="e1",
        tipo_evento="RutaIniciadaEvent",
        routing_key="telemetria.ruta.iniciada",
        payload_json="{}",
    )


def _count(db_session: Session, model: type[RouteModel] | type[OutboxModel]) -> int:
    return db_session.execute(select(func.count()).select_from(model)).scalar_one()


def test_guarda_y_lee_origen_y_hora_inicio_en_utc(db_session: Session) -> None:
    repo = SqlAlchemyRouteRepository(db_session)
    route = _route("a1")
    repo.save(route)
    db_session.expire_all()  # obliga a releer desde la BD y no desde memoria

    leida = repo.get_by_id("r1")

    assert leida is not None
    assert leida.origen == CENTRO_OPERACIONES
    assert leida.hora_inicio.isoformat() == route.hora_inicio.isoformat()


def test_ruta_y_evento_se_confirman_juntos(db_session: Session) -> None:
    SqlAlchemyRouteRepository(db_session).add(_route("a1"))
    SqlAlchemyOutboxRepository(db_session).add(_outbox_record())

    SqlAlchemyUnitOfWork(db_session).commit()

    assert _count(db_session, RouteModel) == 1
    assert _count(db_session, OutboxModel) == 1


def test_rollback_descarta_ruta_y_evento(db_session: Session) -> None:
    SqlAlchemyRouteRepository(db_session).add(_route("a1"))
    SqlAlchemyOutboxRepository(db_session).add(_outbox_record())

    SqlAlchemyUnitOfWork(db_session).rollback()

    assert _count(db_session, RouteModel) == 0
    assert _count(db_session, OutboxModel) == 0


def test_misma_asignacion_dos_veces_lanza_ruta_duplicada(db_session: Session) -> None:
    repo = SqlAlchemyRouteRepository(db_session)
    repo.add(_route("a1", route_id="r1"))
    SqlAlchemyUnitOfWork(db_session).commit()

    with pytest.raises(DuplicateEntityError) as exc:
        repo.add(_route("a1", route_id="r2"))

    assert exc.value.code == "RUTA_DUPLICADA"

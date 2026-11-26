"""Tests de integración HU-03: POST /api/v1/route con SQLite en memoria."""

import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.domain.models.route import Coordinate, Route, RouteStatus
from app.domain.models.trip_simulation import haversine_km
from app.infrastructure.db.orm_models import OutboxModel, RouteModel
from app.infrastructure.repositories.route_repository import SqlAlchemyRouteRepository
from app.main import app
from app.presentation.dependencies import get_route_repository

URL = "/api/v1/route"
DESTINO = {"destino_latitud": 3.4372, "destino_longitud": -76.5225}


def _seed(db: Session, asignacion_id: str, *, hace: timedelta = timedelta(hours=2)) -> Route:
    route = Route.start_new(
        id=f"ruta-{asignacion_id}",
        asignacion_id=asignacion_id,
        vehiculo_id="veh-501",
        conductor_id="cond-101",
    )
    route.hora_inicio = datetime.now(UTC) - hace
    with Session(bind=db.get_bind()) as seed:
        repo = SqlAlchemyRouteRepository(seed)
        repo.add(route)
        seed.commit()
    return route


# ---------- 200 (criterios 3, 4, 5 y 6) ----------


def test_200_con_destino_enviado_finaliza_y_guarda_el_cierre(
    client: TestClient, db_session: Session
) -> None:
    route = _seed(db_session, "asig-ok")

    response = client.post(URL, json={"asignacion_id": "asig-ok", **DESTINO})

    assert response.status_code == 200
    body = response.json()
    esperado = round(haversine_km(route.origen, Coordinate(3.4372, -76.5225)), 2)
    assert body["estado"] == "FINALIZADA"
    assert body["distancia_recorrida_km"] == esperado
    assert body["origen"] == {"latitud": 3.4516, "longitud": -76.532}
    assert body["destino"] == {"latitud": 3.4372, "longitud": -76.5225}
    assert body["vehiculo_id"] == "veh-501"

    db_session.expire_all()
    model = db_session.get(RouteModel, route.id)
    assert model is not None and model.estado == "FINALIZADA"
    assert model.hora_fin is not None
    assert (model.latitud_destino, model.longitud_destino) == (3.4372, -76.5225)
    assert model.distancia_recorrida_km == esperado


def test_200_sin_destino_simula_uno_a_5_25_km(client: TestClient, db_session: Session) -> None:
    _seed(db_session, "asig-sim")

    response = client.post(URL, json={"asignacion_id": "asig-sim"})

    assert response.status_code == 200
    assert 5.0 - 0.01 <= response.json()["distancia_recorrida_km"] <= 25.0 + 0.01


def test_viaje_de_menos_de_un_minuto_registra_0_50_km(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session, "asig-corta", hace=timedelta(seconds=5))

    response = client.post(URL, json={"asignacion_id": "asig-corta", **DESTINO})

    assert response.json()["distancia_recorrida_km"] == 0.50


def test_deja_route_completed_event_pendiente_en_outbox(
    client: TestClient, db_session: Session
) -> None:
    route = _seed(db_session, "asig-evento")

    client.post(URL, json={"asignacion_id": "asig-evento", **DESTINO})

    outbox = db_session.execute(select(OutboxModel)).scalars().all()
    assert len(outbox) == 1
    assert outbox[0].tipo_evento == "route_completed_event"
    assert outbox[0].routing_key == "telemetria.ruta.finalizada"
    assert outbox[0].estado == "PENDIENTE"
    payload = json.loads(outbox[0].payload_json)["payload"]
    assert payload["ruta_id"] == route.id
    assert payload["estado"] == "FINALIZADA"


def test_tambien_responde_sin_prefijo_api_v1(client: TestClient, db_session: Session) -> None:
    _seed(db_session, "asig-sin-prefijo")

    response = client.post("/route", json={"asignacion_id": "asig-sin-prefijo"})

    assert response.status_code == 200


def test_get_posterior_muestra_la_ruta_finalizada(client: TestClient, db_session: Session) -> None:
    route = _seed(db_session, "asig-get")
    client.post(URL, json={"asignacion_id": "asig-get"})

    response = client.get(f"/api/v1/rutas/{route.id}")

    assert response.json()["estado"] == RouteStatus.FINALIZADA.value


# ---------- 404 y 409 (criterio 2) ----------


def test_404_si_no_hay_ruta_para_la_asignacion(client: TestClient) -> None:
    response = client.post(URL, json={"asignacion_id": "asig-inexistente"})

    assert response.status_code == 404
    assert response.json()["codigo"] == "RUTA_NO_ENCONTRADA"
    assert response.json()["mensaje"] == (
        "No existe una ruta asociada a la asignación asig-inexistente"
    )


def test_409_si_la_ruta_ya_estaba_finalizada_y_no_duplica_evento(
    client: TestClient, db_session: Session
) -> None:
    _seed(db_session, "asig-doble")
    assert client.post(URL, json={"asignacion_id": "asig-doble"}).status_code == 200

    response = client.post(URL, json={"asignacion_id": "asig-doble"})

    assert response.status_code == 409
    assert response.json()["codigo"] == "ESTADO_RUTA_INVALIDO"
    assert len(db_session.execute(select(OutboxModel)).scalars().all()) == 1


def test_update_condicional_solo_deja_ganar_un_cierre(db_session: Session) -> None:
    route = _seed(db_session, "asig-carrera")
    repo = SqlAlchemyRouteRepository(db_session)
    route.finish(datetime.now(UTC), Coordinate(3.5, -76.5), 6.0)

    assert repo.finish(route) is True
    assert repo.finish(route) is False


# ---------- 400 (criterio 1) ----------


def test_400_si_falta_asignacion_id(client: TestClient) -> None:
    response = client.post(URL, json={})

    assert response.status_code == 400
    assert response.json()["codigo"] == "DATOS_INVALIDOS"
    assert response.json()["mensaje"] == "El campo asignacion_id es obligatorio"


def test_400_si_el_cuerpo_no_es_json(client: TestClient) -> None:
    response = client.post(URL, content="{no es json", headers={"Content-Type": "application/json"})

    assert response.status_code == 400
    assert response.json()["codigo"] == "JSON_INVALIDO"


@pytest.mark.parametrize(
    "extra",
    [{"destino_latitud": 3.4}, {"destino_latitud": 95, "destino_longitud": -76.5}],
)
def test_400_si_el_destino_es_incompleto_o_invalido(
    client: TestClient, extra: dict[str, float]
) -> None:
    response = client.post(URL, json={"asignacion_id": "asig-x", **extra})

    assert response.status_code == 400
    assert response.json()["codigo"] == "DATOS_INVALIDOS"


# ---------- 503 (criterio 8) ----------


class _BrokenRepo(SqlAlchemyRouteRepository):
    def get_by_asignacion_id(self, asignacion_id: str) -> Route | None:
        raise DatabaseUnavailableError("BD caída")


@pytest.fixture
def broken_db(client: TestClient, db_session: Session) -> Generator[None, None, None]:
    app.dependency_overrides[get_route_repository] = lambda: _BrokenRepo(db_session)
    yield
    app.dependency_overrides.pop(get_route_repository, None)


@pytest.mark.usefixtures("broken_db")
def test_503_si_la_bd_no_responde_y_no_emite_eventos(
    client: TestClient, db_session: Session
) -> None:
    response = client.post(URL, json={"asignacion_id": "asig-503"})

    assert response.status_code == 503
    assert response.json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
    assert db_session.execute(select(OutboxModel)).scalars().all() == []


def test_repositorio_exige_destino_para_finalizar(db_session: Session) -> None:
    route = _seed(db_session, "asig-sin-destino")

    with pytest.raises(ValueError):
        SqlAlchemyRouteRepository(db_session).finish(route)


def test_repositorio_traduce_error_de_bd_a_503(db_session: Session) -> None:
    route = _seed(db_session, "asig-error-bd")
    route.finish(datetime.now(UTC), Coordinate(3.5, -76.5), 6.0)
    session = MagicMock(spec=Session)
    session.execute.side_effect = OperationalError("UPDATE", {}, Exception("caída"))

    with pytest.raises(DatabaseUnavailableError):
        SqlAlchemyRouteRepository(session).finish(route)
    session.rollback.assert_called_once()

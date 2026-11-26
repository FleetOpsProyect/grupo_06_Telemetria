"""Tests de integración GET /api/v1/route y GET /api/v1/route/{id}."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.domain.models.route import Coordinate, Route, RouteStatus
from app.infrastructure.repositories.route_repository import SqlAlchemyRouteRepository
from app.main import app
from app.presentation.dependencies import get_route_repository

URL = "/api/v1/route"


def _seed_route(
    db: Session,
    *,
    route_id: str,
    asignacion_id: str,
    vehiculo_id: str = "veh-1",
    estado: RouteStatus = RouteStatus.EN_CURSO,
    hora_inicio: datetime | None = None,
) -> Route:
    route = Route(
        id=route_id,
        asignacion_id=asignacion_id,
        vehiculo_id=vehiculo_id,
        conductor_id="cond-1",
        estado=RouteStatus.EN_CURSO,
        hora_inicio=hora_inicio or datetime.now(UTC),
        origen=Coordinate(latitud=3.4516, longitud=-76.5320),
    )
    with Session(bind=db.get_bind()) as seed:
        repo = SqlAlchemyRouteRepository(seed)
        repo.add(route)
        if estado == RouteStatus.FINALIZADA:
            route.finish(
                hora_fin=datetime.now(UTC),
                destino=Coordinate(latitud=3.4372, longitud=-76.5225),
                distancia_km=12.5,
            )
            repo.finish(route)
        seed.commit()
    return route


def test_list_routes_orden_descendente_y_paginacion(
    client: TestClient, db_session: Session
) -> None:
    ahora = datetime.now(UTC)
    _seed_route(
        db_session, route_id="r-vieja", asignacion_id="a-1", hora_inicio=ahora - timedelta(hours=2)
    )
    _seed_route(
        db_session, route_id="r-nueva", asignacion_id="a-2", hora_inicio=ahora - timedelta(hours=1)
    )

    resp = client.get(f"{URL}?page=0&size=1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 0
    assert body["size"] == 1
    assert body["total"] == 2
    assert len(body["contenido"]) == 1
    assert body["contenido"][0]["id"] == "r-nueva"


def test_list_routes_filtros_y_lista_vacia(client: TestClient, db_session: Session) -> None:
    _seed_route(
        db_session,
        route_id="r-fin",
        asignacion_id="a-fin",
        vehiculo_id="veh-99",
        estado=RouteStatus.FINALIZADA,
    )

    ok = client.get(f"{URL}?estado=FINALIZADA&vehiculo_id=veh-99")
    assert ok.status_code == 200
    assert ok.json()["total"] == 1

    vacio = client.get(f"{URL}?asignacion_id=no-existe")
    assert vacio.status_code == 200
    assert vacio.json()["contenido"] == []
    assert vacio.json()["total"] == 0


def test_list_routes_parametros_invalidos_retorna_400(client: TestClient) -> None:
    for query in ("?size=0", "?page=-1", "?fecha_desde=25-11-2026", "?estado=OTRO"):
        resp = client.get(f"{URL}{query}")
        assert resp.status_code == 400
        assert resp.json()["codigo"] == "DATOS_INVALIDOS"


def test_get_route_detail_200_y_404(client: TestClient, db_session: Session) -> None:
    _seed_route(
        db_session,
        route_id="r-det",
        asignacion_id="a-det",
        estado=RouteStatus.FINALIZADA,
    )

    ok = client.get(f"{URL}/r-det")
    assert ok.status_code == 200
    assert ok.json()["coordenada_origen"] == {"latitud": 3.4516, "longitud": -76.532}
    assert ok.json()["coordenada_destino"] == {"latitud": 3.4372, "longitud": -76.5225}

    not_found = client.get(f"{URL}/no-existe")
    assert not_found.status_code == 404
    assert not_found.json()["codigo"] == "RUTA_NO_ENCONTRADA"


def test_list_routes_bd_caida_retorna_503(client: TestClient) -> None:
    repo_mock = MagicMock()
    repo_mock.list_routes.side_effect = DatabaseUnavailableError()
    app.dependency_overrides[get_route_repository] = lambda: repo_mock
    try:
        resp = client.get(URL)
        assert resp.status_code == 503
        assert resp.json()["codigo"] == "SERVICIO_NO_DISPONIBLE"
    finally:
        app.dependency_overrides.clear()
"""Tests unitarios para la entidad de dominio Route del arquetipo."""

from datetime import UTC, datetime

from app.domain.models.route import CENTRO_OPERACIONES, Route, RouteStatus


class TestRouteModel:
    """Pruebas de la entidad de dominio Route."""

    def test_start_new_route(self) -> None:
        route = Route.start_new(
            id="ruta-001",
            asignacion_id="asig-001",
            vehiculo_id="veh-001",
            conductor_id="cond-001",
        )
        assert route.id == "ruta-001"
        assert route.asignacion_id == "asig-001"
        assert route.vehiculo_id == "veh-001"
        assert route.conductor_id == "cond-001"
        assert route.estado == RouteStatus.EN_CURSO
        assert route.hora_inicio is not None
        assert route.hora_fin is None

    def test_route_constructor(self) -> None:
        now = datetime.now(UTC)
        route = Route(
            id="ruta-002",
            asignacion_id="asig-002",
            vehiculo_id="veh-002",
            conductor_id="cond-002",
            estado=RouteStatus.FINALIZADA,
            hora_inicio=now,
            hora_fin=now,
        )
        assert route.id == "ruta-002"
        assert route.estado == RouteStatus.FINALIZADA
        assert route.hora_fin == now

    def test_start_new_fija_origen_en_centro_de_operaciones(self) -> None:
        route = Route.start_new(id="r1", asignacion_id="a1", vehiculo_id="v1", conductor_id="c1")

        assert route.estado == RouteStatus.EN_CURSO
        assert route.origen == CENTRO_OPERACIONES
        assert (route.origen.latitud, route.origen.longitud) == (3.4516, -76.5320)

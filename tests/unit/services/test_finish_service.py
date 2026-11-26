"""Tests unitarios del caso de uso HU-03 FinishRouteService (AAA Pattern)."""

import json
import random
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.application.dtos.route_finish import RouteFinishDTO, RouteFinishedResponseDTO
from app.application.services.finish_service import FinishRouteService
from app.core.exceptions import (
    DatabaseUnavailableError,
    EntityNotFoundError,
    InvalidStateTransitionError,
)
from app.domain.models.events import (
    ROUTE_COMPLETED_EVENT,
    ROUTE_COMPLETED_ROUTING_KEY,
    route_completed_event,
)
from app.domain.models.route import CENTRO_OPERACIONES, Coordinate, Route, RouteStatus
from app.domain.models.trip_simulation import haversine_km
from app.domain.ports.repositories import OutboxRecord

ASIGNACION_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
INICIO = datetime(2026, 10, 29, 8, tzinfo=UTC)
FIN = INICIO + timedelta(hours=2, minutes=30)


def _route(estado: RouteStatus = RouteStatus.EN_CURSO) -> Route:
    return Route(
        id="ruta-1",
        asignacion_id=ASIGNACION_ID,
        vehiculo_id="veh-501",
        conductor_id="cond-101",
        estado=estado,
        hora_inicio=INICIO,
    )


@pytest.fixture
def mocks() -> dict[str, MagicMock]:
    route_repo = MagicMock()
    route_repo.get_by_asignacion_id.return_value = _route()
    route_repo.finish.return_value = True
    return {"route_repo": route_repo, "outbox_repo": MagicMock(), "uow": MagicMock()}


def _service(m: dict[str, MagicMock], seed: int = 7) -> FinishRouteService:
    return FinishRouteService(
        route_repo=m["route_repo"],
        outbox_repo=m["outbox_repo"],
        unit_of_work=m["uow"],
        clock=lambda: FIN,
        rng=random.Random(seed),
    )


def _outbox(m: dict[str, MagicMock]) -> OutboxRecord:
    record: OutboxRecord = m["outbox_repo"].add.call_args.args[0]
    return record


# ---------- Escenario feliz (criterios 3, 4, 5 y 6) ----------


def test_con_destino_enviado_calcula_haversine_y_finaliza(mocks: dict[str, MagicMock]) -> None:
    dto = RouteFinishDTO(
        asignacion_id=ASIGNACION_ID, destino_latitud=3.4372, destino_longitud=-76.5225
    )

    result = _service(mocks).finish_route(dto)

    destino = Coordinate(3.4372, -76.5225)
    assert result.estado == "FINALIZADA"
    assert result.destino.latitud == 3.4372 and result.destino.longitud == -76.5225
    assert result.distancia_recorrida_km == round(haversine_km(CENTRO_OPERACIONES, destino), 2)
    assert result.hora_fin == FIN.isoformat()
    mocks["route_repo"].finish.assert_called_once()
    mocks["uow"].commit.assert_called_once()


def test_sin_destino_lo_simula_entre_5_y_25_km(mocks: dict[str, MagicMock]) -> None:
    result = _service(mocks).finish_route(RouteFinishDTO(asignacion_id=ASIGNACION_ID))

    assert 5.0 - 0.01 <= result.distancia_recorrida_km <= 25.0 + 0.01


def test_viaje_de_menos_de_un_minuto_registra_0_50_km(mocks: dict[str, MagicMock]) -> None:
    service = _service(mocks)
    service.clock = lambda: INICIO + timedelta(seconds=30)

    result = service.finish_route(RouteFinishDTO(asignacion_id=ASIGNACION_ID))

    assert result.distancia_recorrida_km == 0.50


def test_guarda_route_completed_event_con_contrato_del_das(mocks: dict[str, MagicMock]) -> None:
    result = _service(mocks).finish_route(RouteFinishDTO(asignacion_id=ASIGNACION_ID))

    record = _outbox(mocks)
    assert record.tipo_evento == ROUTE_COMPLETED_EVENT
    assert record.routing_key == ROUTE_COMPLETED_ROUTING_KEY
    event = json.loads(record.payload_json)
    assert set(event) == {"evento_id", "tipo_evento", "origen", "timestamp", "version", "payload"}
    assert event["tipo_evento"] == "route_completed_event"
    assert event["evento_id"] == record.evento_id
    assert event["payload"] == {
        "ruta_id": "ruta-1",
        "asignacion_id": ASIGNACION_ID,
        "vehiculo_id": "veh-501",
        "conductor_id": "cond-101",
        "estado": "FINALIZADA",
        "hora_inicio": INICIO.isoformat(),
        "hora_fin": FIN.isoformat(),
        "distancia_recorrida_km": result.distancia_recorrida_km,
    }


def test_hora_inicio_sin_zona_se_trata_como_utc(mocks: dict[str, MagicMock]) -> None:
    route = _route()
    route.hora_inicio = INICIO.replace(tzinfo=None)
    mocks["route_repo"].get_by_asignacion_id.return_value = route

    result = _service(mocks).finish_route(RouteFinishDTO(asignacion_id=ASIGNACION_ID))

    assert result.hora_inicio == INICIO.isoformat()


# ---------- 404 y 409 (criterio 2) ----------


def test_sin_ruta_para_la_asignacion_responde_404(mocks: dict[str, MagicMock]) -> None:
    mocks["route_repo"].get_by_asignacion_id.return_value = None

    with pytest.raises(EntityNotFoundError) as exc:
        _service(mocks).finish_route(RouteFinishDTO(asignacion_id=ASIGNACION_ID))

    assert exc.value.code == "RUTA_NO_ENCONTRADA"
    assert exc.value.message == f"No existe una ruta asociada a la asignación {ASIGNACION_ID}"
    mocks["uow"].commit.assert_not_called()


@pytest.mark.parametrize("estado", [RouteStatus.FINALIZADA, RouteStatus.INTERRUMPIDA])
def test_ruta_ya_cerrada_responde_409(mocks: dict[str, MagicMock], estado: RouteStatus) -> None:
    mocks["route_repo"].get_by_asignacion_id.return_value = _route(estado)

    with pytest.raises(InvalidStateTransitionError) as exc:
        _service(mocks).finish_route(RouteFinishDTO(asignacion_id=ASIGNACION_ID))

    assert exc.value.code == "ESTADO_RUTA_INVALIDO"
    mocks["route_repo"].finish.assert_not_called()
    mocks["outbox_repo"].add.assert_not_called()


def test_cierre_concurrente_responde_409_sin_evento(mocks: dict[str, MagicMock]) -> None:
    mocks["route_repo"].finish.return_value = False

    with pytest.raises(InvalidStateTransitionError):
        _service(mocks).finish_route(RouteFinishDTO(asignacion_id=ASIGNACION_ID))

    mocks["outbox_repo"].add.assert_not_called()
    mocks["uow"].commit.assert_not_called()
    mocks["uow"].rollback.assert_called_once()


# ---------- 503 (criterio 8) ----------


def test_bd_caida_al_consultar_responde_503_y_registra_error(mocks: dict[str, MagicMock]) -> None:
    mocks["route_repo"].get_by_asignacion_id.side_effect = DatabaseUnavailableError("caída")

    with patch("app.application.services.finish_service.logger") as logger:
        with pytest.raises(DatabaseUnavailableError) as exc:
            _service(mocks).finish_route(RouteFinishDTO(asignacion_id=ASIGNACION_ID))

    assert exc.value.code == "SERVICIO_NO_DISPONIBLE"
    logger.error.assert_called_once()
    mocks["outbox_repo"].add.assert_not_called()


def test_fallo_al_confirmar_hace_rollback_y_responde_503(mocks: dict[str, MagicMock]) -> None:
    mocks["uow"].commit.side_effect = DatabaseUnavailableError("caída")

    with pytest.raises(DatabaseUnavailableError):
        _service(mocks).finish_route(RouteFinishDTO(asignacion_id=ASIGNACION_ID))

    mocks["uow"].rollback.assert_called_once()


# ---------- Dominio y DTO ----------


def test_route_finish_rechaza_ruta_no_en_curso() -> None:
    with pytest.raises(ValueError):
        _route(RouteStatus.FINALIZADA).finish(FIN, CENTRO_OPERACIONES, 1.0)


def test_evento_y_respuesta_exigen_ruta_finalizada() -> None:
    with pytest.raises(ValueError):
        route_completed_event(_route())
    with pytest.raises(ValueError):
        RouteFinishedResponseDTO.from_domain(_route())


def test_dto_exige_latitud_y_longitud_juntas() -> None:
    with pytest.raises(ValueError):
        RouteFinishDTO(asignacion_id=ASIGNACION_ID, destino_latitud=3.4)

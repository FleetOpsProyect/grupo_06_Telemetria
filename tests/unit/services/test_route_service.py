"""Tests unitarios del caso de uso HU-01 StartRouteService (AAA Pattern)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.application.dtos.route_start import RouteStartDTO
from app.application.services.start_service import StartRouteService
from app.core.exceptions import (
    CircuitBreakerOpenError,
    DatabaseUnavailableError,
    DuplicateEntityError,
    EntityNotFoundError,
    ExternalDependencyError,
    InvalidStateTransitionError,
)
from app.domain.models.events import ROUTE_STARTED_EVENT, ROUTE_STARTED_ROUTING_KEY
from app.domain.models.route import CENTRO_OPERACIONES, Route, RouteStatus
from app.domain.ports.external_services import AssignmentSnapshot
from app.domain.ports.repositories import OutboxRecord

ASIGNACION_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
DTO = RouteStartDTO(asignacion_id=ASIGNACION_ID)


def _assignment(estado: str = "PENDIENTE") -> AssignmentSnapshot:
    return AssignmentSnapshot(
        asignacion_id=ASIGNACION_ID, estado=estado, vehiculo_id="veh-501", conductor_id="cond-101"
    )


@pytest.fixture
def mocks() -> dict[str, MagicMock]:
    """Dobles de prueba en el escenario feliz; cada test cambia solo lo que necesita."""
    route_repo = MagicMock()
    route_repo.get_by_asignacion_id.return_value = None
    assignments = MagicMock()
    assignments.get_assignment.return_value = _assignment()
    return {
        "route_repo": route_repo,
        "outbox_repo": MagicMock(),
        "assignments": assignments,
        "uow": MagicMock(),
    }


def _service(m: dict[str, MagicMock]) -> StartRouteService:
    return StartRouteService(
        route_repo=m["route_repo"],
        outbox_repo=m["outbox_repo"],
        assignments_client=m["assignments"],
        unit_of_work=m["uow"],
    )


def _assert_nothing_persisted(m: dict[str, MagicMock]) -> None:
    m["route_repo"].add.assert_not_called()
    m["outbox_repo"].add.assert_not_called()
    m["uow"].commit.assert_not_called()


# ---------- Escenario feliz (criterios 3, 5 y 6) ----------


def test_inicia_ruta_en_curso_con_datos_de_asignaciones(mocks: dict[str, MagicMock]) -> None:
    result = _service(mocks).start_route(DTO)

    assert result.asignacion_id == ASIGNACION_ID
    assert (result.vehiculo_id, result.conductor_id) == ("veh-501", "cond-101")
    assert result.estado == "EN_CURSO"
    assert result.coordenada_origen.latitud == CENTRO_OPERACIONES.latitud
    mocks["assignments"].get_assignment.assert_called_once_with(ASIGNACION_ID)


def test_guarda_ruta_y_evento_en_la_misma_transaccion(mocks: dict[str, MagicMock]) -> None:
    result = _service(mocks).start_route(DTO)

    route: Route = mocks["route_repo"].add.call_args.args[0]
    assert route.id == result.id
    assert route.estado == RouteStatus.EN_CURSO
    mocks["outbox_repo"].add.assert_called_once()
    mocks["uow"].commit.assert_called_once()
    mocks["uow"].rollback.assert_not_called()


def test_evento_ruta_iniciada_tiene_sobre_estandar_y_datos(mocks: dict[str, MagicMock]) -> None:
    result = _service(mocks).start_route(DTO)

    record: OutboxRecord = mocks["outbox_repo"].add.call_args.args[0]
    assert record.routing_key == ROUTE_STARTED_ROUTING_KEY
    assert record.tipo_evento == ROUTE_STARTED_EVENT
    assert record.estado == "PENDIENTE"
    envelope = json.loads(record.payload_json)
    assert envelope["evento_id"] == record.evento_id
    assert envelope["datos"]["ruta_id"] == result.id
    assert envelope["datos"]["hora_inicio"] == result.hora_inicio


# ---------- Reglas de negocio (criterios 2 y 4) ----------


def test_ruta_existente_responde_duplicada_sin_llamar_asignaciones(
    mocks: dict[str, MagicMock],
) -> None:
    mocks["route_repo"].get_by_asignacion_id.return_value = Route(
        id="ruta-existente", asignacion_id=ASIGNACION_ID, vehiculo_id="v", conductor_id="c"
    )

    with pytest.raises(DuplicateEntityError) as exc:
        _service(mocks).start_route(DTO)

    assert exc.value.code == "RUTA_DUPLICADA"
    mocks["assignments"].get_assignment.assert_not_called()
    _assert_nothing_persisted(mocks)


def test_asignacion_inexistente_responde_404(mocks: dict[str, MagicMock]) -> None:
    mocks["assignments"].get_assignment.return_value = None

    with pytest.raises(EntityNotFoundError) as exc:
        _service(mocks).start_route(DTO)

    assert exc.value.code == "ASIGNACION_NO_ENCONTRADA"
    assert exc.value.message == f"No existe una asignación con id {ASIGNACION_ID}"
    _assert_nothing_persisted(mocks)


@pytest.mark.parametrize("estado", ["EN_CURSO", "FINALIZADA", "CANCELADA"])
def test_asignacion_no_pendiente_responde_409(mocks: dict[str, MagicMock], estado: str) -> None:
    mocks["assignments"].get_assignment.return_value = _assignment(estado)

    with pytest.raises(InvalidStateTransitionError) as exc:
        _service(mocks).start_route(DTO)

    assert exc.value.code == "ASIGNACION_NO_PENDIENTE"
    _assert_nothing_persisted(mocks)


# ---------- Fallos de dependencias (criterios 7 y 8) ----------


@pytest.mark.parametrize(
    "error", [ExternalDependencyError("caído"), CircuitBreakerOpenError("circuito abierto")]
)
def test_asignaciones_no_disponible_propaga_503_sin_persistir(
    mocks: dict[str, MagicMock], error: Exception
) -> None:
    mocks["assignments"].get_assignment.side_effect = error

    with pytest.raises(ExternalDependencyError) as exc:
        _service(mocks).start_route(DTO)

    assert exc.value.code == "DEPENDENCIA_NO_DISPONIBLE"
    _assert_nothing_persisted(mocks)


def test_inicio_concurrente_detectado_por_bd_responde_duplicada(
    mocks: dict[str, MagicMock],
) -> None:
    mocks["route_repo"].add.side_effect = DuplicateEntityError("unique violation")

    with pytest.raises(DuplicateEntityError) as exc:
        _service(mocks).start_route(DTO)

    assert exc.value.code == "RUTA_DUPLICADA"
    assert ASIGNACION_ID in exc.value.message
    mocks["uow"].rollback.assert_called_once()
    mocks["uow"].commit.assert_not_called()


def test_fallo_al_confirmar_responde_503_y_registra_error(mocks: dict[str, MagicMock]) -> None:
    mocks["uow"].commit.side_effect = DatabaseUnavailableError("conexión perdida")

    with (
        patch("app.application.services.start_service.logger") as log,
        pytest.raises(DatabaseUnavailableError) as exc,
    ):
        _service(mocks).start_route(DTO)

    assert exc.value.code == "SERVICIO_NO_DISPONIBLE"
    assert exc.value.message == "Servicio de persistencia no disponible"
    mocks["uow"].rollback.assert_called_once()
    log.error.assert_called_once()


def test_bd_caida_en_consulta_inicial_no_llama_asignaciones(mocks: dict[str, MagicMock]) -> None:
    mocks["route_repo"].get_by_asignacion_id.side_effect = DatabaseUnavailableError("down")

    with (
        patch("app.application.services.start_service.logger") as log,
        pytest.raises(DatabaseUnavailableError),
    ):
        _service(mocks).start_route(DTO)

    mocks["assignments"].get_assignment.assert_not_called()
    log.error.assert_called_once()

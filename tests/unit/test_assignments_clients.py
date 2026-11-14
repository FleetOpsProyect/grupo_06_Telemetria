"""Tests unitarios del cliente HTTP hacia Asignaciones (HU-01) con httpx.MockTransport."""

import sys
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

# Asegura que el paquete de la aplicación sea importable al ejecutar este test
# directamente, además de cuando pytest se ejecuta desde la raíz del proyecto.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.circuit_breaker import CircuitBreaker, CircuitState
from app.core.exceptions import CircuitBreakerOpenError, ExternalDependencyError
from app.infrastructure.http_clients.assignments_clients import HttpAssignmentsClient

ASIG = "asig-8472"


def _client(
    handler: Callable[[httpx.Request], httpx.Response], breaker: CircuitBreaker | None = None
) -> HttpAssignmentsClient:
    return HttpAssignmentsClient(
        base_url="http://asignaciones.test",
        path_template="/asignaciones/{asignacion_id}",
        timeout_seconds=2.0,
        breaker=breaker or CircuitBreaker(name="test", failure_threshold=5),
        transport=httpx.MockTransport(handler),
    )


def test_200_con_campos_en_espanol() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/asignaciones/{ASIG}"
        assert "X-Correlation-Id" in request.headers
        return httpx.Response(
            200, json={"estado": "PENDIENTE", "vehiculo_id": "v1", "conductor_id": "c1"}
        )

    result = _client(handler).get_assignment(ASIG)

    assert result is not None
    assert (result.estado, result.vehiculo_id, result.conductor_id) == ("PENDIENTE", "v1", "c1")


def test_200_con_campos_en_ingles_ignora_campos_extra() -> None:
    body = {"state": "PENDIENTE", "vehicle_id": "v2", "driver_id": "c2", "origin": "Cali"}

    result = _client(lambda _: httpx.Response(200, json=body)).get_assignment(ASIG)

    assert result is not None
    assert (result.vehiculo_id, result.conductor_id) == ("v2", "c2")


def test_404_retorna_none() -> None:
    assert _client(lambda _: httpx.Response(404)).get_assignment(ASIG) is None


@pytest.mark.parametrize("status_code", [500, 502, 503])
def test_5xx_lanza_dependencia_no_disponible(status_code: int) -> None:
    with pytest.raises(ExternalDependencyError) as exc:
        _client(lambda _: httpx.Response(status_code)).get_assignment(ASIG)

    assert exc.value.code == "DEPENDENCIA_NO_DISPONIBLE"


def test_timeout_lanza_dependencia_no_disponible() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(ExternalDependencyError):
        _client(handler).get_assignment(ASIG)


def test_respuesta_sin_vehiculo_ni_conductor_lanza_dependencia_no_disponible() -> None:
    with pytest.raises(ExternalDependencyError):
        _client(lambda _: httpx.Response(200, json={"estado": "PENDIENTE"})).get_assignment(ASIG)


def test_cinco_fallos_abren_el_circuito_y_no_se_hacen_mas_llamadas() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    breaker = CircuitBreaker(name="test", failure_threshold=5, recovery_timeout_seconds=30)
    client = _client(handler, breaker)

    for _ in range(5):
        with pytest.raises(ExternalDependencyError):
            client.get_assignment(ASIG)
    assert breaker.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerOpenError) as exc:
        client.get_assignment(ASIG)

    assert calls["n"] == 5  # la 6.ª llamada NO llegó a Asignaciones
    assert exc.value.code == "DEPENDENCIA_NO_DISPONIBLE"


def test_404_no_cuenta_como_fallo_del_circuito() -> None:
    breaker = CircuitBreaker(name="test", failure_threshold=1)

    _client(lambda _: httpx.Response(404), breaker).get_assignment(ASIG)

    assert breaker.state == CircuitState.CLOSED

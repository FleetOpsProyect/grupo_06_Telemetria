"""Cliente HTTP hacia el MS de Asignaciones protegido con timeout y Circuit Breaker (HU-01)."""

from typing import Any

import httpx

from app.core.circuit_breaker import CircuitBreaker
from app.core.config import settings
from app.core.exceptions import CircuitBreakerOpenError, ExternalDependencyError
from app.core.logging import correlation_id_ctx, logger
from app.domain.ports.external_services import AssignmentSnapshot, IAssignmentsClient

DEPENDENCY_UNAVAILABLE_MESSAGE = "No fue posible validar la asignación, intente nuevamente"

# Tolerant Reader: nombres aceptados para cada campo mientras se cierra el contrato con G2.
_STATE_KEYS = ("estado", "state", "status")
_VEHICLE_KEYS = ("vehiculo_id", "vehicle_id")
_DRIVER_KEYS = ("conductor_id", "driver_id")

# Instancia compartida entre peticiones: el conteo de fallos debe sobrevivir a cada request.
assignments_breaker = CircuitBreaker(
    name="asignaciones",
    failure_threshold=settings.circuit_breaker_failure_threshold,
    recovery_timeout_seconds=settings.circuit_breaker_recovery_timeout_seconds,
)


class _UpstreamServerError(Exception):
    """Asignaciones respondió 5xx; cuenta como fallo para el Circuit Breaker."""


def _first_value(body: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = body.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


class HttpAssignmentsClient(IAssignmentsClient):
    """Adaptador httpx que implementa el puerto IAssignmentsClient."""

    def __init__(
        self,
        base_url: str | None = None,
        path_template: str | None = None,
        timeout_seconds: float | None = None,
        breaker: CircuitBreaker | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url or settings.assignments_base_url
        self._path_template = path_template or settings.assignments_get_path
        self._timeout = (
            timeout_seconds if timeout_seconds is not None else settings.assignments_timeout_seconds
        )
        self._breaker = breaker or assignments_breaker
        self._transport = transport

    def get_assignment(self, asignacion_id: str) -> AssignmentSnapshot | None:
        try:
            response = self._breaker.execute(self._fetch, asignacion_id)
        except CircuitBreakerOpenError as e:
            logger.warning(f"Circuito abierto hacia Asignaciones; asignacion_id={asignacion_id}")
            raise CircuitBreakerOpenError(message=DEPENDENCY_UNAVAILABLE_MESSAGE) from e
        except (httpx.HTTPError, _UpstreamServerError) as e:
            logger.error(f"Asignaciones no disponible ({type(e).__name__}): {e}")
            raise ExternalDependencyError(message=DEPENDENCY_UNAVAILABLE_MESSAGE) from e

        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        if response.status_code != httpx.codes.OK:
            logger.error(f"Respuesta inesperada de Asignaciones: HTTP {response.status_code}")
            raise ExternalDependencyError(message=DEPENDENCY_UNAVAILABLE_MESSAGE)

        return self._parse(asignacion_id, response)

    def _fetch(self, asignacion_id: str) -> httpx.Response:
        path = self._path_template.format(asignacion_id=asignacion_id)
        headers = {"X-Correlation-Id": correlation_id_ctx.get()}
        with httpx.Client(
            base_url=self._base_url, timeout=self._timeout, transport=self._transport
        ) as client:
            response = client.get(path, headers=headers)
        if response.status_code >= httpx.codes.INTERNAL_SERVER_ERROR:
            raise _UpstreamServerError(f"HTTP {response.status_code}")
        return response

    @staticmethod
    def _parse(asignacion_id: str, response: httpx.Response) -> AssignmentSnapshot:
        try:
            body = response.json()
        except ValueError as e:
            logger.error("Asignaciones devolvió un cuerpo que no es JSON")
            raise ExternalDependencyError(message=DEPENDENCY_UNAVAILABLE_MESSAGE) from e

        if isinstance(body, dict) and isinstance(body.get("data"), dict):
            body = body["data"]
        if not isinstance(body, dict):
            raise ExternalDependencyError(message=DEPENDENCY_UNAVAILABLE_MESSAGE)

        estado = _first_value(body, _STATE_KEYS)
        vehiculo_id = _first_value(body, _VEHICLE_KEYS)
        conductor_id = _first_value(body, _DRIVER_KEYS)
        if not (estado and vehiculo_id and conductor_id):
            logger.error(
                f"Respuesta de Asignaciones sin estado/vehiculo_id/conductor_id: {sorted(body)}"
            )
            raise ExternalDependencyError(message=DEPENDENCY_UNAVAILABLE_MESSAGE)

        return AssignmentSnapshot(
            asignacion_id=asignacion_id,
            estado=estado,
            vehiculo_id=vehiculo_id,
            conductor_id=conductor_id,
        )

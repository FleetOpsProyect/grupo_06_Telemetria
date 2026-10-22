"""Tests unitarios para la máquina de estados del patrón Circuit Breaker."""

import time

import pytest

from app.core.circuit_breaker import CircuitBreaker, CircuitState
from app.core.exceptions import CircuitBreakerOpenError


class TestCircuitBreaker:
    """Verificación de la máquina de estados del Circuit Breaker."""

    def test_initial_state_is_closed(self) -> None:
        cb = CircuitBreaker(name="test_cb", failure_threshold=3, recovery_timeout_seconds=0.5)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_allowed() is True

    def test_circuit_opens_after_reaching_threshold(self) -> None:
        cb = CircuitBreaker(name="test_cb", failure_threshold=3, recovery_timeout_seconds=0.5)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_allowed() is False

    def test_execute_raises_when_circuit_is_open(self) -> None:
        cb = CircuitBreaker(name="test_cb", failure_threshold=2, recovery_timeout_seconds=1.0)
        cb.record_failure()
        cb.record_failure()

        with pytest.raises(CircuitBreakerOpenError):
            cb.execute(lambda: "resultado")

    def test_circuit_transitions_to_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker(name="test_cb", failure_threshold=1, recovery_timeout_seconds=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.is_allowed() is True

    def test_success_resets_circuit_to_closed(self) -> None:
        cb = CircuitBreaker(name="test_cb", failure_threshold=1, recovery_timeout_seconds=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._consecutive_failures == 0

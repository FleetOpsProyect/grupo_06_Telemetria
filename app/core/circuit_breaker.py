"""Implementación del patrón Circuit Breaker para protección de llamadas salientes."""

import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

from app.core.exceptions import CircuitBreakerOpenError
from app.core.logging import logger

T = TypeVar("T")


class CircuitState(str, Enum):
    """Estados posibles del Circuit Breaker."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Máquina de estados para el patrón Circuit Breaker.

    - CLOSED: Operación normal. Cuenta fallos consecutivos.
    - OPEN: Tras N fallos consecutivos, rechaza peticiones de inmediato durante recovery_timeout.
    - HALF_OPEN: Transcurrido el timeout, permite una petición de prueba.
    """

    def __init__(
        self,
        name: str = "default_breaker",
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Determina el estado actual considerando si expiró la ventana de apertura."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                now = time.monotonic()
                if now - self._last_failure_time >= self.recovery_timeout_seconds:
                    logger.info(
                        f"CircuitBreaker [{self.name}] pasa a HALF_OPEN tras "
                        f"{self.recovery_timeout_seconds}s de recuperación."
                    )
                    self._state = CircuitState.HALF_OPEN
            return self._state

    def is_allowed(self) -> bool:
        """Verifica si se permite despachar una llamada hacia la dependencia."""
        current_state = self.state
        if current_state == CircuitState.OPEN:
            return False
        return True

    def record_success(self) -> None:
        """Registra una llamada exitosa restableciendo el circuito a CLOSED."""
        with self._lock:
            if self._state != CircuitState.CLOSED:
                logger.info(f"CircuitBreaker [{self.name}] restablecido a CLOSED con éxito.")
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0

    def record_failure(self) -> None:
        """Registra un fallo. Si alcanza el umbral, abre el circuito."""
        with self._lock:
            self._consecutive_failures += 1
            self._last_failure_time = time.monotonic()
            if self._consecutive_failures >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    logger.warning(
                        f"CircuitBreaker [{self.name}] ABIERTO tras "
                        f"{self._consecutive_failures} fallos. "
                        f"Rechazará llamadas por {self.recovery_timeout_seconds}s."
                    )
                self._state = CircuitState.OPEN

    def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Ejecuta una función protegiéndola con el circuito."""
        if not self.is_allowed():
            raise CircuitBreakerOpenError(
                message=f"Circuito abierto [{self.name}], dependencia temporalmente inaccesible"
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

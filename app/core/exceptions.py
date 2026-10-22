"""Jerarquía de excepciones de dominio y aplicación para el microservicio."""

from typing import Any


class AppError(Exception):
    """Excepción base del sistema con código de error estandarizado."""

    def __init__(
        self,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []


AppException = AppError


class EntityNotFoundError(AppError):
    """Recurso o entidad no encontrada en la base de datos o servicio externo (HTTP 404)."""

    def __init__(self, message: str, code: str = "RUTA_NO_ENCONTRADA") -> None:
        super().__init__(code=code, message=message)


class DuplicateEntityError(AppError):
    """Entidad duplicada que viola la regla de unicidad (HTTP 409)."""

    def __init__(self, message: str, code: str = "RUTA_DUPLICADA") -> None:
        super().__init__(code=code, message=message)


class InvalidStateTransitionError(AppError):
    """Transición de estado no permitida según las reglas de negocio (HTTP 409)."""

    def __init__(self, message: str, code: str = "ESTADO_RUTA_INVALIDO") -> None:
        super().__init__(code=code, message=message)


class ExternalDependencyError(AppError):
    """Fallo de comunicación, timeout o degradación con un servicio externo (HTTP 503)."""

    def __init__(
        self,
        message: str = "Servicio externo temporalmente no disponible",
        code: str = "DEPENDENCIA_NO_DISPONIBLE",
    ) -> None:
        super().__init__(code=code, message=message)


class CircuitBreakerOpenError(ExternalDependencyError):
    """Rechazo temprano porque el Circuit Breaker se encuentra ABIERTO (HTTP 503)."""

    def __init__(
        self,
        message: str = "Dependencia temporalmente inaccesible por circuito abierto",
    ) -> None:
        super().__init__(code="DEPENDENCIA_NO_DISPONIBLE", message=message)


class DatabaseUnavailableError(AppError):
    """Fallo de persistencia en la base de datos local (HTTP 503)."""

    def __init__(
        self,
        message: str = "Servicio de persistencia no disponible",
        code: str = "SERVICIO_NO_DISPONIBLE",
    ) -> None:
        super().__init__(code=code, message=message)


class ValidationError(AppError):
    """Error de validación de datos de entrada en el cuerpo o query params (HTTP 400)."""

    def __init__(
        self,
        message: str = "Parámetros de consulta o cuerpo inválidos",
        code: str = "DATOS_INVALIDOS",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, details=details)


ValidationException = ValidationError

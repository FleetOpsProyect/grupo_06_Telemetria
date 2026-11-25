"""Manejador global de excepciones para estandarizar las respuestas JSON de error."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AppError,
    CircuitBreakerOpenError,
    DatabaseUnavailableError,
    DuplicateEntityError,
    EntityNotFoundError,
    ExternalDependencyError,
    InvalidStateTransitionError,
    ValidationError,
)
from app.core.logging import logger

_REQUIRED_FIELDS_ERROR_TYPES = frozenset({"missing", "string_too_short"})


def _is_required_field_error(err: Any) -> bool:
    """Indica si el error de validacion corresponde a un campo requerido faltante o vacío."""
    return isinstance(err, dict) and err.get("type") in _REQUIRED_FIELDS_ERROR_TYPES


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los manejadores de excepciones en la aplicación FastAPI."""

    @app.exception_handler(AppError)
    async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        if isinstance(exc, EntityNotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, (DuplicateEntityError, InvalidStateTransitionError)):
            status_code = status.HTTP_409_CONFLICT
        elif isinstance(exc, ValidationError):
            status_code = status.HTTP_400_BAD_REQUEST
        elif isinstance(
            exc, (ExternalDependencyError, CircuitBreakerOpenError, DatabaseUnavailableError)
        ):
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return JSONResponse(
            status_code=status_code,
            content={
                "codigo": exc.code,
                "mensaje": exc.message,
                "errores": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errores = []
        is_json_invalid = False

        for err in exc.errors():
            loc = err.get("loc", ())
            campo = str(loc[-1]) if loc else "cuerpo"
            msg = err.get("msg", "Dato inválido")
            err_type = err.get("type", "")

            if "json" in err_type:
                is_json_invalid = True

            errores.append({"campo": campo, "detalle": msg})

        codigo = "JSON_INVALIDO" if is_json_invalid else "DATOS_INVALIDOS"
        required_field_error = len(exc.errors()) == 1 and _is_required_field_error(exc.errors()[0])

        if is_json_invalid:
            mensaje = "El cuerpo de la solicitud no es un JSON válido"
        elif required_field_error:
            loc = exc.errors()[0].get("loc", ())
            campo = str(loc[-1]) if loc else "requerido"
            mensaje = f"El campo {campo} es obligatorio"
        else:
            mensaje = "Los datos de la solicitud no cumplen con las validaciones"

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "codigo": codigo,
                "mensaje": mensaje,
                "errores": errores,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Error no controlado en la aplicación: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "codigo": "SERVICIO_NO_DISPONIBLE",
                "mensaje": "Error interno del servidor, intente nuevamente",
                "errores": [],
            },
        )

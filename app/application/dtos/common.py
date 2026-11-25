"""DTOs transversales para paginación, filtros comunes y respuestas de error."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Detalle de fallo en un campo de entrada."""

    campo: str
    detalle: str


class ErrorResponse(BaseModel):
    """Esquema estándar para todas las respuestas de error JSON de la API."""

    codigo: str
    mensaje: str
    errores: list[ErrorDetail] = Field(default_factory=list)


class PaginationParams(BaseModel):
    """Parámetros de paginación para consultas de listados."""

    page: int = Field(default=0, ge=0, description="Índice de página base 0")
    size: int = Field(default=20, ge=1, le=100, description="Tamaño de página entre 1 y 100")


class PaginatedResponse(BaseModel, Generic[T]):
    """Envoltura estándar para respuestas paginadas de la API."""

    contenido: list[T]
    page: int
    size: int
    total: int

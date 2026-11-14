"""DTOS de entrada para iniciar una ruta (HU-01, POST /rutas/iniciar)."""

from pydantic import BaseModel, ConfigDict, Field


class RouteStartDTO(BaseModel):
    """
    Orden de inicicio enviada por el conductor

    Solo viaja asignacion_id: el origen, la hora y los ids de vehiculo/conductor los determina
    el servidor, asi el cliente no puede alterarlos.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    asignacion_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Identificador de la asignación que se va a iniciar",
        examples=["f47ac10b-58cc-4372-a567-0e02b2c3d479"],
    )

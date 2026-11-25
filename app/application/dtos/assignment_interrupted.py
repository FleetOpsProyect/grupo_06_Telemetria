"""Contrato de entrada de AsignacionInterrumpidaEvent (HU-04)."""

from typing import Annotated, Literal

from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AssignmentInterruptedDataDTO(BaseModel):
    """Datos que usa Telemetría; ignora los campos de otros servicios."""

    model_config = ConfigDict(extra="ignore", strict=True)

    asignacion_id: Annotated[NonBlankText, Field(max_length=64)]


class AssignmentEventDTO(BaseModel):
    """Campos comunes del sobre, independientes del transporte."""

    model_config = ConfigDict(extra="ignore", strict=True)

    evento_id: UUID4
    version: NonBlankText
    fecha_evento: AwareDatetime
    origen: NonBlankText


class AssignmentInterruptedEventDTO(AssignmentEventDTO):
    """Valida el evento que inicia el cierre de una ruta."""

    tipo_evento: Literal["AsignacionInterrumpidaEvent"]
    datos: AssignmentInterruptedDataDTO

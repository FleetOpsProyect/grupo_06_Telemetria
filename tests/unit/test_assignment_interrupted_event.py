"""Contrato de entrada de AsignacionInterrumpidaEvent (HU-04)."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.application.dtos.assignment_interrupted import AssignmentInterruptedEventDTO


@pytest.fixture
def envelope() -> dict[str, Any]:
    return {
        "evento_id": "4edb78c6-dd82-45dc-b187-00a89abf519a",
        "tipo_evento": "AsignacionInterrumpidaEvent",
        "version": "1.0",
        "fecha_evento": "2026-10-05T09:15:00Z",
        "origen": "asignaciones",
        "datos": {
            "asignacion_id": "asig-8472",
            "incidente_id": "inc-302",
            "reasignacion_resultado": {"estado": "PENDIENTE"},
        },
        "correlacion_id": "extra",
    }


def test_accepts_event_and_ignores_extra_fields(envelope: dict[str, Any]) -> None:
    event = AssignmentInterruptedEventDTO.model_validate_json(json.dumps(envelope))

    assert str(event.evento_id) == envelope["evento_id"]
    assert event.datos.model_dump() == {"asignacion_id": "asig-8472"}
    assert "correlacion_id" not in event.model_dump()


@pytest.mark.parametrize(
    "field", ["evento_id", "tipo_evento", "version", "fecha_evento", "origen", "datos"]
)
def test_requires_every_envelope_field(envelope: dict[str, Any], field: str) -> None:
    del envelope[field]

    with pytest.raises(ValidationError) as exc:
        AssignmentInterruptedEventDTO.model_validate_json(json.dumps(envelope))

    assert exc.value.errors()[0]["loc"] == (field,)


def test_reports_missing_assignment_id(envelope: dict[str, Any]) -> None:
    del envelope["datos"]["asignacion_id"]

    with pytest.raises(ValidationError) as exc:
        AssignmentInterruptedEventDTO.model_validate_json(json.dumps(envelope))

    assert exc.value.errors()[0]["loc"] == ("datos", "asignacion_id")


@pytest.mark.parametrize("assignment_id", [None, 123, "", "   "])
def test_rejects_invalid_assignment_id(envelope: dict[str, Any], assignment_id: object) -> None:
    envelope["datos"]["asignacion_id"] = assignment_id

    with pytest.raises(ValidationError) as exc:
        AssignmentInterruptedEventDTO.model_validate_json(json.dumps(envelope))

    assert exc.value.errors()[0]["loc"] == ("datos", "asignacion_id")


def test_rejects_unrelated_event_on_interruption_contract(envelope: dict[str, Any]) -> None:
    envelope["tipo_evento"] = "RutaIniciadaEvent"

    with pytest.raises(ValidationError) as exc:
        AssignmentInterruptedEventDTO.model_validate_json(json.dumps(envelope))

    assert exc.value.errors()[0]["loc"] == ("tipo_evento",)


def test_rejects_invalid_json() -> None:
    with pytest.raises(ValidationError) as exc:
        AssignmentInterruptedEventDTO.model_validate_json(b'{"evento_id":')

    assert exc.value.errors()[0]["type"] == "json_invalid"

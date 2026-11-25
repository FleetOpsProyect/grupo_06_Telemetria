"""Tests de validación y mapeo de los DTOs de rutas (HU-01, criterios 1, 5 y 9)."""

import pytest
from pydantic import ValidationError

from app.application.dtos.route import RouteResponseDTO
from app.application.dtos.route_start import RouteStartDTO
from app.domain.models.route import Route


def test_quita_espacios_alrededor_del_id() -> None:
    assert RouteStartDTO(asignacion_id="  asig-1  ").asignacion_id == "asig-1"


@pytest.mark.parametrize("valor", ["", "   ", "x" * 65])
def test_rechaza_id_vacio_o_demasiado_largo(valor: str) -> None:
    with pytest.raises(ValidationError):
        RouteStartDTO(asignacion_id=valor)


def test_rechaza_cuerpo_sin_asignacion_id() -> None:
    with pytest.raises(ValidationError):
        RouteStartDTO.model_validate({})


def test_rechaza_id_que_no_es_texto() -> None:
    with pytest.raises(ValidationError):
        RouteStartDTO.model_validate({"asignacion_id": 123})


def test_ignora_coordenadas_enviadas_por_el_cliente() -> None:
    dto = RouteStartDTO.model_validate({"asignacion_id": "a1", "origen_latitud": 0})

    assert dto.model_dump() == {"asignacion_id": "a1"}


def test_from_domain_incluye_estado_hora_y_origen() -> None:
    route = Route.start_new(id="r1", asignacion_id="a1", vehiculo_id="v1", conductor_id="c1")

    dto = RouteResponseDTO.from_domain(route)

    assert dto.estado == "EN_CURSO"
    assert dto.hora_inicio == route.hora_inicio.isoformat()
    assert dto.coordenada_origen.latitud == 3.4516
    assert dto.coordenada_origen.longitud == -76.5320

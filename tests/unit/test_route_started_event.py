"""Tests del contenido de RutaIniciadaEvent (HU-01, criterio 6)"""

import json
from dataclasses import asdict

from app.domain.models.events import (
    ROUTE_STARTED_EVENT,
    ROUTE_STARTED_ROUTING_KEY,
    EventEnvelope,
    route_started_data,
)
from app.domain.models.route import Coordinate, Route


def _route() -> Route:
    """Crea una instancia de Route para pruebas."""
    return Route(
        id="r1",
        asignacion_id="a1",
        vehiculo_id="v1",
        conductor_id="c1",
        origen=Coordinate(latitud=3.4516, longitud=-76.5320),
    )


def test_datos_contienen_ids_estado_y_origen() -> None:
    route = _route()

    datos = route_started_data(route)

    assert datos["ruta_id"] == "r1"
    assert datos["asignacion_id"] == "a1"
    assert datos["vehiculo_id"] == "v1"
    assert datos["conductor_id"] == "c1"
    assert datos["estado"] == "EN_CURSO"
    assert datos["hora_inicio"] == route.hora_inicio.isoformat()
    assert datos["coordenada_origen"] == {"latitud": 3.4516, "longitud": -76.5320}


def test_sobre_estandar_se_puede_serializar_a_json() -> None:
    envelope = EventEnvelope.create(
        tipo_evento=ROUTE_STARTED_EVENT, datos=route_started_data(_route())
    )

    payload_json = json.dumps(asdict(envelope))

    payload = json.loads(payload_json)

    assert payload["tipo_evento"] == "RutaIniciadaEvent"
    assert payload["origen"] == "telemetria"
    assert payload["version"] == "1.0"
    assert payload["evento_id"]
    assert payload["datos"]["ruta_id"] == "r1"
    assert ROUTE_STARTED_ROUTING_KEY == "telemetria.ruta.iniciada"

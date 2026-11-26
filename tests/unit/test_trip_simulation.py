"""Tests de la simulación geoespacial de la HU-03 (Haversine y destino simulado)."""

import random
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.models.route import CENTRO_OPERACIONES, Coordinate
from app.domain.models.trip_simulation import (
    MIN_DISTANCE_KM,
    haversine_km,
    random_destination,
    trip_distance_km,
)

INICIO = datetime(2026, 10, 29, 8, tzinfo=UTC)


def test_haversine_un_decimo_de_grado_de_latitud_son_11_12_km() -> None:
    destino = Coordinate(latitud=CENTRO_OPERACIONES.latitud + 0.1, longitud=-76.5320)
    assert haversine_km(CENTRO_OPERACIONES, destino) == pytest.approx(11.12, abs=0.01)


def test_haversine_mismo_punto_es_cero() -> None:
    assert haversine_km(CENTRO_OPERACIONES, CENTRO_OPERACIONES) == 0


@pytest.mark.parametrize("seed", range(50))
def test_destino_simulado_queda_entre_5_y_25_km(seed: int) -> None:
    destino = random_destination(CENTRO_OPERACIONES, random.Random(seed))
    assert 5.0 - 0.01 <= haversine_km(CENTRO_OPERACIONES, destino) <= 25.0 + 0.01


def test_viaje_de_menos_de_un_minuto_asigna_distancia_minima() -> None:
    destino = Coordinate(latitud=3.6, longitud=-76.5)
    fin = INICIO + timedelta(seconds=59)
    assert trip_distance_km(CENTRO_OPERACIONES, destino, INICIO, fin) == MIN_DISTANCE_KM


def test_viaje_de_un_minuto_o_mas_usa_haversine_redondeado_a_2_decimales() -> None:
    destino = Coordinate(latitud=3.4372, longitud=-76.5225)
    distancia = trip_distance_km(CENTRO_OPERACIONES, destino, INICIO, INICIO + timedelta(hours=2))
    assert distancia == round(haversine_km(CENTRO_OPERACIONES, destino), 2)
    assert distancia == pytest.approx(1.92, abs=0.01)

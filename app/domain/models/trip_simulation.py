"""Simulación geoespacial del cierre de ruta (HU-03): destino simulado y Haversine."""

import random
from datetime import datetime
from math import asin, atan2, cos, degrees, radians, sin

from app.domain.models.route import Coordinate
from app.domain.models.travel_plan import EARTH_RADIUS_KM
from app.domain.models.travel_plan import Coordinate as GeoPoint

MIN_SIMULATED_KM = 5.0
MAX_SIMULATED_KM = 25.0
MIN_DURATION_SECONDS = 60
MIN_DISTANCE_KM = 0.50


def haversine_km(origen: Coordinate, destino: Coordinate) -> float:
    """Distancia sobre la superficie terrestre (Haversine, R = 6371.0 km)."""
    a = GeoPoint(origen.latitud, origen.longitud)
    b = GeoPoint(destino.latitud, destino.longitud)
    return a.angular_distance_to(b) * EARTH_RADIUS_KM


def random_destination(origen: Coordinate, rng: random.Random) -> Coordinate:
    """
    Simula el destino sin GPS: un punto a una distancia aleatoria de 5 a 25 km del origen,
    en una dirección aleatoria (equivale a sumar un delta en latitud y longitud).
    """
    distance_km = rng.uniform(MIN_SIMULATED_KM, MAX_SIMULATED_KM)
    bearing = rng.uniform(0.0, 2.0 * 3.141592653589793)
    angle = distance_km / EARTH_RADIUS_KM
    lat1, lon1 = radians(origen.latitud), radians(origen.longitud)
    lat2 = asin(sin(lat1) * cos(angle) + cos(lat1) * sin(angle) * cos(bearing))
    lon2 = lon1 + atan2(sin(bearing) * sin(angle) * cos(lat1), cos(angle) - sin(lat1) * sin(lat2))
    return Coordinate(
        latitud=round(degrees(lat2), 6),
        longitud=round((degrees(lon2) + 180) % 360 - 180, 6),
    )


def trip_distance_km(
    origen: Coordinate, destino: Coordinate, hora_inicio: datetime, hora_fin: datetime
) -> float:
    """Distancia final redondeada a 2 decimales; 0.50 km si el viaje duró menos de 1 minuto."""
    if (hora_fin - hora_inicio).total_seconds() < MIN_DURATION_SECONDS:
        return MIN_DISTANCE_KM
    return round(haversine_km(origen, destino), 2)

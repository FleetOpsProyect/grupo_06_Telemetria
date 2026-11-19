"""Estimación geodésica de avance con los datos del plan de viaje."""

from dataclasses import dataclass
from math import asin, atan2, cos, degrees, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float

    def radians(self) -> tuple[float, float]:
        return radians(self.latitude), radians(self.longitude)

    def angular_distance_to(self, other: "Coordinate") -> float:
        lat1, lon1 = self.radians()
        lat2, lon2 = other.radians()
        a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
        return 2 * asin(sqrt(max(0.0, min(a, 1.0))))


@dataclass(frozen=True)
class TravelPlan:
    origin: Coordinate
    destination: Coordinate
    duration_seconds: int

    def position_at(self, elapsed_seconds: float) -> Coordinate:
        fraction = max(0.0, min(elapsed_seconds / self.duration_seconds, 1.0))
        if fraction == 0:
            return self.origin
        if fraction == 1:
            return self.destination

        lat1, lon1 = self.origin.radians()
        lat2, lon2 = self.destination.radians()
        delta_lon = lon2 - lon1
        bearing = atan2(
            sin(delta_lon) * cos(lat2),
            cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(delta_lon),
        )
        angle = self.origin.angular_distance_to(self.destination) * fraction
        sin_lat = sin(lat1) * cos(angle) + cos(lat1) * sin(angle) * cos(bearing)
        lat = asin(max(-1.0, min(sin_lat, 1.0)))
        lon = lon1 + atan2(sin(bearing) * sin(angle) * cos(lat1), cos(angle) - sin(lat1) * sin(lat))
        return Coordinate(degrees(lat), (degrees(lon) + 180) % 360 - 180)

    def distance_at(self, elapsed_seconds: float) -> float:
        return self.origin.angular_distance_to(self.position_at(elapsed_seconds)) * EARTH_RADIUS_KM

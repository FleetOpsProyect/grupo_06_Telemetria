"""DTOs consulta paginada y detalle histórico de rutas (GET /route)."""

from pydantic import BaseModel

from app.application.dtos.route import CoordinateDTO
from app.domain.models.route import Route


class RouteSummaryDTO(BaseModel):
    """Vista resumida de una ruta para cada elemento de `contenido` en GET /route."""

    id: str
    asignacion_id: str
    vehiculo_id: str
    distancia_recorrida_km: float | None
    hora_inicio: str
    hora_fin: str | None
    estado: str

    @classmethod
    def from_domain(cls, route: Route) -> "RouteSummaryDTO":
        """Mapea la entidad de dominio Route al resumen del listado paginado."""
        return cls(
            id=route.id,
            asignacion_id=route.asignacion_id,
            vehiculo_id=route.vehiculo_id,
            distancia_recorrida_km=route.distancia_recorrida_km,
            hora_inicio=route.hora_inicio.isoformat(),
            hora_fin=route.hora_fin.isoformat() if route.hora_fin else None,
            estado=route.estado.value,
        )


class RouteDetailDTO(RouteSummaryDTO):
    """Vista completa de una ruta para GET /route/{id}, incluyendo coordenadas."""

    conductor_id: str
    coordenada_origen: CoordinateDTO
    coordenada_destino: CoordinateDTO | None

    @classmethod
    def from_domain(cls, route: Route) -> "RouteDetailDTO":
        """Mapea la entidad de dominio Route al detalle completo con origen y destino."""
        return cls(
            id=route.id,
            asignacion_id=route.asignacion_id,
            vehiculo_id=route.vehiculo_id,
            conductor_id=route.conductor_id,
            distancia_recorrida_km=route.distancia_recorrida_km,
            hora_inicio=route.hora_inicio.isoformat(),
            hora_fin=route.hora_fin.isoformat() if route.hora_fin else None,
            estado=route.estado.value,
            coordenada_origen=CoordinateDTO(
                latitud=route.origen.latitud,
                longitud=route.origen.longitud,
            ),
            coordenada_destino=(
                CoordinateDTO(
                    latitud=route.destino.latitud,
                    longitud=route.destino.longitud,
                )
                if route.destino
                else None
            ),
        )

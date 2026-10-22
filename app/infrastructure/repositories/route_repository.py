"""Implementación concreta del repositorio de rutas mediante SQLAlchemy."""

from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseUnavailableError
from app.domain.models.route import Route, RouteStatus
from app.domain.ports.repositories import IRouteRepository
from app.infrastructure.db.orm_models import RouteModel


class SqlAlchemyRouteRepository(IRouteRepository):
    """Adaptador de persistencia relacional para el agregado Route."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _to_domain(self, model: RouteModel) -> Route:
        """Mapea un modelo ORM a la entidad pura de dominio."""
        return Route(
            id=model.id,
            asignacion_id=model.asignacion_id,
            vehiculo_id=model.vehiculo_id,
            conductor_id=model.conductor_id,
            estado=RouteStatus(model.estado),
            hora_inicio=model.hora_inicio,
            hora_fin=model.hora_fin,
        )

    def save(self, route: Route) -> Route:
        """Inserta o actualiza una ruta en la base de datos dentro de la transacción activa."""
        try:
            model = self.session.get(RouteModel, route.id)
            if not model:
                model = RouteModel(
                    id=route.id,
                    asignacion_id=route.asignacion_id,
                    vehiculo_id=route.vehiculo_id,
                    conductor_id=route.conductor_id,
                    estado=route.estado.value,
                    hora_inicio=route.hora_inicio,
                    hora_fin=route.hora_fin,
                )
                self.session.add(model)
            else:
                model.estado = route.estado.value
                model.hora_fin = route.hora_fin

            self.session.commit()
            self.session.refresh(model)
            return self._to_domain(model)
        except Exception as e:
            self.session.rollback()
            raise DatabaseUnavailableError(f"Error al persistir ruta: {e}") from e

    def get_by_id(self, route_id: str) -> Route | None:
        """Busca una ruta por su clave primaria."""
        try:
            model = self.session.get(RouteModel, route_id)
            return self._to_domain(model) if model else None
        except Exception as e:
            raise DatabaseUnavailableError(f"Fallo al consultar ruta por id: {e}") from e

    def get_by_asignacion_id(self, asignacion_id: str) -> Route | None:
        """Busca una ruta por asignación (índice único)."""
        try:
            stmt = select(RouteModel).where(RouteModel.asignacion_id == asignacion_id)
            model = self.session.execute(stmt).scalar_one_or_none()
            return self._to_domain(model) if model else None
        except Exception as e:
            raise DatabaseUnavailableError(f"Fallo al consultar ruta por asignacion: {e}") from e

    def get_active_route_by_asignacion(self, asignacion_id: str) -> Route | None:
        """Busca ruta activa EN_CURSO optimizada por índice compuesto."""
        try:
            stmt = select(RouteModel).where(
                RouteModel.asignacion_id == asignacion_id,
                RouteModel.estado == RouteStatus.EN_CURSO.value,
            )
            model = self.session.execute(stmt).scalar_one_or_none()
            return self._to_domain(model) if model else None
        except Exception as e:
            raise DatabaseUnavailableError(f"Fallo al consultar ruta activa: {e}") from e

    def list_routes(
        self,
        asignacion_id: str | None = None,
        vehiculo_id: str | None = None,
        estado: RouteStatus | None = None,
        fecha_desde: str | None = None,
        fecha_hasta: str | None = None,
        page: int = 0,
        size: int = 20,
    ) -> tuple[list[Route], int]:
        """Consulta paginada ordenada descendente por hora_inicio."""
        try:
            stmt = select(RouteModel)

            if asignacion_id:
                stmt = stmt.where(RouteModel.asignacion_id == asignacion_id)
            if vehiculo_id:
                stmt = stmt.where(RouteModel.vehiculo_id == vehiculo_id)
            if estado:
                stmt = stmt.where(RouteModel.estado == estado.value)
            if fecha_desde:
                dt_desde = datetime.strptime(fecha_desde, "%Y-%m-%d")
                stmt = stmt.where(RouteModel.hora_inicio >= dt_desde)
            if fecha_hasta:
                dt_hasta = datetime.strptime(f"{fecha_hasta} 23:59:59", "%Y-%m-%d %H:%M:%S")
                stmt = stmt.where(RouteModel.hora_inicio <= dt_hasta)

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = self.session.execute(count_stmt).scalar() or 0

            stmt = stmt.order_by(desc(RouteModel.hora_inicio)).offset(page * size).limit(size)
            models = self.session.execute(stmt).scalars().all()

            routes = [self._to_domain(m) for m in models]
            return routes, total
        except Exception as e:
            raise DatabaseUnavailableError(f"Fallo al listar rutas: {e}") from e

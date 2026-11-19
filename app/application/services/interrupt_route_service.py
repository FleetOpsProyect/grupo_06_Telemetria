"""Preparación del cierre de una ruta por interrupción de su asignación."""

from app.application.dtos.assignment_interrupted import AssignmentInterruptedEventDTO
from app.core.logging import logger
from app.domain.models.route import Route
from app.domain.ports.repositories import IProcessedEventRepository, IRouteRepository


class InterruptRouteService:
    """Descarta eventos ya atendidos y busca la ruta candidata al cierre."""

    def __init__(
        self,
        route_repo: IRouteRepository,
        processed_event_repo: IProcessedEventRepository,
    ) -> None:
        self.route_repo = route_repo
        self.processed_event_repo = processed_event_repo

    def find_route_to_interrupt(self, event: AssignmentInterruptedEventDTO) -> Route | None:
        """Devuelve la ruta activa sin cerrar ni registrar el evento todavía.

        Si no hay ruta activa, registra el evento como atendido y devuelve None,
        igual que para un duplicado. Un fallo de persistencia se propaga al llamador.
        """
        event_id = str(event.evento_id)
        if self.processed_event_repo.is_processed(event_id):
            return None

        assignment_id = event.datos.asignacion_id
        route = self.route_repo.get_active_route_by_asignacion(assignment_id)
        if route is None:
            self.processed_event_repo.mark_processed(event_id, event.tipo_evento)
            logger.info(
                "No había ruta activa por cerrar; asignacion_id=%s evento_id=%s",
                assignment_id,
                event_id,
            )
        return route

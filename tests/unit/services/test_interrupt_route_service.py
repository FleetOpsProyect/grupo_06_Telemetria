"""Primer corte HU-04: duplicados y asignaciones sin ruta activa."""

from unittest.mock import create_autospec

import pytest
from sqlalchemy.orm import Session

from app.application.dtos.assignment_interrupted import AssignmentInterruptedEventDTO
from app.application.services.interrupt_route_service import InterruptRouteService
from app.core.exceptions import DatabaseUnavailableError
from app.domain.models.route import Route, RouteStatus
from app.domain.ports.repositories import IProcessedEventRepository, IRouteRepository
from app.infrastructure.repositories.processed_event_repo import SqlAlchemyProcessedEventRepository
from app.infrastructure.repositories.route_repository import SqlAlchemyRouteRepository


@pytest.fixture
def event() -> AssignmentInterruptedEventDTO:
    return AssignmentInterruptedEventDTO.model_validate_json(
        b"""{
            "evento_id": "4edb78c6-dd82-45dc-b187-00a89abf519a",
            "tipo_evento": "AsignacionInterrumpidaEvent",
            "version": "1.0",
            "fecha_evento": "2026-10-05T09:15:00Z",
            "origen": "asignaciones",
            "datos": {"asignacion_id": "asig-8472"}
        }"""
    )


def test_duplicate_skips_route_lookup_and_writes(event: AssignmentInterruptedEventDTO) -> None:
    routes = create_autospec(IRouteRepository, instance=True, spec_set=True)
    processed = create_autospec(IProcessedEventRepository, instance=True, spec_set=True)
    processed.is_processed.return_value = True

    assert InterruptRouteService(routes, processed).find_route_to_interrupt(event) is None

    processed.is_processed.assert_called_once_with(str(event.evento_id))
    processed.mark_processed.assert_not_called()
    assert routes.mock_calls == []


@pytest.mark.parametrize("status", [None, RouteStatus.FINALIZADA, RouteStatus.INTERRUMPIDA])
def test_no_active_route_records_event_without_changing_history(
    event: AssignmentInterruptedEventDTO, db_session: Session, status: RouteStatus | None
) -> None:
    routes = SqlAlchemyRouteRepository(db_session)
    processed = SqlAlchemyProcessedEventRepository(db_session)
    if status is not None:
        routes.save(Route("ruta-1", event.datos.asignacion_id, "veh-1", "cond-1", estado=status))

    assert InterruptRouteService(routes, processed).find_route_to_interrupt(event) is None

    db_session.rollback()
    assert processed.is_processed(str(event.evento_id))
    history = routes.get_by_asignacion_id(event.datos.asignacion_id)
    if status is None:
        assert history is None
    else:
        assert history is not None
        assert history.id == "ruta-1"
        assert history.estado == status


def test_active_route_is_returned_without_marking_event_processed(
    event: AssignmentInterruptedEventDTO, db_session: Session
) -> None:
    routes = SqlAlchemyRouteRepository(db_session)
    processed = SqlAlchemyProcessedEventRepository(db_session)
    routes.save(Route("ruta-1", event.datos.asignacion_id, "veh-1", "cond-1"))

    route = InterruptRouteService(routes, processed).find_route_to_interrupt(event)

    assert route is not None
    assert route.id == "ruta-1"
    assert route.estado == RouteStatus.EN_CURSO
    assert not processed.is_processed(str(event.evento_id))


def test_route_lookup_failure_is_not_treated_as_no_active_route(
    event: AssignmentInterruptedEventDTO,
) -> None:
    routes = create_autospec(IRouteRepository, instance=True, spec_set=True)
    processed = create_autospec(IProcessedEventRepository, instance=True, spec_set=True)
    processed.is_processed.return_value = False
    routes.get_active_route_by_asignacion.side_effect = DatabaseUnavailableError()

    with pytest.raises(DatabaseUnavailableError):
        InterruptRouteService(routes, processed).find_route_to_interrupt(event)

    processed.mark_processed.assert_not_called()

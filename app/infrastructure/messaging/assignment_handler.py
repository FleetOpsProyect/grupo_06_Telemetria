"""Entrada para el cuerpo JSON de un mensaje local o de una cola SQS."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from pydantic import Field, TypeAdapter
from sqlalchemy.orm import Session

from app.application.dtos.assignment_interrupted import AssignmentInterruptedEventDTO
from app.application.dtos.travel_plan import TravelPlanEventDTO
from app.application.services.assignment_message_service import process_assignment_event
from app.infrastructure.repositories.assignment_message_store import (
    SqlAlchemyAssignmentMessageStore,
)

AssignmentMessage = Annotated[
    TravelPlanEventDTO | AssignmentInterruptedEventDTO, Field(discriminator="tipo_evento")
]
assignment_message_adapter: TypeAdapter[AssignmentMessage] = TypeAdapter(AssignmentMessage)


def handle_assignment_message(
    session_factory: Callable[[], Session],
    body: str | bytes,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> None:
    """Abre una sesión por entrega; un retorno normal garantiza el commit."""
    event = assignment_message_adapter.validate_json(body)
    with session_factory() as session, session.begin():
        process_assignment_event(event, SqlAlchemyAssignmentMessageStore(session), clock)

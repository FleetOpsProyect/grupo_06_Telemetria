"""Tests unitarios para el control de deduplicación e idempotencia."""

from sqlalchemy.orm import Session

from app.infrastructure.repositories.processed_event_repo import SqlAlchemyProcessedEventRepository


class TestIdempotentConsumer:
    """Verificación del control de idempotencia con processed_events."""

    def test_event_is_not_processed_initially(self, db_session: Session) -> None:
        repo = SqlAlchemyProcessedEventRepository(db_session)
        assert repo.is_processed("evt-test-101") is False

    def test_mark_processed_records_event(self, db_session: Session) -> None:
        repo = SqlAlchemyProcessedEventRepository(db_session)
        repo.mark_processed("evt-test-101", "TestEvent")
        assert repo.is_processed("evt-test-101") is True

    def test_duplicate_marking_does_not_fail(self, db_session: Session) -> None:
        repo = SqlAlchemyProcessedEventRepository(db_session)
        repo.mark_processed("evt-test-101", "TestEvent")
        repo.mark_processed("evt-test-101", "TestEvent")
        assert repo.is_processed("evt-test-101") is True

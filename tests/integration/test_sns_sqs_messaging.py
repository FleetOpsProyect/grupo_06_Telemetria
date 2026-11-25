"""Flujo SNS/SQS de Telemetría simulado con moto (no se llama a AWS real)."""

import json
from collections.abc import Generator
from typing import Any

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.domain.models.route import Route, RouteStatus
from app.infrastructure.messaging.connection import reset_messaging_health_cache
from app.infrastructure.messaging.consumers.sqs_consumer import (
    SqsAssignmentConsumer,
    unwrap_sns_envelope,
)
from app.infrastructure.messaging.publisher import (
    SnsEventPublisher,
    dispatch_pending_outbox_events,
)
from app.infrastructure.repositories.outbox_repository import SqlAlchemyOutboxRepository
from app.infrastructure.repositories.route_repository import SqlAlchemyRouteRepository
from tests.integration.test_assignment_message_flow import START, message, plan_message

REGION = "us-east-2"
ENTRADA = ["PlanViajeAsignacionEvent", "AsignacionInterrumpidaEvent"]


@pytest.fixture
def aws(monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, Any], None, None]:
    """Crea en moto el tópico, la cola de Telemetría con su DLQ y una cola 'Vehículos'."""
    for key, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": REGION,
    }.items():
        monkeypatch.setenv(key, value)

    with mock_aws():
        sns = boto3.client("sns", region_name=REGION)
        sqs = boto3.client("sqs", region_name=REGION)
        topic_arn = sns.create_topic(Name="fleetops-eventos")["TopicArn"]

        dlq_url = sqs.create_queue(QueueName="telemetria-eventos-dlq")["QueueUrl"]
        dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])[
            "Attributes"
        ]["QueueArn"]
        queue_url = sqs.create_queue(
            QueueName="telemetria-eventos",
            Attributes={
                "RedrivePolicy": json.dumps(
                    {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "5"}
                ),
            },
        )["QueueUrl"]
        vehiculos_url = sqs.create_queue(QueueName="vehiculos-eventos")["QueueUrl"]

        def subscribe(url: str, tipos: list[str]) -> None:
            arn = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["QueueArn"])["Attributes"][
                "QueueArn"
            ]
            sns.subscribe(
                TopicArn=topic_arn,
                Protocol="sqs",
                Endpoint=arn,
                Attributes={"FilterPolicy": json.dumps({"tipo_evento": tipos})},
            )

        subscribe(queue_url, ENTRADA)
        subscribe(vehiculos_url, ["RutaFinalizadaEvent"])

        monkeypatch.setattr(settings, "aws_region", REGION)
        monkeypatch.setattr(settings, "sns_topic_arn", topic_arn)
        monkeypatch.setattr(settings, "sqs_queue_url", queue_url)
        # Los hilos de fondo no se arrancan en pruebas; aquí se llaman a mano
        monkeypatch.setattr(settings, "messaging_workers_enabled", False)
        reset_messaging_health_cache()
        yield {
            "sns": sns,
            "sqs": sqs,
            "topic_arn": topic_arn,
            "queue_url": queue_url,
            "vehiculos_url": vehiculos_url,
        }
    reset_messaging_health_cache()


def publish_as_asignaciones(aws: dict[str, Any], body: bytes) -> None:
    """Simula al MS de Asignaciones publicando en el tópico con su atributo de filtro."""
    tipo = json.loads(body)["tipo_evento"]
    aws["sns"].publish(
        TopicArn=aws["topic_arn"],
        Message=body.decode(),
        MessageAttributes={"tipo_evento": {"DataType": "String", "StringValue": tipo}},
    )


def test_unwrap_sns_envelope_returns_inner_message() -> None:
    inner = '{"tipo_evento": "X"}'
    envelope = json.dumps({"Type": "Notification", "Message": inner})
    assert unwrap_sns_envelope(envelope) == inner
    assert unwrap_sns_envelope(inner) == inner
    assert unwrap_sns_envelope("no-json") == "no-json"


def test_flujo_completo_sqs_a_outbox_a_sns(aws: dict[str, Any], db_session: Session) -> None:
    factory = sessionmaker(bind=db_session.get_bind())
    consumer = SqsAssignmentConsumer(factory)

    publish_as_asignaciones(aws, plan_message())
    assert consumer.poll_once(wait_time_seconds=0) == 1

    with Session(bind=db_session.get_bind()) as seed:
        SqlAlchemyRouteRepository(seed).save(
            Route("ruta-1", "asig-8472", "veh-1", "cond-1", hora_inicio=START)
        )
    publish_as_asignaciones(aws, message("AsignacionInterrumpidaEvent", incidente_id="inc-1"))
    assert consumer.poll_once(wait_time_seconds=0) == 1

    route = SqlAlchemyRouteRepository(db_session).get_by_id("ruta-1")
    assert route is not None and route.estado == RouteStatus.INTERRUMPIDA

    # El worker del outbox publica RutaFinalizadaEvent en SNS
    sent = dispatch_pending_outbox_events(
        SqlAlchemyOutboxRepository(db_session), SnsEventPublisher()
    )
    assert sent == 1

    # Solo la cola suscrita a RutaFinalizadaEvent lo recibe (filtro por tipo_evento)
    received = aws["sqs"].receive_message(QueueUrl=aws["vehiculos_url"], WaitTimeSeconds=0)
    body = json.loads(unwrap_sns_envelope(received["Messages"][0]["Body"]))
    assert body["tipo_evento"] == "RutaFinalizadaEvent"
    own = aws["sqs"].receive_message(QueueUrl=aws["queue_url"], WaitTimeSeconds=0)
    assert "Messages" not in own


def test_mensaje_que_falla_no_se_borra(aws: dict[str, Any], db_session: Session) -> None:
    consumer = SqsAssignmentConsumer(sessionmaker(bind=db_session.get_bind()), client=aws["sqs"])
    # Interrupción con ruta activa y sin plan: error recuperable, debe quedar en la cola
    with Session(bind=db_session.get_bind()) as seed:
        SqlAlchemyRouteRepository(seed).save(
            Route("ruta-2", "asig-8472", "veh-1", "cond-1", hora_inicio=START)
        )
    publish_as_asignaciones(aws, message("AsignacionInterrumpidaEvent"))
    assert consumer.poll_once(wait_time_seconds=0) == 0

    attrs = aws["sqs"].get_queue_attributes(
        QueueUrl=aws["queue_url"],
        AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
    )["Attributes"]
    pending = int(attrs["ApproximateNumberOfMessages"]) + int(
        attrs["ApproximateNumberOfMessagesNotVisible"]
    )
    assert pending == 1


def test_publisher_sin_topico_deja_evento_pendiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sns_topic_arn", "")
    assert SnsEventPublisher().publish("telemetria.ruta.finalizada", "{}") is False


def test_health_reporta_broker_up_con_aws(aws: dict[str, Any], client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["broker"] == "UP"


def test_health_broker_disabled_fuera_de_produccion(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(settings, "sns_topic_arn", "")
    monkeypatch.setattr(settings, "environment", "development")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["broker"] == "DISABLED"


def test_health_falla_en_produccion_sin_mensajeria(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(settings, "sns_topic_arn", "")
    monkeypatch.setattr(settings, "environment", "production")
    response = client.get("/health")
    assert response.status_code == 503

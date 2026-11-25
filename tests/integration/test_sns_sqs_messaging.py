"""Flujo SNS/SQS de Telemetría simulado con moto (no se llama a AWS real)."""

import json
import time
from collections.abc import Generator
from typing import Any

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.domain.models.route import Route, RouteStatus
from app.infrastructure.messaging import workers as workers_module
from app.infrastructure.messaging.connection import reset_messaging_health_cache
from app.infrastructure.messaging.consumers.sqs_consumer import (
    SqsAssignmentConsumer,
    unwrap_sns_envelope,
)
from app.infrastructure.messaging.publisher import (
    SnsEventPublisher,
    dispatch_pending_outbox_events,
)
from app.infrastructure.messaging.workers import MessagingWorkers
from app.infrastructure.repositories.outbox_repository import SqlAlchemyOutboxRepository
from app.infrastructure.repositories.route_repository import SqlAlchemyRouteRepository
from app.main import app
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


def _wait_until(condition: Any, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def test_workers_consumen_cola_y_publican_outbox(aws: dict[str, Any], db_session: Session) -> None:
    """Un ciclo de cada worker, sin hilos: determinista también en CI."""
    factory = sessionmaker(bind=db_session.get_bind())
    workers = MessagingWorkers(factory)
    with Session(bind=db_session.get_bind()) as seed:
        SqlAlchemyRouteRepository(seed).save(
            Route("ruta-3", "asig-8472", "veh-1", "cond-1", hora_inicio=START)
        )

    publish_as_asignaciones(aws, plan_message())
    assert workers.consumer.poll_once(wait_time_seconds=0) == 1
    publish_as_asignaciones(aws, message("AsignacionInterrumpidaEvent"))
    assert workers.consumer.poll_once(wait_time_seconds=0) == 1

    assert workers.outbox_once() == 1
    assert workers.outbox_once() == 0

    received = aws["sqs"].receive_message(QueueUrl=aws["vehiculos_url"], WaitTimeSeconds=0)
    body = json.loads(unwrap_sns_envelope(received["Messages"][0]["Body"]))
    assert body["tipo_evento"] == "RutaFinalizadaEvent"


def test_hilos_de_workers_arrancan_se_recuperan_y_se_detienen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los ciclos siguen vivos aunque una vuelta falle, y stop() los detiene."""
    monkeypatch.setattr(settings, "outbox_dispatch_interval_seconds", 0.01)
    monkeypatch.setattr(workers_module, "CONSUMER_ERROR_BACKOFF_SECONDS", 0.01)
    calls = {"outbox": 0, "consumer": 0}

    class FakeWorkers(MessagingWorkers):
        def outbox_once(self) -> int:
            calls["outbox"] += 1
            if calls["outbox"] == 1:
                raise RuntimeError("fallo transitorio del outbox")
            return 0

        def consumer_once(self) -> int:
            calls["consumer"] += 1
            if calls["consumer"] == 1:
                raise RuntimeError("fallo transitorio de SQS")
            time.sleep(0.01)
            return 0

    workers = FakeWorkers(
        sessionmaker(),
        publisher=SnsEventPublisher(topic_arn="arn:aws:sns:us-east-2:1:t"),
        consumer=SqsAssignmentConsumer(sessionmaker(), queue_url="http://cola"),
    )
    workers.start()
    try:
        assert _wait_until(lambda: calls["outbox"] >= 3 and calls["consumer"] >= 3)
    finally:
        workers.stop(timeout=5)
    assert all(not thread.is_alive() for thread in workers._threads)


def test_lifespan_arranca_workers_si_hay_mensajeria(
    aws: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "messaging_workers_enabled", True)
    started: list[str] = []
    monkeypatch.setattr(MessagingWorkers, "start", lambda self: started.append("start"))
    monkeypatch.setattr(MessagingWorkers, "stop", lambda self, timeout=25.0: started.append("stop"))
    with TestClient(app):
        pass
    assert started == ["start", "stop"]


def test_publisher_devuelve_false_si_sns_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    class Roto:
        def publish(self, **_: Any) -> None:
            raise RuntimeError("sin red")

    publisher = SnsEventPublisher(topic_arn="arn:aws:sns:us-east-2:1:t", client=Roto())
    assert publisher.publish("telemetria.ruta.finalizada", "no-json") is False


def test_health_down_si_aws_no_responde(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setattr(settings, "aws_region", REGION)
    monkeypatch.setattr(settings, "sns_topic_arn", "arn:aws:sns:us-east-2:1:no-existe")
    monkeypatch.setattr(settings, "sqs_queue_url", "http://127.0.0.1:9/cola")
    monkeypatch.setattr(settings, "aws_endpoint_url", "http://127.0.0.1:9")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    reset_messaging_health_cache()
    try:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["broker"] == "DOWN"
        # La segunda consulta sale del caché sin volver a llamar a AWS
        assert client.get("/health").json()["broker"] == "DOWN"
    finally:
        reset_messaging_health_cache()

"""Tests de integración HU-01: POST /api/v1/rutas/iniciar con SQLite en memoria."""

import json
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import CircuitBreakerOpenError
from app.domain.ports.external_services import AssignmentSnapshot, IAssignmentsClient
from app.infrastructure.db.orm_models import OutboxModel, RouteModel
from app.main import app
from app.presentation.dependencies import get_assignments_client

URL = "/api/v1/rutas/iniciar"


class FakeAssignmentsClient(IAssignmentsClient):
    """Doble de prueba configurable del MS de Asignaciones."""

    def __init__(self) -> None:
        self.estado: str | None = "PENDIENTE"  # None simula un 404
        self.error: Exception | None = None
        self.calls = 0

    def get_assignment(self, asignacion_id: str) -> AssignmentSnapshot | None:
        self.calls += 1
        if self.error:
            raise self.error
        if self.estado is None:
            return None
        return AssignmentSnapshot(
            asignacion_id=asignacion_id,
            estado=self.estado,
            vehiculo_id="veh-501",
            conductor_id="cond-101",
        )


@pytest.fixture
def fake_assignments(client: TestClient) -> Generator[FakeAssignmentsClient, None, None]:
    fake = FakeAssignmentsClient()
    app.dependency_overrides[get_assignments_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_assignments_client, None)


# ---------- 201 (criterios 3, 5, 6 y 9) ----------


def test_201_y_get_posterior_devuelve_los_mismos_datos(
    client: TestClient, fake_assignments: FakeAssignmentsClient
) -> None:
    response = client.post(URL, json={"asignacion_id": "asig-001"})

    assert response.status_code == 201
    created = response.json()
    assert created["estado"] == "EN_CURSO"
    assert (created["vehiculo_id"], created["conductor_id"]) == ("veh-501", "cond-101")
    assert created["coordenada_origen"] == {"latitud": 3.4516, "longitud": -76.532}

    fetched = client.get(f"/api/v1/rutas/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_deja_ruta_iniciada_event_pendiente_en_outbox(
    client: TestClient, fake_assignments: FakeAssignmentsClient, db_session: Session
) -> None:
    response = client.post(URL, json={"asignacion_id": "asig-outbox"})

    outbox = db_session.execute(select(OutboxModel)).scalars().all()
    assert len(outbox) == 1
    assert outbox[0].routing_key == "telemetria.ruta.iniciada"
    assert outbox[0].estado == "PENDIENTE"
    assert json.loads(outbox[0].payload_json)["datos"]["ruta_id"] == response.json()["id"]


def test_ignora_coordenadas_enviadas_por_el_cliente(
    client: TestClient, fake_assignments: FakeAssignmentsClient
) -> None:
    payload = {"asignacion_id": "asig-coords", "origen_latitud": 0, "origen_longitud": 0}

    response = client.post(URL, json=payload)

    assert response.status_code == 201
    assert response.json()["coordenada_origen"]["latitud"] == 3.4516


# ---------- Errores (criterios 1, 2, 4 y 7) ----------


@pytest.mark.parametrize("payload", [{}, {"asignacion_id": ""}, {"asignacion_id": "   "}])
def test_400_datos_invalidos_sin_crear_nada(
    client: TestClient,
    fake_assignments: FakeAssignmentsClient,
    db_session: Session,
    payload: dict[str, str],
) -> None:
    response = client.post(URL, json=payload)

    assert response.status_code == 400
    assert response.json()["codigo"] == "DATOS_INVALIDOS"
    assert response.json()["mensaje"] == "El campo asignacion_id es obligatorio"
    assert db_session.execute(select(RouteModel)).first() is None
    assert fake_assignments.calls == 0


def test_400_json_invalido(client: TestClient, fake_assignments: FakeAssignmentsClient) -> None:
    response = client.post(
        URL, content=b'{"asignacion_id": ', headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 400
    assert response.json()["codigo"] == "JSON_INVALIDO"


def test_404_asignacion_no_encontrada(
    client: TestClient, fake_assignments: FakeAssignmentsClient
) -> None:
    fake_assignments.estado = None

    response = client.post(URL, json={"asignacion_id": "asig-x"})

    assert response.status_code == 404
    assert response.json()["codigo"] == "ASIGNACION_NO_ENCONTRADA"


def test_409_asignacion_no_pendiente(
    client: TestClient, fake_assignments: FakeAssignmentsClient
) -> None:
    fake_assignments.estado = "CANCELADA"

    response = client.post(URL, json={"asignacion_id": "asig-cancel"})

    assert response.status_code == 409
    assert response.json()["codigo"] == "ASIGNACION_NO_PENDIENTE"


def test_409_ruta_duplicada(client: TestClient, fake_assignments: FakeAssignmentsClient) -> None:
    assert client.post(URL, json={"asignacion_id": "asig-dup"}).status_code == 201

    response = client.post(URL, json={"asignacion_id": "asig-dup"})

    assert response.status_code == 409
    assert response.json()["codigo"] == "RUTA_DUPLICADA"


def test_503_dependencia_no_disponible_sin_persistir(
    client: TestClient, fake_assignments: FakeAssignmentsClient, db_session: Session
) -> None:
    fake_assignments.error = CircuitBreakerOpenError("circuito abierto")

    response = client.post(URL, json={"asignacion_id": "asig-down"})

    assert response.status_code == 503
    assert response.json()["codigo"] == "DEPENDENCIA_NO_DISPONIBLE"
    assert db_session.execute(select(OutboxModel)).first() is None



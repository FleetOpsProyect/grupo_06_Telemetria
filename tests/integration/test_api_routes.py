"""Tests de integración end-to-end para los endpoints del arquetipo."""

from fastapi.testclient import TestClient


class TestApiRoutesIntegration:
    """Pruebas end-to-end con TestClient y base de datos SQLite en memoria."""

    def test_health_check_returns_status(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "broker" in data

    def test_crear_ruta_exito_retorna_201(self, client: TestClient) -> None:
        payload = {
            "asignacion_id": "asig-001",
            "vehiculo_id": "veh-101",
            "conductor_id": "cond-201",
        }
        response = client.post("/api/v1/rutas", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["asignacion_id"] == "asig-001"
        assert data["vehiculo_id"] == "veh-101"
        assert data["estado"] == "EN_CURSO"
        assert "id" in data

    def test_crear_ruta_duplicada_retorna_409(self, client: TestClient) -> None:
        payload = {
            "asignacion_id": "asig-dup-1",
            "vehiculo_id": "veh-101",
            "conductor_id": "cond-201",
        }
        r1 = client.post("/api/v1/rutas", json=payload)
        assert r1.status_code == 201

        r2 = client.post("/api/v1/rutas", json=payload)
        assert r2.status_code == 409
        data = r2.json()
        assert data["codigo"] == "RUTA_DUPLICADA"

    def test_crear_ruta_con_campos_vacios_retorna_400(self, client: TestClient) -> None:
        payload = {
            "asignacion_id": "   ",
            "vehiculo_id": "veh-101",
            "conductor_id": "cond-201",
        }
        response = client.post("/api/v1/rutas", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert data["codigo"] == "DATOS_INVALIDOS"

    def test_obtener_ruta_por_id_exito_retorna_200(self, client: TestClient) -> None:
        payload = {
            "asignacion_id": "asig-find-1",
            "vehiculo_id": "veh-101",
            "conductor_id": "cond-201",
        }
        create_res = client.post("/api/v1/rutas", json=payload)
        route_id = create_res.json()["id"]

        get_res = client.get(f"/api/v1/rutas/{route_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == route_id

    def test_obtener_ruta_inexistente_retorna_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/rutas/ruta-no-existe-999")
        assert response.status_code == 404
        data = response.json()
        assert data["codigo"] == "RUTA_NO_ENCONTRADA"

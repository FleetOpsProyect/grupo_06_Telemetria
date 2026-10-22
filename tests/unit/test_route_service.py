"""Tests unitarios del servicio transaccional RouteService (AAA Pattern)."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.route import RouteCreateDTO
from app.application.services.route_service import RouteService
from app.core.exceptions import DuplicateEntityError, EntityNotFoundError
from app.domain.models.route import Route, RouteStatus


class TestRouteService:
    """Suite de pruebas unitarias para RouteService."""

    def test_create_route_success(self) -> None:
        # Arrange
        mock_repo = MagicMock()
        mock_repo.get_by_asignacion_id.return_value = None

        dto = RouteCreateDTO(
            asignacion_id="asig-100",
            vehiculo_id="veh-200",
            conductor_id="cond-300",
        )

        mock_saved_route = Route(
            id="ruta-test-1",
            asignacion_id=dto.asignacion_id,
            vehiculo_id=dto.vehiculo_id,
            conductor_id=dto.conductor_id,
            estado=RouteStatus.EN_CURSO,
        )
        mock_repo.save.return_value = mock_saved_route
        service = RouteService(route_repo=mock_repo)

        # Act
        result = service.create_route(dto)

        # Assert
        assert result.id == "ruta-test-1"
        assert result.asignacion_id == "asig-100"
        assert result.estado == "EN_CURSO"
        mock_repo.save.assert_called_once()

    def test_create_route_duplicate_raises_duplicate_error(self) -> None:
        # Arrange
        mock_repo = MagicMock()
        mock_repo.get_by_asignacion_id.return_value = Route(
            id="ruta-existing",
            asignacion_id="asig-100",
            vehiculo_id="veh-200",
            conductor_id="cond-300",
        )
        service = RouteService(route_repo=mock_repo)
        dto = RouteCreateDTO(
            asignacion_id="asig-100",
            vehiculo_id="veh-200",
            conductor_id="cond-300",
        )

        # Act & Assert
        with pytest.raises(DuplicateEntityError) as exc_info:
            service.create_route(dto)

        assert "Ya existe una ruta" in str(exc_info.value)
        mock_repo.save.assert_not_called()

    def test_get_route_by_id_success(self) -> None:
        # Arrange
        mock_repo = MagicMock()
        mock_route = Route(
            id="ruta-123",
            asignacion_id="asig-100",
            vehiculo_id="veh-200",
            conductor_id="cond-300",
            estado=RouteStatus.EN_CURSO,
        )
        mock_repo.get_by_id.return_value = mock_route
        service = RouteService(route_repo=mock_repo)

        # Act
        result = service.get_route_by_id("ruta-123")

        # Assert
        assert result.id == "ruta-123"
        assert result.asignacion_id == "asig-100"
        assert result.estado == "EN_CURSO"
        mock_repo.get_by_id.assert_called_once_with("ruta-123")

    def test_get_route_by_id_not_found_raises_entity_not_found(self) -> None:
        # Arrange
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        service = RouteService(route_repo=mock_repo)

        # Act & Assert
        with pytest.raises(EntityNotFoundError) as exc_info:
            service.get_route_by_id("ruta-inexistente")

        assert "No existe una ruta con id" in str(exc_info.value)

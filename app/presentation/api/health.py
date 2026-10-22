"""Endpoint de salud y diagnóstico de dependencias para probes de balanceadores y orquestadores."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.db.session import get_db
from app.infrastructure.messaging.connection import check_rabbitmq_socket

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Diagnóstico de salud del servicio y dependencias",
    response_description="Estado de operatividad del microservicio, BD y broker",
)
def health_check(response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    """
    Endpoint público (sin autenticación JWT) para probes de AWS ALB y Kubernetes.

    - Sondeo activo a Base de Datos (SELECT 1 con timeout de 1.0 s).
    - Sondeo activo a RabbitMQ (socket TCP con timeout de 1.0 s).
    - Retorna 200 OK si ambos están UP; 503 Service Unavailable si alguno está DOWN.
    """
    # 1. Probar base de datos
    db_status = "DOWN"
    try:
        db.execute(text("SELECT 1"))
        db_status = "UP"
    except Exception:
        db_status = "DOWN"

    # 2. Probar broker RabbitMQ
    broker_status = "UP" if check_rabbitmq_socket(timeout=1.0) else "DOWN"

    # 3. Evaluar estado global
    is_healthy = (db_status == "UP") and (broker_status == "UP")
    overall_status = "UP" if is_healthy else "DOWN"

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": overall_status,
        "database": db_status,
        "broker": broker_status,
        "timestamp": datetime.now(UTC).isoformat(),
    }

"""Endpoint de salud y diagnóstico de dependencias para probes de balanceadores y orquestadores."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.db.session import get_db
from app.infrastructure.messaging.connection import check_messaging

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
    - Sondeo a AWS SNS/SQS (tópico y cola accesibles; resultado en caché 30 s).
    - Retorna 200 OK si ambos están UP; 503 Service Unavailable si alguno está DOWN.
    - Fuera de producción, la mensajería sin configurar se reporta DISABLED sin fallar.
    """
    # 1. Probar base de datos
    db_status = "DOWN"
    try:
        db.execute(text("SELECT 1"))
        db_status = "UP"
    except Exception:
        db_status = "DOWN"

    # 2. Probar mensajería AWS (SNS/SQS)
    broker_status = check_messaging()
    broker_ok = broker_status == "UP" or (
        broker_status == "DISABLED" and settings.environment != "production"
    )

    # 3. Evaluar estado global
    is_healthy = (db_status == "UP") and broker_ok
    overall_status = "UP" if is_healthy else "DOWN"

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": overall_status,
        "database": db_status,
        "broker": broker_status,
        "timestamp": datetime.now(UTC).isoformat(),
    }

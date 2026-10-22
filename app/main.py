"""Punto de entrada principal de la aplicación FastAPI."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.db.session import Base, engine
from app.presentation.api.health import router as health_router
from app.presentation.api.v1.router import api_v1_router
from app.presentation.exception_handlers import register_exception_handlers
from app.presentation.middleware import CorrelationIdMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestiona el ciclo de vida de la aplicación (inicio y apagado)."""
    logger.info(f"Iniciando {settings.app_name} en entorno [{settings.environment}]...")
    # Crear tablas en desarrollo o pruebas si no existen
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Verificación de esquema de base de datos completada.")
    except Exception as e:
        logger.warning(f"No fue posible auto-crear tablas de BD al inicio: {e}")

    yield

    logger.info(f"Apagando {settings.app_name}...")


def create_app() -> FastAPI:
    """Fábrica para crear y configurar la instancia de FastAPI."""
    app = FastAPI(
        title="FleetOps — Telemetría y Rutas",
        description=(
            "Microservicio para la gestión de ciclo de vida de recorridos, odómetros de flota, "
            "simulación geoespacial (Haversine) y sincronización con Combustible y Asignaciones."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configurar CORS permisivo para desarrollo y API Gateway
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware de trazabilidad con Correlation ID
    app.add_middleware(CorrelationIdMiddleware)

    # Registrar manejadores globales de excepciones estandarizadas
    register_exception_handlers(app)

    # Endpoints de salud (accesibles en /health y /api/v1/health)
    app.include_router(health_router)
    app.include_router(health_router, prefix=settings.api_v1_prefix)

    # Endpoints del arquetipo v1 (accesibles con y sin prefijo)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    app.include_router(api_v1_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=settings.debug)

"""Agregador principal de routers para la API versión 1 del arquetipo."""

from fastapi import APIRouter

from app.presentation.api.v1.routes import router as routes_router
from app.presentation.api.v1.routes_finish import router as routes_finish_router
from app.presentation.api.v1.routes_query import router as routes_query_router
from app.presentation.api.v1.routes_start import router as routes_start_router

api_v1_router = APIRouter()
api_v1_router.include_router(routes_router)
api_v1_router.include_router(routes_start_router)
api_v1_router.include_router(routes_finish_router)
api_v1_router.include_router(routes_query_router)

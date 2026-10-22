"""Agregador principal de routers para la API versión 1 del arquetipo."""

from fastapi import APIRouter

from app.presentation.api.v1.routes import router as routes_router

api_v1_router = APIRouter()
api_v1_router.include_router(routes_router)

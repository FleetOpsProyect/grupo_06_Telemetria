"""Mecanismo de seguridad y extracción de identidad delegada por el API Gateway."""

from typing import Any

import jwt
from fastapi import Header, HTTPException, status

from app.core.config import settings


def verify_authorization(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> dict[str, Any]:
    """
    Verifica las credenciales delegadas por el API Gateway.

    Acepta el token JWT en la cabecera Authorization o directamente los claims
    prevalidados por el API Gateway (X-User-Id).
    """
    if x_user_id:
        return {"sub": x_user_id, "role": "OPERATOR"}

    if not authorization:
        # En desarrollo se permite continuar con identidad de prueba si no viene token
        if settings.environment == "development" or settings.debug:
            return {"sub": "dev-user-001", "role": "ADMIN"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cabecera Authorization obligatoria",
        )

    try:
        token = authorization.replace("Bearer ", "").strip()
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_signature": settings.environment != "development"},
        )
        return payload  # type: ignore[no-any-return]
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token JWT inválido o expirado: {exc}",
        ) from exc

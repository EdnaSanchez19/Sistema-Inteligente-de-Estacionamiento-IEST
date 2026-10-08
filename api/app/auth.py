from datetime import datetime, timedelta, timezone
import hmac

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import Rol, Usuario

oauth2 = OAuth2PasswordBearer(tokenUrl="auth/login")


def _configured(value: str) -> bool:
    """Los secretos vacíos o con el valor de ejemplo de .env.example se consideran sin configurar."""
    return bool(value) and not value.startswith("cambia_")


def create_token(user_id: int) -> str:
    s = get_settings()
    if not _configured(s.jwt_secret):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "JWT_SECRET no está configurado")
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, s.jwt_secret, algorithm="HS256")


def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    s = get_settings()
    err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada", headers={"WWW-Authenticate": "Bearer"})
    if not _configured(s.jwt_secret):
        raise err
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
        user = db.get(Usuario, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise err from None
    if user is None or not user.activo:
        raise err
    return user


def require_admin(user: Usuario = Depends(get_current_user)) -> Usuario:
    if user.rol != Rol.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requiere permisos de administrador")
    return user


def require_ingest_key(x_api_key: str | None = Header(default=None)) -> None:
    """Autentica al servidor de visión (no es un usuario de la app)."""
    expected = get_settings().ingest_api_key
    if not _configured(expected):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "INGEST_API_KEY no está configurada")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida")

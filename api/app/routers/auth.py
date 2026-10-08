from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_token, get_current_user
from ..db import get_db
from ..models import Usuario
from ..schemas import TokenOut, UsuarioOut
from ..security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# Hash de relleno para que el tiempo de respuesta no revele si el correo existe.
_DUMMY = hash_password("relleno")


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(Usuario).where(Usuario.correo == form.username.strip().lower()))
    ok = verify_password(form.password, user.password_hash if user else _DUMMY)
    if not user or not ok or not user.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    return TokenOut(access_token=create_token(user.id))


@router.get("/me", response_model=UsuarioOut)
def me(user: Usuario = Depends(get_current_user)) -> UsuarioOut:
    return UsuarioOut.of(user)

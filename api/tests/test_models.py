import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, seed
from app.db import Base, make_engine
from app.models import Colgante, Espacio, EstadoEspacio, Rol, TipoColgante, Usuario, Vehiculo, Zona
from app.security import hash_password, verify_password


@pytest.fixture()
def db():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_seed_crea_zonas_espacios_y_admin(db, monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "x" * 12)
    seed.seed_base(db)
    seed.seed_base(db)  # idempotente
    assert db.scalar(select(Zona.id).where(Zona.nombre == "A")) is not None
    assert len(db.scalars(select(Espacio)).all()) == 48
    admin = db.scalar(select(Usuario).where(Usuario.rol == Rol.admin))
    assert admin is not None and admin.password_hash != "x" * 12


def test_cadena_usuario_vehiculo_colgante_espacio(db):
    seed.seed_demo(db)
    seed.seed_base(db)
    colgante = db.scalar(select(Colgante))
    espacio = db.scalar(select(Espacio).where(Espacio.numero == "A-03"))
    espacio.estado = EstadoEspacio.ocupado
    espacio.colgante_actual = colgante
    db.commit()
    assert espacio.colgante_actual.vehiculo.usuario.correo == "demo@iest.edu.mx"


def test_numero_de_espacio_unico_por_zona(db):
    z = Zona(nombre="Z")
    db.add_all([z, Espacio(numero="Z-01", zona=z)])
    db.commit()
    db.add(Espacio(numero="Z-01", zona=z))
    with pytest.raises(IntegrityError):
        db.commit()


def test_colgante_unico_por_vehiculo(db):
    u = Usuario(nombre="u", correo="u@x.mx", password_hash="h")
    v = Vehiculo(usuario=u, marca="m", modelo="m", color="c")
    db.add_all([Colgante(codigo="1", tipo=TipoColgante.docente, vehiculo=v), Colgante(codigo="2", tipo=TipoColgante.docente, vehiculo=v)])
    with pytest.raises(IntegrityError):
        db.commit()


def test_hash_de_password():
    h = hash_password("secreto123")
    assert "secreto123" not in h
    assert verify_password("secreto123", h)
    assert not verify_password("otra", h)
    assert not verify_password("secreto123", "basura")

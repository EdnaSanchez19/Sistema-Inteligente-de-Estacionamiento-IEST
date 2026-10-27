from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    url = url or get_settings().database_url
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    return create_engine(url, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def migrar_esquema(eng=None) -> None:
    """Agrega columnas nuevas a bases ya creadas (create_all no modifica tablas existentes). Sin Alembic, en el piloto."""
    from sqlalchemy import inspect, text

    eng = eng or engine
    columnas = {c["name"] for c in inspect(eng).get_columns("espacios")} if inspect(eng).has_table("espacios") else set()
    if columnas and "monitoreado" not in columnas:
        with eng.begin() as con:
            con.execute(text("ALTER TABLE espacios ADD COLUMN monitoreado BOOLEAN NOT NULL DEFAULT FALSE"))


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db

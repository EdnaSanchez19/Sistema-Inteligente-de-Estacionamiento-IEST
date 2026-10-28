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


COLUMNAS_NUEVAS = {  # tabla -> {columna: definición}; create_all no modifica tablas que ya existen
    "espacios": {
        "monitoreado": "BOOLEAN NOT NULL DEFAULT FALSE",
        "estado_desde": "DATETIME",
        "inicio_observado": "BOOLEAN NOT NULL DEFAULT FALSE",
        "objeto": "VARCHAR(40)",
    },
}
VALORES_NUEVOS = {"espacios": "obstruido", "eventos": "obstruccion"}  # valores de enumeración que una base vieja rechaza (CHECK)


def _reconstruir_tabla_sqlite(eng, nombre: str) -> None:
    """SQLite no puede cambiar un CHECK: crea la tabla con el esquema actual, copia los datos y reemplaza la anterior."""
    from sqlalchemy import text
    from sqlalchemy.schema import CreateTable

    tabla = Base.metadata.tables[nombre]
    nueva = f"{nombre}_nueva"
    ddl = str(CreateTable(tabla).compile(dialect=eng.dialect)).replace(f"CREATE TABLE {nombre} (", f"CREATE TABLE {nueva} (", 1)
    with eng.connect() as con:
        con.exec_driver_sql("PRAGMA foreign_keys=OFF")
        con.exec_driver_sql(f"DROP TABLE IF EXISTS {nueva}")
        con.exec_driver_sql(ddl)
        viejas = {r[1] for r in con.exec_driver_sql(f"PRAGMA table_info({nombre})")}
        comunes = ", ".join(c.name for c in tabla.columns if c.name in viejas)
        con.exec_driver_sql(f"INSERT INTO {nueva} ({comunes}) SELECT {comunes} FROM {nombre}")
        antes = con.execute(text(f"SELECT COUNT(*) FROM {nombre}")).scalar()
        despues = con.execute(text(f"SELECT COUNT(*) FROM {nueva}")).scalar()
        if antes != despues:  # no se toca la tabla original si la copia no quedó completa
            con.exec_driver_sql(f"DROP TABLE {nueva}")
            raise RuntimeError(f"Migración de {nombre} cancelada: se copiaron {despues} de {antes} filas")
        con.exec_driver_sql(f"DROP TABLE {nombre}")
        con.exec_driver_sql(f"ALTER TABLE {nueva} RENAME TO {nombre}")
        for indice in tabla.indexes:
            indice.create(con)
        con.commit()


def migrar_esquema(eng=None) -> None:
    """Pone al día una base ya creada: agrega las columnas nuevas y, en SQLite, el valor de enumeración nuevo.

    Sin Alembic, en el piloto. En PostgreSQL las columnas se agregan igual, pero el CHECK de las enumeraciones se amplía
    con `db/migraciones/002_obstruido.sql` (una base nueva ya nace con el esquema correcto).
    """
    from sqlalchemy import inspect, text

    eng = eng or engine
    insp = inspect(eng)
    for tabla, columnas in COLUMNAS_NUEVAS.items():
        if not insp.has_table(tabla):
            continue
        existentes = {c["name"] for c in insp.get_columns(tabla)}
        with eng.begin() as con:
            for nombre, definicion in columnas.items():
                if nombre not in existentes:
                    con.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}"))
    if eng.dialect.name != "sqlite":
        return
    for tabla, valor in VALORES_NUEVOS.items():
        if not inspect(eng).has_table(tabla):
            continue
        with eng.connect() as con:
            ddl = con.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tabla,)).scalar() or ""
        if "CHECK" in ddl.upper() and f"'{valor}'" not in ddl:  # hay restricción de valores y no incluye el nuevo
            _reconstruir_tabla_sqlite(eng, tabla)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db

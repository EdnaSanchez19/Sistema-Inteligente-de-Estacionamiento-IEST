"""Genera db/schema.sql (PostgreSQL) a partir de los modelos.

Uso: python scripts/export_schema.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base  # noqa: E402


def main() -> None:
    d = postgresql.dialect()
    parts = ["-- Generado por scripts/export_schema.py. No editar a mano: cambia api/app/models.py.\n"]
    for table in Base.metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=d)).strip() + ";\n")
        for index in sorted(table.indexes, key=lambda i: i.name or ""):
            parts.append(str(CreateIndex(index).compile(dialect=d)).strip() + ";\n")
    out = ROOT / "db" / "schema.sql"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Escrito {out.relative_to(ROOT)} ({len(Base.metadata.sorted_tables)} tablas)")


if __name__ == "__main__":
    main()

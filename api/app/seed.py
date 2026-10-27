"""Crea las tablas y carga datos iniciales.

    python -m app.seed            # zonas, cámaras, espacios y usuario admin
    python -m app.seed --demo     # además usuarios/vehículos de ejemplo
    python -m app.seed --demo --muestra 150   # además 150 usuarios, vehículos y colgantes inventados (demostración)

Ejecutar desde la carpeta api/. La contraseña del admin sale de SEED_ADMIN_PASSWORD;
si no existe se genera una aleatoria y se imprime una sola vez.
"""
import os
import secrets
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Base, engine
from .models import (Camara, Colgante, Espacio, EstadoCamara, Rol, TipoColgante, TipoEspacio, Usuario, Vehiculo, Zona)
from .security import hash_password

# El estacionamiento son 8 islas (las "zonas" del modelo de datos) de 40 cajones, cada una vigilada por una cámara:
# 8 x 40 = 320 cajones. Los 2 primeros cajones de cada isla son de un tipo especial.
CAJONES_POR_ISLA = 40
_ESPECIAL = {
    "A": TipoEspacio.discapacidad, "B": TipoEspacio.directivo, "C": TipoEspacio.visitante, "D": TipoEspacio.discapacidad,
    "E": TipoEspacio.directivo, "F": TipoEspacio.visitante, "G": TipoEspacio.motocicleta, "H": TipoEspacio.directivo,
}
ZONAS = [(isla, f"CAM-{i:02d}", CAJONES_POR_ISLA, _ESPECIAL[isla]) for i, isla in enumerate("ABCDEFGH", start=1)]  # (isla, cámara, cajones, tipo especial)


def seed_base(db: Session) -> None:
    for nombre, cam, cantidad, especial in ZONAS:
        zona = db.scalar(select(Zona).where(Zona.nombre == nombre)) or Zona(nombre=nombre, descripcion=f"Isla {nombre}")
        db.add(zona)
        db.flush()
        camara = db.scalar(select(Camara).where(Camara.codigo == cam)) or Camara(codigo=cam, zona_id=zona.id, estado=EstadoCamara.desconectada)
        db.add(camara)
        db.flush()
        for i in range(1, cantidad + 1):
            numero = f"{nombre}-{i:02d}"
            existe = db.scalar(select(Espacio).where(Espacio.zona_id == zona.id, Espacio.numero == numero))
            if not existe:
                db.add(Espacio(numero=numero, zona_id=zona.id, camara_id=camara.id, tipo=especial if i <= 2 else TipoEspacio.general))

    if not db.scalar(select(Usuario).where(Usuario.correo == "admin@iest.edu.mx")):
        password = os.environ.get("SEED_ADMIN_PASSWORD")
        if not password:
            password = secrets.token_urlsafe(12)
            print(f"Contraseña generada para admin@iest.edu.mx: {password}  (guárdala, no se vuelve a mostrar)")
        db.add(Usuario(nombre="Administrador", correo="admin@iest.edu.mx", password_hash=hash_password(password), rol=Rol.admin))
    db.commit()


def seed_demo(db: Session) -> None:
    if db.scalar(select(Usuario).where(Usuario.correo == "demo@iest.edu.mx")):
        return
    password = os.environ.get("SEED_DEMO_PASSWORD") or secrets.token_urlsafe(12)
    print(f"Contraseña de demo@iest.edu.mx: {password}")
    usuario = Usuario(nombre="Usuario Demo", correo="demo@iest.edu.mx", password_hash=hash_password(password), rol=Rol.estudiante)
    vehiculo = Vehiculo(usuario=usuario, placa="ABC-123-D", marca="Nissan", modelo="Versa", color="Gris")
    colgante = Colgante(codigo="IEST-004512", tipo=TipoColgante.estudiante, vehiculo=vehiculo)
    db.add_all([usuario, vehiculo, colgante])
    db.commit()


# --- Datos de muestra para la demostración: personas, vehículos y colgantes INVENTADOS ---------------------------
# La mezcla de tipos sale del perfil del dataset de Kaggle (73 % usuarios registrados, 24 % visitantes, 3 % personal);
# los registrados se reparten entre estudiantes y docentes y el personal entre administrativos y directivos.
_VEHICULOS = [("Nissan", "Versa"), ("Volkswagen", "Jetta"), ("Chevrolet", "Aveo"), ("Toyota", "Corolla"), ("Mazda", "3"), ("Honda", "Civic"), ("Kia", "Rio"), ("Ford", "Fiesta")]
_COLORES = ["Gris", "Blanco", "Negro", "Rojo", "Azul", "Plata"]
_ROL_DE_COLGANTE = {
    TipoColgante.estudiante: Rol.estudiante, TipoColgante.docente: Rol.docente, TipoColgante.administrativo: Rol.administrativo,
    TipoColgante.directivo: Rol.directivo, TipoColgante.visitante: Rol.externo,
}


def tipo_de_muestra(i: int) -> TipoColgante:
    """Tipo del i-ésimo colgante de muestra: 51 % estudiante, 22 % docente, 2 % administrativo, 1 % directivo, 24 % visitante."""
    r = i % 100
    if r < 51:
        return TipoColgante.estudiante
    if r < 73:
        return TipoColgante.docente
    if r < 75:
        return TipoColgante.administrativo
    if r < 76:
        return TipoColgante.directivo
    return TipoColgante.visitante


def colgantes_de_muestra(n: int) -> list[tuple[str, TipoColgante]]:
    """Códigos y tipos de los colgantes de muestra (deterministas: el simulador de cámaras calcula la misma lista)."""
    return [(f"IEST-{100001 + i:06d}", tipo_de_muestra(i)) for i in range(n)]


def seed_muestra(db: Session, n: int) -> int:
    """Crea n usuarios con vehículo y colgante de muestra. Es idempotente; devuelve cuántos creó."""
    creados = 0
    for i, (codigo, tipo) in enumerate(colgantes_de_muestra(n)):
        if db.scalar(select(Colgante).where(Colgante.codigo == codigo)):
            continue
        usuario = Usuario(
            nombre=f"Usuario de muestra {i + 1:03d}", correo=f"muestra{i + 1:03d}@iest.edu.mx",
            password_hash=hash_password(secrets.token_urlsafe(16)),  # nadie conoce esta clave: no son cuentas para entrar
            rol=_ROL_DE_COLGANTE[tipo],
        )
        marca, modelo = _VEHICULOS[i % len(_VEHICULOS)]
        vehiculo = Vehiculo(usuario=usuario, placa=f"MUE-{i + 1:03d}-X", marca=marca, modelo=modelo, color=_COLORES[i % len(_COLORES)])
        db.add_all([usuario, vehiculo, Colgante(codigo=codigo, tipo=tipo, vehiculo=vehiculo)])
        creados += 1
    db.commit()
    return creados


def main() -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_base(db)
        if "--demo" in sys.argv:
            seed_demo(db)
        if "--muestra" in sys.argv:
            i = sys.argv.index("--muestra")
            n = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit() else 150
            print(f"Datos de muestra: {seed_muestra(db, n)} usuarios con vehículo y colgante creados")
    print("Base de datos lista.")


if __name__ == "__main__":
    main()

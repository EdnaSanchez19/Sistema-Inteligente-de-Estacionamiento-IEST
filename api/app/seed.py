"""Crea las tablas y carga datos iniciales.

    python -m app.seed            # zonas, cámaras, espacios (391, como el estacionamiento real) y usuario admin
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

from .db import Base, engine, migrar_esquema
from .models import (Camara, Colgante, Espacio, EstadoCamara, Evento, Rol, TipoColgante, TipoEspacio, Usuario, Vehiculo, Zona)
from .security import hash_password

# El estacionamiento del IEST (medido por el plantel): 8 islas, cada una vigilada por una cámara, y 6 zonas en el perímetro.
#   Isla A y G: 32 cajones · islas B a F: 32 + 2 por costado = 36 · isla H: 27   -> 271 en islas
#   Perímetro: lateral caseta 16, esquina motos 8, lateral biblioteca 42, lateral gimnasio 18, entrada lateral 4,
#   lateral callejón 32                                                         -> 120 en el perímetro
# Total: 391 cajones. Las islas se llaman con su letra ("A"); las del perímetro con su nombre y un prefijo en el número
# (CAS-01, MOT-01...). El perímetro aún no tiene cámaras: sus cajones salen "sin monitoreo" hasta que las tenga.
# Los 2 primeros cajones de cada isla son de un tipo especial (provisional: pendiente de confirmar cuáles son los reales).
CAJONES_POR_ISLA = {"A": 32, "B": 36, "C": 36, "D": 36, "E": 36, "F": 36, "G": 32, "H": 27}
_ESPECIAL = {
    "A": TipoEspacio.discapacidad, "B": TipoEspacio.directivo, "C": TipoEspacio.visitante, "D": TipoEspacio.discapacidad,
    "E": TipoEspacio.directivo, "F": TipoEspacio.visitante, "G": TipoEspacio.discapacidad, "H": TipoEspacio.directivo,
}
# Las únicas cámaras que se usan son 3 (videos reales del IEST), y una ve varias islas. La isla 1 es la A, la 2 la B... la 8 la H
# (se numeran de la más lejana a la más cercana a la cámara). Quién ve qué: la de "Isla 1 y 2" ve las islas A y B; la general
# ("Estacionamiento") se supone que ve de la C a la G (por confirmar); la H aún no tiene grabaciones; la de la entrada no vigila
# cajones, solo el flujo de vehículos.
CAMARAS = [  # (código, nombre, zona a la que pertenece, islas cuyos cajones vigila)
    ("CAM-01", "Fila 1 y 2", "A", "AB"),
    ("CAM-02", "Estacionamiento", "C", "CDEFG"),
    ("CAM-03", "Entrada", "Lateral caseta", ""),
]
_CAMARA_DE_ISLA = {isla: cam for cam, _, _, islas in CAMARAS for isla in islas}
ZONAS = [(isla, _CAMARA_DE_ISLA.get(isla), CAJONES_POR_ISLA[isla], _ESPECIAL[isla]) for isla in "ABCDEFGH"]  # (isla, cámara o None, cajones, tipo especial)
PERIMETRO = [  # (zona, prefijo del número, cajones, tipo de todos sus cajones)
    ("Lateral caseta", "CAS", 16, TipoEspacio.general),
    ("Esquina motos", "MOT", 8, TipoEspacio.motocicleta),
    ("Lateral biblioteca", "BIB", 42, TipoEspacio.general),
    ("Lateral gimnasio", "GIM", 18, TipoEspacio.general),
    ("Entrada lateral", "ENT", 4, TipoEspacio.general),
    ("Lateral callejón", "CAL", 32, TipoEspacio.general),
]
TOTAL_CAJONES = sum(CAJONES_POR_ISLA.values()) + sum(n for _, _, n, _ in PERIMETRO)  # 391


def _crear_cajones(db: Session, zona: Zona, prefijo: str, cantidad: int, camara: Camara | None, tipo, primeros_especiales: bool) -> None:
    for i in range(1, cantidad + 1):
        numero = f"{prefijo}-{i:02d}"
        if not db.scalar(select(Espacio).where(Espacio.zona_id == zona.id, Espacio.numero == numero)):
            db.add(Espacio(numero=numero, zona_id=zona.id, camara_id=camara.id if camara else None,
                           tipo=tipo if (not primeros_especiales or i <= 2) else TipoEspacio.general))


def ajustar_cajones(db: Session) -> int:
    """Quita los cajones que la distribución real no tiene (p. ej. una base creada cuando cada isla tenía 40). Devuelve cuántos quitó.

    Sus eventos se conservan en el historial, solo pierden la referencia al cajón.
    """
    esperados = {nombre: (nombre, n) for nombre, n in CAJONES_POR_ISLA.items()} | {nombre: (pref, n) for nombre, pref, n, _ in PERIMETRO}
    quitados = 0
    for nombre, (prefijo, cantidad) in esperados.items():
        zona = db.scalar(select(Zona).where(Zona.nombre == nombre))
        if zona is None:
            continue
        validos = {f"{prefijo}-{i:02d}" for i in range(1, cantidad + 1)}
        for esp in db.scalars(select(Espacio).where(Espacio.zona_id == zona.id)).all():
            if esp.numero in validos:
                continue
            for ev in db.scalars(select(Evento).where(Evento.espacio_id == esp.id)):
                ev.espacio_id = None
            db.delete(esp)
            quitados += 1
    db.commit()
    return quitados


def ajustar_camaras(db: Session) -> None:
    """Deja solo las cámaras reales: quita las anteriores (CAM-04 a CAM-08 de cuando había una por isla) y reasigna los cajones."""
    codigos = {c[0] for c in CAMARAS}
    for cam in db.scalars(select(Camara)).all():
        if cam.codigo not in codigos:
            for esp in db.scalars(select(Espacio).where(Espacio.camara_id == cam.id)):
                esp.camara_id = None
            for ev in db.scalars(select(Evento).where(Evento.camara_id == cam.id)):
                ev.camara_id = None
            db.delete(cam)
    db.flush()
    por_codigo = {c.codigo: c for c in db.scalars(select(Camara))}
    for isla, cam, _, _ in ZONAS:
        zona = db.scalar(select(Zona).where(Zona.nombre == isla))
        destino = por_codigo[cam].id if cam else None
        for esp in db.scalars(select(Espacio).where(Espacio.zona_id == zona.id)):
            if esp.camara_id != destino:
                esp.camara_id = destino
    db.commit()


def seed_base(db: Session) -> None:
    zonas: dict[str, Zona] = {}
    for nombre in CAJONES_POR_ISLA:
        zonas[nombre] = db.scalar(select(Zona).where(Zona.nombre == nombre)) or Zona(nombre=nombre, descripcion=f"Isla {nombre}")
    for nombre, _, _, _ in PERIMETRO:
        zonas[nombre] = db.scalar(select(Zona).where(Zona.nombre == nombre)) or Zona(nombre=nombre, descripcion=f"Perímetro: {nombre.lower()}")
    db.add_all(zonas.values())
    db.flush()
    camaras: dict[str, Camara] = {}
    for codigo, nombre_cam, zona_base, _ in CAMARAS:
        cam = db.scalar(select(Camara).where(Camara.codigo == codigo)) or Camara(codigo=codigo, zona_id=zonas[zona_base].id, estado=EstadoCamara.desconectada)
        cam.nombre = nombre_cam
        cam.zona_id = zonas[zona_base].id
        db.add(cam)
        camaras[codigo] = cam
    db.flush()
    for isla, cam, cantidad, especial in ZONAS:
        _crear_cajones(db, zonas[isla], isla, cantidad, camaras[cam] if cam else None, especial, primeros_especiales=True)
    for nombre, prefijo, cantidad, tipo in PERIMETRO:
        _crear_cajones(db, zonas[nombre], prefijo, cantidad, None, tipo, primeros_especiales=False)
    db.flush()
    ajustar_cajones(db)
    ajustar_camaras(db)

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
    migrar_esquema()
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

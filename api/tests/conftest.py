import os

# Antes de importar la app: configuración de pruebas (BD en memoria y secretos de prueba).
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "secreto-de-pruebas-con-longitud-suficiente"
os.environ["INGEST_API_KEY"] = "clave-ingesta-pruebas"

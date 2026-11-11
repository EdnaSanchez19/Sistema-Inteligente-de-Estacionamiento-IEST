from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    # Sin valor por defecto seguro: vacío o "cambia_..." => la API rechaza login e ingesta (ver auth.py)
    jwt_secret: str = ""
    jwt_expire_minutes: int = 480
    ingest_api_key: str = ""
    camera_timeout_s: int = 180  # sin señal de una cámara durante este tiempo => desconectada
    camera_check_interval_s: int = 60
    # Orígenes web que pueden llamar a la API desde el navegador (la app en Expo web). Separados por comas.
    # La app nativa (Expo Go) no usa CORS. Vacío = sin CORS.
    cors_origins: str = "http://localhost:8081,http://127.0.0.1:8081,http://localhost:19006"
    # Reportes: cada cuánto se guarda la ocupación por zona en la base de datos y cuántos días se conserva.
    muestra_ocupacion_s: int = 300
    retencion_muestras_dias: int = 365
    utc_offset_h: int = -6  # hora local del campus (Tampico, sin horario de verano) para agrupar por hora del día
    # Alertas (0 = regla apagada). Las evalúa el vigilante cada `alertas_cada_s`.
    alertas_cada_s: int = 60
    alerta_estancia_min: int = 720  # un coche lleva más de esto en el mismo cajón
    alerta_estancia_visitante_min: int = 180  # lo mismo, en cajones de visitante
    alerta_obstruccion_min: int = 15  # un cajón lleva obstruido más de esto
    alerta_ocupacion_pct: int = 95  # los cajones monitoreados están ocupados en este porcentaje o más

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

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

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

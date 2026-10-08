from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"
    # Sin valor por defecto seguro: vacío o "cambia_..." => la API rechaza login e ingesta (ver auth.py)
    jwt_secret: str = ""
    jwt_expire_minutes: int = 480
    ingest_api_key: str = ""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

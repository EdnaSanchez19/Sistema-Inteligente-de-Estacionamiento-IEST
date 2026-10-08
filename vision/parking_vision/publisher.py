"""Envío de resultados a la API (/ingest). Un fallo de red nunca detiene el procesamiento."""
from __future__ import annotations

import logging

import requests

log = logging.getLogger("publisher")


class ApiPublisher:
    def __init__(self, api_url: str, api_key: str, timeout: float = 5.0):
        self.base = api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = api_key
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> bool:
        try:
            r = self.session.post(f"{self.base}{path}", json=payload, timeout=self.timeout)
            r.raise_for_status()
            return True
        except requests.RequestException as e:
            log.warning("No se pudo enviar a %s: %s", path, e)
            return False

    def occupancy(self, camara: str, espacios: list[dict], baja_confianza: bool = False) -> bool:
        """espacios: [{numero, ocupado, confianza, colgante_codigo?, colgante_tipo?}]"""
        return self._post("/ingest/ocupacion", {"camara": camara, "espacios": espacios, "baja_confianza": baja_confianza})

    def camera_status(self, camara: str, en_linea: bool) -> bool:
        return self._post("/ingest/camara-estado", {"camara": camara, "en_linea": en_linea})

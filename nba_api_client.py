"""
Cliente mínimo compartido para API-NBA (api-sports.io), usado por
cargar_temporada_nba.py y actualizar_estadisticas_jugadores_nba.py.

NOTA SOBRE NOMBRES DE CAMPO: la documentación oficial de api-sports.io no es
accesible para scraping automático (devuelve 403), así que los nombres de
campo de /games y /players/statistics usados en este proyecto se basan en
la convención que api-sports.io repite en sus otras APIs (API-Football,
API-Basketball) y en resultados de búsqueda, NO en una verificación directa
contra la API real. Antes de confiar en la ingesta para datos reales,
correr `python debug_nba_api.py` (requiere NBA_API_KEY) y comparar la
respuesta cruda con los nombres usados en cargar_temporada_nba.py /
actualizar_estadisticas_jugadores_nba.py — ajustar ahí si no calzan.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["NBA_API_KEY"]
BASE_URL = "https://v2.nba.api-sports.io"
headers = {"x-apisports-key": API_KEY}


def get_nba(endpoint: str, params: dict | None = None) -> list:
    """GET a un endpoint de API-NBA; devuelve la lista en "response" o []
    si la API reporta un error (plan sin acceso, parámetros inválidos, etc.
    api-sports.io responde HTTP 200 incluso en esos casos — el motivo viene
    en "errors")."""
    respuesta = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params or {})

    if respuesta.status_code != 200:
        print(f"Error al conectar con {endpoint}: {respuesta.status_code} - {respuesta.text}")
        return []

    datos = respuesta.json()
    errores = datos.get("errors")
    if errores:
        print(f"La API rechazó la solicitud a {endpoint}: {errores}")
        return []

    return datos.get("response", [])

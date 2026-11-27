"""
Cliente mínimo compartido para la NBA, usado por cargar_temporada_nba.py y
actualizar_estadisticas_jugadores_nba.py.

Usa API-Basketball de api-sports.io (https://v1.basketball.api-sports.io),
filtrada a la liga NBA (LEAGUE_ID_NBA = 12) — NO el producto "API-NBA"
dedicado (v2.nba.api-sports.io), que es otra suscripción aparte. Reusamos
API_FOOTBALL_KEY porque api-sports.io usa una sola key por cuenta,
compartida entre todos sus productos; lo que varía es el plan contratado
en cada uno (fútbol y básquet ya están en Pro).

Esquema confirmado a mano contra la API real el 2026-11-27 (ver
conversación): /games trae teams.home/away, scores.home/away.total,
status.long ("Game Finished"); /games/statistics/players trae
player.name (un solo campo), field_goals/threepoint_goals/freethrows_goals
como {total, attempts, percentage}, rebounds.total (sin offense/defense),
assists y points — pero NO steals/blocks/turnovers a nivel de jugador.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["API_FOOTBALL_KEY"]
BASE_URL = "https://v1.basketball.api-sports.io"
LEAGUE_ID_NBA = 12
headers = {"x-apisports-key": API_KEY}


def get_nba(endpoint: str, params: dict | None = None) -> list:
    """GET a un endpoint de API-Basketball; devuelve la lista en "response" o
    [] si la API reporta un error (plan sin acceso, parámetros inválidos,
    etc. — api-sports.io responde HTTP 200 incluso en esos casos, el motivo
    viene en "errors")."""
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

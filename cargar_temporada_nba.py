"""
Descarga equipos y partidos de la NBA (temporada regular + playoffs, vía
league=standard) usando API-NBA y los guarda en apuestas.db
(nba_teams / nba_games).

SIN VERIFICAR CONTRA LA API REAL todavía (ver nba_api_client.py): se asume
que /games usa teams.home / teams.visitors (terminología típica de NBA,
distinta del home/away de API-Football) y que scores.home.points /
scores.visitors.points traen el puntaje final. Correr primero
`python debug_nba_api.py` con la NBA_API_KEY real y comparar antes de
confiar en una corrida completa.

Ejecutar:
    python cargar_temporada_nba.py [season]
"""

import sqlite3
import sys
from datetime import date

from crear_db_basquet import inicializar_base_datos_basquet
from nba_api_client import get_nba


def temporada_actual_nba() -> int:
    """La temporada NBA arranca en octubre; antes de eso seguimos
    considerando vigente la temporada iniciada el año anterior."""
    hoy = date.today()
    return hoy.year if hoy.month >= 9 else hoy.year - 1


def guardar_equipos() -> None:
    equipos = get_nba("teams", {"league": "standard"})
    conn = sqlite3.connect("apuestas.db")
    cursor = conn.cursor()
    for equipo in equipos:
        cursor.execute(
            "INSERT OR REPLACE INTO nba_teams (id, name) VALUES (?, ?)",
            (equipo["id"], equipo["name"]),
        )
    conn.commit()
    conn.close()
    print(f"{len(equipos)} equipos NBA guardados.")


def guardar_partidos(season: int) -> None:
    partidos = get_nba("games", {"season": season, "league": "standard"})
    if not partidos:
        print(f"No se encontraron partidos NBA para la temporada {season}.")
        return

    conn = sqlite3.connect("apuestas.db")
    cursor = conn.cursor()

    guardados = 0
    for partido in partidos:
        home = partido["teams"]["home"]
        visitante = partido["teams"]["visitors"]

        cursor.execute(
            "INSERT OR REPLACE INTO nba_teams (id, name) VALUES (?, ?)",
            (home["id"], home["name"]),
        )
        cursor.execute(
            "INSERT OR REPLACE INTO nba_teams (id, name) VALUES (?, ?)",
            (visitante["id"], visitante["name"]),
        )

        cursor.execute(
            """
            INSERT OR REPLACE INTO nba_games
                (id, date, season, home_team_id, away_team_id, status, home_points, away_points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                partido["id"],
                partido["date"]["start"],
                season,
                home["id"],
                visitante["id"],
                partido["status"]["long"],
                partido["scores"]["home"]["points"],
                partido["scores"]["visitors"]["points"],
            ),
        )
        guardados += 1

    conn.commit()
    conn.close()
    print(f"{guardados} partidos NBA guardados para la temporada {season}.")


def cargar_temporada_nba(season: int | None = None) -> None:
    season = season or temporada_actual_nba()
    print(f"NBA, temporada {season}")
    inicializar_base_datos_basquet()
    guardar_equipos()
    guardar_partidos(season)


if __name__ == "__main__":
    season_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    cargar_temporada_nba(season_arg)

"""
Crea (si no existen) las tablas de básquetbol NBA en la misma apuestas.db que
ya usa el módulo de fútbol — tablas separadas (prefijo nba_) para no chocar
con teams/matches de fútbol.

Fuente de datos: API-Basketball de api-sports.io
(https://v1.basketball.api-sports.io), filtrada a la liga NBA (id 12) —
mismo API_FOOTBALL_KEY que el fútbol, porque api-sports.io usa una sola
key por cuenta compartida entre todos sus productos (solo cambia el plan
contratado por producto; este ya está en Pro).

El boxscore por jugador de esta API NO trae robos ni tapones, así que
double_double/triple_double se calculan aproximando con 3 categorías
(puntos, rebotes, asistencias) en vez de las 5 oficiales — ver
actualizar_estadisticas_jugadores_nba.py.

nba_player_game_stats guarda double_double/triple_double ya calculados
(no se derivan al vuelo) porque se usan muy seguido en los reportes y
conviene no recalcular el conteo de categorías >=10 en cada consulta.
"""

import sqlite3


def inicializar_base_datos_basquet() -> None:
    conn = sqlite3.connect("apuestas.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nba_teams (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nba_games (
            id INTEGER PRIMARY KEY,
            date TEXT,
            season TEXT,
            home_team_id INTEGER,
            away_team_id INTEGER,
            status TEXT,
            home_points INTEGER,
            away_points INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nba_players (
            id INTEGER PRIMARY KEY,
            name TEXT,
            team_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nba_player_game_stats (
            game_id INTEGER,
            player_id INTEGER,
            team_id INTEGER,
            points INTEGER,
            three_made INTEGER,
            three_att INTEGER,
            assists INTEGER,
            rebounds_off INTEGER,
            rebounds_def INTEGER,
            rebounds_tot INTEGER,
            steals INTEGER,
            blocks INTEGER,
            turnovers INTEGER,
            minutes TEXT,
            double_double INTEGER,
            triple_double INTEGER,
            PRIMARY KEY (game_id, player_id)
        )
    """)

    conn.commit()
    conn.close()
    print("Tablas de básquetbol (NBA) listas en 'apuestas.db'.")


if __name__ == "__main__":
    inicializar_base_datos_basquet()

import os
import sqlite3
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["API_FOOTBALL_KEY"]
BASE_URL = "https://v3.football.api-sports.io"

headers = {
    'x-apisports-key': API_KEY
}


def temporada_actual_premier_league() -> int:
    """La temporada de la Premier League arranca en agosto; antes de eso
    seguimos considerando vigente la temporada del año anterior."""
    hoy = date.today()
    return hoy.year if hoy.month >= 7 else hoy.year - 1


def inicializar_base_datos():
    conn = sqlite3.connect("apuestas.db")
    cursor = conn.cursor()

    # Creamos la tabla de equipos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY,
            name TEXT,
            country TEXT
        )
    """)

    # Creamos la tabla de partidos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY,
            date TEXT,
            league_id INTEGER,
            season INTEGER,
            home_team_id INTEGER,
            away_team_id INTEGER,
            status TEXT,
            home_goals INTEGER,
            away_goals INTEGER
        )
    """)

    conn.commit()
    conn.close()
    print("¡Base de datos 'apuestas.db' creada con éxito en tu PC!")


def descargar_y_guardar_partidos(league_id, season):
    url = f"{BASE_URL}/fixtures"
    params = {
        "league": league_id,
        "season": season
    }

    print(f"Conectando con la API para traer partidos (Liga ID: {league_id}, Temporada: {season})...")
    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Error al conectar: {response.status_code} - {response.text}")
        return

    data = response.json()

    # api-sports.io devuelve HTTP 200 incluso cuando tu plan no tiene acceso
    # a la temporada pedida; el motivo viene en "errors", no en el status code.
    errores = data.get("errors")
    if errores:
        print(f"La API rechazó la solicitud: {errores}")
        print("Si el motivo menciona tu plan, usa una de las temporadas que sí cubre (revisa el mensaje de arriba).")
        return

    fixtures = data.get("response", [])

    if not fixtures:
        print("No se encontraron partidos para esos datos.")
        return

    conn = sqlite3.connect("apuestas.db")
    cursor = conn.cursor()

    guardados = 0
    for match in fixtures:
        match_id = match['fixture']['id']
        date_ = match['fixture']['date']
        status = match['fixture']['status']['short']
        season_ = match['league']['season']

        home_team_id = match['teams']['home']['id']
        home_team_name = match['teams']['home']['name']

        away_team_id = match['teams']['away']['id']
        away_team_name = match['teams']['away']['name']

        home_goals = match['goals']['home']
        away_goals = match['goals']['away']

        cursor.execute("INSERT OR REPLACE INTO teams (id, name) VALUES (?, ?)", (home_team_id, home_team_name))
        cursor.execute("INSERT OR REPLACE INTO teams (id, name) VALUES (?, ?)", (away_team_id, away_team_name))

        cursor.execute("""
            INSERT OR REPLACE INTO matches (id, date, league_id, season, home_team_id, away_team_id, status, home_goals, away_goals)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (match_id, date_, league_id, season_, home_team_id, away_team_id, status, home_goals, away_goals))

        guardados += 1

    conn.commit()
    conn.close()
    print(f"¡Listo! Se guardaron {guardados} partidos en tu base de datos.")


if __name__ == "__main__":
    inicializar_base_datos()
    # Piloto: Premier League (ID 39), temporada vigente calculada automáticamente
    descargar_y_guardar_partidos(league_id=39, season=temporada_actual_premier_league())

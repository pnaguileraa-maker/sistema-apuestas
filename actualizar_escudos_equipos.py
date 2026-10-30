"""
Descarga los escudos (logos) y el país de los equipos de la Premier League
desde api-football y los guarda en teams.logo_url / teams.country. Solo
hace falta correrlo una vez por temporada (casi no cambian).

Ejecutar:
    python actualizar_escudos_equipos.py
"""

import sqlite3

import requests

from crear_db_y_partidos import API_KEY, BASE_URL, temporada_actual_premier_league

PREMIER_LEAGUE_ID = 39

headers = {
    "x-apisports-key": API_KEY,
}


def asegurar_columnas(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    columnas_existentes = {fila[1] for fila in cursor.execute("PRAGMA table_info(teams)")}
    if "logo_url" not in columnas_existentes:
        cursor.execute("ALTER TABLE teams ADD COLUMN logo_url TEXT")
    if "country" not in columnas_existentes:
        cursor.execute("ALTER TABLE teams ADD COLUMN country TEXT")
    conn.commit()


def actualizar_escudos(season: int, league_id: int = PREMIER_LEAGUE_ID) -> None:
    conn = sqlite3.connect("apuestas.db")
    asegurar_columnas(conn)
    cursor = conn.cursor()

    print(f"Consultando equipos de la liga {league_id} (temporada {season})...")
    response = requests.get(
        f"{BASE_URL}/teams",
        headers=headers,
        params={"league": league_id, "season": season},
    )

    if response.status_code != 200:
        print(f"Error al conectar: {response.status_code} - {response.text}")
        conn.close()
        return

    equipos = response.json().get("response", [])
    if not equipos:
        print("La API no devolvió equipos para esa liga/temporada.")
        conn.close()
        return

    for item in equipos:
        team = item["team"]
        cursor.execute(
            "UPDATE teams SET logo_url = ?, country = ? WHERE id = ?",
            (team["logo"], team["country"], team["id"]),
        )

    conn.commit()
    conn.close()
    print(f"¡Listo! Escudos y país actualizados para {len(equipos)} equipos.")


if __name__ == "__main__":
    actualizar_escudos(season=temporada_actual_premier_league())

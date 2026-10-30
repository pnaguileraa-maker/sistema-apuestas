"""
Rellena córners, tarjetas y tiros al arco por partido (home/away) llamando a
/fixtures/statistics de api-sports.io, un partido a la vez.

⚠️ Este script SÍ consume tu cuota de la API (una llamada por cada partido
   pendiente). Con el plan Pro (7500 llamadas/día, 300/minuto) una temporada
   completa (~380 partidos) se procesa de sobra en una sola corrida. Igual
   solo procesa los partidos que todavía no tienen estadísticas
   (stats_checked = 0), así que es seguro detenerlo y volver a correrlo.

Ejecutar:
    python actualizar_estadisticas_partidos.py
"""

import sqlite3
import time

import requests

from crear_db_y_partidos import API_KEY, BASE_URL, temporada_actual_premier_league

PREMIER_LEAGUE_ID = 39
SEGUNDOS_ENTRE_LLAMADAS = 0.3  # ~200 llamadas/min, con margen bajo el límite de 300/min del plan Pro

headers = {
    'x-apisports-key': API_KEY
}


def asegurar_columnas_estadisticas(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    columnas_existentes = {fila[1] for fila in cursor.execute("PRAGMA table_info(matches)")}

    columnas_nuevas = {
        "home_corners": "INTEGER",
        "away_corners": "INTEGER",
        "home_yellow_cards": "INTEGER",
        "home_red_cards": "INTEGER",
        "away_yellow_cards": "INTEGER",
        "away_red_cards": "INTEGER",
        "home_shots_on_target": "INTEGER",
        "away_shots_on_target": "INTEGER",
        "stats_checked": "INTEGER DEFAULT 0",
    }

    # Si "home_shots_on_target" es nueva, los partidos ya marcados como
    # stats_checked = 1 nunca llegaron a pedirle este dato a la API: hay que
    # reabrirlos para que la próxima corrida los vuelva a pedir (misma
    # llamada a /fixtures/statistics, así que no gasta cuota extra).
    es_columna_nueva = "home_shots_on_target" not in columnas_existentes

    for columna, tipo in columnas_nuevas.items():
        if columna not in columnas_existentes:
            cursor.execute(f"ALTER TABLE matches ADD COLUMN {columna} {tipo}")

    if es_columna_nueva:
        cursor.execute("UPDATE matches SET stats_checked = 0 WHERE status = 'FT'")

    conn.commit()


def extraer_valor(estadisticas: list[dict], tipo: str) -> int | None:
    for item in estadisticas:
        if item.get("type") == tipo:
            valor = item.get("value")
            return int(valor) if valor is not None else None
    return None


def obtener_estadisticas_partido(fixture_id: int) -> dict | None:
    response = requests.get(
        f"{BASE_URL}/fixtures/statistics",
        headers=headers,
        params={"fixture": fixture_id},
    )

    if response.status_code != 200:
        print(f"  Error al conectar (fixture {fixture_id}): {response.status_code}")
        return None

    bloques = response.json().get("response", [])
    if len(bloques) != 2:
        # Algunos partidos antiguos no tienen estadísticas disponibles en la API
        return None

    por_equipo = {}
    for bloque in bloques:
        team_id = bloque["team"]["id"]
        stats = bloque["statistics"]
        por_equipo[team_id] = {
            "corners": extraer_valor(stats, "Corner Kicks"),
            "yellow": extraer_valor(stats, "Yellow Cards"),
            "red": extraer_valor(stats, "Red Cards"),
            "shots_on_target": extraer_valor(stats, "Shots on Goal"),
        }
    return por_equipo


def actualizar_estadisticas(league_id: int, season: int) -> None:
    conn = sqlite3.connect("apuestas.db")
    asegurar_columnas_estadisticas(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, home_team_id, away_team_id FROM matches
        WHERE league_id = ? AND season = ? AND status = 'FT'
          AND (stats_checked IS NULL OR stats_checked = 0)
        """,
        (league_id, season),
    )
    pendientes = cursor.fetchall()

    if not pendientes:
        print("No hay partidos pendientes de estadísticas para esa liga/temporada.")
        conn.close()
        return

    print(f"Actualizando estadísticas de {len(pendientes)} partidos (Liga {league_id}, Temporada {season})...")

    for indice, (fixture_id, home_team_id, away_team_id) in enumerate(pendientes, start=1):
        por_equipo = obtener_estadisticas_partido(fixture_id)

        if por_equipo is None:
            cursor.execute("UPDATE matches SET stats_checked = 1 WHERE id = ?", (fixture_id,))
        else:
            home = por_equipo.get(home_team_id, {})
            away = por_equipo.get(away_team_id, {})
            cursor.execute(
                """
                UPDATE matches SET
                    home_corners = ?, away_corners = ?,
                    home_yellow_cards = ?, home_red_cards = ?,
                    away_yellow_cards = ?, away_red_cards = ?,
                    home_shots_on_target = ?, away_shots_on_target = ?,
                    stats_checked = 1
                WHERE id = ?
                """,
                (
                    home.get("corners"), away.get("corners"),
                    home.get("yellow"), home.get("red"),
                    away.get("yellow"), away.get("red"),
                    home.get("shots_on_target"), away.get("shots_on_target"),
                    fixture_id,
                ),
            )

        conn.commit()
        print(f"  [{indice}/{len(pendientes)}] Partido {fixture_id} procesado.")
        time.sleep(SEGUNDOS_ENTRE_LLAMADAS)

    conn.close()
    print("¡Listo! Vuelve a correr este script más tarde si tu cuota diaria se agotó a mitad de camino.")


if __name__ == "__main__":
    actualizar_estadisticas(league_id=PREMIER_LEAGUE_ID, season=temporada_actual_premier_league())

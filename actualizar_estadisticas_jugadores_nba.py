"""
Rellena el boxscore por jugador de cada partido NBA terminado, llamando a
/games/statistics/players?id=<game_id> de API-Basketball (api-sports.io).

Esta API NO trae robos ni tapones por jugador (solo field_goals,
threepoint_goals, freethrows_goals, rebounds.total, assists y points), así
que double_double/triple_double se calculan aproximando con 3 categorías
en vez de las 5 oficiales (puntos, rebotes totales, asistencias) — cubre
la gran mayoría de los casos reales pero no el 100%. Decisión explícita
del usuario (2026-11-27) para no pagar una suscripción aparte a API-NBA
solo por esas dos categorías.

⚠️ Consume cuota de la API: una llamada por partido pendiente. Solo procesa
partidos sin stats_checked = 1, así que es seguro detenerlo y reanudarlo.

Ejecutar:
    python actualizar_estadisticas_jugadores_nba.py
"""

import sqlite3
import time

from nba_api_client import get_nba

SEGUNDOS_ENTRE_LLAMADAS = 0.3
ESTADOS_TERMINADO = ("Game Finished", "After Over Time")


def asegurar_columna_stats_checked(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    columnas = {fila[1] for fila in cursor.execute("PRAGMA table_info(nba_games)")}
    if "stats_checked" not in columnas:
        cursor.execute("ALTER TABLE nba_games ADD COLUMN stats_checked INTEGER DEFAULT 0")
        conn.commit()


def contar_doble_triple(puntos: int, rebotes: int, asistencias: int) -> tuple[int, int]:
    categorias_en_doble_digito = sum(1 for valor in (puntos, rebotes, asistencias) if valor >= 10)
    return int(categorias_en_doble_digito >= 2), int(categorias_en_doble_digito >= 3)


def actualizar_estadisticas_jugadores() -> None:
    conn = sqlite3.connect("apuestas.db")
    asegurar_columna_stats_checked(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id FROM nba_games
        WHERE status IN (?, ?) AND (stats_checked IS NULL OR stats_checked = 0)
        """,
        ESTADOS_TERMINADO,
    )
    pendientes = [fila[0] for fila in cursor.fetchall()]

    if not pendientes:
        print("No hay partidos NBA pendientes de estadísticas de jugadores.")
        conn.close()
        return

    print(f"Actualizando boxscore de jugadores de {len(pendientes)} partidos NBA...")

    for indice, game_id in enumerate(pendientes, start=1):
        filas = get_nba("games/statistics/players", {"id": game_id})

        for fila in filas:
            puntos = fila.get("points") or 0
            rebotes = (fila.get("rebounds") or {}).get("total") or 0
            asistencias = fila.get("assists") or 0
            doble, triple = contar_doble_triple(puntos, rebotes, asistencias)

            jugador = fila["player"]
            equipo = fila["team"]
            triples = fila.get("threepoint_goals") or {}

            cursor.execute(
                "INSERT OR REPLACE INTO nba_players (id, name, team_id) VALUES (?, ?, ?)",
                (jugador["id"], jugador["name"], equipo["id"]),
            )
            cursor.execute(
                """
                INSERT OR REPLACE INTO nba_player_game_stats
                    (game_id, player_id, team_id, points, three_made, three_att, assists,
                     rebounds_off, rebounds_def, rebounds_tot, steals, blocks, turnovers,
                     minutes, double_double, triple_double)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    game_id, jugador["id"], equipo["id"],
                    puntos, triples.get("total"), triples.get("attempts"), asistencias,
                    None, None, rebotes,
                    None, None, None,
                    fila.get("minutes"), doble, triple,
                ),
            )

        cursor.execute("UPDATE nba_games SET stats_checked = 1 WHERE id = ?", (game_id,))
        conn.commit()
        print(f"  [{indice}/{len(pendientes)}] Partido {game_id}: {len(filas)} jugadores procesados.")
        time.sleep(SEGUNDOS_ENTRE_LLAMADAS)

    conn.close()
    print("¡Listo! Vuelve a correr este script más tarde si tu cuota diaria se agotó a mitad de camino.")


if __name__ == "__main__":
    actualizar_estadisticas_jugadores()

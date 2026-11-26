"""
Rellena el boxscore por jugador de cada partido NBA terminado, llamando a
/players/statistics?game=<id> de API-NBA (api-sports.io), y calcula
double_double / triple_double a partir de los conteos de puntos, rebotes
totales, asistencias, robos y tapones.

SIN VERIFICAR CONTRA LA API REAL todavía — ver aviso en nba_api_client.py.
Correr `python debug_nba_api.py` primero con la NBA_API_KEY real.

⚠️ Consume cuota de la API: una llamada por partido pendiente. Solo procesa
partidos sin stats_checked = 1, así que es seguro detenerlo y reanudarlo.

Ejecutar:
    python actualizar_estadisticas_jugadores_nba.py
"""

import sqlite3
import time

from nba_api_client import get_nba

SEGUNDOS_ENTRE_LLAMADAS = 0.3
CATEGORIAS_DOBLE = ("points", "totReb", "assists", "steals", "blocks")


def asegurar_columna_stats_checked(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    columnas = {fila[1] for fila in cursor.execute("PRAGMA table_info(nba_games)")}
    if "stats_checked" not in columnas:
        cursor.execute("ALTER TABLE nba_games ADD COLUMN stats_checked INTEGER DEFAULT 0")
        conn.commit()


def contar_doble_triple(fila: dict) -> tuple[int, int]:
    categorias_en_doble_digito = sum(1 for cat in CATEGORIAS_DOBLE if (fila.get(cat) or 0) >= 10)
    return int(categorias_en_doble_digito >= 2), int(categorias_en_doble_digito >= 3)


def actualizar_estadisticas_jugadores() -> None:
    conn = sqlite3.connect("apuestas.db")
    asegurar_columna_stats_checked(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id FROM nba_games
        WHERE status = 'Finished' AND (stats_checked IS NULL OR stats_checked = 0)
        """
    )
    pendientes = [fila[0] for fila in cursor.fetchall()]

    if not pendientes:
        print("No hay partidos NBA pendientes de estadísticas de jugadores.")
        conn.close()
        return

    print(f"Actualizando boxscore de jugadores de {len(pendientes)} partidos NBA...")

    for indice, game_id in enumerate(pendientes, start=1):
        filas = get_nba("players/statistics", {"game": game_id})

        for fila in filas:
            doble, triple = contar_doble_triple(fila)
            jugador = fila["player"]
            equipo = fila["team"]
            nombre = f"{jugador['firstname']} {jugador['lastname']}"

            cursor.execute(
                "INSERT OR REPLACE INTO nba_players (id, name, team_id) VALUES (?, ?, ?)",
                (jugador["id"], nombre, equipo["id"]),
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
                    fila.get("points"), fila.get("tpm"), fila.get("tpa"), fila.get("assists"),
                    fila.get("offReb"), fila.get("defReb"), fila.get("totReb"),
                    fila.get("steals"), fila.get("blocks"), fila.get("turnovers"),
                    fila.get("min"), doble, triple,
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

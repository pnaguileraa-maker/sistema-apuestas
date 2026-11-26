"""
Motor estadístico de jugadores NBA: para cada stat (puntos, triples,
asistencias, rebotes) calcula una línea cercana al promedio del jugador y el
% de partidos que la supera, más la tasa de doble-doble y triple-doble.
Se calcula 100% desde nba_player_game_stats + nba_games (apuestas.db); lo
reutiliza enviar_telegram_basquet.py.

La línea de cada stat se fija "justo debajo" del promedio redondeado del
jugador (ver _linea_desde_promedio) — igual que un mercado de casa de
apuestas suele poner la línea cerca del promedio real, en vez de usar un
número fijo para todos los jugadores (a diferencia de la línea de puntos
totales de equipo en analizar_basquet.py, que sí es fija para todos).

Ejecutar manualmente para ver un reporte de candidatos por consola:
    python analizar_jugadores_basquet.py
"""

import sqlite3

MIN_PARTIDOS_JUGADOR = 10  # muestra mínima para confiar en un %
UMBRAL_MOSTRAR_JUGADOR = 60.0  # % mínimo para considerar una selección de prop

STATS_JUGADOR = {
    "points": "Puntos",
    "three_made": "Triples",
    "assists": "Asistencias",
    "rebounds_tot": "Rebotes",
}


def _linea_desde_promedio(promedio: float) -> float:
    """Línea .5 apenas debajo del promedio, redondeado al medio punto más
    cercano (ej: promedio 24.3 -> línea 24.0; promedio 24.8 -> línea 24.5)."""
    return round(promedio * 2) / 2 - 0.5


def _partidos_jugador(player_id: int, season: int) -> list[sqlite3.Row]:
    conn = sqlite3.connect("apuestas.db")
    conn.row_factory = sqlite3.Row
    filas = conn.execute(
        """
        SELECT s.points, s.three_made, s.assists, s.rebounds_tot,
               s.double_double, s.triple_double
        FROM nba_player_game_stats s
        JOIN nba_games g ON g.id = s.game_id
        WHERE s.player_id = ? AND g.season = ?
        """,
        (player_id, season),
    ).fetchall()
    conn.close()
    return filas


def perfil_jugador_nba(player_id: int, season: int) -> dict | None:
    conn = sqlite3.connect("apuestas.db")
    fila = conn.execute("SELECT name, team_id FROM nba_players WHERE id = ?", (player_id,)).fetchone()
    conn.close()
    if fila is None:
        return None
    nombre, team_id = fila

    partidos = _partidos_jugador(player_id, season)
    jugados = len(partidos)
    if jugados < MIN_PARTIDOS_JUGADOR:
        return None

    props = {}
    for columna, etiqueta in STATS_JUGADOR.items():
        valores = [p[columna] for p in partidos if p[columna] is not None]
        if not valores:
            continue
        promedio = sum(valores) / len(valores)
        linea = _linea_desde_promedio(promedio)
        sobre_linea = sum(1 for v in valores if v > linea)
        props[columna] = {
            "etiqueta": etiqueta,
            "promedio": round(promedio, 1),
            "linea": linea,
            "overPct": round(sobre_linea / len(valores) * 100, 1),
        }

    return {
        "playerId": player_id,
        "playerName": nombre,
        "teamId": team_id,
        "played": jugados,
        "props": props,
        "doubleDoublePct": round(sum(p["double_double"] for p in partidos) / jugados * 100, 1),
        "tripleDoublePct": round(sum(p["triple_double"] for p in partidos) / jugados * 100, 1),
    }


def elegir_top_props_jugador(perfil: dict, top: int = 3) -> list[dict]:
    """Selecciones (stat + línea + % estimado) de un jugador, ordenadas de
    mayor a menor probabilidad y filtradas por UMBRAL_MOSTRAR_JUGADOR."""
    selecciones = [
        {"etiqueta": f"Más de {datos['linea']} {datos['etiqueta']}", "probabilidad": datos["overPct"]}
        for datos in perfil["props"].values()
    ]
    if perfil["doubleDoublePct"] >= UMBRAL_MOSTRAR_JUGADOR:
        selecciones.append({"etiqueta": "Doble-doble", "probabilidad": perfil["doubleDoublePct"]})
    if perfil["tripleDoublePct"] >= UMBRAL_MOSTRAR_JUGADOR:
        selecciones.append({"etiqueta": "Triple-doble", "probabilidad": perfil["tripleDoublePct"]})

    selecciones = [s for s in selecciones if s["probabilidad"] >= UMBRAL_MOSTRAR_JUGADOR]
    selecciones.sort(key=lambda s: s["probabilidad"], reverse=True)
    return selecciones[:top]


def analizar_candidatos_jugadores(season: int) -> None:
    conn = sqlite3.connect("apuestas.db")
    jugadores = conn.execute("SELECT id FROM nba_players").fetchall()
    conn.close()

    print("\n" + "=" * 70)
    print(f" NBA — PROPS DE JUGADORES CON >= {UMBRAL_MOSTRAR_JUGADOR}% DE ACIERTO HISTORICO")
    print("=" * 70)

    for (player_id,) in jugadores:
        perfil = perfil_jugador_nba(player_id, season)
        if perfil is None:
            continue
        for seleccion in elegir_top_props_jugador(perfil, top=len(STATS_JUGADOR) + 2):
            print(f"{perfil['playerName']:<25} | {seleccion['etiqueta']:<20} | {seleccion['probabilidad']}%")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    from cargar_temporada_nba import temporada_actual_nba

    analizar_candidatos_jugadores(temporada_actual_nba())

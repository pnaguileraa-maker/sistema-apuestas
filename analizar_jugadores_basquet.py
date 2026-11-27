"""
Motor estadístico de jugadores NBA: para cada stat (puntos, triples,
asistencias, rebotes) calcula una línea cercana al promedio del jugador y el
% de partidos que la supera, más la tasa de doble-doble y triple-doble.
Se calcula 100% desde nba_player_game_stats + nba_games (apuestas.db); lo
reutiliza enviar_telegram_basquet.py.

La línea de cada stat se fija con un margen real debajo del promedio del
jugador (ver _linea_desde_promedio), no pegada al promedio — una línea
puesta justo en el promedio da ~50% de probabilidad sin importar lo
dominante que sea el jugador (la mitad de sus partidos quedan arriba, la
mitad abajo, por pura definición de promedio). Con margen, un anotador
consistente de alto volumen (ej. 34 puntos de promedio) sí aparece con
una probabilidad alta de "sí calificarla" — que es lo que lo hace un pick
atractivo — en vez de quedar en un empate técnico.

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


FACTOR_LINEA = 0.85  # margen real bajo el promedio (ver docstring del módulo)


def _linea_desde_promedio(promedio: float) -> float:
    """Línea .5 con margen real bajo el promedio (ej: promedio 33.9 ->
    línea 28.5, no 33.5). Nunca baja de 0.5: una línea <= 0 no es un
    mercado real (un stat que siempre es >= 0 la cumpliría siempre, dando
    un "100%" sin sentido)."""
    return max(0.5, round(promedio * FACTOR_LINEA * 2) / 2 - 0.5)


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


def jugadores_del_equipo(team_id: int, season: int) -> list[dict]:
    """Perfil de todos los jugadores del equipo con muestra suficiente."""
    conn = sqlite3.connect("apuestas.db")
    jugadores = conn.execute("SELECT id FROM nba_players WHERE team_id = ?", (team_id,)).fetchall()
    conn.close()
    return [p for (player_id,) in jugadores if (p := perfil_jugador_nba(player_id, season)) is not None]


UMBRAL_PICK_PARTIDO = 55.0  # % mínimo para que un jugador cuente como pick seguro de un indicador
MAX_PICKS_POR_STAT = 4  # tope por indicador para no listar a todo el plantel que raspa el umbral

# Promedio mínimo para que el indicador sea relevante — sin esto, un
# suplente que promedia 1.7 puntos "supera el 70%" una línea de 1.0, lo
# cual es estadísticamente cierto pero no es un pick de puntos que le
# sirva a nadie. Valores aproximados a lo que un analista consideraría
# "producción real" en cada categoría.
PROMEDIO_MINIMO_STAT = {
    "points": 10.0,
    "three_made": 1.5,
    "assists": 3.0,
    "rebounds_tot": 4.0,
}


def mejores_picks_partido(equipos: list[tuple[int, str]], season: int, lesionados: dict | None = None) -> dict:
    """Decisión de analista: TODOS los jugadores (de cualquiera de los dos
    equipos) que superan UMBRAL_PICK_PARTIDO en cada indicador (puntos,
    triples, asistencias, rebotes, doble-doble, triple-doble) y además
    tienen un promedio real en esa categoría (ver PROMEDIO_MINIMO_STAT),
    ordenados de mayor a menor probabilidad — no uno solo, para no dejar
    afuera a otro jugador que también es un pick seguro. Si nadie califica
    en un indicador, esa categoría queda vacía en vez de forzar un pick de
    baja confianza o irrelevante.

    `lesionados` (mismo formato que lesionados_nba.obtener_lesionados()) es
    obligatorio en la práctica: un jugador confirmado "Out" se excluye por
    completo — no tiene sentido recomendar una apuesta sobre alguien que no
    va a jugar. Los "Day-To-Day" sí se incluyen (pueden jugar) pero quedan
    marcados con "alerta" para que se avise la duda en vez de esconderla."""
    lesionados = lesionados or {}

    def _estado_jugador(team_name: str, nombre: str) -> str | None:
        bajas_equipo = lesionados.get(team_name, [])
        for baja in bajas_equipo:
            if baja["jugador"] == nombre:
                return baja["estado"]

        # Fallback por apellido: ESPN a veces usa un apodo como primer
        # nombre (ej. "Anunoby OG" vs "Anunoby Ogugua" en nuestra base) y
        # el match exacto falla aunque sea la misma persona. Solo se usa
        # si el apellido es único en la lista de bajas del equipo, para no
        # confundir a dos jugadores distintos con el mismo apellido.
        apellido = nombre.split()[0]
        coincidencias = [b for b in bajas_equipo if b["jugador"].split()[0] == apellido]
        if len(coincidencias) == 1:
            return coincidencias[0]["estado"]
        return None

    candidatos_stat = {stat_key: [] for stat_key in STATS_JUGADOR}
    candidatos_dd, candidatos_td = [], []

    for team_id, team_name in equipos:
        for perfil in jugadores_del_equipo(team_id, season):
            estado = _estado_jugador(team_name, perfil["playerName"])
            if estado == "Out":
                continue  # confirmado afuera: no tiene sentido recomendarlo

            alerta = {"alerta": estado} if estado else {}

            for stat_key in STATS_JUGADOR:
                datos = perfil["props"].get(stat_key)
                if datos is not None and datos["promedio"] >= PROMEDIO_MINIMO_STAT[stat_key]:
                    candidatos_stat[stat_key].append(
                        {"jugador": perfil["playerName"], "equipo": team_name, "probabilidad": datos["overPct"], **datos, **alerta}
                    )
            if perfil["doubleDoublePct"] > 0:
                candidatos_dd.append({"jugador": perfil["playerName"], "equipo": team_name, "probabilidad": perfil["doubleDoublePct"], **alerta})
            if perfil["tripleDoublePct"] > 0:
                candidatos_td.append({"jugador": perfil["playerName"], "equipo": team_name, "probabilidad": perfil["tripleDoublePct"], **alerta})

    def _filtrar(candidatos: list[dict]) -> list[dict]:
        calificados = [c for c in candidatos if c["probabilidad"] >= UMBRAL_PICK_PARTIDO]
        calificados.sort(key=lambda c: c["probabilidad"], reverse=True)
        return calificados[:MAX_PICKS_POR_STAT]

    picks = {stat_key: _filtrar(candidatos_stat[stat_key]) for stat_key in STATS_JUGADOR}
    picks["doble_doble"] = _filtrar(candidatos_dd)
    picks["triple_doble"] = _filtrar(candidatos_td)
    return picks


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


def _partidos_con_y_sin(team_id: int, jugador_id: int, season: int) -> tuple[set, set]:
    """IDs de partidos TERMINADOS del equipo esta temporada, separados entre
    los que jugador_id jugó y los que no (no hay fila de stats para él)."""
    conn = sqlite3.connect("apuestas.db")
    partidos_equipo = {
        fila[0]
        for fila in conn.execute(
            """
            SELECT id FROM nba_games
            WHERE season = ? AND (home_team_id = ? OR away_team_id = ?) AND home_points IS NOT NULL
            """,
            (season, team_id, team_id),
        ).fetchall()
    }
    jugo = {
        fila[0] for fila in conn.execute("SELECT game_id FROM nba_player_game_stats WHERE player_id = ?", (jugador_id,)).fetchall()
    }
    conn.close()
    jugo = jugo & partidos_equipo
    return jugo, partidos_equipo - jugo


def companeros_que_podrian_absorber(
    team_id: int, jugador_ausente_id: int, season: int, stat: str = "points", min_partidos: int = 2
) -> list[dict]:
    """Compañeros del jugador ausente cuyo promedio de `stat` sube en los
    partidos donde él NO jugó esta temporada, respecto a cuando sí jugó.
    Muestra chica (min_partidos por defecto) porque una baja reciente no
    deja mucho historial sin el jugador — es una señal exploratoria, no una
    certeza estadística."""
    jugo, no_jugo = _partidos_con_y_sin(team_id, jugador_ausente_id, season)
    if len(no_jugo) < min_partidos or len(jugo) < min_partidos:
        return []

    conn = sqlite3.connect("apuestas.db")
    filas = conn.execute(
        f"SELECT player_id, game_id, {stat} FROM nba_player_game_stats WHERE team_id = ?",
        (team_id,),
    ).fetchall()
    conn.close()

    por_jugador: dict[int, dict[str, list]] = {}
    for player_id, game_id, valor in filas:
        if player_id == jugador_ausente_id or valor is None:
            continue
        splits = por_jugador.setdefault(player_id, {"con": [], "sin": []})
        if game_id in jugo:
            splits["con"].append(valor)
        elif game_id in no_jugo:
            splits["sin"].append(valor)

    conn = sqlite3.connect("apuestas.db")
    resultado = []
    for player_id, splits in por_jugador.items():
        if len(splits["con"]) < min_partidos or len(splits["sin"]) < min_partidos:
            continue
        promedio_con = sum(splits["con"]) / len(splits["con"])
        promedio_sin = sum(splits["sin"]) / len(splits["sin"])
        if promedio_sin <= promedio_con:
            continue
        nombre = conn.execute("SELECT name FROM nba_players WHERE id = ?", (player_id,)).fetchone()[0]
        resultado.append(
            {
                "playerId": player_id,
                "playerName": nombre,
                "promedioCon": round(promedio_con, 1),
                "promedioSin": round(promedio_sin, 1),
                "diferencia": round(promedio_sin - promedio_con, 1),
            }
        )
    conn.close()

    resultado.sort(key=lambda r: r["diferencia"], reverse=True)
    return resultado


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

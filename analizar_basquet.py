"""
Motor estadístico de equipos NBA: perfil general/local/visita (moneyline,
puntos a favor/en contra) y % de partidos sobre una línea de puntos totales.
Se calcula 100% desde nba_games (apuestas.db); lo reutiliza
enviar_telegram_basquet.py para armar el reporte nocturno.

Ejecutar manualmente para ver un reporte de candidatos por consola:
    python analizar_basquet.py
"""

import sqlite3

MIN_PARTIDOS_PERFIL = 10  # muestra mínima para confiar en un % (home o away)
LINEA_PUNTOS_TOTALES = 220.5  # línea de referencia para "más de N puntos" entre ambos equipos
UMBRAL_CANDIDATO = 65.0  # % mínimo (win rate u over rate) para aparecer en el reporte


def _resumen_splits(partidos: list[dict]) -> dict | None:
    jugados = len(partidos)
    if jugados == 0:
        return None

    ganados = sum(1 for p in partidos if p["puntos_favor"] > p["puntos_contra"])
    sobre_linea = sum(1 for p in partidos if p["puntos_favor"] + p["puntos_contra"] > LINEA_PUNTOS_TOTALES)

    puntos_favor_avg = sum(p["puntos_favor"] for p in partidos) / jugados
    puntos_contra_avg = sum(p["puntos_contra"] for p in partidos) / jugados

    return {
        "played": jugados,
        "won": ganados,
        "winPct": round(ganados / jugados * 100, 1),
        "pointsForAvg": round(puntos_favor_avg, 1),
        "pointsAgainstAvg": round(puntos_contra_avg, 1),
        "pointsDiffAvg": round(puntos_favor_avg - puntos_contra_avg, 1),
        "overTotalPct": round(sobre_linea / jugados * 100, 1),
    }


def perfil_equipo_nba(team_id: int, season: int) -> dict | None:
    conn = sqlite3.connect("apuestas.db")
    cursor = conn.cursor()

    fila = cursor.execute("SELECT name FROM nba_teams WHERE id = ?", (team_id,)).fetchone()
    if fila is None:
        conn.close()
        return None
    nombre_equipo = fila[0]

    cursor.execute(
        """
        SELECT home_team_id, away_team_id, home_points, away_points
        FROM nba_games
        WHERE season = ? AND (home_team_id = ? OR away_team_id = ?)
          AND home_points IS NOT NULL AND away_points IS NOT NULL
        ORDER BY date ASC
        """,
        (season, team_id, team_id),
    )
    partidos_db = cursor.fetchall()
    conn.close()

    generales, como_local, como_visita = [], [], []
    for home_id, away_id, home_pts, away_pts in partidos_db:
        es_local = home_id == team_id
        registro = {
            "puntos_favor": home_pts if es_local else away_pts,
            "puntos_contra": away_pts if es_local else home_pts,
        }
        generales.append(registro)
        (como_local if es_local else como_visita).append(registro)

    return {
        "teamId": team_id,
        "teamName": nombre_equipo,
        "general": _resumen_splits(generales),
        "home": _resumen_splits(como_local),
        "away": _resumen_splits(como_visita),
    }


def pronostico_partido(home_id: int, away_id: int, season: int) -> dict | None:
    """Moneyline y diferencia de puntos promedio (+/-) de CADA equipo en su
    rol (local/visita), más puntos totales (over/under la línea), para un
    partido puntual. Se muestran los dos equipos siempre — no se elige un
    "favorito" único — para que se pueda evaluar la apuesta de cualquiera
    de los dos lados. None si a alguno de los dos equipos le falta muestra."""
    perfil_home = perfil_equipo_nba(home_id, season)
    perfil_away = perfil_equipo_nba(away_id, season)
    if perfil_home is None or perfil_away is None:
        return None

    casa, visita = perfil_home["home"], perfil_away["away"]
    if casa is None or visita is None or casa["played"] < MIN_PARTIDOS_PERFIL or visita["played"] < MIN_PARTIDOS_PERFIL:
        return None

    puntos_total_pct = round((casa["overTotalPct"] + visita["overTotalPct"]) / 2, 1)

    return {
        "home": {"nombre": perfil_home["teamName"], "moneyline": casa["winPct"], "margen": casa["pointsDiffAvg"]},
        "away": {"nombre": perfil_away["teamName"], "moneyline": visita["winPct"], "margen": visita["pointsDiffAvg"]},
        "puntosTotales": {"linea": LINEA_PUNTOS_TOTALES, "overPct": puntos_total_pct},
    }


def analizar_candidatos_moneyline(season: int) -> None:
    conn = sqlite3.connect("apuestas.db")
    equipos = conn.execute("SELECT id FROM nba_teams").fetchall()
    conn.close()

    print("\n" + "=" * 70)
    print(f" NBA — EQUIPOS CON >= {UMBRAL_CANDIDATO}% DE VICTORIAS COMO LOCAL O VISITA")
    print("=" * 70)

    for (team_id,) in equipos:
        perfil = perfil_equipo_nba(team_id, season)
        if perfil is None:
            continue
        for rol, etiqueta in (("home", "local"), ("away", "visita")):
            splits = perfil[rol]
            if splits and splits["played"] >= MIN_PARTIDOS_PERFIL and splits["winPct"] >= UMBRAL_CANDIDATO:
                print(f"{perfil['teamName']:<25} | {etiqueta:<6} | {splits['played']:<3} PJ | {splits['winPct']}%")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    from cargar_temporada_nba import temporada_actual_nba

    analizar_candidatos_moneyline(temporada_actual_nba())

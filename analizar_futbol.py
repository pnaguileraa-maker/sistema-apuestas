"""
Motor estadístico de partidos de fútbol para el resumen ejecutivo en PDF
(generar_pdf_futbol.py): resultado (1X2), hándicap de goles, y mercados
totales + por equipo de goles (incluyendo 1er/2do tiempo), córners,
tarjetas y tiros al arco. Es un análisis de EQUIPOS/duelos, no de
jugadores — el fútbol no tiene picks individuales como el básquet.

Reutiliza el motor ya existente de backend/app.py (elegir_top_mercados
para los mercados "totales" del partido) y agrega lo que faltaba: un
resumen por equipo EN SU ROL (local o visitante) con W/D/L, margen de
goles y líneas de córners/tarjetas/tiros al arco — más los mercados de
goles de 1er/2do tiempo, que no estaban en el motor original.

Las consultas de este módulo son propias (no tocan las funciones
compartidas de backend/app.py, cuyas filas tienen una forma fija de la
que depende _valor_partido) para no arriesgar el backend en producción.
"""

import sqlite3

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import _filas_equipo_en_rol, _filas_h2h, elegir_top_mercados, ETIQUETA_MERCADO

MIN_PARTIDOS_ROL = 5  # muestra mínima para confiar en un perfil de equipo en su rol
FACTOR_LINEA = 0.85  # mismo criterio que en NBA: línea con margen real bajo el promedio
UMBRAL_RESULTADO_DESTACADO = 45.0  # % mínimo para que un resultado (1X2) se note como favorito


def _linea_y_pct(valores: list[int]) -> tuple[float | None, float | None, float | None]:
    if not valores:
        return None, None, None
    promedio = sum(valores) / len(valores)
    linea = max(0.5, round(promedio * FACTOR_LINEA * 2) / 2 - 0.5)
    sobre = sum(1 for v in valores if v > linea)
    return round(promedio, 1), linea, round(100 * sobre / len(valores), 1)


def _propio_rival(fila: tuple, es_local: bool) -> tuple[dict, dict]:
    """De una fila de _filas_equipo_en_rol (home_goals, away_goals,
    home_corners, away_corners, home_yellow, home_red, away_yellow,
    away_red, home_sot, away_sot), separa los valores del equipo cuyo rol
    estamos mirando de los del rival."""
    (
        home_goals, away_goals, home_corners, away_corners,
        home_yellow, home_red, away_yellow, away_red, home_sot, away_sot,
    ) = fila

    home_tarjetas = (home_yellow + home_red) if home_yellow is not None and home_red is not None else None
    away_tarjetas = (away_yellow + away_red) if away_yellow is not None and away_red is not None else None

    propio = {"goles": home_goals, "corners": home_corners, "tarjetas": home_tarjetas, "tiros": home_sot}
    rival = {"goles": away_goals, "corners": away_corners, "tarjetas": away_tarjetas, "tiros": away_sot}
    return (propio, rival) if es_local else (rival, propio)


def perfil_equipo_rol(team_id: int, season: int, league_id: int, es_local: bool) -> dict | None:
    """Resumen del equipo jugando siempre en el mismo rol (local o
    visitante) esta temporada: % victorias/empates/derrotas, margen de
    goles, y promedio/línea/% para córners, tarjetas y tiros al arco
    PROPIOS (no del rival ni del total del partido)."""
    filas = _filas_equipo_en_rol(team_id, season, league_id, es_local)
    jugados = len(filas)
    if jugados < MIN_PARTIDOS_ROL:
        return None

    ganados = empatados = perdidos = 0
    goles_favor = goles_contra = 0
    corners_propios, tarjetas_propias, tiros_propios = [], [], []

    for fila in filas:
        propio, rival = _propio_rival(fila, es_local)
        if propio["goles"] > rival["goles"]:
            ganados += 1
        elif propio["goles"] == rival["goles"]:
            empatados += 1
        else:
            perdidos += 1
        goles_favor += propio["goles"]
        goles_contra += rival["goles"]

        if propio["corners"] is not None:
            corners_propios.append(propio["corners"])
        if propio["tarjetas"] is not None:
            tarjetas_propias.append(propio["tarjetas"])
        if propio["tiros"] is not None:
            tiros_propios.append(propio["tiros"])

    corners_prom, corners_linea, corners_pct = _linea_y_pct(corners_propios)
    tarjetas_prom, tarjetas_linea, tarjetas_pct = _linea_y_pct(tarjetas_propias)
    tiros_prom, tiros_linea, tiros_pct = _linea_y_pct(tiros_propios)

    return {
        "teamId": team_id,
        "played": jugados,
        "winPct": round(100 * ganados / jugados, 1),
        "drawPct": round(100 * empatados / jugados, 1),
        "lossPct": round(100 * perdidos / jugados, 1),
        "goalsForAvg": round(goles_favor / jugados, 1),
        "goalsAgainstAvg": round(goles_contra / jugados, 1),
        "margen": round((goles_favor - goles_contra) / jugados, 1),
        "corners": {"promedio": corners_prom, "linea": corners_linea, "overPct": corners_pct},
        "tarjetas": {"promedio": tarjetas_prom, "linea": tarjetas_linea, "overPct": tarjetas_pct},
        "tiros": {"promedio": tiros_prom, "linea": tiros_linea, "overPct": tiros_pct},
    }


def _goles_por_tiempo(team_id: int, season: int, league_id: int, es_local: bool) -> dict:
    """Promedio/línea/% de goles PROPIOS en el 1er y 2do tiempo, jugando
    siempre en el mismo rol. Consulta propia (no reutiliza
    _filas_equipo_en_rol porque esa función no trae home_goals_ht/
    away_goals_ht, y agregarlas rompería a _valor_partido en
    backend/app.py, que depende del orden/cantidad exacta de columnas)."""
    columna_rol = "home_team_id" if es_local else "away_team_id"
    conn = sqlite3.connect("apuestas.db")
    filas = conn.execute(
        f"""
        SELECT home_goals, away_goals, home_goals_ht, away_goals_ht
        FROM matches
        WHERE league_id = ? AND season = ? AND {columna_rol} = ?
          AND home_goals IS NOT NULL AND away_goals IS NOT NULL
          AND home_goals_ht IS NOT NULL AND away_goals_ht IS NOT NULL
        """,
        (league_id, season, team_id),
    ).fetchall()
    conn.close()

    primer_tiempo, segundo_tiempo = [], []
    for home_goals, away_goals, home_ht, away_ht in filas:
        propio_ht = home_ht if es_local else away_ht
        propio_total = home_goals if es_local else away_goals
        primer_tiempo.append(propio_ht)
        segundo_tiempo.append(propio_total - propio_ht)

    prom_1t, linea_1t, pct_1t = _linea_y_pct(primer_tiempo)
    prom_2t, linea_2t, pct_2t = _linea_y_pct(segundo_tiempo)
    return {
        "primerTiempo": {"promedio": prom_1t, "linea": linea_1t, "overPct": pct_1t},
        "segundoTiempo": {"promedio": prom_2t, "linea": linea_2t, "overPct": pct_2t},
    }


def _total_por_tiempo_partido(home_id: int, away_id: int, season: int, league_id: int) -> dict:
    """Línea/% de goles TOTALES del partido (ambos equipos sumados) por
    tiempo, combinando el historial del local en casa + visitante afuera
    — mismo criterio "global" que usa construir_rachas en backend/app.py
    para los mercados totales de goles/córners/tarjetas/tiros."""
    conn = sqlite3.connect("apuestas.db")
    filas_home = conn.execute(
        """
        SELECT home_goals_ht, away_goals_ht, home_goals, away_goals
        FROM matches
        WHERE league_id = ? AND season = ? AND home_team_id = ?
          AND home_goals_ht IS NOT NULL AND away_goals_ht IS NOT NULL
        """,
        (league_id, season, home_id),
    ).fetchall()
    filas_away = conn.execute(
        """
        SELECT home_goals_ht, away_goals_ht, home_goals, away_goals
        FROM matches
        WHERE league_id = ? AND season = ? AND away_team_id = ?
          AND home_goals_ht IS NOT NULL AND away_goals_ht IS NOT NULL
        """,
        (league_id, season, away_id),
    ).fetchall()
    conn.close()

    primer_tiempo, segundo_tiempo = [], []
    for home_ht, away_ht, home_goals, away_goals in filas_home + filas_away:
        primer_tiempo.append(home_ht + away_ht)
        segundo_tiempo.append((home_goals - home_ht) + (away_goals - away_ht))

    prom_1t, linea_1t, pct_1t = _linea_y_pct(primer_tiempo)
    prom_2t, linea_2t, pct_2t = _linea_y_pct(segundo_tiempo)
    return {
        "primerTiempo": {"promedio": prom_1t, "linea": linea_1t, "overPct": pct_1t},
        "segundoTiempo": {"promedio": prom_2t, "linea": linea_2t, "overPct": pct_2t},
    }


def pronostico_partido_futbol(home_id: int, away_id: int, season: int, league_id: int) -> dict | None:
    """Resultado (1X2), hándicap de goles, y mercados totales (goles,
    córners, tarjetas, tiros al arco, con 1er/2do tiempo para goles) +
    por-equipo (córners/tarjetas/tiros) para un partido puntual. None si a
    alguno de los dos equipos le falta muestra en su rol."""
    perfil_home = perfil_equipo_rol(home_id, season, league_id, True)
    perfil_away = perfil_equipo_rol(away_id, season, league_id, False)
    if perfil_home is None or perfil_away is None:
        return None

    p_home_bruto = perfil_home["winPct"] + perfil_away["lossPct"]
    p_draw_bruto = perfil_home["drawPct"] + perfil_away["drawPct"]
    p_away_bruto = perfil_home["lossPct"] + perfil_away["winPct"]
    total_bruto = p_home_bruto + p_draw_bruto + p_away_bruto
    p_home = round(100 * p_home_bruto / total_bruto, 1) if total_bruto else 0.0
    p_draw = round(100 * p_draw_bruto / total_bruto, 1) if total_bruto else 0.0
    p_away = round(100 * p_away_bruto / total_bruto, 1) if total_bruto else 0.0

    handicap_home = round((perfil_home["margen"] - perfil_away["margen"]) / 2, 1)

    filas_home_local = _filas_equipo_en_rol(home_id, season, league_id, True)
    filas_away_visita = _filas_equipo_en_rol(away_id, season, league_id, False)
    filas_h2h = _filas_h2h(home_id, away_id)
    mercados_totales = elegir_top_mercados(filas_home_local, filas_away_visita, filas_h2h, top=len(ETIQUETA_MERCADO))

    return {
        "resultado": {"homePct": p_home, "drawPct": p_draw, "awayPct": p_away},
        "handicapHome": handicap_home,
        "mercadosTotales": mercados_totales,
        "golesPorTiempoTotal": _total_por_tiempo_partido(home_id, away_id, season, league_id),
        "home": {"perfil": perfil_home, "golesPorTiempo": _goles_por_tiempo(home_id, season, league_id, True)},
        "away": {"perfil": perfil_away, "golesPorTiempo": _goles_por_tiempo(away_id, season, league_id, False)},
    }

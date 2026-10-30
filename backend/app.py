"""
API ligera que expone estadísticas por equipo (% Over 2.5 goles, córners
promedio, tarjetas promedio, forma reciente, tabla de posiciones oficial),
calculadas a partir de apuestas.db. Soporta Premier League y Champions
League (ver league_id en COMPETICIONES) — Premier League es la liga por
defecto cuando no se indica league_id.

Ejecutar:
    python app.py
Endpoints:
    GET http://localhost:5000/api/equipos
    GET http://localhost:5000/api/equipos?season=2026&min_partidos=5&league_id=2
    GET http://localhost:5000/api/posiciones?season=2026&league_id=2
    GET http://localhost:5000/api/equipos/<team_id>/calendario?season=2026&league_id=2
    GET http://localhost:5000/api/equipos/<team_id>/resumen?season=2026&league_id=2
    GET http://localhost:5000/api/equipos/<team_id>/perfil?season=2026&league_id=2
    GET http://localhost:5000/api/pronosticos/hoy?season=2026&league_id=2
    GET http://localhost:5000/api/pronosticos/manana?season=2026&league_id=2
    GET http://localhost:5000/api/pronosticos/semana?season=2026&league_id=2
    GET http://localhost:5000/api/calendario-semana
    GET http://localhost:5000/api/partidos?fecha=2026-10-19&season=2026
    GET http://localhost:5000/api/competiciones
    GET http://localhost:5000/api/temporadas?league_id=2
"""

import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from statistics import mean

import anthropic
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "apuestas.db")
PREMIER_LEAGUE_ID = 39
CHAMPIONS_LEAGUE_ID = 2
DEFAULT_MIN_MATCHES = 5

COMPETICIONES = [
    {"id": PREMIER_LEAGUE_ID, "nombre": "Premier League"},
    {"id": CHAMPIONS_LEAGUE_ID, "nombre": "UEFA Champions League"},
    {"id": 140, "nombre": "La Liga"},
    {"id": 61, "nombre": "Ligue 1"},
    {"id": 78, "nombre": "Bundesliga"},
    {"id": 135, "nombre": "Serie A"},
    {"id": 94, "nombre": "Primeira Liga"},
    {"id": 88, "nombre": "Eredivisie"},
    {"id": 265, "nombre": "Primera División (Chile)"},
    {"id": 128, "nombre": "Liga Profesional Argentina"},
    {"id": 71, "nombre": "Brasileirão Série A"},
    {"id": 262, "nombre": "Liga MX"},
    {"id": 253, "nombre": "MLS"},
    {"id": 307, "nombre": "Saudi Pro League"},
]
NOMBRE_LIGA = {c["id"]: c["nombre"] for c in COMPETICIONES}

app = Flask(__name__)
# Dev local: el Angular dev server corre en otro puerto (4200),
# así que el navegador bloquearía la petición sin CORS habilitado.
CORS(app)


@app.route("/")
def health():
    return jsonify({"status": "ok", "servicio": "sistema-apuestas backend"})

_anthropic_client: anthropic.Anthropic | None = None


def get_anthropic_client() -> anthropic.Anthropic:
    """Cliente perezoso: solo se crea (y solo falla por falta de ANTHROPIC_API_KEY)
    cuando realmente se pide un pronóstico, no al levantar el servidor."""
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def asegurar_columnas_estadisticas(conn: sqlite3.Connection) -> None:
    """Migra matches in-place para soportar temporada, córners y tarjetas (idempotente)."""
    cursor = conn.cursor()
    columnas_existentes = {fila[1] for fila in cursor.execute("PRAGMA table_info(matches)")}

    columnas_nuevas = {
        "season": "INTEGER",
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
    # reabrirlos para que actualizar_estadisticas_partidos.py los reprocese
    # (misma llamada a /fixtures/statistics, sin gastar cuota extra).
    es_columna_nueva = "home_shots_on_target" not in columnas_existentes

    for columna, tipo in columnas_nuevas.items():
        if columna not in columnas_existentes:
            cursor.execute(f"ALTER TABLE matches ADD COLUMN {columna} {tipo}")

    if es_columna_nueva:
        cursor.execute("UPDATE matches SET stats_checked = 0 WHERE status = 'FT'")

    # Los partidos cargados antes de esta migración son todos de la temporada 2023 (prueba inicial)
    cursor.execute(
        "UPDATE matches SET season = 2023 WHERE season IS NULL AND league_id = ?",
        (PREMIER_LEAGUE_ID,),
    )

    columnas_teams = {fila[1] for fila in cursor.execute("PRAGMA table_info(teams)")}
    if "logo_url" not in columnas_teams:
        cursor.execute("ALTER TABLE teams ADD COLUMN logo_url TEXT")

    conn.commit()


def asegurar_tabla_pronosticos(conn: sqlite3.Connection) -> None:
    """Caché de pronósticos: una fila fija por partido (fixture_id es único
    por partido, así que ya identifica día+encuentro+liga). Se escribe una
    sola vez y se sirve igual en cada carga, salvo regeneración manual."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pronosticos_cache (
            fixture_id INTEGER PRIMARY KEY,
            league_id INTEGER NOT NULL,
            informe TEXT NOT NULL,
            opciones_json TEXT NOT NULL,
            generado_en TEXT NOT NULL
        )
        """
    )
    conn.commit()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    asegurar_columnas_estadisticas(conn)
    asegurar_tabla_pronosticos(conn)
    return conn


def temporada_actual_premier_league() -> int:
    hoy = date.today()
    return hoy.year if hoy.month >= 7 else hoy.year - 1


def temporada_por_defecto(league_id: int = PREMIER_LEAGUE_ID) -> int:
    """La temporada más reciente que ya tengamos cargada en la BD para esa liga;
    si todavía no hay ninguna, cae a la temporada vigente calculada por fecha."""
    conn = get_connection()
    fila = conn.execute(
        "SELECT MAX(season) FROM matches WHERE league_id = ?", (league_id,)
    ).fetchone()
    conn.close()
    return fila[0] if fila and fila[0] is not None else temporada_actual_premier_league()


def semana_actual() -> tuple:
    """Lunes y domingo (ISO) de la semana en curso, usados para filtrar los
    pronósticos semanales (p. ej. Champions League, que juega entre semana)."""
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)
    return lunes.isoformat(), domingo.isoformat()


def resultado_para(goles_propios: int, goles_rival: int) -> str:
    if goles_propios > goles_rival:
        return "W"
    if goles_propios == goles_rival:
        return "D"
    return "L"


LINEAS_MERCADOS = {
    "goals": [0.5, 1.5, 2.5, 3.5, 4.5],
    "corners": [7.5, 8.5, 9.5, 10.5, 11.5],
    "cards": [1.5, 2.5, 3.5, 4.5, 5.5],
    "shots_on_target": [2.5, 3.5, 4.5, 5.5, 6.5],
}


def porcentajes_por_lineas(valores: list, lineas: list) -> dict:
    """% de partidos que superan cada línea de la lista (abierto, sin límite de líneas).
    Valores None en todas las líneas si todavía no hay datos para esa métrica."""
    validos = [v for v in valores if v is not None]
    if not validos:
        return {str(linea): None for linea in lineas}
    return {
        str(linea): round(100 * sum(1 for v in validos if v > linea) / len(validos), 1)
        for linea in lineas
    }


def linea_y_porcentaje(valores: list) -> tuple:
    """A partir de los valores por partido de una métrica (córners o tarjetas
    de un equipo), calcula el promedio, una línea de apuesta (redondeo - 0.5)
    y el % de partidos que superan esa línea. Devuelve (None, None, None)
    si todavía no hay datos (p. ej. no se corrió actualizar_estadisticas_partidos.py)."""
    valores_validos = [v for v in valores if v is not None]
    if not valores_validos:
        return None, None, None

    promedio = round(mean(valores_validos), 1)
    linea = round(promedio) - 0.5
    porcentaje = round(
        100 * sum(1 for v in valores_validos if v > linea) / len(valores_validos), 1
    )
    return promedio, linea, porcentaje


def calcular_estadisticas_equipos(season: int, min_partidos: int, league_id: int = PREMIER_LEAGUE_ID) -> list:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT m.home_team_id, t1.name, t1.logo_url,
               m.away_team_id, t2.name, t2.logo_url,
               m.home_goals, m.away_goals,
               m.home_corners, m.away_corners,
               m.home_yellow_cards, m.home_red_cards,
               m.away_yellow_cards, m.away_red_cards
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE m.league_id = ? AND m.season = ?
          AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        ORDER BY m.date ASC
        """,
        (league_id, season),
    )
    partidos = cursor.fetchall()
    conn.close()

    equipos: dict = {}

    for (
        home_id, home_name, home_logo, away_id, away_name, away_logo,
        home_goals, away_goals,
        home_corners, away_corners,
        home_yellow, home_red, away_yellow, away_red,
    ) in partidos:
        total_goles = home_goals + away_goals
        es_over_25 = total_goles > 2.5

        home_cards = (
            home_yellow + home_red if home_yellow is not None and home_red is not None else None
        )
        away_cards = (
            away_yellow + away_red if away_yellow is not None and away_red is not None else None
        )
        total_corners = (
            home_corners + away_corners if home_corners is not None and away_corners is not None else None
        )
        total_cards = home_cards + away_cards if home_cards is not None and away_cards is not None else None

        perspectivas = (
            (
                home_id, home_name, home_logo, resultado_para(home_goals, away_goals),
                home_goals, away_goals, home_corners, away_corners, home_cards, away_cards,
            ),
            (
                away_id, away_name, away_logo, resultado_para(away_goals, home_goals),
                away_goals, home_goals, away_corners, home_corners, away_cards, home_cards,
            ),
        )

        for (
            team_id, team_name, team_logo, resultado,
            goles_favor, goles_contra, corners_favor, corners_contra, cards_favor, cards_contra,
        ) in perspectivas:
            equipo = equipos.setdefault(
                team_id,
                {
                    "teamId": team_id,
                    "teamName": team_name,
                    "teamLogo": team_logo,
                    "matchesPlayed": 0,
                    "over25Count": 0,
                    "form": [],
                    "_corners": [],
                    "_cards": [],
                    "_goals_total": [], "_goals_for": [], "_goals_against": [],
                    "_corners_total": [], "_corners_for": [], "_corners_against": [],
                    "_cards_total": [], "_cards_for": [], "_cards_against": [],
                },
            )
            equipo["matchesPlayed"] += 1
            equipo["over25Count"] += 1 if es_over_25 else 0
            equipo["form"].append(resultado)
            equipo["_corners"].append(corners_favor)
            equipo["_cards"].append(cards_favor)

            equipo["_goals_total"].append(total_goles)
            equipo["_goals_for"].append(goles_favor)
            equipo["_goals_against"].append(goles_contra)
            equipo["_corners_total"].append(total_corners)
            equipo["_corners_for"].append(corners_favor)
            equipo["_corners_against"].append(corners_contra)
            equipo["_cards_total"].append(total_cards)
            equipo["_cards_for"].append(cards_favor)
            equipo["_cards_against"].append(cards_contra)

    resultado = []
    for equipo in equipos.values():
        if equipo["matchesPlayed"] < min_partidos:
            continue

        corners_avg, corners_line, corners_pct = linea_y_porcentaje(equipo.pop("_corners"))
        cards_avg, cards_line, cards_pct = linea_y_porcentaje(equipo.pop("_cards"))

        equipo["league"] = NOMBRE_LIGA.get(league_id, "")
        equipo["over25Pct"] = round((equipo["over25Count"] / equipo["matchesPlayed"]) * 100, 1)
        equipo["form"] = equipo["form"][-5:]
        equipo["cornersAvg"] = corners_avg
        equipo["cornersLine"] = corners_line
        equipo["cornersOverPct"] = corners_pct
        equipo["cardsAvg"] = cards_avg
        equipo["cardsLine"] = cards_line
        equipo["cardsOverPct"] = cards_pct

        # Líneas múltiples (totalmente abierto): % de partidos sobre cada umbral,
        # separado en total del partido / a favor del equipo / en contra (concedido).
        equipo["lines"] = {
            "goals": {
                "total": porcentajes_por_lineas(equipo.pop("_goals_total"), LINEAS_MERCADOS["goals"]),
                "for": porcentajes_por_lineas(equipo.pop("_goals_for"), LINEAS_MERCADOS["goals"]),
                "against": porcentajes_por_lineas(equipo.pop("_goals_against"), LINEAS_MERCADOS["goals"]),
            },
            "corners": {
                "total": porcentajes_por_lineas(equipo.pop("_corners_total"), LINEAS_MERCADOS["corners"]),
                "for": porcentajes_por_lineas(equipo.pop("_corners_for"), LINEAS_MERCADOS["corners"]),
                "against": porcentajes_por_lineas(equipo.pop("_corners_against"), LINEAS_MERCADOS["corners"]),
            },
            "cards": {
                "total": porcentajes_por_lineas(equipo.pop("_cards_total"), LINEAS_MERCADOS["cards"]),
                "for": porcentajes_por_lineas(equipo.pop("_cards_for"), LINEAS_MERCADOS["cards"]),
                "against": porcentajes_por_lineas(equipo.pop("_cards_against"), LINEAS_MERCADOS["cards"]),
            },
        }
        resultado.append(equipo)

    resultado.sort(key=lambda e: e["over25Pct"], reverse=True)
    return resultado


def calcular_tabla_posiciones(season: int, league_id: int = PREMIER_LEAGUE_ID) -> list:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT m.id, m.date,
               m.home_team_id, t1.name, t1.logo_url,
               m.away_team_id, t2.name, t2.logo_url,
               m.home_goals, m.away_goals,
               m.home_corners, m.away_corners,
               m.home_yellow_cards, m.home_red_cards,
               m.away_yellow_cards, m.away_red_cards
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE m.league_id = ? AND m.season = ?
          AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        ORDER BY m.date ASC
        """,
        (league_id, season),
    )
    partidos = cursor.fetchall()
    conn.close()

    equipos: dict = {}

    for (
        fixture_id, fecha, home_id, home_name, home_logo, away_id, away_name, away_logo, home_goals, away_goals,
        home_corners, away_corners, home_yellow, home_red, away_yellow, away_red,
    ) in partidos:
        home_cards = (
            home_yellow + home_red if home_yellow is not None and home_red is not None else None
        )
        away_cards = (
            away_yellow + away_red if away_yellow is not None and away_red is not None else None
        )

        perspectivas = (
            (
                home_id, home_name, home_logo, home_goals, away_goals, True,
                away_id, away_name, away_logo, home_corners, home_cards,
            ),
            (
                away_id, away_name, away_logo, away_goals, home_goals, False,
                home_id, home_name, home_logo, away_corners, away_cards,
            ),
        )

        for (
            team_id, team_name, team_logo, goles_favor, goles_contra, es_local,
            rival_id, rival_name, rival_logo, corners_equipo, cards_equipo,
        ) in perspectivas:
            equipo = equipos.setdefault(
                team_id,
                {
                    "teamId": team_id,
                    "teamName": team_name,
                    "teamLogo": team_logo,
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "goalsFor": 0,
                    "goalsAgainst": 0,
                    "_history": [],
                    "_corners": [],
                    "_cards": [],
                },
            )
            equipo["played"] += 1
            equipo["goalsFor"] += goles_favor
            equipo["goalsAgainst"] += goles_contra
            if goles_favor > goles_contra:
                equipo["won"] += 1
            elif goles_favor == goles_contra:
                equipo["drawn"] += 1
            else:
                equipo["lost"] += 1

            equipo["_corners"].append(corners_equipo)
            equipo["_cards"].append(cards_equipo)

            # Detalle del partido desde la perspectiva de este equipo, usado para
            # los puntos de forma (últimos 5) con tooltip en la tabla de posiciones.
            equipo["_history"].append(
                {
                    "fixtureId": fixture_id,
                    "date": fecha,
                    "opponentId": rival_id,
                    "opponentName": rival_name,
                    "opponentLogo": rival_logo,
                    "isHome": es_local,
                    "homeGoals": home_goals,
                    "awayGoals": away_goals,
                    "homeCorners": home_corners,
                    "awayCorners": away_corners,
                    "homeCards": home_cards,
                    "awayCards": away_cards,
                    "result": resultado_para(goles_favor, goles_contra),
                }
            )

    tabla = list(equipos.values())
    for equipo in tabla:
        equipo["goalDiff"] = equipo["goalsFor"] - equipo["goalsAgainst"]
        equipo["points"] = equipo["won"] * 3 + equipo["drawn"]
        equipo["last5"] = equipo.pop("_history")[-5:]
        equipo["goalsForAvg"] = round(equipo["goalsFor"] / equipo["played"], 2)
        equipo["cornersAvg"], _, _ = linea_y_porcentaje(equipo.pop("_corners"))
        equipo["cardsAvg"], _, _ = linea_y_porcentaje(equipo.pop("_cards"))

    # Criterio oficial de desempate: puntos, luego diferencia de goles, luego goles a favor
    tabla.sort(key=lambda e: (-e["points"], -e["goalDiff"], -e["goalsFor"], e["teamName"]))
    for posicion, equipo in enumerate(tabla, start=1):
        equipo["position"] = posicion

    return tabla


def calcular_calendario_equipo(team_id: int, season: int, league_id: int = PREMIER_LEAGUE_ID) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()

    fila = cursor.execute("SELECT name, logo_url FROM teams WHERE id = ?", (team_id,)).fetchone()
    if fila is None:
        conn.close()
        return None
    team_name, team_logo = fila

    cursor.execute(
        """
        SELECT m.id, m.date, m.status,
               m.home_team_id, t1.name, t1.logo_url,
               m.away_team_id, t2.name, t2.logo_url,
               m.home_goals, m.away_goals
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE m.league_id = ? AND m.season = ?
          AND (m.home_team_id = ? OR m.away_team_id = ?)
        ORDER BY m.date ASC
        """,
        (league_id, season, team_id, team_id),
    )
    partidos = cursor.fetchall()
    conn.close()

    pasados = []
    proximos = []
    for (
        fixture_id, fecha, status, home_id, home_name, home_logo,
        away_id, away_name, away_logo, home_goals, away_goals,
    ) in partidos:
        es_local = home_id == team_id
        rival_id = away_id if es_local else home_id
        rival_name = away_name if es_local else home_name
        rival_logo = away_logo if es_local else home_logo

        if status == "FT" and home_goals is not None and away_goals is not None:
            goles_favor = home_goals if es_local else away_goals
            goles_contra = away_goals if es_local else home_goals
            pasados.append(
                {
                    "fixtureId": fixture_id,
                    "date": fecha,
                    "opponentId": rival_id,
                    "opponentName": rival_name,
                    "opponentLogo": rival_logo,
                    "isHome": es_local,
                    "homeGoals": home_goals,
                    "awayGoals": away_goals,
                    "result": resultado_para(goles_favor, goles_contra),
                }
            )
        else:
            proximos.append(
                {
                    "fixtureId": fixture_id,
                    "date": fecha,
                    "opponentId": rival_id,
                    "opponentName": rival_name,
                    "opponentLogo": rival_logo,
                    "isHome": es_local,
                    "status": status,
                }
            )

    pasados.sort(key=lambda p: p["date"], reverse=True)
    proximos.sort(key=lambda p: p["date"])

    return {
        "teamId": team_id,
        "teamName": team_name,
        "teamLogo": team_logo,
        "pasados": pasados,
        "proximos": proximos,
    }


def calcular_resumen_equipo(team_id: int, season: int, league_id: int = PREMIER_LEAGUE_ID) -> dict | None:
    """Ficha de equipo (head-to-head): % W/D/L, % Over 1.5/2.5 goles y
    córners/tarjetas promedio, sin el filtro de min_partidos (se pide para
    un equipo puntual, ya elegido por el usuario en la tabla de posiciones)."""
    conn = get_connection()
    cursor = conn.cursor()

    fila = cursor.execute("SELECT name, logo_url FROM teams WHERE id = ?", (team_id,)).fetchone()
    if fila is None:
        conn.close()
        return None
    team_name, team_logo = fila

    cursor.execute(
        """
        SELECT m.home_team_id, m.away_team_id,
               m.home_goals, m.away_goals,
               m.home_corners, m.away_corners,
               m.home_yellow_cards, m.home_red_cards,
               m.away_yellow_cards, m.away_red_cards
        FROM matches m
        WHERE m.league_id = ? AND m.season = ?
          AND (m.home_team_id = ? OR m.away_team_id = ?)
          AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        """,
        (league_id, season, team_id, team_id),
    )
    partidos = cursor.fetchall()
    conn.close()

    won = drawn = lost = 0
    over15_count = over25_count = over35_count = 0
    corners_propios: list = []
    cards_propios: list = []

    for (
        home_id, away_id, home_goals, away_goals,
        home_corners, away_corners, home_yellow, home_red, away_yellow, away_red,
    ) in partidos:
        es_local = home_id == team_id
        goles_favor = home_goals if es_local else away_goals
        goles_contra = away_goals if es_local else home_goals
        total_goles = home_goals + away_goals

        resultado = resultado_para(goles_favor, goles_contra)
        if resultado == "W":
            won += 1
        elif resultado == "D":
            drawn += 1
        else:
            lost += 1

        if total_goles > 1.5:
            over15_count += 1
        if total_goles > 2.5:
            over25_count += 1
        if total_goles > 3.5:
            over35_count += 1

        corners_propios.append(home_corners if es_local else away_corners)
        yellow = home_yellow if es_local else away_yellow
        red = home_red if es_local else away_red
        cards_propios.append(yellow + red if yellow is not None and red is not None else None)

    matches_played = len(partidos)
    corners_avg, corners_line, corners_pct = linea_y_porcentaje(corners_propios)
    cards_avg, cards_line, cards_pct = linea_y_porcentaje(cards_propios)

    def porcentaje(count: int) -> float:
        return round(100 * count / matches_played, 1) if matches_played else 0.0

    return {
        "teamId": team_id,
        "teamName": team_name,
        "teamLogo": team_logo,
        "matchesPlayed": matches_played,
        "won": won,
        "drawn": drawn,
        "lost": lost,
        "winPct": porcentaje(won),
        "drawPct": porcentaje(drawn),
        "lossPct": porcentaje(lost),
        "over15Pct": porcentaje(over15_count),
        "over25Pct": porcentaje(over25_count),
        "over35Pct": porcentaje(over35_count),
        "cornersAvg": corners_avg,
        "cornersLine": corners_line,
        "cornersOverPct": corners_pct,
        "cardsAvg": cards_avg,
        "cardsLine": cards_line,
        "cardsOverPct": cards_pct,
    }


def _resumen_splits(registros: list) -> dict:
    """A partir de una lista de {golesFavor, golesContra, btts} calcula PJ, PPG,
    % de victorias, promedios de gol y % de BTTS / valla invicta (clean sheet)."""
    played = len(registros)
    if played == 0:
        return {
            "played": 0, "won": 0, "drawn": 0, "lost": 0, "points": 0, "ppg": 0.0,
            "winPct": 0.0, "goalsForAvg": 0.0, "goalsAgainstAvg": 0.0,
            "bttsPct": 0.0, "cleanSheetPct": 0.0,
        }

    won = sum(1 for r in registros if r["golesFavor"] > r["golesContra"])
    drawn = sum(1 for r in registros if r["golesFavor"] == r["golesContra"])
    lost = played - won - drawn
    points = won * 3 + drawn
    goles_favor = sum(r["golesFavor"] for r in registros)
    goles_contra = sum(r["golesContra"] for r in registros)
    btts = sum(1 for r in registros if r["btts"])
    vallas_invictas = sum(1 for r in registros if r["golesContra"] == 0)

    def porcentaje(n: int) -> float:
        return round(100 * n / played, 1)

    return {
        "played": played,
        "won": won,
        "drawn": drawn,
        "lost": lost,
        "points": points,
        "ppg": round(points / played, 2),
        "winPct": porcentaje(won),
        "goalsForAvg": round(goles_favor / played, 2),
        "goalsAgainstAvg": round(goles_contra / played, 2),
        "bttsPct": porcentaje(btts),
        "cleanSheetPct": porcentaje(vallas_invictas),
    }


def calcular_perfil_equipo(team_id: int, season: int, league_id: int = PREMIER_LEAGUE_ID) -> dict | None:
    """Perfil avanzado para el pop-up de equipo: posición en la tabla, país,
    forma reciente y el desglose General / Como local / Como visitante."""
    conn = get_connection()
    cursor = conn.cursor()

    fila = cursor.execute(
        "SELECT name, logo_url, country FROM teams WHERE id = ?", (team_id,)
    ).fetchone()
    if fila is None:
        conn.close()
        return None
    team_name, team_logo, team_country = fila

    cursor.execute(
        """
        SELECT m.home_team_id, m.away_team_id, m.home_goals, m.away_goals
        FROM matches m
        WHERE m.league_id = ? AND m.season = ?
          AND (m.home_team_id = ? OR m.away_team_id = ?)
          AND m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
        ORDER BY m.date ASC
        """,
        (league_id, season, team_id, team_id),
    )
    partidos = cursor.fetchall()
    conn.close()

    generales, como_local, como_visita, form = [], [], [], []

    for home_id, away_id, home_goals, away_goals in partidos:
        es_local = home_id == team_id
        goles_favor = home_goals if es_local else away_goals
        goles_contra = away_goals if es_local else home_goals
        registro = {
            "golesFavor": goles_favor,
            "golesContra": goles_contra,
            "btts": home_goals > 0 and away_goals > 0,
        }
        generales.append(registro)
        (como_local if es_local else como_visita).append(registro)
        form.append(resultado_para(goles_favor, goles_contra))

    posicion = next(
        (e["position"] for e in calcular_tabla_posiciones(season, league_id) if e["teamId"] == team_id),
        None,
    )

    return {
        "teamId": team_id,
        "teamName": team_name,
        "teamLogo": team_logo,
        "country": team_country,
        "position": posicion,
        "form": form[-5:],
        "general": _resumen_splits(generales),
        "home": _resumen_splits(como_local),
        "away": _resumen_splits(como_visita),
    }


@app.route("/api/equipos")
def listar_equipos():
    min_partidos = request.args.get("min_partidos", default=DEFAULT_MIN_MATCHES, type=int)
    league_id = request.args.get("league_id", type=int, default=None) or PREMIER_LEAGUE_ID
    season = request.args.get("season", type=int, default=None) or temporada_por_defecto(league_id)
    return jsonify(calcular_estadisticas_equipos(season, min_partidos, league_id))


@app.route("/api/posiciones")
def tabla_posiciones():
    league_id = request.args.get("league_id", type=int, default=None) or PREMIER_LEAGUE_ID
    season = request.args.get("season", type=int, default=None) or temporada_por_defecto(league_id)
    return jsonify(calcular_tabla_posiciones(season, league_id))


@app.route("/api/equipos/<int:team_id>/calendario")
def calendario_equipo(team_id):
    league_id = request.args.get("league_id", type=int, default=None) or PREMIER_LEAGUE_ID
    season = request.args.get("season", type=int, default=None) or temporada_por_defecto(league_id)
    data = calcular_calendario_equipo(team_id, season, league_id)
    if data is None:
        return jsonify({"error": "Equipo no encontrado"}), 404
    return jsonify(data)


@app.route("/api/equipos/<int:team_id>/resumen")
def resumen_equipo(team_id):
    league_id = request.args.get("league_id", type=int, default=None) or PREMIER_LEAGUE_ID
    season = request.args.get("season", type=int, default=None) or temporada_por_defecto(league_id)
    data = calcular_resumen_equipo(team_id, season, league_id)
    if data is None:
        return jsonify({"error": "Equipo no encontrado"}), 404
    return jsonify(data)


def partidos_para_pronostico(
    season: int, fecha_inicio: str, fecha_fin: str, league_id: int = PREMIER_LEAGUE_ID
) -> list:
    conn = get_connection()
    filas = conn.execute(
        """
        SELECT m.id, m.date,
               m.home_team_id, t1.name, t1.logo_url,
               m.away_team_id, t2.name, t2.logo_url
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE m.league_id = ? AND m.season = ? AND date(m.date) BETWEEN ? AND ?
        ORDER BY m.date ASC
        """,
        (league_id, season, fecha_inicio, fecha_fin),
    ).fetchall()
    conn.close()
    return filas


def construir_contexto_equipo(team_id: int, season: int, league_id: int = PREMIER_LEAGUE_ID) -> dict:
    """Agrupa, para un equipo, exactamente las estadísticas ya calculadas por el
    resto de la API (perfil + resumen) — el modelo de IA no recibe ni un número
    que no provenga de apuestas.db."""
    perfil = calcular_perfil_equipo(team_id, season, league_id)
    resumen = calcular_resumen_equipo(team_id, season, league_id)
    return {
        "posicionEnLaTabla": perfil["position"],
        "formaUltimos5": perfil["form"],
        "general": perfil["general"],
        "comoLocal": perfil["home"],
        "comoVisitante": perfil["away"],
        "over15GolesPct": resumen["over15Pct"],
        "over25GolesPct": resumen["over25Pct"],
        "over35GolesPct": resumen["over35Pct"],
        "cornersPromedio": resumen["cornersAvg"],
        "cornersLinea": resumen["cornersLine"],
        "cornersSobreLineaPct": resumen["cornersOverPct"],
        "tarjetasPromedio": resumen["cardsAvg"],
        "tarjetasLinea": resumen["cardsLine"],
        "tarjetasSobreLineaPct": resumen["cardsOverPct"],
    }


def generar_pronostico_partido(
    fecha: str, liga_nombre: str, home_name: str, away_name: str, contexto_home: dict, contexto_away: dict
) -> str:
    client = get_anthropic_client()

    datos_partido = {
        "competicion": liga_nombre,
        "fecha": fecha,
        "local": {"equipo": home_name, **contexto_home},
        "visitante": {"equipo": away_name, **contexto_away},
    }

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        thinking={"type": "disabled"},
        output_config={"effort": "medium"},
        system=(
            "Eres un analista deportivo que redacta informes breves para partidos de "
            "fútbol, basados ESTRICTAMENTE en las estadísticas que se te entregan en JSON "
            "(incluida la competición indicada en el campo 'competicion'). No inventes datos, "
            "lesiones, alineaciones ni resultados que no estén en el input. No propongas un "
            "mercado ni una línea de apuesta concreta (eso se calcula aparte, de forma "
            "estadística). Escribe en español, un máximo de 2 párrafos cortos (no más de 4-5 "
            "líneas cada uno), tono profesional y directo, sin encabezados ni markdown. Sé "
            "conciso: todo el texto debe caber holgadamente dentro del límite de salida."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    "Estadísticas del partido (JSON):\n"
                    f"{json.dumps(datos_partido, ensure_ascii=False, indent=2)}\n\n"
                    "Redacta el análisis de este encuentro."
                ),
            }
        ],
    )

    if response.stop_reason == "refusal":
        return "El modelo no pudo generar un pronóstico para este partido."

    return next(block.text for block in response.content if block.type == "text")


def obtener_pronostico_partido(
    fixture_id: int,
    season: int,
    league_id: int,
    home_id: int,
    home_name: str,
    away_id: int,
    away_name: str,
    fecha: str,
    liga_nombre: str,
    forzar: bool = False,
) -> dict:
    """Pronóstico fijo de un partido: hasta 3 opciones de apuesta (cálculo
    estadístico con `elegir_top_mercados`, sin IA) + un análisis narrativo
    (IA, generado una sola vez). Se cachea por fixture_id en
    pronosticos_cache y de ahí en adelante se sirve igual en cada carga,
    salvo forzar=True (botón "Regenerar")."""
    conn = get_connection()
    if not forzar:
        fila = conn.execute(
            "SELECT informe, opciones_json FROM pronosticos_cache WHERE fixture_id = ?",
            (fixture_id,),
        ).fetchone()
        if fila is not None:
            conn.close()
            informe, opciones_json = fila
            return {"informe": informe, "opciones": json.loads(opciones_json)}

    filas_home_local = _filas_equipo_en_rol(home_id, season, league_id, True)
    filas_away_visita = _filas_equipo_en_rol(away_id, season, league_id, False)
    filas_h2h = _filas_h2h(home_id, away_id)
    opciones = [
        {
            "mercado": c["mercado"],
            "linea": c["linea"],
            "recomendacion": f"{ICONO_MERCADO[c['mercado']]} Más de {c['linea']} {ETIQUETA_MERCADO[c['mercado']]}",
            "rachas": c["rachas"],
            "probabilidad": c["probabilidad"],
            "solido": c["solido"],
        }
        for c in elegir_top_mercados(filas_home_local, filas_away_visita, filas_h2h, top=3)
    ]

    contexto_home = construir_contexto_equipo(home_id, season, league_id)
    contexto_away = construir_contexto_equipo(away_id, season, league_id)
    try:
        informe = generar_pronostico_partido(
            fecha, liga_nombre, home_name, away_name, contexto_home, contexto_away
        )
    except Exception as error:
        # Cubre fallos de la API (rate limit, red), una ANTHROPIC_API_KEY
        # ausente/inválida en el .env (el SDK la reporta como TypeError) y
        # cualquier otro problema de este paso externo, sin tumbar el resto
        # de los pronósticos del día. No se cachea: el próximo intento
        # reintenta solo (p. ej. tras corregir la API key en el .env).
        conn.close()
        return {
            "informe": f"No se pudo generar el pronóstico (API de Claude): {error}",
            "opciones": opciones,
        }

    conn.execute(
        """
        INSERT INTO pronosticos_cache (fixture_id, league_id, informe, opciones_json, generado_en)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(fixture_id) DO UPDATE SET
            league_id = excluded.league_id,
            informe = excluded.informe,
            opciones_json = excluded.opciones_json,
            generado_en = excluded.generado_en
        """,
        (fixture_id, league_id, informe, json.dumps(opciones, ensure_ascii=False), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"informe": informe, "opciones": opciones}


def generar_pronosticos_del_dia(
    season: int,
    fecha_inicio: str,
    fecha_fin: str,
    league_id: int = PREMIER_LEAGUE_ID,
    liga_nombre: str = "Premier League",
    forzar: bool = False,
) -> list:
    partidos = partidos_para_pronostico(season, fecha_inicio, fecha_fin, league_id)

    resultado = []
    for fixture_id, fecha_partido, home_id, home_name, home_logo, away_id, away_name, away_logo in partidos:
        pronostico = obtener_pronostico_partido(
            fixture_id, season, league_id, home_id, home_name, away_id, away_name,
            fecha_partido, liga_nombre, forzar,
        )
        resultado.append(
            {
                "fixtureId": fixture_id,
                "date": fecha_partido,
                "homeTeamId": home_id,
                "homeTeamName": home_name,
                "homeTeamLogo": home_logo,
                "awayTeamId": away_id,
                "awayTeamName": away_name,
                "awayTeamLogo": away_logo,
                "informe": pronostico["informe"],
                "opciones": pronostico["opciones"],
            }
        )

    return resultado


def _forzar_regeneracion() -> bool:
    return request.args.get("forzar") == "1"


@app.route("/api/pronosticos/hoy")
def pronosticos_hoy():
    league_id = request.args.get("league_id", type=int, default=None) or PREMIER_LEAGUE_ID
    season = request.args.get("season", type=int, default=None) or temporada_por_defecto(league_id)
    hoy = date.today().isoformat()
    return jsonify(
        generar_pronosticos_del_dia(
            season, hoy, hoy, league_id, NOMBRE_LIGA.get(league_id, ""), forzar=_forzar_regeneracion()
        )
    )


@app.route("/api/pronosticos/manana")
def pronosticos_manana():
    league_id = request.args.get("league_id", type=int, default=None) or PREMIER_LEAGUE_ID
    season = request.args.get("season", type=int, default=None) or temporada_por_defecto(league_id)
    manana = (date.today() + timedelta(days=1)).isoformat()
    return jsonify(
        generar_pronosticos_del_dia(
            season, manana, manana, league_id, NOMBRE_LIGA.get(league_id, ""), forzar=_forzar_regeneracion()
        )
    )


@app.route("/api/pronosticos/semana")
def pronosticos_semana():
    league_id = request.args.get("league_id", type=int, default=None) or PREMIER_LEAGUE_ID
    season = request.args.get("season", type=int, default=None) or temporada_por_defecto(league_id)
    lunes, domingo = semana_actual()
    return jsonify(
        generar_pronosticos_del_dia(
            season, lunes, domingo, league_id, NOMBRE_LIGA.get(league_id, ""), forzar=_forzar_regeneracion()
        )
    )


# ---------------------------------------------------------------------------
# Scout Picks: tarjetas destacadas con el mercado mejor respaldado por los
# datos para cada partido, acompañado de 4 líneas de cumplimiento:
#   - "global": todo lo jugado esta temporada por el local en casa + el
#     visitante fuera (sin tope de partidos).
#   - "últimos 10 / 5: Local / Visitante": lo mismo pero acotado a los
#     últimos N partidos combinados (local en casa + visitante fuera).
#   - "H2H global": todos los enfrentamientos directos entre ambos equipos
#     que tengamos en la BD (cualquier temporada/competición), sin tope.
# Ningún número se inventa: todo sale de matches/teams en apuestas.db.
# ---------------------------------------------------------------------------


def _valor_partido(
    mercado: str,
    home_goals, away_goals, home_corners, away_corners,
    home_yellow, home_red, away_yellow, away_red,
    home_shots_on_target, away_shots_on_target,
):
    """Valor total del partido para el mercado pedido, o None si falta el dato
    (partidos sin estadísticas de córners/tarjetas/tiros al arco todavía cargadas)."""
    if mercado == "goals":
        return home_goals + away_goals
    if mercado == "corners":
        if home_corners is None or away_corners is None:
            return None
        return home_corners + away_corners
    if mercado == "cards":
        if None in (home_yellow, home_red, away_yellow, away_red):
            return None
        return (home_yellow + home_red) + (away_yellow + away_red)
    if mercado == "shots_on_target":
        if home_shots_on_target is None or away_shots_on_target is None:
            return None
        return home_shots_on_target + away_shots_on_target
    raise ValueError(f"Mercado desconocido: {mercado}")


def _filas_equipo_en_rol(team_id: int, season: int, league_id: int, es_local: bool) -> list:
    """Partidos finalizados de un equipo jugando siempre en el mismo rol
    (local o visitante), del más reciente al más antiguo."""
    columna_rol = "home_team_id" if es_local else "away_team_id"
    conn = get_connection()
    filas = conn.execute(
        f"""
        SELECT home_goals, away_goals, home_corners, away_corners,
               home_yellow_cards, home_red_cards, away_yellow_cards, away_red_cards,
               home_shots_on_target, away_shots_on_target
        FROM matches
        WHERE league_id = ? AND season = ? AND {columna_rol} = ?
          AND home_goals IS NOT NULL AND away_goals IS NOT NULL
        ORDER BY date DESC
        """,
        (league_id, season, team_id),
    ).fetchall()
    conn.close()
    return filas


def _filas_h2h(home_id: int, away_id: int) -> list:
    """Todos los enfrentamientos directos entre dos equipos (en cualquier
    temporada o competición de la BD), del más reciente al más antiguo."""
    conn = get_connection()
    filas = conn.execute(
        """
        SELECT home_goals, away_goals, home_corners, away_corners,
               home_yellow_cards, home_red_cards, away_yellow_cards, away_red_cards,
               home_shots_on_target, away_shots_on_target
        FROM matches
        WHERE ((home_team_id = ? AND away_team_id = ?) OR (home_team_id = ? AND away_team_id = ?))
          AND home_goals IS NOT NULL AND away_goals IS NOT NULL
        ORDER BY date DESC
        """,
        (home_id, away_id, away_id, home_id),
    ).fetchall()
    conn.close()
    return filas


def _racha_de_filas(filas: list, mercado: str, linea: float, limite: int | None = None) -> tuple:
    """(aciertos, total) de partidos que superan la línea, sobre como máximo
    los `limite` partidos más recientes (o todos, si no se pasa límite)."""
    if limite is not None:
        filas = filas[:limite]

    aciertos = total = 0
    for fila in filas:
        valor = _valor_partido(mercado, *fila)
        if valor is None:
            continue
        total += 1
        if valor > linea:
            aciertos += 1
    return aciertos, total


def construir_rachas(filas_home_local: list, filas_away_visita: list, filas_h2h: list, mercado: str, linea: float) -> list:
    def combinar(limite_local: int | None, limite_visita: int | None) -> tuple:
        hits_l, total_l = _racha_de_filas(filas_home_local, mercado, linea, limite_local)
        hits_v, total_v = _racha_de_filas(filas_away_visita, mercado, linea, limite_visita)
        return hits_l + hits_v, total_l + total_v

    def paquete(aciertos: int, total: int, etiqueta: str) -> dict:
        return {
            "aciertos": aciertos,
            "total": total,
            "porcentaje": round(100 * aciertos / total) if total else None,
            "etiqueta": etiqueta,
        }

    global_hits, global_total = combinar(None, None)
    u10_hits, u10_total = combinar(5, 5)
    u5_hits, u5_total = combinar(3, 2)
    h2h_hits, h2h_total = _racha_de_filas(filas_h2h, mercado, linea)

    return [
        paquete(global_hits, global_total, "global"),
        paquete(u10_hits, u10_total, "últimos 10: Local / Visitante"),
        paquete(h2h_hits, h2h_total, "H2H global"),
        paquete(u5_hits, u5_total, "últimos 5: Local / Visitante"),
    ]


UMBRAL_CONFIANZA = 70  # % mínimo (global y últimos 10, con muestra >= 4) para considerar una línea "sólida"


def elegir_top_mercados(
    filas_home_local: list, filas_away_visita: list, filas_h2h: list, top: int = 3
) -> list[dict]:
    """Rankea los mercados/línea candidatos para un partido, mejor primero.
    Prioriza líneas "sólidas" (>= UMBRAL_CONFIANZA en global y en los
    últimos 10, con muestra >= 4): entre esas, por mercado se queda con la
    MÁS ALTA (la apuesta más selectiva, no la trivial de siempre-se-cumple
    como +0.5 goles) y luego ordena por confianza. Si ningún mercado llega a
    ser sólido (muestra chica, inicio de temporada), ordena por confianza
    entre TODAS las líneas que tengan al menos un partido con dato, marcadas
    como no sólidas — así el partido siempre tiene opciones, aunque no sean
    sólidas. En ambos casos se evita repetir mercado al completar `top`, para
    que las opciones sean de mercados distintos (goles/córners/tarjetas)
    cuando hay datos. El primer elemento (índice 0) es siempre el mismo pick
    que antes devolvía `elegir_mercado_destacado`. Lista vacía solo si no hay
    ni un partido con dato."""
    candidatos = []  # (score, solido, mercado, linea, rachas)
    for mercado, lineas in LINEAS_MERCADOS.items():
        for linea in lineas:
            rachas = construir_rachas(filas_home_local, filas_away_visita, filas_h2h, mercado, linea)
            global_r, u10_r, _h2h_r, _u5_r = rachas
            if global_r["porcentaje"] is None or u10_r["porcentaje"] is None:
                continue
            score = (global_r["porcentaje"] + u10_r["porcentaje"]) / 2
            solido = (
                u10_r["total"] >= 4
                and global_r["porcentaje"] >= UMBRAL_CONFIANZA
                and u10_r["porcentaje"] >= UMBRAL_CONFIANZA
            )
            candidatos.append((score, solido, mercado, linea, rachas))

    if not candidatos:
        return []

    solidos = [c for c in candidatos if c[1]]
    if solidos:
        mejor_por_mercado: dict = {}
        for score, solido, mercado, linea, rachas in solidos:
            actual = mejor_por_mercado.get(mercado)
            if actual is None or linea > actual[3]:
                mejor_por_mercado[mercado] = (score, solido, mercado, linea, rachas)
        pool = list(mejor_por_mercado.values())
    else:
        pool = candidatos

    pool.sort(key=lambda c: c[0], reverse=True)

    elegidos = []
    mercados_usados = set()
    for score, solido, mercado, linea, rachas in pool:
        if mercado in mercados_usados:
            continue
        mercados_usados.add(mercado)
        elegidos.append(
            {"mercado": mercado, "linea": linea, "rachas": rachas, "probabilidad": score, "solido": solido}
        )
        if len(elegidos) == top:
            break
    return elegidos


def elegir_mercado_destacado(filas_home_local: list, filas_away_visita: list, filas_h2h: list) -> dict | None:
    """El único mercado a destacar para el calendario/Scout Pick (el mismo
    pick de siempre: el primero de `elegir_top_mercados`)."""
    top = elegir_top_mercados(filas_home_local, filas_away_visita, filas_h2h, top=1)
    return top[0] if top else None


ETIQUETA_MERCADO = {"goals": "goles", "corners": "córners", "cards": "tarjetas", "shots_on_target": "tiros al arco"}
ICONO_MERCADO = {"goals": "📊", "corners": "🚩", "cards": "🟨", "shots_on_target": "🎯"}


def construir_scout_pick(
    fixture_id, fecha, league_id, league_name,
    home_id, home_name, home_logo, away_id, away_name, away_logo, season,
) -> dict:
    """Arma la tarjeta Scout Pick de un partido. Siempre devuelve una tarjeta
    (aunque sea sin datos suficientes) para que todo partido del calendario
    tenga su propia sección embebida, en vez de desaparecer de la lista."""
    filas_home_local = _filas_equipo_en_rol(home_id, season, league_id, True)
    filas_away_visita = _filas_equipo_en_rol(away_id, season, league_id, False)
    filas_h2h = _filas_h2h(home_id, away_id)
    elegido = elegir_mercado_destacado(filas_home_local, filas_away_visita, filas_h2h)

    base = {
        "fixtureId": fixture_id,
        "date": fecha,
        "leagueId": league_id,
        "leagueName": league_name,
        "homeTeamId": home_id,
        "homeTeamName": home_name,
        "homeTeamLogo": home_logo,
        "awayTeamId": away_id,
        "awayTeamName": away_name,
        "awayTeamLogo": away_logo,
    }

    if elegido is None:
        return {
            **base,
            "mercado": None,
            "linea": None,
            "recomendacion": "Sin datos suficientes todavía",
            "rachas": [],
            "probabilidad": None,
            "solido": False,
        }

    mercado, linea = elegido["mercado"], elegido["linea"]
    return {
        **base,
        "mercado": mercado,
        "linea": linea,
        "recomendacion": f"{ICONO_MERCADO[mercado]} Más de {linea} {ETIQUETA_MERCADO[mercado]}",
        "rachas": elegido["rachas"],
        "probabilidad": elegido["probabilidad"],
        "solido": elegido["solido"],
    }


LEAGUE_PRIORITY = {CHAMPIONS_LEAGUE_ID: 0, PREMIER_LEAGUE_ID: 1}


@app.route("/api/calendario-semana")
def calendario_semana():
    """Calendario de la semana actual (lunes a domingo): Premier League +
    Champions League, con el Scout Pick embebido en cada partido (mercado
    estrella + líneas de cumplimiento) y ordenado con la Champions League
    priorizada y, dentro de cada liga, de mayor a menor probabilidad."""
    lunes, domingo = semana_actual()
    season_cl = temporada_por_defecto(CHAMPIONS_LEAGUE_ID)
    season_pl = temporada_por_defecto(PREMIER_LEAGUE_ID)

    fuentes = [
        (CHAMPIONS_LEAGUE_ID, "UEFA Champions League", season_cl),
        (PREMIER_LEAGUE_ID, "Premier League", season_pl),
    ]

    partidos = []
    for league_id, league_name, season in fuentes:
        filas = partidos_calendario(season, league_id, lunes, domingo)
        for (
            fixture_id, fecha, status, home_id, home_name, home_logo,
            away_id, away_name, away_logo, home_goals, away_goals,
        ) in filas:
            pick = construir_scout_pick(
                fixture_id, fecha, league_id, league_name,
                home_id, home_name, home_logo, away_id, away_name, away_logo, season,
            )
            partidos.append({**pick, "status": status, "homeGoals": home_goals, "awayGoals": away_goals})

    # "Sólidas" primero (umbral + muestra mínima cumplidos) y, dentro de cada
    # grupo de solidez, de mayor a menor probabilidad — así un 100% con 2
    # partidos de muestra no le gana a un 83% con 6 partidos de respaldo.
    partidos.sort(
        key=lambda p: (
            LEAGUE_PRIORITY.get(p["leagueId"], 99),
            0 if p["solido"] else 1,
            -(p["probabilidad"] if p["probabilidad"] is not None else -1),
        )
    )
    return jsonify(partidos)


def partidos_calendario(season: int, league_id: int, fecha_inicio: str, fecha_fin: str) -> list:
    conn = get_connection()
    filas = conn.execute(
        """
        SELECT m.id, m.date, m.status,
               m.home_team_id, t1.name, t1.logo_url,
               m.away_team_id, t2.name, t2.logo_url,
               m.home_goals, m.away_goals
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE m.league_id = ? AND m.season = ? AND date(m.date) BETWEEN ? AND ?
        ORDER BY m.date ASC
        """,
        (league_id, season, fecha_inicio, fecha_fin),
    ).fetchall()
    conn.close()
    return filas


def partidos_por_fecha(season: int, fecha: str) -> list:
    return partidos_calendario(season, PREMIER_LEAGUE_ID, fecha, fecha)


def _estadisticas_rapidas_equipo(team_id: int, season: int) -> dict:
    """Subconjunto de perfil + resumen usado tanto en las tarjetas de partido
    como en el cálculo del Radar de la Jornada."""
    perfil = calcular_perfil_equipo(team_id, season)
    resumen = calcular_resumen_equipo(team_id, season)
    return {
        "teamId": team_id,
        "teamName": perfil["teamName"],
        "teamLogo": perfil["teamLogo"],
        "goalsForAvg": perfil["general"]["goalsForAvg"],
        "over25Pct": resumen["over25Pct"],
        "cornersAvg": resumen["cornersAvg"],
        "cornersOverPct": resumen["cornersOverPct"],
        "cardsAvg": resumen["cardsAvg"],
        "cardsOverPct": resumen["cardsOverPct"],
    }


def calcular_radar_jornada(equipos_del_dia: list) -> dict | None:
    """A partir de las estadísticas rápidas de los equipos que juegan en el día
    seleccionado, destaca: mayor media goleadora, la tendencia (goles u córners)
    más fuerte, y el mayor riesgo de tarjetas."""
    if not equipos_del_dia:
        return None

    mayor_goleador = max(equipos_del_dia, key=lambda e: e["goalsForAvg"])

    tendencias = [(e["over25Pct"], e, "Over 2.5 goles") for e in equipos_del_dia]
    tendencias += [
        (e["cornersOverPct"], e, "Córners sobre línea")
        for e in equipos_del_dia
        if e["cornersOverPct"] is not None
    ]
    mejor_valor, mejor_equipo, mejor_mercado = max(tendencias, key=lambda t: t[0])

    candidatos_tarjetas = [e for e in equipos_del_dia if e["cardsAvg"] is not None]
    mayor_riesgo = max(candidatos_tarjetas, key=lambda e: e["cardsAvg"]) if candidatos_tarjetas else None

    return {
        "mayorMediaGoleadora": {
            "teamId": mayor_goleador["teamId"],
            "teamName": mayor_goleador["teamName"],
            "teamLogo": mayor_goleador["teamLogo"],
            "valor": mayor_goleador["goalsForAvg"],
        },
        "tendenciaMasFuerte": {
            "teamId": mejor_equipo["teamId"],
            "teamName": mejor_equipo["teamName"],
            "teamLogo": mejor_equipo["teamLogo"],
            "mercado": mejor_mercado,
            "valor": mejor_valor,
        },
        "mayorRiesgoTarjetas": (
            {
                "teamId": mayor_riesgo["teamId"],
                "teamName": mayor_riesgo["teamName"],
                "teamLogo": mayor_riesgo["teamLogo"],
                "valor": mayor_riesgo["cardsAvg"],
            }
            if mayor_riesgo is not None
            else None
        ),
    }


@app.route("/api/partidos")
def partidos_del_dia():
    season = request.args.get("season", type=int, default=None) or temporada_por_defecto()
    fecha = request.args.get("fecha", default=None) or date.today().isoformat()

    filas = partidos_por_fecha(season, fecha)

    equipos_vistos: dict = {}
    partidos = []

    for (
        fixture_id, fecha_partido, status, home_id, home_name, home_logo,
        away_id, away_name, away_logo, home_goals, away_goals,
    ) in filas:
        if home_id not in equipos_vistos:
            equipos_vistos[home_id] = _estadisticas_rapidas_equipo(home_id, season)
        if away_id not in equipos_vistos:
            equipos_vistos[away_id] = _estadisticas_rapidas_equipo(away_id, season)

        partidos.append(
            {
                "fixtureId": fixture_id,
                "date": fecha_partido,
                "status": status,
                "leagueId": PREMIER_LEAGUE_ID,
                "leagueName": "Premier League",
                "homeGoals": home_goals,
                "awayGoals": away_goals,
                "home": equipos_vistos[home_id],
                "away": equipos_vistos[away_id],
            }
        )

    return jsonify(
        {
            "fecha": fecha,
            "radar": calcular_radar_jornada(list(equipos_vistos.values())),
            "partidos": partidos,
        }
    )


@app.route("/api/competiciones")
def competiciones():
    return jsonify(COMPETICIONES)


@app.route("/api/equipos/<int:team_id>/perfil")
def perfil_equipo(team_id):
    league_id = request.args.get("league_id", type=int, default=None) or PREMIER_LEAGUE_ID
    season = request.args.get("season", type=int, default=None) or temporada_por_defecto(league_id)
    data = calcular_perfil_equipo(team_id, season, league_id)
    if data is None:
        return jsonify({"error": "Equipo no encontrado"}), 404
    return jsonify(data)


@app.route("/api/temporadas")
def listar_temporadas():
    league_id = request.args.get("league_id", type=int, default=None) or PREMIER_LEAGUE_ID
    conn = get_connection()
    filas = conn.execute(
        "SELECT DISTINCT season FROM matches WHERE league_id = ? AND season IS NOT NULL ORDER BY season DESC",
        (league_id,),
    ).fetchall()
    conn.close()
    return jsonify([fila[0] for fila in filas])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

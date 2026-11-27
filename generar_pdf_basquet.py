"""
Arma el mismo reporte NBA que se manda por texto a Telegram
(enviar_telegram_basquet.py), pero como PDF con tablas reales — un
resumen ejecutivo organizado POR PARTIDO: moneyline y diferencia de
puntos de ambos equipos, y una tabla ancha con los 4 indicadores de todos
los jugadores de ambos equipos, para ver en un solo lugar todo lo
apostable de ese partido puntual.
"""

import sqlite3
from datetime import date

from fpdf import FPDF

from analizar_jugadores_basquet import companeros_que_podrian_absorber, perfil_jugador_nba

TOP_JUGADORES_POR_EQUIPO = 8  # rotación habitual; deja afuera a los que casi no suman minutos
DIFERENCIA_MINIMA_ABSORCION = 3.0

STATS_JUGADOR = (
    ("points", "Puntos"),
    ("three_made", "Triples"),
    ("assists", "Asistencias"),
    ("rebounds_tot", "Rebotes"),
)

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# Anchos de columna (mm) que suman el ancho útil de una página A4 apaisada
# con márgenes de 12mm (297 - 24 = 273mm): Jugador + Equipo + 4 stats x
# (Prom/Línea/%) + DD% + TD%.
ANCHO_JUGADOR = 48
ANCHO_EQUIPO = 34
ANCHO_STAT = (14, 13, 12)  # Promedio, Línea, %
ANCHO_DOBLE = 16


def formatear_fecha(fecha_iso: str) -> str:
    fecha = date.fromisoformat(fecha_iso)
    return f"{DIAS_ES[fecha.weekday()]} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


def jugadores_del_equipo(team_id: int, season: int) -> list[dict]:
    conn = sqlite3.connect("apuestas.db")
    jugadores = conn.execute("SELECT id FROM nba_players WHERE team_id = ?", (team_id,)).fetchall()
    conn.close()
    return [p for (player_id,) in jugadores if (p := perfil_jugador_nba(player_id, season)) is not None]


class ReportePDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 8, f"Página {self.page_no()}", align="C")


def _titulo(pdf: FPDF, texto: str, tamano: int = 13) -> None:
    pdf.set_font("helvetica", "B", tamano)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(0, 8, texto, new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(1)


def _tabla(pdf: FPDF, encabezados: list[str], anchos: list[float], filas: list[list[str]]) -> None:
    pdf.set_font("helvetica", "B", 8)
    pdf.set_fill_color(245, 245, 245)
    for encabezado, ancho in zip(encabezados, anchos):
        pdf.cell(ancho, 6.5, encabezado, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("helvetica", "", 8)
    for fila in filas:
        for valor, ancho in zip(fila, anchos):
            pdf.cell(ancho, 6, str(valor), border=1, align="C")
        pdf.ln()
    pdf.ln(3)


def _anchos_tabla_jugadores() -> list[float]:
    anchos = [ANCHO_JUGADOR, ANCHO_EQUIPO]
    for _ in STATS_JUGADOR:
        anchos.extend(ANCHO_STAT)
    anchos.extend([ANCHO_DOBLE, ANCHO_DOBLE])
    return anchos


def _encabezados_tabla_jugadores() -> list[str]:
    encabezados = ["Jugador", "Equipo"]
    for _, etiqueta in STATS_JUGADOR:
        encabezados.extend([f"{etiqueta[:4]} Prom", f"{etiqueta[:4]} Lín", f"{etiqueta[:4]} %"])
    encabezados.extend(["DD%", "TD%"])
    return encabezados


def _fila_jugador(perfil: dict, equipo: str) -> list[str]:
    fila = [perfil["playerName"][:22], equipo.split()[-1]]
    for stat_key, _ in STATS_JUGADOR:
        datos = perfil["props"].get(stat_key)
        if datos is None:
            fila.extend(["-", "-", "-"])
        else:
            fila.extend([f"{datos['promedio']:.1f}", f"{datos['linea']:.1f}", f"{datos['overPct']:.0f}%"])
    fila.extend([f"{perfil['doubleDoublePct']:.0f}%", f"{perfil['tripleDoublePct']:.0f}%"])
    return fila


def _seccion_partido(pdf: FPDF, partido: dict, season: int, lesionados: dict) -> None:
    pronostico = partido["pronostico"]
    home, away = pronostico["home"], pronostico["away"]

    _titulo(pdf, f"{partido['home']} vs {partido['away']}", tamano=14)

    _tabla(
        pdf,
        ["Equipo", "Moneyline", "Dif. de puntos", "Más de pts. totales"],
        [110, 45, 45, 73],
        [
            [home["nombre"], f"{home['moneyline']:.0f}%", f"{home['margen']:+.1f}", f"{pronostico['puntosTotales']['linea']} ({pronostico['puntosTotales']['overPct']:.0f}%)"],
            [away["nombre"], f"{away['moneyline']:.0f}%", f"{away['margen']:+.1f}", ""],
        ],
    )

    filas_jugadores = []
    for team_id, team_name in ((partido["homeId"], partido["home"]), (partido["awayId"], partido["away"])):
        jugadores = sorted(
            jugadores_del_equipo(team_id, season),
            key=lambda p: p["props"].get("points", {}).get("promedio", 0),
            reverse=True,
        )[:TOP_JUGADORES_POR_EQUIPO]
        filas_jugadores.extend(_fila_jugador(perfil, team_name) for perfil in jugadores)

    if filas_jugadores:
        _tabla(pdf, _encabezados_tabla_jugadores(), _anchos_tabla_jugadores(), filas_jugadores)

    filas_bajas = []
    for team_name in (partido["home"], partido["away"]):
        for baja in lesionados.get(team_name, []):
            filas_bajas.append([team_name, baja["jugador"], baja["estado"]])
    if filas_bajas:
        _tabla(pdf, ["Equipo", "Jugador", "Estado"], [100, 100, 73], filas_bajas)

    filas_absorcion = _filas_absorcion(partido, lesionados, season)
    if filas_absorcion:
        _tabla(pdf, ["Equipo", "Jugador Out", "Compañero a vigilar", "Prom. con/sin"], [70, 60, 70, 73], filas_absorcion)


def _filas_absorcion(partido: dict, lesionados: dict, season: int) -> list[list[str]]:
    filas = []
    conn = sqlite3.connect("apuestas.db")
    for team_id, team_name in ((partido["homeId"], partido["home"]), (partido["awayId"], partido["away"])):
        for baja in lesionados.get(team_name, []):
            if baja["estado"] != "Out":
                continue
            fila = conn.execute(
                "SELECT id FROM nba_players WHERE team_id = ? AND name = ?", (team_id, baja["jugador"])
            ).fetchone()
            if fila is None:
                continue
            candidatos = companeros_que_podrian_absorber(team_id, fila[0], season, stat="points")
            if not candidatos or candidatos[0]["diferencia"] < DIFERENCIA_MINIMA_ABSORCION:
                continue
            mejor = candidatos[0]
            filas.append(
                [team_name, baja["jugador"], mejor["playerName"], f"{mejor['promedioCon']} -> {mejor['promedioSin']} ({mejor['diferencia']:+.1f})"]
            )
    conn.close()
    return filas


def generar_pdf(ruta: str, partidos: list[dict], fecha_hoy: str, lesionados: dict, season: int) -> str:
    pdf = ReportePDF(orientation="L", unit="mm", format="A4")
    pdf.set_margin(12)
    pdf.add_page()

    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 12, "Pronósticos NBA de hoy", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 8, formatear_fecha(fecha_hoy), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if not partidos:
        pdf.set_font("helvetica", "", 11)
        pdf.cell(0, 8, "No encontramos partidos NBA con datos suficientes para hoy.")
        pdf.output(ruta)
        return ruta

    for partido in partidos:
        _seccion_partido(pdf, partido, season, lesionados)

    pdf.output(ruta)
    return ruta

"""
Arma el mismo reporte NBA que se manda por texto a Telegram
(enviar_telegram_basquet.py), pero como PDF — un resumen ejecutivo
organizado POR PARTIDO: un pick de equipo (moneyline o +/-), y los
mejores picks de jugador por indicador (puntos, triples, asistencias,
rebotes, doble/triple-doble), filtrados por probabilidad y promedio real
— no el plantel completo.
"""

import sqlite3
from datetime import date

from fpdf import FPDF

from analizar_basquet import mejor_pick_equipo
from analizar_jugadores_basquet import companeros_que_podrian_absorber, mejores_picks_partido

DIFERENCIA_MINIMA_ABSORCION = 3.0

ETIQUETAS_STAT = {
    "points": "Puntos",
    "three_made": "Triples",
    "assists": "Asistencias",
    "rebounds_tot": "Rebotes",
    "doble_doble": "Doble-doble",
    "triple_doble": "Triple-doble",
}

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def formatear_fecha(fecha_iso: str) -> str:
    fecha = date.fromisoformat(fecha_iso)
    return f"{DIAS_ES[fecha.weekday()]} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


class ReportePDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 8, f"Página {self.page_no()}", align="C")


def _titulo(pdf: FPDF, texto: str, tamano: int = 14) -> None:
    pdf.set_font("helvetica", "B", tamano)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(0, 8, texto, new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(1)


def _tabla(pdf: FPDF, encabezados: list[str], anchos: list[float], filas: list[list[str]]) -> None:
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(245, 245, 245)
    for encabezado, ancho in zip(encabezados, anchos):
        pdf.cell(ancho, 6.5, encabezado, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("helvetica", "", 9)
    for fila in filas:
        for valor, ancho in zip(fila, anchos):
            pdf.cell(ancho, 6, str(valor), border=1, align="C")
        pdf.ln()
    pdf.ln(3)


def _texto_pick_equipo(pick: dict | None) -> str:
    if pick is None:
        return "Partido parejo - sin pick de equipo confiable"
    if pick["tipo"] == "moneyline":
        return f"Pick de equipo: {pick['equipo']} - Moneyline {pick['valor']:.0f}%"
    return f"Pick de equipo: {pick['equipo']} - Diferencia de puntos {pick['valor']:+.1f}"


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


def _seccion_partido(pdf: FPDF, partido: dict, season: int, lesionados: dict) -> None:
    pronostico = partido["pronostico"]

    _titulo(pdf, f"{partido['home']} vs {partido['away']}")

    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, _texto_pick_equipo(mejor_pick_equipo(pronostico)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(
        0, 7,
        f"Más de {pronostico['puntosTotales']['linea']} puntos totales - {pronostico['puntosTotales']['overPct']:.0f}%",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(2)

    equipos = [(partido["homeId"], partido["home"]), (partido["awayId"], partido["away"])]
    picks = mejores_picks_partido(equipos, season)

    filas_picks = []
    for stat_key in ("points", "three_made", "assists", "rebounds_tot"):
        for candidato in picks.get(stat_key, []):
            filas_picks.append(
                [
                    ETIQUETAS_STAT[stat_key],
                    candidato["jugador"],
                    candidato["equipo"].split()[-1],
                    f"{candidato['promedio']:.1f}",
                    f"{candidato['linea']:.1f}",
                    f"{candidato['probabilidad']:.0f}%",
                ]
            )
    if filas_picks:
        _tabla(pdf, ["Indicador", "Jugador", "Equipo", "Promedio", "Línea", "Prob."], [40, 55, 35, 30, 30, 25], filas_picks)

    filas_dobles = []
    for clave in ("doble_doble", "triple_doble"):
        for candidato in picks.get(clave, []):
            filas_dobles.append([ETIQUETAS_STAT[clave], candidato["jugador"], candidato["equipo"].split()[-1], f"{candidato['probabilidad']:.0f}%"])
    if filas_dobles:
        _tabla(pdf, ["Indicador", "Jugador", "Equipo", "Prob."], [40, 70, 50, 55], filas_dobles)

    filas_bajas = []
    for team_name in (partido["home"], partido["away"]):
        for baja in lesionados.get(team_name, []):
            filas_bajas.append([team_name, baja["jugador"], baja["estado"]])
    if filas_bajas:
        _tabla(pdf, ["Equipo", "Jugador", "Estado"], [100, 100, 73], filas_bajas)

    filas_absorcion = _filas_absorcion(partido, lesionados, season)
    if filas_absorcion:
        _tabla(pdf, ["Equipo", "Jugador Out", "Compañero a vigilar", "Prom. con/sin"], [70, 60, 70, 73], filas_absorcion)

    pdf.ln(4)


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

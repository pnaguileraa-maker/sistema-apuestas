"""
Resumen ejecutivo NBA en PDF, organizado POR PARTIDO: un pick de equipo
(moneyline + diferencia de puntos/hándicap juntos), los mejores picks de
jugador por indicador (puntos, triples, asistencias, rebotes, doble/
triple-doble) filtrados por probabilidad real y producción real — no el
plantel completo — y, para cada baja confirmada, qué aportaba ese
jugador y quién lo absorbe en cada categoría donde era pieza clave.

Es el ÚNICO formato que se manda por Telegram (ver
enviar_telegram_basquet.py) — ya no se manda un mensaje de texto aparte.
"""

import sqlite3
from datetime import date

from fpdf import FPDF

from analizar_basquet import mejor_pick_equipo
from analizar_jugadores_basquet import analizar_impacto_baja, mejores_picks_partido

ETIQUETAS_STAT = {
    "points": "Puntos",
    "three_made": "Triples",
    "assists": "Asistencias",
    "rebounds_tot": "Rebotes",
    "doble_doble": "Doble-doble",
    "triple_doble": "Triple-doble",
}

# Un color de fondo por indicador, para diferenciarlos de un vistazo en la
# tabla de picks (todas igual de claras para no tapar el texto negro).
COLOR_POR_INDICADOR = {
    "Puntos": (217, 235, 255),
    "Triples": (221, 245, 221),
    "Asistencias": (255, 245, 204),
    "Rebotes": (255, 228, 214),
    "Doble-doble": (233, 222, 247),
    "Triple-doble": (247, 222, 237),
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


def _tabla_coloreada_por_indicador(pdf: FPDF, encabezados: list[str], anchos: list[float], filas: list[list[str]]) -> None:
    """Igual que _tabla, pero pinta cada fila según su columna 0
    (Indicador) usando COLOR_POR_INDICADOR — así se distinguen puntos,
    triples, asistencias y rebotes de un vistazo."""
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(245, 245, 245)
    for encabezado, ancho in zip(encabezados, anchos):
        pdf.cell(ancho, 6.5, encabezado, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("helvetica", "", 9)
    for fila in filas:
        color = COLOR_POR_INDICADOR.get(fila[0], (255, 255, 255))
        pdf.set_fill_color(*color)
        for valor, ancho in zip(fila, anchos):
            pdf.cell(ancho, 6, str(valor), border=1, align="C", fill=True)
        pdf.ln()
    pdf.ln(3)


def _texto_pick_equipo(pick: dict | None) -> str:
    if pick is None:
        return "Partido parejo - sin pick de equipo confiable"
    if pick["tipo"] == "moneyline":
        return f"Pick de equipo: {pick['equipo']} - Moneyline {pick['moneyline']:.0f}% | Hándicap {pick['margen']:+.1f} pts"
    # Si el pick se decidio por handicap es porque NINGUN equipo tiene un
    # moneyline confiable (<55%) - mostrarlo igual se leeria como una
    # recomendacion de moneyline que no es real.
    return f"Pick de equipo: {pick['equipo']} - Hándicap {pick['margen']:+.1f} pts (moneyline parejo)"


def _filas_impacto_bajas(partido: dict, lesionados: dict, season: int) -> list[list[str]]:
    filas = []
    for team_id, team_name in ((partido["homeId"], partido["home"]), (partido["awayId"], partido["away"])):
        for baja in lesionados.get(team_name, []):
            if baja["estado"] != "Out":
                continue
            impacto = analizar_impacto_baja(team_id, team_name, baja["jugador"], season)
            if impacto is None or not impacto["impactos"]:
                continue
            for item in impacto["impactos"]:
                companero = item["companero"]
                filas.append(
                    [
                        baja["jugador"],
                        f"{item['etiqueta']}: {item['propioPromedio']:.1f}",
                        companero["playerName"],
                        f"{companero['promedioCon']} -> {companero['promedioSin']} ({companero['diferencia']:+.1f})",
                    ]
                )
    return filas


def _seccion_partido(pdf: FPDF, partido: dict, season: int, lesionados: dict) -> None:
    pronostico = partido["pronostico"]

    _titulo(pdf, f"{partido['home']} vs {partido['away']}")

    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, _texto_pick_equipo(mejor_pick_equipo(pronostico)), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    equipos = [(partido["homeId"], partido["home"]), (partido["awayId"], partido["away"])]
    picks = mejores_picks_partido(equipos, season, lesionados)

    filas_picks = []
    for stat_key in ("points", "three_made", "assists", "rebounds_tot"):
        for candidato in picks.get(stat_key, []):
            nombre = candidato["jugador"] + (f" ({candidato['alerta']})" if candidato.get("alerta") else "")
            filas_picks.append(
                [
                    ETIQUETAS_STAT[stat_key],
                    nombre,
                    candidato["equipo"].split()[-1],
                    f"{candidato['promedio']:.1f}",
                    f"{candidato['linea']:.1f}",
                    f"{candidato['probabilidad']:.0f}%",
                ]
            )
    if filas_picks:
        _tabla_coloreada_por_indicador(pdf, ["Indicador", "Jugador", "Equipo", "Promedio", "Línea", "Prob."], [40, 55, 35, 30, 30, 25], filas_picks)

    filas_dobles = []
    for clave in ("doble_doble", "triple_doble"):
        for candidato in picks.get(clave, []):
            nombre = candidato["jugador"] + (f" ({candidato['alerta']})" if candidato.get("alerta") else "")
            filas_dobles.append([ETIQUETAS_STAT[clave], nombre, candidato["equipo"].split()[-1], f"{candidato['probabilidad']:.0f}%"])
    if filas_dobles:
        _tabla_coloreada_por_indicador(pdf, ["Indicador", "Jugador", "Equipo", "Prob."], [40, 70, 50, 55], filas_dobles)

    filas_bajas = []
    for team_name in (partido["home"], partido["away"]):
        for baja in lesionados.get(team_name, []):
            filas_bajas.append([team_name, baja["jugador"], baja["estado"]])
    if filas_bajas:
        _tabla(pdf, ["Equipo", "Jugador", "Estado"], [100, 100, 73], filas_bajas)

    filas_impacto = _filas_impacto_bajas(partido, lesionados, season)
    if filas_impacto:
        pdf.set_font("helvetica", "I", 8)
        pdf.cell(0, 5, "Impacto de las bajas Out - qué aportaba y quién lo absorbe en cada categoría:", new_x="LMARGIN", new_y="NEXT")
        _tabla(pdf, ["Jugador Out", "Su aporte", "Compañero a vigilar", "Prom. con/sin él"], [50, 50, 55, 78], filas_impacto)

    pdf.ln(4)


def generar_pdf(ruta: str, partidos: list[dict], fecha_hoy: str, lesionados: dict, season: int) -> str:
    pdf = ReportePDF(orientation="L", unit="mm", format="A4")
    pdf.set_margin(12)
    pdf.add_page()

    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 12, "Pronósticos NBA de hoy", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 8, formatear_fecha(fecha_hoy), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 6, "Hándicap +/-: puntos que el equipo puede ganar o perder por margen y seguir cubriendo (ej. +8.5 = cubre perdiendo por 8 o menos).", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "DD/TD considera puntos + rebotes + asistencias (sin robos/tapones, no disponibles en esta fuente).", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Out = confirmado afuera (excluido de los picks). Day-To-Day = podria jugar, aparece marcado junto al nombre.", new_x="LMARGIN", new_y="NEXT")
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

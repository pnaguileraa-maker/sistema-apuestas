"""
Arma el mismo reporte NBA que se manda por texto a Telegram
(enviar_telegram_basquet.py), pero como PDF con tablas reales — un
resumen ejecutivo para guardar/reenviar, en vez de tener que desplazarse
por varios mensajes de texto.

No duplica ningún cálculo: recibe las mismas estructuras ya armadas
(partidos ordenados, pool de jugadores, lesionados) que usa el mensaje de
Telegram, así que ambos formatos siempre muestran exactamente lo mismo.
"""

import sqlite3
from datetime import date

from fpdf import FPDF

from analizar_jugadores_basquet import companeros_que_podrian_absorber

# Duplicados a propósito desde enviar_telegram_basquet.py (en vez de
# importarlos) para que este módulo no dependa de ese otro — evita un
# import circular, ya que enviar_telegram_basquet.py es el que llama a
# generar_pdf() desde su main().
TOP_TABLA = 8
DIFERENCIA_MINIMA_ABSORCION = 3.0
STATS_TABLA = (
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


def formatear_fecha(fecha_iso: str) -> str:
    fecha = date.fromisoformat(fecha_iso)
    return f"{DIAS_ES[fecha.weekday()]} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


def _apodo(nombre_equipo: str) -> str:
    return nombre_equipo.split()[-1]


class ReportePDF(FPDF):
    def header(self) -> None:
        pass  # título propio por página, no header repetido

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 8, f"Página {self.page_no()}", align="C")


def _titulo_seccion(pdf: FPDF, texto: str) -> None:
    pdf.set_font("helvetica", "B", 13)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(0, 8, texto, new_x="LMARGIN", new_y="NEXT", fill=True)
    pdf.ln(2)


def _tabla(pdf: FPDF, encabezados: list[str], anchos: list[int], filas: list[list[str]]) -> None:
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(245, 245, 245)
    for encabezado, ancho in zip(encabezados, anchos):
        pdf.cell(ancho, 7, encabezado, border=1, fill=True)
    pdf.ln()

    pdf.set_font("helvetica", "", 9)
    for fila in filas:
        for valor, ancho in zip(fila, anchos):
            pdf.cell(ancho, 6.5, str(valor), border=1)
        pdf.ln()
    pdf.ln(4)


def _seccion_partidos(pdf: FPDF, partidos: list[dict]) -> None:
    _titulo_seccion(pdf, "Partidos de hoy (de mayor a menor probabilidad)")
    filas = []
    for indice, partido in enumerate(partidos, start=1):
        pronostico = partido["pronostico"]
        if pronostico["moneyline"] is not None:
            pick = f"{pronostico['moneyline']['equipo']} ({pronostico['moneyline']['probabilidad']:.0f}%)"
        else:
            margen = pronostico["margen"]
            pick = f"{margen['equipo']} ({margen['diferencia']:+.1f} dif.)" if margen else "Sin favorito claro"
        filas.append(
            [
                str(indice),
                f"{partido['home']} vs {partido['away']}",
                pick,
                f"{pronostico['puntosTotales']['linea']} pts ({pronostico['puntosTotales']['overPct']:.0f}%)",
            ]
        )
    _tabla(pdf, ["#", "Partido", "Pick principal", "Total de puntos"], [10, 75, 55, 50], filas)


def _seccion_stat(pdf: FPDF, pool: list[dict], stat_key: str, titulo: str) -> None:
    filas_datos = []
    for item in pool:
        datos = item["perfil"]["props"].get(stat_key)
        if datos is not None:
            filas_datos.append((item["perfil"]["playerName"], item["rival"], datos["promedio"], datos["linea"], datos["overPct"]))
    if not filas_datos:
        return

    filas_datos.sort(key=lambda f: f[2], reverse=True)
    filas_datos = filas_datos[:TOP_TABLA]

    _titulo_seccion(pdf, titulo)
    filas = [[nombre, _apodo(rival), f"{promedio:.1f}", f"{linea:.1f}", f"{pct:.0f}%"] for nombre, rival, promedio, linea, pct in filas_datos]
    _tabla(pdf, ["Jugador", "Rival", "Promedio", "Línea", "% Sobre línea"], [55, 40, 30, 30, 35], filas)


def _seccion_dobles(pdf: FPDF, pool: list[dict]) -> None:
    filas_datos = [
        (item["perfil"]["playerName"], item["rival"], item["perfil"]["doubleDoublePct"], item["perfil"]["tripleDoublePct"])
        for item in pool
        if item["perfil"]["doubleDoublePct"] > 0
    ]
    if not filas_datos:
        return

    filas_datos.sort(key=lambda f: (f[2], f[3]), reverse=True)
    filas_datos = filas_datos[:TOP_TABLA]

    _titulo_seccion(pdf, "Doble-doble / Triple-doble")
    filas = [[nombre, _apodo(rival), f"{dd:.0f}%", f"{td:.0f}%"] for nombre, rival, dd, td in filas_datos]
    _tabla(pdf, ["Jugador", "Rival", "% Doble-doble", "% Triple-doble"], [55, 40, 45, 45], filas)


def _seccion_bajas(pdf: FPDF, partidos: list[dict], lesionados: dict) -> None:
    filas = []
    equipos_vistos = set()
    for partido in partidos:
        for team_name in (partido["home"], partido["away"]):
            if team_name in equipos_vistos:
                continue
            equipos_vistos.add(team_name)
            for baja in lesionados.get(team_name, []):
                filas.append([team_name, baja["jugador"], baja["estado"]])

    if not filas:
        return
    _titulo_seccion(pdf, "Bajas de hoy")
    _tabla(pdf, ["Equipo", "Jugador", "Estado"], [70, 60, 40], filas)


def _seccion_absorciones(pdf: FPDF, partidos: list[dict], lesionados: dict, season: int) -> None:
    filas = []
    equipos_vistos = set()
    conn = sqlite3.connect("apuestas.db")
    for partido in partidos:
        for team_id, team_name in ((partido["homeId"], partido["home"]), (partido["awayId"], partido["away"])):
            if team_name in equipos_vistos:
                continue
            equipos_vistos.add(team_name)
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
                    [
                        team_name,
                        baja["jugador"],
                        mejor["playerName"],
                        f"{mejor['promedioCon']} -> {mejor['promedioSin']} ({mejor['diferencia']:+.1f})",
                    ]
                )
    conn.close()

    if not filas:
        return
    _titulo_seccion(pdf, "Posible absorción de puntos por lesión")
    _tabla(pdf, ["Equipo", "Jugador Out", "Compañero a vigilar", "Prom. con/sin"], [45, 40, 45, 50], filas)


def generar_pdf(
    ruta: str,
    partidos: list[dict],
    fecha_hoy: str,
    pool: list[dict],
    lesionados: dict,
    season: int,
) -> str:
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

    _seccion_partidos(pdf, partidos)
    for stat_key, titulo in STATS_TABLA:
        _seccion_stat(pdf, pool, stat_key, titulo)

    _seccion_dobles(pdf, pool)
    _seccion_bajas(pdf, partidos, lesionados)
    _seccion_absorciones(pdf, partidos, lesionados, season)

    pdf.output(ruta)
    return ruta

"""
Resumen ejecutivo de fútbol en PDF, mismo formato que el de NBA
(generar_pdf_basquet.py) pero centrado en EQUIPOS/duelos, no jugadores
(el fútbol no tiene picks individuales en este reporte): resultado (1X2),
hándicap de goles, y mercados totales + por equipo de goles (con 1er/2do
tiempo), córners, tarjetas y tiros al arco.

Es el ÚNICO formato que se manda por Telegram (ver
enviar_telegram_futbol.py) — solo el PDF, sin mensaje de texto aparte.
"""

from datetime import date

from fpdf import FPDF

ETIQUETA_MERCADO_TOTAL = {
    "goals": "Goles totales",
    "corners": "Córners totales",
    "cards": "Tarjetas totales",
    "shots_on_target": "Tiros al arco totales",
}

COLOR_POR_MERCADO = {
    "Goles totales": (217, 235, 255),
    "Córners totales": (221, 245, 221),
    "Tarjetas totales": (255, 245, 204),
    "Tiros al arco totales": (255, 228, 214),
    "1er tiempo (goles)": (233, 222, 247),
    "2do tiempo (goles)": (247, 222, 237),
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


def _asegurar_espacio(pdf: FPDF, filas_encabezado: int, cantidad_filas: int, alto_fila: float = 6.5) -> None:
    """Fuerza un salto de página ANTES de empezar una tabla si no entra
    completa en lo que queda de la página — sin esto, FPDF puede cortar el
    encabezado a mitad de camino (una fila del encabezado en una página,
    el resto en la siguiente), dejando una tabla ilegible."""
    if pdf.will_page_break(alto_fila * (filas_encabezado + cantidad_filas)):
        pdf.add_page()


def _tabla(pdf: FPDF, encabezados: list[str], anchos: list[float], filas: list[list[str]]) -> None:
    _asegurar_espacio(pdf, filas_encabezado=1, cantidad_filas=len(filas))
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


def _tabla_equipos(pdf: FPDF, ancho_equipo: float, ancho_sub: float, grupos: list[str], filas: list[list[str]]) -> None:
    """Tabla con encabezado de DOS niveles: "Equipo" (ocupa las dos filas
    de encabezado) + un grupo por indicador (ej. "Córners") que a su vez
    cubre 3 columnas hijas (Prom/Lín/%). Con un solo nivel de encabezado,
    el texto de columnas como "Córners Prom" no entra en ~12mm y se
    superpone con la columna vecina."""
    alto_fila = 6
    _asegurar_espacio(pdf, filas_encabezado=2, cantidad_filas=len(filas), alto_fila=alto_fila)

    x_inicio = pdf.get_x()
    y_inicio = pdf.get_y()

    pdf.set_font("helvetica", "B", 8)
    pdf.set_fill_color(245, 245, 245)
    pdf.cell(ancho_equipo, alto_fila * 2, "Equipo", border=1, align="C", fill=True)

    x = x_inicio + ancho_equipo
    for grupo in grupos:
        pdf.set_xy(x, y_inicio)
        pdf.cell(ancho_sub * 3, alto_fila, grupo, border=1, align="C", fill=True)
        x += ancho_sub * 3

    x = x_inicio + ancho_equipo
    pdf.set_xy(x, y_inicio + alto_fila)
    for _ in grupos:
        for sub in ("Prom", "Lín", "%"):
            pdf.cell(ancho_sub, alto_fila, sub, border=1, align="C", fill=True)
    pdf.ln(alto_fila)

    pdf.set_font("helvetica", "", 8)
    for fila in filas:
        pdf.cell(ancho_equipo, alto_fila, str(fila[0]), border=1, align="C")
        for valor in fila[1:]:
            pdf.cell(ancho_sub, alto_fila, str(valor), border=1, align="C")
        pdf.ln()
    pdf.ln(3)


def _tabla_coloreada(pdf: FPDF, encabezados: list[str], anchos: list[float], filas: list[list[str]]) -> None:
    _asegurar_espacio(pdf, filas_encabezado=1, cantidad_filas=len(filas))
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(245, 245, 245)
    for encabezado, ancho in zip(encabezados, anchos):
        pdf.cell(ancho, 6.5, encabezado, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("helvetica", "", 9)
    for fila in filas:
        color = COLOR_POR_MERCADO.get(fila[0], (255, 255, 255))
        pdf.set_fill_color(*color)
        for valor, ancho in zip(fila, anchos):
            pdf.cell(ancho, 6, str(valor), border=1, align="C", fill=True)
        pdf.ln()
    pdf.ln(3)


def _texto_resultado(partido: dict) -> str:
    resultado = partido["pronostico"]["resultado"]
    opciones = [
        (partido["home"], resultado["homePct"]),
        ("Empate", resultado["drawPct"]),
        (partido["away"], resultado["awayPct"]),
    ]
    favorito, pct = max(opciones, key=lambda o: o[1])
    handicap = partido["pronostico"]["handicapHome"]
    return (
        f"Pick de resultado: {favorito} ({pct:.0f}%) "
        f"| 1X2 -> {partido['home']} {resultado['homePct']:.0f}% / Empate {resultado['drawPct']:.0f}% / {partido['away']} {resultado['awayPct']:.0f}% "
        f"| Hándicap {partido['home']} {handicap:+.1f} goles"
    )


def _filas_mercados_totales(pronostico: dict) -> list[list[str]]:
    filas = []
    for mercado in pronostico["mercadosTotales"]:
        etiqueta = ETIQUETA_MERCADO_TOTAL[mercado["mercado"]]
        filas.append([etiqueta, f"{mercado['linea']}", f"{mercado['probabilidad']:.0f}%"])

    goles_tiempo = pronostico["golesPorTiempoTotal"]
    for clave, etiqueta in (("primerTiempo", "1er tiempo (goles)"), ("segundoTiempo", "2do tiempo (goles)")):
        datos = goles_tiempo[clave]
        if datos["linea"] is not None:
            filas.append([etiqueta, f"{datos['linea']}", f"{datos['overPct']:.0f}%"])
    return filas


def _fila_equipo(nombre: str, lado: dict) -> list[str]:
    perfil = lado["perfil"]
    tiempo = lado["golesPorTiempo"]

    def _grupo(datos: dict) -> list[str]:
        if datos["promedio"] is None:
            return ["-", "-", "-"]
        return [f"{datos['promedio']:.1f}", f"{datos['linea']:.1f}", f"{datos['overPct']:.0f}%"]

    fila = [nombre]
    fila += _grupo(perfil["corners"])
    fila += _grupo(perfil["tarjetas"])
    fila += _grupo(perfil["tiros"])
    fila += _grupo(tiempo["primerTiempo"])
    fila += _grupo(tiempo["segundoTiempo"])
    return fila


def _seccion_partido(pdf: FPDF, partido: dict) -> None:
    pronostico = partido["pronostico"]

    _titulo(pdf, f"{partido['liga']} - {partido['home']} vs {partido['away']}")

    pdf.set_font("helvetica", "B", 10)
    pdf.multi_cell(0, 6, _texto_resultado(partido), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    filas_totales = _filas_mercados_totales(pronostico)
    if filas_totales:
        _tabla_coloreada(pdf, ["Mercado (total del partido)", "Línea", "Prob."], [90, 40, 40], filas_totales)

    grupos_equipo = ["Córners", "Tarjetas", "Tiros al arco", "1er tiempo", "2do tiempo"]
    filas_equipo = [
        _fila_equipo(partido["home"], pronostico["home"]),
        _fila_equipo(partido["away"], pronostico["away"]),
    ]
    _tabla_equipos(pdf, ancho_equipo=42, ancho_sub=15, grupos=grupos_equipo, filas=filas_equipo)

    pdf.ln(4)


def generar_pdf(ruta: str, partidos: list[dict], fecha_manana: str) -> str:
    pdf = ReportePDF(orientation="L", unit="mm", format="A4")
    pdf.set_margin(12)
    pdf.add_page()

    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 12, "Pronósticos de fútbol para mañana", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 8, formatear_fecha(fecha_manana), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 6, "Hándicap: goles que el equipo local puede ganar o perder por margen y seguir cubriendo (ej. +1.1 = cubre perdiendo por 1 gol o menos).", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Prom./Lín./%: promedio real del equipo en su rol, línea de apuesta con margen bajo ese promedio, y % historico que la supera.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    if not partidos:
        pdf.set_font("helvetica", "", 11)
        pdf.cell(0, 8, "No encontramos partidos de fútbol con datos suficientes para mañana.")
        pdf.output(ruta)
        return ruta

    for partido in partidos:
        _seccion_partido(pdf, partido)

    pdf.output(ruta)
    return ruta

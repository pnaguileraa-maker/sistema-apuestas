"""
Envía por Telegram, cada tarde/noche antes de que empiecen, el reporte de
pronósticos NBA (moneyline, puntos totales, tablas de jugadores por
indicador y lesionados) de los partidos de HOY.

Mensaje SEPARADO del reporte de fútbol (enviar_telegram.py) — mismo bot y
chat, pero un envío aparte, para no mezclar ambos deportes en un solo texto.

Se calcula 100% desde apuestas.db (analizar_basquet.py /
analizar_jugadores_basquet.py) + el reporte de lesionados en vivo de ESPN
(lesionados_nba.py), sin depender de la API de Claude.

Variables de entorno requeridas (.env):
    TELEGRAM_BOT_TOKEN   Token del bot (de @BotFather)
    TELEGRAM_CHAT_ID     Chat ID del grupo donde se envía el reporte

Ejecutar manualmente:
    python enviar_telegram_basquet.py
"""

import os
import sqlite3
import tempfile
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

from analizar_basquet import pronostico_partido
from analizar_jugadores_basquet import companeros_que_podrian_absorber, perfil_jugador_nba
from cargar_temporada_nba import temporada_actual_nba
from lesionados_nba import obtener_lesionados

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
TELEGRAM_API_URL = f"{TELEGRAM_API_BASE}/sendMessage"

MAX_PARTIDOS = 10
TOP_TABLA = 8  # filas por tabla de indicador
DIFERENCIA_MINIMA_ABSORCION = 3.0  # puntos de más sin el compañero para que valga la pena avisarlo
LIMITE_CARACTERES_MENSAJE = 3800

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

STATS_TABLA = (
    ("points", "📊 *Puntos*"),
    ("three_made", "🎯 *Triples*"),
    ("assists", "🤝 *Asistencias*"),
    ("rebounds_tot", "🏉 *Rebotes*"),
)


def formatear_fecha(fecha_iso: str) -> str:
    fecha = date.fromisoformat(fecha_iso)
    return f"{DIAS_ES[fecha.weekday()]} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


def _apodo(nombre_equipo: str) -> str:
    """Último término del nombre oficial (ej. "Los Angeles Lakers" ->
    "Lakers") — así entran en las columnas angostas de las tablas."""
    return nombre_equipo.split()[-1]


def partidos_de_hoy() -> tuple[list[dict], str, int]:
    """Partidos de HOY (el día real en que se juegan, para quien lee el
    reporte). La API agrupa los partidos nocturnos de EEUU bajo el día
    calendario UTC siguiente (7pm ET = medianoche UTC del día de mañana),
    así que la consulta interna usa esa fecha "de mañana" en UTC — pero
    para el humano que lee el mensaje a las 19:00 Chile, esos partidos son
    los de HOY a la noche, no los de mañana. Por eso se devuelve
    date.today() como fecha real a mostrar, no la fecha usada en la query."""
    season = temporada_actual_nba()
    hoy = date.today().isoformat()
    bucket_utc_partidos_de_hoy = (date.today() + timedelta(days=1)).isoformat()

    conn = sqlite3.connect("apuestas.db")
    filas = conn.execute(
        """
        SELECT g.id, g.home_team_id, h.name, g.away_team_id, a.name
        FROM nba_games g
        JOIN nba_teams h ON h.id = g.home_team_id
        JOIN nba_teams a ON a.id = g.away_team_id
        WHERE g.season = ? AND date(g.date) = ? AND g.home_points IS NULL
          AND g.status != 'Cancelled'
        """,
        (season, bucket_utc_partidos_de_hoy),
    ).fetchall()
    conn.close()

    partidos = []
    for _game_id, home_id, home_name, away_id, away_name in filas:
        pronostico = pronostico_partido(home_id, away_id, season)
        if pronostico is None:
            continue
        partidos.append(
            {
                "home": home_name,
                "away": away_name,
                "homeId": home_id,
                "awayId": away_id,
                "pronostico": pronostico,
            }
        )

    return partidos[:MAX_PARTIDOS], hoy, season


def _clave_orden_partido(partido: dict) -> float:
    """Probabilidad del pick de moneyline; 0 (al final) si no hay favorito
    claro — ahí no hay un "éxito" concreto que ordenar."""
    moneyline = partido["pronostico"]["moneyline"]
    return moneyline["probabilidad"] if moneyline is not None else 0.0


def construir_resumen_partidos(partidos: list[dict]) -> str:
    lineas = ["*Partidos de hoy (de mayor a menor probabilidad)*"]
    for indice, partido in enumerate(partidos, start=1):
        pronostico = partido["pronostico"]
        if pronostico["moneyline"] is not None:
            pick = f"💰 {pronostico['moneyline']['equipo']} ({pronostico['moneyline']['probabilidad']:.0f}%)"
        else:
            margen = pronostico["margen"]
            pick = f"📐 {margen['equipo']} ({margen['diferencia']:+.1f})" if margen else "sin favorito claro"
        lineas.append(
            f"{indice}. {partido['home']} vs {partido['away']} — {pick} · "
            f"más de {pronostico['puntosTotales']['linea']} pts ({pronostico['puntosTotales']['overPct']:.0f}%)"
        )
    return "\n".join(lineas)


def construir_pool_jugadores(partidos: list[dict], season: int) -> list[dict]:
    """Perfil de TODOS los jugadores con muestra suficiente de los equipos
    que juegan hoy (no solo los "destacados"), para armar las tablas de
    indicadores sobre el universo completo de la jornada."""
    conn = sqlite3.connect("apuestas.db")
    pool = []
    for partido in partidos:
        for team_id, team_name, rival in (
            (partido["homeId"], partido["home"], partido["away"]),
            (partido["awayId"], partido["away"], partido["home"]),
        ):
            jugadores = conn.execute("SELECT id FROM nba_players WHERE team_id = ?", (team_id,)).fetchall()
            for (player_id,) in jugadores:
                perfil = perfil_jugador_nba(player_id, season)
                if perfil is not None:
                    pool.append({"perfil": perfil, "equipo": team_name, "rival": rival})
    conn.close()
    return pool


def construir_tabla_stat(pool: list[dict], stat_key: str, etiqueta: str) -> str:
    filas = []
    for item in pool:
        datos = item["perfil"]["props"].get(stat_key)
        if datos is None:
            continue
        filas.append((item["perfil"]["playerName"], item["rival"], datos["promedio"], datos["linea"], datos["overPct"]))

    if not filas:
        return ""

    filas.sort(key=lambda f: f[2], reverse=True)
    filas = filas[:TOP_TABLA]

    cabecera = f"{'Jugador':<16}{'Rival':<9}{'Prom':>5}{'Lin':>5}{'%':>5}"
    cuerpo = [cabecera]
    for nombre, rival, promedio, linea, pct in filas:
        cuerpo.append(f"{nombre[:15]:<16}{_apodo(rival)[:8]:<9}{promedio:>5.1f}{linea:>5.1f}{pct:>4.0f}%")

    return etiqueta + "\n```\n" + "\n".join(cuerpo) + "\n```"


def construir_tabla_dobles(pool: list[dict]) -> str:
    filas = [
        (item["perfil"]["playerName"], item["rival"], item["perfil"]["doubleDoublePct"], item["perfil"]["tripleDoublePct"])
        for item in pool
        if item["perfil"]["doubleDoublePct"] > 0
    ]
    if not filas:
        return ""

    filas.sort(key=lambda f: (f[2], f[3]), reverse=True)
    filas = filas[:TOP_TABLA]

    cabecera = f"{'Jugador':<16}{'Rival':<9}{'DD%':>5}{'TD%':>5}"
    cuerpo = [cabecera]
    for nombre, rival, dd, td in filas:
        cuerpo.append(f"{nombre[:15]:<16}{_apodo(rival)[:8]:<9}{dd:>4.0f}%{td:>4.0f}%")

    return "🔥 *Doble-doble / Triple-doble*\n```\n" + "\n".join(cuerpo) + "\n```"


def construir_bajas(partidos: list[dict], lesionados: dict) -> str:
    lineas = []
    equipos_vistos = set()
    for partido in partidos:
        for team_name in (partido["home"], partido["away"]):
            if team_name in equipos_vistos:
                continue
            equipos_vistos.add(team_name)
            bajas_equipo = lesionados.get(team_name, [])
            if bajas_equipo:
                texto = ", ".join(f"{b['jugador']} ({b['estado']})" for b in bajas_equipo)
                lineas.append(f"• {team_name}: {texto}")

    if not lineas:
        return ""
    return "🚑 *Bajas de hoy*\n" + "\n".join(lineas)


def construir_absorciones(partidos: list[dict], lesionados: dict, season: int) -> str:
    """Compañeros de un jugador confirmado "Out" cuyo promedio de puntos
    sube cuando él no juega esta temporada — señal exploratoria de pocos
    partidos, no una certeza, pero sirve para detectar posibles sorpresas
    por el aumento de intentos/minutos."""
    lineas = []
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
                    continue  # no lo pudimos cruzar con nuestra base (ej. apodo distinto a ESPN)

                candidatos = companeros_que_podrian_absorber(team_id, fila[0], season, stat="points")
                if not candidatos or candidatos[0]["diferencia"] < DIFERENCIA_MINIMA_ABSORCION:
                    continue

                mejor = candidatos[0]
                lineas.append(
                    f"• {team_name} sin *{baja['jugador']}*: *{mejor['playerName']}* promedia "
                    f"{mejor['promedioSin']} pts sin él (vs {mejor['promedioCon']} con él en cancha)"
                )

    conn.close()
    if not lineas:
        return ""
    return "⚠️ *Posible absorción de puntos por lesión*\n" + "\n".join(lineas)


def construir_mensajes(partidos: list[dict], fecha_hoy: str, season: int, lesionados: dict) -> list[str]:
    encabezado = f"🏀 *Pronósticos NBA de hoy* 🏀\n🗓️ {formatear_fecha(fecha_hoy)}\n"

    if not partidos:
        return [encabezado + "\nNo encontramos partidos NBA con datos suficientes para hoy. 📭"]

    partidos = sorted(partidos, key=_clave_orden_partido, reverse=True)
    pool = construir_pool_jugadores(partidos, season)

    secciones = [construir_resumen_partidos(partidos)]
    for stat_key, etiqueta in STATS_TABLA:
        tabla = construir_tabla_stat(pool, stat_key, etiqueta)
        if tabla:
            secciones.append(tabla)

    tabla_dobles = construir_tabla_dobles(pool)
    if tabla_dobles:
        secciones.append(tabla_dobles)

    bajas = construir_bajas(partidos, lesionados)
    if bajas:
        secciones.append(bajas)

    absorciones = construir_absorciones(partidos, lesionados, season)
    if absorciones:
        secciones.append(absorciones)

    mensajes = []
    actual = encabezado
    for seccion in secciones:
        bloque = "\n\n" + seccion
        if len(actual) + len(bloque) > LIMITE_CARACTERES_MENSAJE:
            mensajes.append(actual)
            actual = "🏀 *Pronósticos NBA (continuación)*" + bloque
        else:
            actual += bloque
    mensajes.append(actual)
    return mensajes


def enviar_mensaje_telegram(texto: str) -> None:
    respuesta = requests.post(
        TELEGRAM_API_URL,
        data={"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown", "disable_web_page_preview": True},
        timeout=15,
    )
    if respuesta.status_code != 200:
        print(f"Error al enviar a Telegram: {respuesta.status_code} - {respuesta.text}")
    else:
        print("Mensaje enviado correctamente a Telegram.")


def enviar_documento_telegram(ruta_archivo: str, caption: str = "") -> None:
    with open(ruta_archivo, "rb") as archivo:
        respuesta = requests.post(
            f"{TELEGRAM_API_BASE}/sendDocument",
            data={"chat_id": CHAT_ID, "caption": caption},
            files={"document": archivo},
            timeout=30,
        )
    if respuesta.status_code != 200:
        print(f"Error al enviar el PDF a Telegram: {respuesta.status_code} - {respuesta.text}")
    else:
        print("PDF enviado correctamente a Telegram.")


def main() -> None:
    from generar_pdf_basquet import generar_pdf

    partidos, fecha_hoy, season = partidos_de_hoy()
    lesionados = obtener_lesionados()

    partidos_ordenados = sorted(partidos, key=_clave_orden_partido, reverse=True)
    pool = construir_pool_jugadores(partidos_ordenados, season)

    for mensaje in construir_mensajes(partidos, fecha_hoy, season, lesionados):
        enviar_mensaje_telegram(mensaje)

    with tempfile.TemporaryDirectory() as carpeta_temporal:
        ruta_pdf = f"{carpeta_temporal}/pronosticos_nba_{fecha_hoy}.pdf"
        generar_pdf(ruta_pdf, partidos_ordenados, fecha_hoy, pool, lesionados, season)
        enviar_documento_telegram(ruta_pdf, caption=f"Resumen ejecutivo NBA — {formatear_fecha(fecha_hoy)}")


if __name__ == "__main__":
    main()

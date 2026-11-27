"""
Envía por Telegram, cada tarde/noche antes de que empiecen, el reporte de
pronósticos NBA de los partidos de HOY — organizado POR PARTIDO: moneyline
y diferencia de puntos (+/-) de ambos equipos lado a lado, y los
indicadores de todos los jugadores de ambos equipos (puntos, triples,
asistencias, rebotes, doble/triple-doble), para ver en un solo lugar todo
lo apostable de ese partido puntual.

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

from analizar_basquet import mejor_pick_equipo, pronostico_partido
from analizar_jugadores_basquet import companeros_que_podrian_absorber, mejores_picks_partido
from cargar_temporada_nba import temporada_actual_nba
from lesionados_nba import obtener_lesionados

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
TELEGRAM_API_URL = f"{TELEGRAM_API_BASE}/sendMessage"

MAX_PARTIDOS = 10
DIFERENCIA_MINIMA_ABSORCION = 3.0  # puntos de más sin el compañero para que valga la pena avisarlo
LIMITE_CARACTERES_MENSAJE = 3800

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

ETIQUETAS_STAT = {
    "points": "Puntos",
    "three_made": "Triples",
    "assists": "Asistencias",
    "rebounds_tot": "Rebotes",
    "doble_doble": "Doble-doble",
    "triple_doble": "Triple-doble",
}


def formatear_fecha(fecha_iso: str) -> str:
    fecha = date.fromisoformat(fecha_iso)
    return f"{DIAS_ES[fecha.weekday()]} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


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

    partidos.sort(key=lambda p: max(p["pronostico"]["home"]["moneyline"], p["pronostico"]["away"]["moneyline"]), reverse=True)
    return partidos[:MAX_PARTIDOS], hoy, season


def _texto_pick_equipo(pick: dict | None) -> str:
    if pick is None:
        return "   ⚖️ Partido parejo — sin pick de equipo confiable"
    if pick["tipo"] == "moneyline":
        return f"   💰 Pick: *{pick['equipo']}* — Moneyline *{pick['valor']:.0f}%*"
    return f"   📐 Pick: *{pick['equipo']}* — Diferencia de puntos *{pick['valor']:+.1f}*"


def _texto_candidatos_stat(candidatos: list[dict], con_promedio: bool) -> str:
    def _uno(c: dict) -> str:
        apodo = c["equipo"].split()[-1]
        alerta = f" ⚠️{c['alerta']}" if c.get("alerta") else ""
        if con_promedio:
            return f"{c['jugador']} ({apodo}, {c['promedio']:.1f}, {c['probabilidad']:.0f}%){alerta}"
        return f"{c['jugador']} ({apodo}, {c['probabilidad']:.0f}%){alerta}"

    return ", ".join(_uno(c) for c in candidatos)


def construir_bloque_partido(partido: dict, season: int, lesionados: dict) -> str:
    pronostico = partido["pronostico"]

    lineas = [
        f"🏀 *{partido['home']} vs {partido['away']}*",
        _texto_pick_equipo(mejor_pick_equipo(pronostico)),
        f"   📊 Más de {pronostico['puntosTotales']['linea']} puntos totales — *{pronostico['puntosTotales']['overPct']:.0f}%*",
    ]

    equipos = [(partido["homeId"], partido["home"]), (partido["awayId"], partido["away"])]
    picks = mejores_picks_partido(equipos, season, lesionados)

    for stat_key in ("points", "three_made", "assists", "rebounds_tot"):
        candidatos = picks.get(stat_key)
        if candidatos:
            lineas.append(f"   • {ETIQUETAS_STAT[stat_key]}: {_texto_candidatos_stat(candidatos, con_promedio=True)}")

    for clave in ("doble_doble", "triple_doble"):
        candidatos = picks.get(clave)
        if candidatos:
            lineas.append(f"   • {ETIQUETAS_STAT[clave]}: {_texto_candidatos_stat(candidatos, con_promedio=False)}")

    for team_name in (partido["home"], partido["away"]):
        bajas_equipo = lesionados.get(team_name, [])
        if bajas_equipo:
            texto_bajas = ", ".join(f"{b['jugador']} ({b['estado']})" for b in bajas_equipo)
            lineas.append(f"   🚑 Bajas {team_name}: {texto_bajas}")

    absorciones = construir_absorciones_partido(partido, lesionados, season)
    if absorciones:
        lineas.append(absorciones)

    return "\n".join(lineas)


def construir_absorciones_partido(partido: dict, lesionados: dict, season: int) -> str:
    """Compañeros de un jugador confirmado "Out" (de cualquiera de los dos
    equipos de ESTE partido) cuyo promedio de puntos sube cuando él no
    juega esta temporada — señal exploratoria de pocos partidos, no una
    certeza, pero sirve para detectar posibles sorpresas por el aumento de
    intentos/minutos."""
    lineas = []
    conn = sqlite3.connect("apuestas.db")

    for team_id, team_name in ((partido["homeId"], partido["home"]), (partido["awayId"], partido["away"])):
        jugadores_out_equipo = {b["jugador"] for b in lesionados.get(team_name, []) if b["estado"] == "Out"}

        for baja in lesionados.get(team_name, []):
            if baja["estado"] != "Out":
                continue
            fila = conn.execute(
                "SELECT id FROM nba_players WHERE team_id = ? AND name = ?", (team_id, baja["jugador"])
            ).fetchone()
            if fila is None:
                continue  # no lo pudimos cruzar con nuestra base (ej. apodo distinto a ESPN)

            candidatos = companeros_que_podrian_absorber(team_id, fila[0], season, stat="points")
            # El compañero recomendado tampoco puede estar confirmado Out
            # (podría ser otro jugador lesionado que ya estaba fuera antes).
            candidatos = [c for c in candidatos if c["playerName"] not in jugadores_out_equipo]
            if not candidatos or candidatos[0]["diferencia"] < DIFERENCIA_MINIMA_ABSORCION:
                continue

            mejor = candidatos[0]
            lineas.append(
                f"   ⚠️ Sin *{baja['jugador']}* ({team_name}): *{mejor['playerName']}* promedia "
                f"{mejor['promedioSin']} pts sin él (vs {mejor['promedioCon']} con él en cancha)"
            )

    conn.close()
    return "\n".join(lineas)


def construir_mensajes(partidos: list[dict], fecha_hoy: str, season: int, lesionados: dict) -> list[str]:
    encabezado = (
        f"🏀 *Pronósticos NBA de hoy* 🏀\n🗓️ {formatear_fecha(fecha_hoy)}\n"
        f"_DD/TD considera puntos + rebotes + asistencias (sin robos/tapones, no disponibles en esta fuente)._\n"
    )

    if not partidos:
        return [encabezado + "\nNo encontramos partidos NBA con datos suficientes para hoy. 📭"]

    mensajes = []
    actual = encabezado
    for partido in partidos:
        bloque = "\n\n" + construir_bloque_partido(partido, season, lesionados)
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

    for mensaje in construir_mensajes(partidos, fecha_hoy, season, lesionados):
        enviar_mensaje_telegram(mensaje)

    with tempfile.TemporaryDirectory() as carpeta_temporal:
        ruta_pdf = f"{carpeta_temporal}/pronosticos_nba_{fecha_hoy}.pdf"
        generar_pdf(ruta_pdf, partidos, fecha_hoy, lesionados, season)
        enviar_documento_telegram(ruta_pdf, caption=f"Resumen ejecutivo NBA — {formatear_fecha(fecha_hoy)}")


if __name__ == "__main__":
    main()

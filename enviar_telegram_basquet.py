"""
Envía por Telegram, cada noche, el reporte de pronósticos NBA (moneyline,
puntos totales y props de jugadores destacados) de los partidos de MAÑANA.

Mensaje SEPARADO del reporte de fútbol (enviar_telegram.py) — mismo bot y
chat, pero un envío aparte, para no mezclar ambos deportes en un solo texto.

Se calcula 100% desde apuestas.db (analizar_basquet.py /
analizar_jugadores_basquet.py), sin depender de la API de Claude.

Variables de entorno requeridas (.env):
    TELEGRAM_BOT_TOKEN   Token del bot (de @BotFather)
    TELEGRAM_CHAT_ID     Chat ID del grupo donde se envía el reporte

Ejecutar manualmente:
    python enviar_telegram_basquet.py
"""

import os
import sqlite3
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

from analizar_basquet import pronostico_partido
from analizar_jugadores_basquet import elegir_top_props_jugador, perfil_jugador_nba
from cargar_temporada_nba import temporada_actual_nba
from lesionados_nba import obtener_lesionados

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

MAX_PARTIDOS = 10
JUGADORES_DESTACADOS_POR_EQUIPO = 2
LIMITE_CARACTERES_MENSAJE = 3800

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def formatear_fecha(fecha_iso: str) -> str:
    fecha = date.fromisoformat(fecha_iso)
    return f"{DIAS_ES[fecha.weekday()]} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


def jugadores_destacados(team_id: int, season: int, limite: int) -> list[dict]:
    """Hasta `limite` jugadores del equipo con props por encima del umbral,
    ordenados por promedio de puntos (los titulares suelen ser los que más
    muestra y relevancia tienen para el reporte)."""
    conn = sqlite3.connect("apuestas.db")
    jugadores = conn.execute("SELECT id FROM nba_players WHERE team_id = ?", (team_id,)).fetchall()
    conn.close()

    candidatos = []
    for (player_id,) in jugadores:
        perfil = perfil_jugador_nba(player_id, season)
        if perfil is None:
            continue
        props = elegir_top_props_jugador(perfil, top=3)
        if props:
            candidatos.append({"nombre": perfil["playerName"], "props": props, "promedioPuntos": perfil["props"].get("points", {}).get("promedio", 0)})

    candidatos.sort(key=lambda c: c["promedioPuntos"], reverse=True)
    return candidatos[:limite]


def partidos_de_manana() -> tuple[list[dict], str, int]:
    season = temporada_actual_nba()
    manana = (date.today() + timedelta(days=1)).isoformat()

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
        (season, manana),
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

    return partidos[:MAX_PARTIDOS], manana, season


def construir_bloque_partido(partido: dict, season: int, lesionados: dict) -> str:
    pronostico = partido["pronostico"]
    lineas = [f"🏀 *{partido['home']} vs {partido['away']}*"]

    if pronostico["moneyline"] is not None:
        lineas.append(
            f"   • 💰 Moneyline: *{pronostico['moneyline']['equipo']}* — *{pronostico['moneyline']['probabilidad']:.0f}%*"
        )
    elif pronostico["margen"] is not None:
        margen = pronostico["margen"]
        lineas.append(f"   • 📐 Diferencia de puntos promedio: *{margen['equipo']}* ({margen['diferencia']:+.1f})")

    lineas.append(
        f"   • 📊 Más de {pronostico['puntosTotales']['linea']} puntos totales — *{pronostico['puntosTotales']['overPct']:.0f}%*"
    )

    for team_id, team_name in ((partido["homeId"], partido["home"]), (partido["awayId"], partido["away"])):
        bajas_equipo = lesionados.get(team_name, [])
        jugadores_out = {b["jugador"] for b in bajas_equipo if b["estado"] == "Out"}

        for jugador in jugadores_destacados(team_id, season, JUGADORES_DESTACADOS_POR_EQUIPO):
            if jugador["nombre"] in jugadores_out:
                continue  # está confirmado afuera: la prop no tiene sentido mostrarla
            props_texto = ", ".join(f"{p['etiqueta']} ({p['probabilidad']:.0f}%)" for p in jugador["props"])
            lineas.append(f"   • 🧑‍💼 {jugador['nombre']}: {props_texto}")

        if bajas_equipo:
            texto_bajas = ", ".join(f"{b['jugador']} ({b['estado']})" for b in bajas_equipo)
            lineas.append(f"   • 🚑 Bajas {team_name}: {texto_bajas}")

    return "\n".join(lineas)


def construir_mensajes(partidos: list[dict], fecha_manana: str, season: int, lesionados: dict) -> list[str]:
    encabezado = f"🏀 *Pronósticos NBA para mañana* 🏀\n🗓️ {formatear_fecha(fecha_manana)}\n"

    if not partidos:
        return [encabezado + "\nNo encontramos partidos NBA con datos suficientes para mañana. 📭"]

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


def main() -> None:
    partidos, fecha_manana, season = partidos_de_manana()
    lesionados = obtener_lesionados()
    for mensaje in construir_mensajes(partidos, fecha_manana, season, lesionados):
        enviar_mensaje_telegram(mensaje)


if __name__ == "__main__":
    main()

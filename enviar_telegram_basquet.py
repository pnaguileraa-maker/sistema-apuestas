"""
Arma el resumen ejecutivo NBA (generar_pdf_basquet.py) de los partidos de
HOY y lo manda por Telegram como documento adjunto — ya no se manda
mensaje de texto, solo el PDF (más completo y sin límite de caracteres).

Mensaje SEPARADO del reporte de fútbol (enviar_telegram.py) — mismo bot y
chat, pero un envío aparte, para no mezclar ambos deportes.

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
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from analizar_basquet import pronostico_partido
from cargar_temporada_nba import temporada_actual_nba
from lesionados_nba import obtener_lesionados

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

ZONA_NBA = ZoneInfo("America/New_York")

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def formatear_fecha(fecha_iso: str) -> str:
    fecha = date.fromisoformat(fecha_iso)
    return f"{DIAS_ES[fecha.weekday()]} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


def partidos_de_hoy() -> tuple[list[dict], str, int]:
    """Partidos de la jornada NBA de HOY: todos los que empiezan hoy según
    la hora del Este de EEUU (la fecha oficial de cada partido para la NBA).
    Así entran tanto los de la tarde (ej. 17:00 ET = 19:00 Chile) como los
    de la madrugada en Chile (22:30 ET = 00:30 Chile del día siguiente),
    sin colar los de mañana.

    Antes se filtraba por el día calendario UTC de mañana: eso dejaba
    afuera los partidos que empiezan antes de las 00:00 UTC y metía los de
    la tarde del día siguiente."""
    season = temporada_actual_nba()
    hoy_et = datetime.now(ZONA_NBA).date()
    hoy = hoy_et.isoformat()

    conn = sqlite3.connect("apuestas.db")
    filas = conn.execute(
        """
        SELECT g.id, g.date, g.home_team_id, h.name, g.away_team_id, a.name
        FROM nba_games g
        JOIN nba_teams h ON h.id = g.home_team_id
        JOIN nba_teams a ON a.id = g.away_team_id
        WHERE g.season = ? AND date(g.date) BETWEEN ? AND ?
          AND g.home_points IS NULL AND g.status != 'Cancelled'
        """,
        (season, hoy, (hoy_et + timedelta(days=1)).isoformat()),
    ).fetchall()
    conn.close()
    filas = [
        (game_id, home_id, home_name, away_id, away_name)
        for game_id, fecha, home_id, home_name, away_id, away_name in filas
        if datetime.fromisoformat(fecha).astimezone(ZONA_NBA).date() == hoy_et
    ]

    partidos = []
    for _game_id, home_id, home_name, away_id, away_name in filas:
        pronostico = pronostico_partido(home_id, away_id, season)
        if pronostico is None:
            print(f"Sin pronóstico (faltan datos): {away_name} @ {home_name}")
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
    return partidos, hoy, season


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

    with tempfile.TemporaryDirectory() as carpeta_temporal:
        ruta_pdf = f"{carpeta_temporal}/pronosticos_nba_{fecha_hoy}.pdf"
        generar_pdf(ruta_pdf, partidos, fecha_hoy, lesionados, season)
        enviar_documento_telegram(ruta_pdf, caption=f"Resumen ejecutivo NBA — {formatear_fecha(fecha_hoy)}")


if __name__ == "__main__":
    main()

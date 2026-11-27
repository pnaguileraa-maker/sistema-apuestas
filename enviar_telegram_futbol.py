"""
Arma el resumen ejecutivo de fútbol (generar_pdf_futbol.py) de los
partidos de MAÑANA en todas las ligas configuradas y lo manda por
Telegram como documento adjunto — igual que el de NBA
(enviar_telegram_basquet.py), solo el PDF, sin mensaje de texto.

Mensaje SEPARADO del reporte de NBA — mismo bot y chat, envío aparte.

Se calcula 100% desde apuestas.db (analizar_futbol.py, que reutiliza el
motor de backend/app.py), sin depender de la API de Claude.

Variables de entorno requeridas (.env):
    TELEGRAM_BOT_TOKEN   Token del bot (de @BotFather)
    TELEGRAM_CHAT_ID     Chat ID del grupo donde se envía el reporte

Ejecutar manualmente:
    python enviar_telegram_futbol.py
"""

import os
import sys
import tempfile
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import COMPETICIONES, partidos_calendario, temporada_por_defecto
from analizar_futbol import pronostico_partido_futbol

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

MAX_PARTIDOS = 20

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def formatear_fecha(fecha_iso: str) -> str:
    fecha = date.fromisoformat(fecha_iso)
    return f"{DIAS_ES[fecha.weekday()]} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


def partidos_de_manana() -> tuple[list[dict], str]:
    manana = (date.today() + timedelta(days=1)).isoformat()
    partidos = []

    for liga in COMPETICIONES:
        league_id = liga["id"]
        season = temporada_por_defecto(league_id)
        filas = partidos_calendario(season, league_id, manana, manana)

        for (
            _fixture_id, _fecha, _status, home_id, home_name, _home_logo,
            away_id, away_name, _away_logo, _home_goals, _away_goals,
        ) in filas:
            pronostico = pronostico_partido_futbol(home_id, away_id, season, league_id)
            if pronostico is None:
                continue
            mejor_prob = max(pronostico["resultado"]["homePct"], pronostico["resultado"]["drawPct"], pronostico["resultado"]["awayPct"])
            partidos.append(
                {
                    "liga": liga["nombre"],
                    "home": home_name,
                    "away": away_name,
                    "pronostico": pronostico,
                    "mejorProbabilidad": mejor_prob,
                }
            )

    partidos.sort(key=lambda p: p["mejorProbabilidad"], reverse=True)
    return partidos[:MAX_PARTIDOS], manana


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
    from generar_pdf_futbol import generar_pdf

    partidos, fecha_manana = partidos_de_manana()

    with tempfile.TemporaryDirectory() as carpeta_temporal:
        ruta_pdf = f"{carpeta_temporal}/pronosticos_futbol_{fecha_manana}.pdf"
        generar_pdf(ruta_pdf, partidos, fecha_manana)
        enviar_documento_telegram(ruta_pdf, caption=f"Resumen ejecutivo fútbol — {formatear_fecha(fecha_manana)}")


if __name__ == "__main__":
    main()

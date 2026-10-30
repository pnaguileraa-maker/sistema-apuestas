"""
Envía por Telegram, cada noche, el reporte de pronósticos de los partidos de
MAÑANA en las ligas configuradas en backend/app.py (COMPETICIONES).

Reutiliza el mismo motor estadístico que ya usa el backend para los Scout
Picks (elegir_top_mercados / construir_rachas), calculado 100% a partir de
apuestas.db, SIN llamar a la API de Claude (así el envío nocturno es rápido
y no depende de que esa API esté disponible).

Mercados evaluados por partido: Goles, Córners, Tarjetas, Tiros al arco
(todos como "Más de N.5") y Ambos anotan (BTTS). Partidos y selecciones se
ordenan de mayor a menor probabilidad estimada.

Variables de entorno requeridas (.env):
    TELEGRAM_BOT_TOKEN   Token del bot (de @BotFather)
    TELEGRAM_CHAT_ID     Chat ID del grupo donde se envía el reporte

Ejecutar manualmente:
    python enviar_telegram.py

Para programarlo todos los días a las 21:00, ver el comando de
Task Scheduler que se entregó junto con este script.
"""

import os
import sys
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import (  # noqa: E402
    COMPETICIONES,
    ETIQUETA_MERCADO,
    ICONO_MERCADO,
    calcular_perfil_equipo,
    elegir_top_mercados,
    partidos_calendario,
    temporada_por_defecto,
    _filas_equipo_en_rol,
    _filas_h2h,
)

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

UMBRAL_MOSTRAR = 60  # % mínimo para incluir una selección (evita ruido de baja confianza)
MAX_PARTIDOS = 12  # tope de partidos en el reporte, para que sea fácil de leer
TOP_SELECCIONES_POR_PARTIDO = 3
LIMITE_CARACTERES_MENSAJE = 3800  # margen bajo el límite de 4096 de Telegram

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

MIN_PARTIDOS_PARA_BTTS = 4  # muestra mínima (en casa / fuera) para confiar en el % de BTTS


def formatear_fecha(fecha_iso: str) -> str:
    fecha = date.fromisoformat(fecha_iso)
    return f"{DIAS_ES[fecha.weekday()]} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


def probabilidad_btts(home_id: int, away_id: int, season: int, league_id: int) -> float | None:
    """% estimado de BTTS para el partido: promedio del % de BTTS del local
    jugando en casa y del visitante jugando fuera. None si falta muestra."""
    perfil_home = calcular_perfil_equipo(home_id, season, league_id)
    perfil_away = calcular_perfil_equipo(away_id, season, league_id)
    if perfil_home is None or perfil_away is None:
        return None

    en_casa = perfil_home["home"]
    de_visita = perfil_away["away"]
    if en_casa["played"] < MIN_PARTIDOS_PARA_BTTS or de_visita["played"] < MIN_PARTIDOS_PARA_BTTS:
        return None

    return round((en_casa["bttsPct"] + de_visita["bttsPct"]) / 2, 1)


def analizar_partido(home_id: int, away_id: int, season: int, league_id: int) -> list[dict]:
    """Selecciones (mercado + línea + % estimado) para un partido, ordenadas
    de mayor a menor probabilidad y filtradas por UMBRAL_MOSTRAR."""
    filas_home_local = _filas_equipo_en_rol(home_id, season, league_id, True)
    filas_away_visita = _filas_equipo_en_rol(away_id, season, league_id, False)
    filas_h2h = _filas_h2h(home_id, away_id)

    selecciones = [
        {
            "etiqueta": f"{ICONO_MERCADO[c['mercado']]} Más de {c['linea']} {ETIQUETA_MERCADO[c['mercado']]}",
            "probabilidad": c["probabilidad"],
            "solido": c["solido"],
        }
        for c in elegir_top_mercados(filas_home_local, filas_away_visita, filas_h2h, top=len(ETIQUETA_MERCADO))
    ]

    btts = probabilidad_btts(home_id, away_id, season, league_id)
    if btts is not None:
        selecciones.append({"etiqueta": "🤝 Ambos equipos anotan (BTTS)", "probabilidad": btts, "solido": btts >= 70})

    selecciones = [s for s in selecciones if s["probabilidad"] is not None and s["probabilidad"] >= UMBRAL_MOSTRAR]
    selecciones.sort(key=lambda s: s["probabilidad"], reverse=True)
    return selecciones[:TOP_SELECCIONES_POR_PARTIDO]


def partidos_de_manana() -> tuple[list[dict], str]:
    manana = (date.today() + timedelta(days=1)).isoformat()
    partidos = []

    for liga in COMPETICIONES:
        league_id = liga["id"]
        season = temporada_por_defecto(league_id)
        filas = partidos_calendario(season, league_id, manana, manana)

        for (
            _fixture_id, fecha, _status, home_id, home_name, _home_logo,
            away_id, away_name, _away_logo, _home_goals, _away_goals,
        ) in filas:
            selecciones = analizar_partido(home_id, away_id, season, league_id)
            if not selecciones:
                continue
            partidos.append(
                {
                    "fecha": fecha,
                    "liga": liga["nombre"],
                    "home": home_name,
                    "away": away_name,
                    "selecciones": selecciones,
                    "mejorProbabilidad": selecciones[0]["probabilidad"],
                }
            )

    partidos.sort(key=lambda p: p["mejorProbabilidad"], reverse=True)
    return partidos[:MAX_PARTIDOS], manana


def construir_bloque_partido(partido: dict) -> str:
    lineas = [f"⚽ *{partido['home']} vs {partido['away']}*", f"🏆 {partido['liga']}"]
    for seleccion in partido["selecciones"]:
        marca = "🔥" if seleccion["solido"] else "📈"
        lineas.append(f"   • {marca} {seleccion['etiqueta']} — *{seleccion['probabilidad']:.0f}%*")
    return "\n".join(lineas)


def construir_mensajes(partidos: list[dict], fecha_manana: str) -> list[str]:
    encabezado = f"🔮 *Pronósticos para mañana* 🔮\n🗓️ {formatear_fecha(fecha_manana)}\n"

    if not partidos:
        return [encabezado + "\nNo encontramos partidos con datos suficientes para mañana en las ligas configuradas. 📭"]

    mensajes = []
    actual = encabezado
    for partido in partidos:
        bloque = "\n\n" + construir_bloque_partido(partido)
        if len(actual) + len(bloque) > LIMITE_CARACTERES_MENSAJE:
            mensajes.append(actual)
            actual = "🔮 *Pronósticos (continuación)*" + bloque
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
    partidos, fecha_manana = partidos_de_manana()
    for mensaje in construir_mensajes(partidos, fecha_manana):
        enviar_mensaje_telegram(mensaje)


if __name__ == "__main__":
    main()

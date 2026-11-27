"""
Lesionados/bajas NBA desde la API pública de ESPN (sin key, sin costo) —
la API de pago que ya usamos para el resto del análisis (BALONCESTO /
API-Basketball de api-sports.io) no tiene endpoint de lesionados.

Se consulta en vivo al armar el reporte (no se guarda en apuestas.db):
es información que cambia varias veces al día y solo nos importa el
estado justo antes de enviar, no un historial.
"""

import requests

ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"

# ESPN nombra algunos equipos distinto a nuestra fuente de partidos
# (API-Basketball) — mapeo manual confirmado el 2026-11-27 comparando
# ambas listas de equipos.
MAPEO_NOMBRES_ESPN = {"LA Clippers": "Los Angeles Clippers"}


def obtener_lesionados() -> dict[str, list[dict]]:
    """{nombre_equipo (como en nba_teams.name): [{"jugador", "estado"}]}.
    Diccionario vacío si ESPN no responde — no debe frenar el resto del
    reporte."""
    try:
        respuesta = requests.get(ESPN_INJURIES_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    except requests.RequestException as error:
        print(f"No se pudo obtener el reporte de lesionados de ESPN: {error}")
        return {}

    if respuesta.status_code != 200:
        print(f"No se pudo obtener el reporte de lesionados de ESPN: HTTP {respuesta.status_code}")
        return {}

    lesionados_por_equipo = {}
    for bloque in respuesta.json().get("injuries", []):
        equipo = MAPEO_NOMBRES_ESPN.get(bloque["displayName"], bloque["displayName"])
        lesionados_por_equipo[equipo] = [
            {
                # "Apellido Nombre", igual que nba_players.name (viene así
                # de API-Basketball) — para poder cruzar lesionados con los
                # jugadores destacados del reporte.
                "jugador": f"{inj['athlete']['lastName']} {inj['athlete']['firstName']}",
                "estado": inj["status"],
            }
            for inj in bloque.get("injuries", [])
        ]
    return lesionados_por_equipo

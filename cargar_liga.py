"""
Descarga partidos, escudos y estadísticas (córners/tarjetas) de CUALQUIER
liga de api-football para su temporada vigente, reusando el mismo pipeline
que crear_db_y_partidos.py / actualizar_escudos_equipos.py /
actualizar_estadisticas_partidos.py ya usan para la Premier League.

A diferencia de cargar_champions_league.py (temporada fija al calendario
europeo agosto-julio), este script le pregunta a api-football cuál es la
temporada vigente de CADA liga puntual — necesario para ligas que no siguen
ese calendario (Chile, Argentina, Brasil, México, USA, entre otras).

Ejecutar:
    python cargar_liga.py <league_id> [season]
"""

import sys

import requests

from actualizar_escudos_equipos import actualizar_escudos
from actualizar_estadisticas_partidos import actualizar_estadisticas
from crear_db_y_partidos import API_KEY, BASE_URL, descargar_y_guardar_partidos, inicializar_base_datos

headers = {"x-apisports-key": API_KEY}


def temporada_actual_liga(league_id: int) -> int:
    """Temporada vigente ("current": true) para una liga puntual, según
    api-football — evita asumir el calendario europeo, que no aplica a
    todas las ligas."""
    response = requests.get(f"{BASE_URL}/leagues", headers=headers, params={"id": league_id})
    datos = response.json().get("response", [])
    if not datos:
        raise ValueError(f"No se encontró la liga {league_id} en api-football")

    for temporada in datos[0]["seasons"]:
        if temporada.get("current"):
            return temporada["year"]

    raise ValueError(f"La liga {league_id} no tiene una temporada vigente marcada en api-football")


def cargar_liga(league_id: int, season: int | None = None) -> None:
    season = season or temporada_actual_liga(league_id)
    print(f"Liga {league_id}, temporada {season}")
    inicializar_base_datos()
    descargar_y_guardar_partidos(league_id=league_id, season=season)
    actualizar_escudos(season=season, league_id=league_id)
    actualizar_estadisticas(league_id=league_id, season=season)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python cargar_liga.py <league_id> [season]")
        sys.exit(1)

    league_id_arg = int(sys.argv[1])
    season_arg = int(sys.argv[2]) if len(sys.argv) > 2 else None
    cargar_liga(league_id_arg, season_arg)

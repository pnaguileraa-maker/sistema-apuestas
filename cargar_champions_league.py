"""
Descarga partidos, escudos y estadísticas (córners/tarjetas) de la UEFA
Champions League (liga ID 2 en api-football) para la temporada vigente,
reusando el mismo pipeline que crear_db_y_partidos.py /
actualizar_escudos_equipos.py / actualizar_estadisticas_partidos.py ya usan
para la Premier League.

Ejecutar:
    python cargar_champions_league.py
"""

from actualizar_escudos_equipos import actualizar_escudos
from actualizar_estadisticas_partidos import actualizar_estadisticas
from crear_db_y_partidos import (
    descargar_y_guardar_partidos,
    inicializar_base_datos,
    temporada_actual_premier_league,
)

CHAMPIONS_LEAGUE_ID = 2

if __name__ == "__main__":
    temporada = temporada_actual_premier_league()  # mismo calendario europeo (jul-jun)
    inicializar_base_datos()
    descargar_y_guardar_partidos(league_id=CHAMPIONS_LEAGUE_ID, season=temporada)
    actualizar_escudos(season=temporada, league_id=CHAMPIONS_LEAGUE_ID)
    actualizar_estadisticas(league_id=CHAMPIONS_LEAGUE_ID, season=temporada)

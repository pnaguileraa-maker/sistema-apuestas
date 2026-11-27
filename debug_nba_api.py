"""
Smoke-test manual contra la API real de NBA (API-Basketball, liga id 12) —
útil si algo en la ingesta empieza a fallar y hay que confirmar rápido que
la API sigue devolviendo lo esperado (plan activo, forma del JSON sin
cambios, etc.).

Ejecutar:
    python debug_nba_api.py [YYYY-MM-DD]   # por defecto, mañana
"""

import json
import sys
from datetime import date, timedelta

from nba_api_client import LEAGUE_ID_NBA, get_nba
from cargar_temporada_nba import temporada_actual_nba


def dump(titulo: str, datos) -> None:
    print(f"\n{'=' * 70}\n{titulo}\n{'=' * 70}")
    print(json.dumps(datos, indent=2, ensure_ascii=False)[:3000])


def main() -> None:
    fecha = sys.argv[1] if len(sys.argv) > 1 else (date.today() + timedelta(days=1)).isoformat()
    season = temporada_actual_nba()

    equipos = get_nba("teams", {"league": LEAGUE_ID_NBA, "season": season})
    dump(f"/teams (temporada {season})", equipos[:2])

    juegos = get_nba("games", {"league": LEAGUE_ID_NBA, "season": season, "date": fecha})
    dump(f"/games?date={fecha}", juegos[:2])

    juego_terminado = next(
        (
            get_nba("games", {"league": LEAGUE_ID_NBA, "season": season, "team": equipo["id"]})
            for equipo in equipos[:1]
        ),
        [],
    )
    juego_con_boxscore = next((g for g in juego_terminado if g["status"]["long"] == "Game Finished"), None)

    if juego_con_boxscore:
        gid = juego_con_boxscore["id"]
        dump(f"/games/statistics/players?id={gid}", get_nba("games/statistics/players", {"id": gid})[:3])
    else:
        print("\nNo se encontró ningún partido terminado para probar el boxscore de jugadores.")


if __name__ == "__main__":
    main()

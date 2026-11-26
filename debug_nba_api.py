"""
Script de UNA SOLA VEZ para confirmar, contra la API real, los nombres de
campo exactos que devuelve API-NBA (api-sports.io) antes de construir el
parser definitivo de ingesta (cargar_temporada_nba.py /
actualizar_estadisticas_jugadores_nba.py).

No hace falta adivinar la forma del JSON: este script pega contra varios
endpoints candidatos y vuelca la respuesta cruda (o el error, que en
api-sports.io suele ser descriptivo) para poder mapear los campos reales.

Requiere NBA_API_KEY en el .env (suscripción a API-NBA en api-sports.io,
producto aparte de API_FOOTBALL_KEY).

Ejecutar:
    python debug_nba_api.py [YYYY-MM-DD]   # por defecto, hoy
"""

import json
import os
import sys
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["NBA_API_KEY"]
BASE_URL = "https://v2.nba.api-sports.io"
headers = {"x-apisports-key": API_KEY}


def dump(titulo: str, respuesta: requests.Response) -> None:
    print(f"\n{'=' * 70}\n{titulo}\n{'=' * 70}")
    print(f"HTTP {respuesta.status_code}")
    try:
        datos = respuesta.json()
    except ValueError:
        print(respuesta.text[:1000])
        return
    print(json.dumps(datos, indent=2, ensure_ascii=False)[:4000])


def main() -> None:
    fecha = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()

    r_games = requests.get(f"{BASE_URL}/games", headers=headers, params={"date": fecha})
    dump(f"/games?date={fecha}", r_games)

    juegos = r_games.json().get("response", [])
    game_id = juegos[0]["id"] if juegos else None

    r_teams = requests.get(f"{BASE_URL}/teams", headers=headers, params={"league": "standard"})
    dump("/teams?league=standard", r_teams)

    if game_id:
        dump(
            f"/games/statistics?id={game_id} (stats de EQUIPO del partido)",
            requests.get(f"{BASE_URL}/games/statistics", headers=headers, params={"id": game_id}),
        )
        dump(
            f"/players/statistics?game={game_id} (candidato a box score por JUGADOR)",
            requests.get(f"{BASE_URL}/players/statistics", headers=headers, params={"game": game_id}),
        )
    else:
        print(f"\nNo hay partidos para la fecha {fecha}; probá con una fecha donde sí haya juegos de NBA.")


if __name__ == "__main__":
    main()

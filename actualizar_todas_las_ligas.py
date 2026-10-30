"""
Refresca partidos, escudos y estadísticas (córners/tarjetas/tiros al arco)
de TODAS las ligas configuradas en backend/app.py (COMPETICIONES) — una
corrida que deja apuestas.db al día antes de generar cualquier reporte.

Pensado para correr cada noche desde GitHub Actions (ver
.github/workflows/reporte_telegram.yml) antes de enviar_telegram.py, pero
también sirve para refrescar todo a mano:
    python actualizar_todas_las_ligas.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import COMPETICIONES  # noqa: E402
from cargar_liga import cargar_liga  # noqa: E402

if __name__ == "__main__":
    for liga in COMPETICIONES:
        print(f"\n=== {liga['nombre']} (league_id={liga['id']}) ===")
        cargar_liga(liga["id"])

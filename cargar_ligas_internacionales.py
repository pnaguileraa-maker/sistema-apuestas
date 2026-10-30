"""
Carga de una sola corrida las 12 ligas top (primera división, masculino)
agregadas el 2026-10-23: España, Francia, Alemania, Italia, Portugal,
Holanda, Chile, Argentina, Brasil, México, USA y Arabia Saudita.

Ejecutar:
    python cargar_ligas_internacionales.py
"""

from cargar_liga import cargar_liga

LIGAS_A_CARGAR = {
    140: "España — La Liga",
    61: "Francia — Ligue 1",
    78: "Alemania — Bundesliga",
    135: "Italia — Serie A",
    94: "Portugal — Primeira Liga",
    88: "Holanda — Eredivisie",
    265: "Chile — Primera División",
    128: "Argentina — Liga Profesional",
    71: "Brasil — Brasileirão Série A",
    262: "México — Liga MX",
    253: "USA — MLS",
    307: "Arabia Saudita — Saudi Pro League",
}

if __name__ == "__main__":
    for league_id, etiqueta in LIGAS_A_CARGAR.items():
        print(f"\n=== {etiqueta} (league_id={league_id}) ===")
        cargar_liga(league_id)

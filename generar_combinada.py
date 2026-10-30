import random
import sqlite3


def generar_apuesta_combinada():
  conn = sqlite3.connect("apuestas.db")
  cursor = conn.cursor()

  # Buscamos partidos recientes o simulamos selección de candidatos con >70% de over 2.5
  cursor.execute("""
        SELECT m.id, t1.name as home_team, t2.name as away_team, m.home_goals, m.away_goals
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
    """)

  partidos = cursor.fetchall()
  conn.close()

  # Diccionario para calcular porcentajes de over 2.5 por equipo
  stats_goles = {}
  for p in partidos:
    _, home, away, h_g, a_g = p
    total = h_g + a_g
    for equipo in [home, away]:
      if equipo not in stats_goles:
        stats_goles[equipo] = {"total": 0, "over": 0}
      stats_goles[equipo]["total"] += 1
      if total > 2.5:
        stats_goles[equipo]["over"] += 1

  # Filtramos equipos con más del 65% de over 2.5
  buenos_candidatos = []
  for eq, st in stats_goles.items():
    if st["total"] >= 10:
      pct = (st["over"] / st["total"]) * 100
      if pct >= 68.0:
        buenos_candidatos.append((eq, pct))

  print("\n" + "=" * 65)
  print(" 🎫 GENERADOR AUTOMÁTICO DE APUESTA COMBINADA (ACUMULADA)")
  print("=" * 65)

  if len(buenos_candidatos) < 3:
    print("No hay suficientes candidatos para armar una combinada segura.")
    return

  # Seleccionamos al azar 3 equipos top para armar una combinada de 3 selecciones
  seleccionados = random.sample(buenos_candidatos, 3)

  cuota_total = 1.0
  print(f"{'Selección (Evento / Mercado)':<40} | {'Prob. Est.':<10} | {'Cuota'}")
  print("-" * 65)

  for equipo, pct in seleccionados:
    # Simulamos una cuota realista basada en el porcentaje (a mayor probabilidad, menor cuota)
    cuota_estimada = round(
        1.0 + (100 / (pct * 0.9)), 2
    )  # Fórmula simulada de cuota
    cuota_total *= cuota_estimada
    print(
        f"{'Más de 2.5 goles en partidazo de ' + equipo:<40} |"
        f" {pct:.1f}%      | {cuota_estimada}"
    )

  cuota_total = round(cuota_total, 2)
  print("=" * 65)
  print(f"🔥 CUOTA TOTAL COMBINADA ESTIMADA: {cuota_total}")
  print(
      "💡 Consejo: Una combinada de 3 selecciones con estos filtros estadísticos"
      " reduce el factor suerte."
  )
  print("=" * 65 + "\n")


if __name__ == "__main__":
  generar_apuesta_combinada()
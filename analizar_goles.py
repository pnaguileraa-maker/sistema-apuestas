import sqlite3


def analizar_candidatos_estrictos():
  conn = sqlite3.connect("apuestas.db")
  cursor = conn.cursor()

  # Consultamos los partidos terminados con sus goles totales y por mitades
  cursor.execute("""
        SELECT m.id, t1.name as home_team, t2.name as away_team,
               m.home_goals, m.away_goals
        FROM matches m
        JOIN teams t1 ON m.home_team_id = t1.id
        JOIN teams t2 ON m.away_team_id = t2.id
        WHERE m.home_goals IS NOT NULL AND m.away_goals IS NOT NULL
    """)

  partidos = cursor.fetchall()
  estadisticas_equipos = {}

  for partido in partidos:
    match_id, home, away, h_goals, a_goals = partido
    total_goles = h_goals + a_goals

    if home not in estadisticas_equipos:
      estadisticas_equipos[home] = {"partidos": 0, "over_2_5": 0}
    if away not in estadisticas_equipos:
      estadisticas_equipos[away] = {"partidos": 0, "over_2_5": 0}

    # Estadísticas para el equipo local
    estadisticas_equipos[home]["partidos"] += 1
    if total_goles > 2.5:
      estadisticas_equipos[home]["over_2_5"] += 1

    # Estadísticas para el equipo visitante
    estadisticas_equipos[away]["partidos"] += 1
    if total_goles > 2.5:
      estadisticas_equipos[away]["over_2_5"] += 1

  conn.close()

  # Imprimimos los resultados exigiendo un filtro estricto (ej. >= 75% u 80%)
  print("\n" + "=" * 70)
  print(" FILTRO DE ALTO RENDIMIENTO: EQUIPOS CON >= 75% DE PARTIDOS +2.5 GOLES")
  print("=" * 70)
  print(f"{'Equipo':<25} | {'Partidos':<10} | {'>2.5 Goles':<12} | {'%':<6}")
  print("-" * 70)

  candidatos_encontrados = 0
  for equipo, stats in estadisticas_equipos.items():
    total = stats["partidos"]
    if total >= 10:  # Mínimo 10 partidos analizados para que sea estadísticamente válido
      porcentaje = (stats["over_2_5"] / total) * 100
      # Aquí ajustamos el filtro a tu meta (ej. 75% o 80%)
      if porcentaje >= 75.0:
        print(
            f"{equipo:<25} | {total:<10} | {stats['over_2_5']:<12} |"
            f" {porcentaje:.1f}%"
        )
        candidatos_encontrados += 1

  if candidatos_encontrados == 0:
    print(
        "No hay equipos que superen el 75% con el filtro actual (prueba bajando"
        " un poco el umbral si deseas ver más opciones)."
    )

  print("=" * 70 + "\n")


if __name__ == "__main__":
  analizar_candidatos_estrictos()
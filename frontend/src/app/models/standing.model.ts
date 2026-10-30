/** Un partido ya finalizado, desde la perspectiva de un equipo (para forma y calendario) */
export interface MatchResult {
  fixtureId: number;
  date: string;
  opponentId: number;
  opponentName: string;
  opponentLogo: string | null;
  isHome: boolean;
  homeGoals: number;
  awayGoals: number;
  /** null si ese partido todavía no tiene estadísticas (ver actualizar_estadisticas_partidos.py) */
  homeCorners: number | null;
  awayCorners: number | null;
  homeCards: number | null;
  awayCards: number | null;
  result: 'W' | 'D' | 'L';
}

/** Fila de la tabla de posiciones oficial, calculada a partir de apuestas.db */
export interface Standing {
  position: number;
  teamId: number;
  teamName: string;
  teamLogo: string | null;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDiff: number;
  points: number;
  /** Últimos 5 partidos jugados, del más antiguo al más reciente */
  last5: MatchResult[];
  /** Promedios usados en las barras de tendencia; corners/cards son null sin datos de actualizar_estadisticas_partidos.py */
  goalsForAvg: number;
  cornersAvg: number | null;
  cardsAvg: number | null;
}

/** Refleja la tabla `teams` de apuestas.db */
export interface Team {
  id: number;
  name: string;
  country?: string;
}

/** Refleja la tabla `matches` de apuestas.db */
export interface Match {
  id: number;
  date: string;
  leagueId: number;
  homeTeamId: number;
  awayTeamId: number;
  status: string;
  homeGoals: number | null;
  awayGoals: number | null;
}

/** Estadísticas rápidas de un equipo, embebidas en cada partido del día */
export interface QuickTeamStats {
  teamId: number;
  teamName: string;
  teamLogo: string | null;
  goalsForAvg: number;
  over25Pct: number;
  cornersAvg: number | null;
  cornersOverPct: number | null;
  cardsAvg: number | null;
  cardsOverPct: number | null;
}

/** Un partido programado/jugado en una fecha concreta */
export interface DayMatch {
  fixtureId: number;
  date: string;
  status: string;
  leagueId: number;
  leagueName: string;
  homeGoals: number | null;
  awayGoals: number | null;
  home: QuickTeamStats;
  away: QuickTeamStats;
}

export interface RadarEntry {
  teamId: number;
  teamName: string;
  teamLogo: string | null;
  valor: number;
  mercado?: string;
}

/** Métricas destacadas del día: mayor media goleadora, tendencia más fuerte y mayor riesgo de tarjetas */
export interface JornadaRadar {
  mayorMediaGoleadora: RadarEntry;
  tendenciaMasFuerte: RadarEntry;
  mayorRiesgoTarjetas: RadarEntry | null;
}

export interface DayMatchesResponse {
  fecha: string;
  radar: JornadaRadar | null;
  partidos: DayMatch[];
}

import { MatchResult } from './standing.model';

/** Un partido todavía no jugado, desde la perspectiva de un equipo */
export interface UpcomingMatch {
  fixtureId: number;
  date: string;
  opponentId: number;
  opponentName: string;
  opponentLogo: string | null;
  isHome: boolean;
  status: string;
}

/** Calendario completo de un equipo para una temporada: jugados y por jugar */
export interface TeamSchedule {
  teamId: number;
  teamName: string;
  teamLogo: string | null;
  pasados: MatchResult[];
  proximos: UpcomingMatch[];
}

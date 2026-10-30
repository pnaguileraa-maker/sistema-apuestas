/**
 * Ficha de equipo (head-to-head): % W/D/L, % Over 1.5/2.5 goles y
 * córners/tarjetas promedio para la temporada, sin filtro de min_partidos.
 */
export interface TeamSummary {
  teamId: number;
  teamName: string;
  teamLogo: string | null;
  matchesPlayed: number;
  won: number;
  drawn: number;
  lost: number;
  winPct: number;
  drawPct: number;
  lossPct: number;
  over15Pct: number;
  over25Pct: number;
  over35Pct: number;
  cornersAvg: number | null;
  cornersLine: number | null;
  cornersOverPct: number | null;
  cardsAvg: number | null;
  cardsLine: number | null;
  cardsOverPct: number | null;
}

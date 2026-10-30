/**
 * Estadística agregada por equipo, equivalente al resultado de
 * analizar_goles.py pero calculada/servida para la UI.
 *
 * cornersAvg/cardsAvg y sus derivados son `null` hasta que se corra
 * actualizar_estadisticas_partidos.py para esa temporada.
 */
/** % de partidos sobre cada línea (umbral), totalmente abierto: sin límite de cantidad de líneas */
export type LineBreakdown = Record<string, number | null>;

/** Líneas múltiples por mercado, separadas en total del partido / a favor / en contra */
export interface MarketLineSplit {
  total: LineBreakdown;
  for: LineBreakdown;
  against: LineBreakdown;
}

export interface TeamStat {
  teamId: number;
  teamName: string;
  teamLogo: string | null;
  league: string;
  matchesPlayed: number;
  over25Count: number;
  over25Pct: number;
  cornersAvg: number | null;
  cornersLine: number | null;
  cornersOverPct: number | null;
  cardsAvg: number | null;
  cardsLine: number | null;
  cardsOverPct: number | null;
  form: ('W' | 'D' | 'L')[];
  lines: {
    goals: MarketLineSplit;
    corners: MarketLineSplit;
    cards: MarketLineSplit;
  };
}

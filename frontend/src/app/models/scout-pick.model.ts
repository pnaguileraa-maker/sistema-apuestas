/** Mercado sobre el que se calculan las líneas de cumplimiento de un Scout Pick */
export type MercadoPick = 'goals' | 'corners' | 'cards';

/** Una línea de cumplimiento (ej. "5/5 · global (100%)") */
export interface RachaMercado {
  aciertos: number;
  total: number;
  /** null cuando no hay partidos con ese dato todavía (total = 0) */
  porcentaje: number | null;
  etiqueta: string;
}

/** Tarjeta "Scout Pick": el mercado con mejor respaldo estadístico para un
 * partido, con sus 4 líneas de cumplimiento (global, últimos 10, H2H, últimos 5).
 * Es también la entrada de cada partido en el calendario semanal. */
export interface ScoutPick {
  fixtureId: number;
  date: string;
  status: string;
  homeGoals: number | null;
  awayGoals: number | null;
  leagueId: number;
  leagueName: string;
  homeTeamId: number;
  homeTeamName: string;
  homeTeamLogo: string | null;
  awayTeamId: number;
  awayTeamName: string;
  awayTeamLogo: string | null;
  /** null cuando no hay datos suficientes todavía para elegir un mercado */
  mercado: MercadoPick | null;
  linea: number | null;
  recomendacion: string;
  rachas: RachaMercado[];
  /** Promedio de % global y % de últimos 10 del mercado elegido; null sin datos */
  probabilidad: number | null;
  /** true si el pick supera el umbral de confianza con muestra mínima */
  solido: boolean;
}

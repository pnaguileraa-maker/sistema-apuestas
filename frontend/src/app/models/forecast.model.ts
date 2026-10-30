import { MercadoPick, RachaMercado } from './scout-pick.model';

/** Una de las 3 mejores opciones de apuesta de un partido: cálculo
 * estadístico fijo (sin IA), igual al que arma cada Scout Pick. */
export interface SuggestedOption {
  mercado: MercadoPick;
  linea: number;
  recomendacion: string;
  rachas: RachaMercado[];
  probabilidad: number | null;
  solido: boolean;
}

/** Pronóstico fijo de un partido de hoy o de mañana: 3 mejores opciones de
 * apuesta (estadísticas) + un análisis narrativo (IA, generado una sola vez
 * y reutilizado en cada carga). */
export interface MatchForecast {
  fixtureId: number;
  date: string;
  homeTeamId: number;
  homeTeamName: string;
  homeTeamLogo: string | null;
  awayTeamId: number;
  awayTeamName: string;
  awayTeamLogo: string | null;
  informe: string;
  opciones: SuggestedOption[];
}

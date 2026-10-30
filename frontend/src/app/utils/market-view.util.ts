import { MarketKey } from '../models/market.model';
import { TeamStat } from '../models/team-stat.model';

export interface MarketView {
  /** Valor mostrado en la columna principal de la tabla (% o promedio) */
  displayValue: number | null;
  /** Línea/umbral evaluado para este equipo y mercado (null si aún no hay datos) */
  line: number | null;
  /** Probabilidad estimada 0-100 usada para la cuota del boleto */
  probability: number | null;
  /** Etiqueta de la selección dentro del boleto, p. ej. "Over 5.5 Córners" */
  betLabel: string;
}

export function getMarketView(stat: TeamStat, market: MarketKey): MarketView {
  switch (market) {
    case 'goles':
      return {
        displayValue: stat.over25Pct,
        line: 2.5,
        probability: stat.over25Pct,
        betLabel: 'Over 2.5 Goles',
      };
    case 'corners':
      return {
        displayValue: stat.cornersAvg,
        line: stat.cornersLine,
        probability: stat.cornersOverPct,
        betLabel: stat.cornersLine !== null ? `Over ${stat.cornersLine} Córners` : 'Córners',
      };
    case 'cards':
      return {
        displayValue: stat.cardsAvg,
        line: stat.cardsLine,
        probability: stat.cardsOverPct,
        betLabel: stat.cardsLine !== null ? `Over ${stat.cardsLine} Tarjetas` : 'Tarjetas',
      };
  }
}

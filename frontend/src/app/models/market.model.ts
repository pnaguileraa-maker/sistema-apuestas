export type MarketKey = 'goles' | 'corners' | 'cards';

export interface MarketDefinition {
  key: MarketKey;
  label: string;
  icon: string;
  /** Etiqueta de la columna numérica principal en la tabla */
  columnLabel: string;
  /** Explica qué línea/umbral se evalúa para calcular el % sobre línea de este mercado */
  lineDescription: string;
}

/** Claves usadas en TeamStat.lines (inglés, reflejan las keys que arma el backend) */
export type LineMarketKey = 'goals' | 'corners' | 'cards';

export const LINE_MARKET_KEY: Record<MarketKey, LineMarketKey> = {
  goles: 'goals',
  corners: 'corners',
  cards: 'cards',
};

/** Umbrales de líneas múltiples por mercado — deben reflejar LINEAS_MERCADOS en backend/app.py */
export const MARKET_LINES: Record<MarketKey, number[]> = {
  goles: [0.5, 1.5, 2.5, 3.5, 4.5],
  corners: [7.5, 8.5, 9.5, 10.5, 11.5],
  cards: [1.5, 2.5, 3.5, 4.5, 5.5],
};

export const MARKETS: MarketDefinition[] = [
  {
    key: 'goles',
    label: 'Goles (+2.5)',
    icon: '⚽',
    columnLabel: '% +2.5 Goles',
    lineDescription: 'Línea fija para todos los equipos: Over 2.5 goles totales del partido.',
  },
  {
    key: 'corners',
    label: 'Córners (Promedio)',
    icon: '🚩',
    columnLabel: 'Córners (avg)',
    lineDescription:
      'Línea personalizada por equipo (su propio promedio redondeado − 0.5) — valor exacto en la columna "Línea".',
  },
  {
    key: 'cards',
    label: 'Tarjetas (Promedio)',
    icon: '🟨',
    columnLabel: 'Tarjetas (avg)',
    lineDescription:
      'Línea personalizada por equipo (su propio promedio redondeado − 0.5) — valor exacto en la columna "Línea".',
  },
];

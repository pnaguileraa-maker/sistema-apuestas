/**
 * Cuota estimada a partir de una probabilidad (0-100), misma fórmula
 * simulada usada en generar_combinada.py: a mayor probabilidad, menor cuota.
 */
export function estimateOddsFromProbability(probabilityPct: number): number {
  return Math.round((1 + 100 / (probabilityPct * 0.9)) * 100) / 100;
}

export type EstadoPartido = 'en-directo' | 'proximos' | 'finalizados';

const FINALIZADOS = new Set(['FT', 'AET', 'PEN']);
const EN_DIRECTO = new Set(['1H', 'HT', '2H', 'ET', 'BT', 'P', 'LIVE', 'SUSP', 'INT']);

export function clasificarEstado(status: string): EstadoPartido {
  if (FINALIZADOS.has(status)) return 'finalizados';
  if (EN_DIRECTO.has(status)) return 'en-directo';
  return 'proximos';
}

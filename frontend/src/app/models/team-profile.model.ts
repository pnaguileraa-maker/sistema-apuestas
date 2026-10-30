/** Desglose de rendimiento (General / Local / Visitante) para el pop-up de equipo */
export interface TeamSplitStats {
  played: number;
  won: number;
  drawn: number;
  lost: number;
  points: number;
  ppg: number;
  winPct: number;
  goalsForAvg: number;
  goalsAgainstAvg: number;
  bttsPct: number;
  cleanSheetPct: number;
}

/** Perfil avanzado de equipo: posición, país, forma y splits General/Local/Visitante */
export interface TeamProfile {
  teamId: number;
  teamName: string;
  teamLogo: string | null;
  country: string | null;
  position: number | null;
  form: ('W' | 'D' | 'L')[];
  general: TeamSplitStats;
  home: TeamSplitStats;
  away: TeamSplitStats;
}

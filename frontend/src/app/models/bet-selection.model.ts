/** Una selección dentro del boleto de apuestas combinada */
export interface BetSelection {
  id: string;
  teamId: number;
  teamName: string;
  /** Etiqueta libre, p. ej. "Over 2.5 Goles" o "Over 5.5 Córners" */
  market: string;
  /** Probabilidad estimada 0-100, usada para derivar la cuota */
  probability: number;
  odds: number;
}

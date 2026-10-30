import { Injectable, computed, signal } from '@angular/core';
import { BetSelection } from '../models/bet-selection.model';

/** Estado del "boleto" de apuestas: selecciones activas, stake y cuota combinada. */
@Injectable({ providedIn: 'root' })
export class BetSlipService {
  private readonly _selections = signal<BetSelection[]>([]);
  private readonly _stake = signal<number>(10);

  readonly selections = this._selections.asReadonly();
  readonly stake = this._stake.asReadonly();

  readonly totalOdds = computed(() => {
    const picks = this._selections();
    if (picks.length === 0) return 0;
    const product = picks.reduce((acc, pick) => acc * pick.odds, 1);
    return Math.round(product * 100) / 100;
  });

  readonly potentialReturn = computed(() => {
    return Math.round(this.totalOdds() * this._stake() * 100) / 100;
  });

  isSelected(teamId: number, market: BetSelection['market']): boolean {
    return this._selections().some((s) => s.teamId === teamId && s.market === market);
  }

  toggle(selection: BetSelection): void {
    const exists = this._selections().some((s) => s.id === selection.id);
    this._selections.update((current) =>
      exists ? current.filter((s) => s.id !== selection.id) : [...current, selection],
    );
  }

  remove(selectionId: string): void {
    this._selections.update((current) => current.filter((s) => s.id !== selectionId));
  }

  clear(): void {
    this._selections.set([]);
  }

  setStake(value: number): void {
    this._stake.set(Number.isFinite(value) && value > 0 ? value : 0);
  }
}

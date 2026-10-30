import { Injectable, signal } from '@angular/core';
import { MarketKey } from '../models/market.model';

/** Mercado activo compartido entre la tabla de equipos y el dashboard. */
@Injectable({ providedIn: 'root' })
export class MarketFilterService {
  private readonly _selected = signal<MarketKey>('goles');

  readonly selected = this._selected.asReadonly();

  select(market: MarketKey): void {
    this._selected.set(market);
  }
}

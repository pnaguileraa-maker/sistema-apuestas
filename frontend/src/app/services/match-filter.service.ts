import { Injectable, signal } from '@angular/core';

export type EstadoFiltro = 'todos' | 'en-directo' | 'proximos' | 'finalizados';

/** Estado de los filtros del panel "Inicio": estado del partido y competición. */
@Injectable({ providedIn: 'root' })
export class MatchFilterService {
  private readonly _estado = signal<EstadoFiltro>('todos');
  private readonly _competicionId = signal<number | null>(null);

  readonly estado = this._estado.asReadonly();
  readonly competicionId = this._competicionId.asReadonly();

  setEstado(estado: EstadoFiltro): void {
    this._estado.set(estado);
  }

  setCompeticion(id: number | null): void {
    this._competicionId.set(id);
  }
}

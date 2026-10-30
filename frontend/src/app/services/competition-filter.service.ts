import { Injectable, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, of } from 'rxjs';
import { Competition } from '../models/competition.model';
import { MatchesService } from './matches.service';

const PREMIER_LEAGUE_ID = 39;

/** Competición activa en el Panel de Análisis: la tabla de estadísticas, los
 * % sobre línea, la tabla de posiciones y los calendarios de equipo se
 * recalculan todos a partir de esta selección. */
@Injectable({ providedIn: 'root' })
export class CompetitionFilterService {
  private readonly matchesService = inject(MatchesService);

  readonly competiciones = toSignal(
    this.matchesService.getCompeticiones().pipe(catchError(() => of<Competition[]>([]))),
    { initialValue: [] as Competition[] },
  );

  private readonly _selectedId = signal(PREMIER_LEAGUE_ID);
  readonly selectedId = this._selectedId.asReadonly();

  readonly selected = computed<Competition | null>(
    () => this.competiciones().find((c) => c.id === this.selectedId()) ?? null,
  );

  select(id: number | string): void {
    // Los <select> nativos del DOM emiten el valor como string incluso con
    // [value]="c.id" numérico; se normaliza aquí para que todo lo que
    // dependa de selectedId (estadísticas, posiciones, calendarios) reciba
    // siempre un number consistente.
    this._selectedId.set(Number(id));
  }
}

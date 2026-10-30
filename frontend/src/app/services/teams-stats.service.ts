import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { catchError, of, switchMap } from 'rxjs';
import { API_BASE_URL } from '../core/api';
import { TeamStat } from '../models/team-stat.model';
import { CompetitionFilterService } from './competition-filter.service';

/**
 * Consume la API local respaldada por apuestas.db y la lógica de analizar_goles.py.
 * Si el backend no está corriendo, expone una lista vacía en vez de romper la UI.
 * Se recalcula automáticamente al cambiar la competición activa.
 */
@Injectable({ providedIn: 'root' })
export class TeamsStatsService {
  private readonly http = inject(HttpClient);
  private readonly competitionFilter = inject(CompetitionFilterService);

  readonly stats = toSignal(
    toObservable(this.competitionFilter.selectedId).pipe(
      switchMap((leagueId) =>
        this.http.get<TeamStat[]>(`${API_BASE_URL}/equipos`, { params: { league_id: leagueId } }).pipe(
          catchError((error) => {
            console.error('No se pudo conectar con la API de estadísticas (¿está corriendo backend/app.py?)', error);
            return of<TeamStat[]>([]);
          }),
        ),
      ),
    ),
    { initialValue: [] },
  );
}

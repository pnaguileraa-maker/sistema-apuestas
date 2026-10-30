import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../core/api';
import { ScoutPick } from '../models/scout-pick.model';

@Injectable({ providedIn: 'root' })
export class CalendarioSemanaService {
  private readonly http = inject(HttpClient);

  /** Partidos de la semana actual (Premier League + Champions League,
   * priorizada), cada uno con su Scout Pick embebido, ya ordenados por el
   * backend (liga, solidez y probabilidad). */
  getCalendarioSemana(): Observable<ScoutPick[]> {
    return this.http.get<ScoutPick[]>(`${API_BASE_URL}/calendario-semana`);
  }
}

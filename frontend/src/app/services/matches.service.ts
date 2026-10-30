import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../core/api';
import { Competition } from '../models/competition.model';
import { DayMatchesResponse } from '../models/match-day.model';

@Injectable({ providedIn: 'root' })
export class MatchesService {
  private readonly http = inject(HttpClient);

  getPartidosDelDia(fecha: string, season: number | null): Observable<DayMatchesResponse> {
    const params: Record<string, string | number> = { fecha };
    if (season !== null) params['season'] = season;
    return this.http.get<DayMatchesResponse>(`${API_BASE_URL}/partidos`, { params });
  }

  getCompeticiones(): Observable<Competition[]> {
    return this.http.get<Competition[]>(`${API_BASE_URL}/competiciones`);
  }
}

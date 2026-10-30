import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../core/api';
import { MatchForecast } from '../models/forecast.model';

function query(leagueId: number, forzar: boolean): string {
  const params = [`league_id=${leagueId}`];
  if (forzar) params.push('forzar=1');
  return `?${params.join('&')}`;
}

@Injectable({ providedIn: 'root' })
export class ForecastService {
  private readonly http = inject(HttpClient);

  getPronosticosHoy(leagueId: number, forzar = false): Observable<MatchForecast[]> {
    return this.http.get<MatchForecast[]>(`${API_BASE_URL}/pronosticos/hoy${query(leagueId, forzar)}`);
  }

  getPronosticosManana(leagueId: number, forzar = false): Observable<MatchForecast[]> {
    return this.http.get<MatchForecast[]>(`${API_BASE_URL}/pronosticos/manana${query(leagueId, forzar)}`);
  }

  getPronosticosSemana(leagueId: number, forzar = false): Observable<MatchForecast[]> {
    return this.http.get<MatchForecast[]>(`${API_BASE_URL}/pronosticos/semana${query(leagueId, forzar)}`);
  }
}

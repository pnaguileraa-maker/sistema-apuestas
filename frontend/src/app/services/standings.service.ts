import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../core/api';
import { Standing } from '../models/standing.model';
import { TeamProfile } from '../models/team-profile.model';
import { TeamSchedule } from '../models/team-schedule.model';
import { TeamSummary } from '../models/team-summary.model';

const PREMIER_LEAGUE_ID = 39;

@Injectable({ providedIn: 'root' })
export class StandingsService {
  private readonly http = inject(HttpClient);

  getSeasons(leagueId: number): Observable<number[]> {
    return this.http.get<number[]>(`${API_BASE_URL}/temporadas`, { params: { league_id: leagueId } });
  }

  getStandings(season: number, leagueId: number): Observable<Standing[]> {
    return this.http.get<Standing[]>(`${API_BASE_URL}/posiciones`, {
      params: { season, league_id: leagueId },
    });
  }

  getCalendario(teamId: number, season: number, leagueId: number): Observable<TeamSchedule> {
    return this.http.get<TeamSchedule>(`${API_BASE_URL}/equipos/${teamId}/calendario`, {
      params: { season, league_id: leagueId },
    });
  }

  getResumen(teamId: number, season: number, leagueId: number): Observable<TeamSummary> {
    return this.http.get<TeamSummary>(`${API_BASE_URL}/equipos/${teamId}/resumen`, {
      params: { season, league_id: leagueId },
    });
  }

  // Nota: el pop-up global de perfil (team-popup) abre por teamId sin saber
  // en qué competición juega ese partido, así que mantiene el valor por
  // defecto; el Panel de Análisis (que sí sabe la liga activa) pasa el suyo.
  getPerfil(teamId: number, leagueId: number = PREMIER_LEAGUE_ID): Observable<TeamProfile> {
    return this.http.get<TeamProfile>(`${API_BASE_URL}/equipos/${teamId}/perfil`, {
      params: { league_id: leagueId },
    });
  }
}

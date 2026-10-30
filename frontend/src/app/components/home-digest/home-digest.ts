import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, of } from 'rxjs';
import { DayMatchesResponse } from '../../models/match-day.model';
import { MatchesService } from '../../services/matches.service';
import { ForecastPanel } from '../forecast-panel/forecast-panel';
import { MatchFilterSidebar } from '../match-filter-sidebar/match-filter-sidebar';
import { RadarJornada } from '../radar-jornada/radar-jornada';
import { TeamPopup } from '../team-popup/team-popup';
import { WeeklyCalendar } from '../weekly-calendar/weekly-calendar';

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

@Component({
  selector: 'app-home-digest',
  standalone: true,
  imports: [CommonModule, MatchFilterSidebar, RadarJornada, TeamPopup, ForecastPanel, WeeklyCalendar],
  templateUrl: './home-digest.html',
})
export class HomeDigest {
  private readonly matchesService = inject(MatchesService);

  // Radar de la jornada: siempre referido a hoy (el calendario semanal, abajo, ya cubre toda la semana).
  protected readonly radarHoy = toSignal(
    this.matchesService
      .getPartidosDelDia(toIsoDate(new Date()), null)
      .pipe(catchError(() => of<DayMatchesResponse | null>(null))),
    { initialValue: null as DayMatchesResponse | null },
  );
}

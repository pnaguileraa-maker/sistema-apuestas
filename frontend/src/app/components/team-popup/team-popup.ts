import { CommonModule } from '@angular/common';
import { Component, computed, inject } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { catchError, of, switchMap } from 'rxjs';
import { TeamProfile } from '../../models/team-profile.model';
import { StandingsService } from '../../services/standings.service';
import { TeamPopupService } from '../../services/team-popup.service';
import { TeamCrest } from '../team-crest/team-crest';

interface SplitRow {
  label: string;
  general: string;
  home: string;
  away: string;
}

@Component({
  selector: 'app-team-popup',
  standalone: true,
  imports: [CommonModule, TeamCrest],
  templateUrl: './team-popup.html',
})
export class TeamPopup {
  private readonly standingsService = inject(StandingsService);
  protected readonly popup = inject(TeamPopupService);

  protected readonly profile = toSignal(
    toObservable(this.popup.teamId).pipe(
      switchMap((teamId) =>
        teamId === null
          ? of<TeamProfile | null>(null)
          : this.standingsService.getPerfil(teamId).pipe(catchError(() => of<TeamProfile | null>(null))),
      ),
    ),
    { initialValue: null as TeamProfile | null },
  );

  protected readonly rows = computed<SplitRow[]>(() => {
    const data = this.profile();
    if (!data) return [];

    return [
      { label: 'PJ', general: `${data.general.played}`, home: `${data.home.played}`, away: `${data.away.played}` },
      { label: 'PPG', general: `${data.general.ppg}`, home: `${data.home.ppg}`, away: `${data.away.ppg}` },
      { label: 'Ganar %', general: `${data.general.winPct}%`, home: `${data.home.winPct}%`, away: `${data.away.winPct}%` },
      {
        label: 'Anotados (avg)',
        general: `${data.general.goalsForAvg}`,
        home: `${data.home.goalsForAvg}`,
        away: `${data.away.goalsForAvg}`,
      },
      {
        label: 'Concedidos (avg)',
        general: `${data.general.goalsAgainstAvg}`,
        home: `${data.home.goalsAgainstAvg}`,
        away: `${data.away.goalsAgainstAvg}`,
      },
      { label: 'BTTS %', general: `${data.general.bttsPct}%`, home: `${data.home.bttsPct}%`, away: `${data.away.bttsPct}%` },
      {
        label: 'Valla invicta (CS) %',
        general: `${data.general.cleanSheetPct}%`,
        home: `${data.home.cleanSheetPct}%`,
        away: `${data.away.cleanSheetPct}%`,
      },
    ];
  });

  protected resultBadgeClass(result: 'W' | 'D' | 'L'): string {
    if (result === 'W') return 'bg-emerald-500 text-white';
    if (result === 'L') return 'bg-rose-500 text-white';
    return 'bg-gray-400 text-white';
  }
}

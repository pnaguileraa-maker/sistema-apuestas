import { CommonModule } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { catchError, of, switchMap } from 'rxjs';
import { TeamSchedule as TeamScheduleModel } from '../../models/team-schedule.model';
import { CompetitionFilterService } from '../../services/competition-filter.service';
import { StandingsService } from '../../services/standings.service';
import { TeamCrest } from '../team-crest/team-crest';

@Component({
  selector: 'app-team-schedule',
  standalone: true,
  imports: [CommonModule, TeamCrest],
  templateUrl: './team-schedule.html',
})
export class TeamSchedule {
  private readonly standingsService = inject(StandingsService);
  private readonly competitionFilter = inject(CompetitionFilterService);

  readonly teamId = input<number | null>(null);
  readonly season = input<number | null>(null);

  private readonly params = computed(() => ({
    teamId: this.teamId(),
    season: this.season(),
    leagueId: this.competitionFilter.selectedId(),
  }));

  protected readonly schedule = toSignal(
    toObservable(this.params).pipe(
      switchMap(({ teamId, season, leagueId }) =>
        teamId === null || season === null
          ? of<TeamScheduleModel | null>(null)
          : this.standingsService
              .getCalendario(teamId, season, leagueId)
              .pipe(catchError(() => of<TeamScheduleModel | null>(null))),
      ),
    ),
    { initialValue: null as TeamScheduleModel | null },
  );

  protected resultDotClass(result: 'W' | 'D' | 'L'): string {
    if (result === 'W') return 'bg-emerald-500';
    if (result === 'L') return 'bg-rose-500';
    return 'bg-gray-400';
  }
}

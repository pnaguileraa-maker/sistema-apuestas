import { CommonModule } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { catchError, forkJoin, of, switchMap } from 'rxjs';
import { MatchResult } from '../../models/standing.model';
import { TeamSchedule } from '../../models/team-schedule.model';
import { TeamSummary } from '../../models/team-summary.model';
import { CompetitionFilterService } from '../../services/competition-filter.service';
import { StandingsService } from '../../services/standings.service';
import { TeamCrest } from '../team-crest/team-crest';

interface TeamOverviewData {
  summary: TeamSummary;
  schedule: TeamSchedule;
}

@Component({
  selector: 'app-team-overview',
  standalone: true,
  imports: [CommonModule, TeamCrest],
  templateUrl: './team-overview.html',
})
export class TeamOverview {
  private readonly standingsService = inject(StandingsService);
  private readonly competitionFilter = inject(CompetitionFilterService);

  readonly teamId = input<number | null>(null);
  readonly season = input<number | null>(null);

  private readonly params = computed(() => ({
    teamId: this.teamId(),
    season: this.season(),
    leagueId: this.competitionFilter.selectedId(),
  }));

  protected readonly data = toSignal(
    toObservable(this.params).pipe(
      switchMap(({ teamId, season, leagueId }) =>
        teamId === null || season === null
          ? of<TeamOverviewData | null>(null)
          : forkJoin({
              summary: this.standingsService.getResumen(teamId, season, leagueId),
              schedule: this.standingsService.getCalendario(teamId, season, leagueId),
            }).pipe(catchError(() => of<TeamOverviewData | null>(null))),
      ),
    ),
    { initialValue: null as TeamOverviewData | null },
  );

  protected readonly recentForm = computed<MatchResult['result'][]>(() => {
    const schedule = this.data()?.schedule;
    if (!schedule) return [];
    return schedule.pasados.slice(0, 5).map((m) => m.result);
  });

  protected readonly nextMatch = computed(() => this.data()?.schedule.proximos[0] ?? null);

  protected resultBadgeClass(result: MatchResult['result']): string {
    if (result === 'W') return 'bg-emerald-500 text-white';
    if (result === 'L') return 'bg-rose-500 text-white';
    return 'bg-gray-400 text-white';
  }
}

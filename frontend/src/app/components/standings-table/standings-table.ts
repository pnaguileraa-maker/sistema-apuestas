import { CommonModule } from '@angular/common';
import { Component, computed, effect, inject, input, output, signal } from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { catchError, of, switchMap } from 'rxjs';
import { MatchResult, Standing } from '../../models/standing.model';
import { CompetitionFilterService } from '../../services/competition-filter.service';
import { StandingsService } from '../../services/standings.service';
import { TeamPopupService } from '../../services/team-popup.service';
import { TeamCrest } from '../team-crest/team-crest';

@Component({
  selector: 'app-standings-table',
  standalone: true,
  imports: [CommonModule, FormsModule, TeamCrest],
  templateUrl: './standings-table.html',
})
export class StandingsTable {
  private readonly standingsService = inject(StandingsService);
  protected readonly teamPopup = inject(TeamPopupService);
  protected readonly competitionFilter = inject(CompetitionFilterService);

  /** Versión condensada (escudo, PJ, PTS, últimos 5) para usar como sidebar junto al análisis de mercados. */
  readonly compact = input(false);

  /** Notifica al contenedor qué equipo/temporada están activos, para mostrar la ficha y el calendario fuera de este componente. */
  readonly teamSelected = output<number | null>();
  readonly seasonChanged = output<number | null>();

  private readonly leagueId = this.competitionFilter.selectedId;

  protected readonly seasons = toSignal(
    toObservable(this.leagueId).pipe(
      switchMap((leagueId) => this.standingsService.getSeasons(leagueId).pipe(catchError(() => of<number[]>([])))),
    ),
    { initialValue: [] as number[] },
  );

  // Temporada elegida a mano por el usuario (null = "todavía no eligió,
  // usar la más reciente de la liga activa"). Se deriva de `seasons()`, así
  // que si cambia la liga y esa temporada ya no existe para la liga nueva,
  // vuelve a caer en la más reciente automáticamente — sin necesidad de
  // "recordar" la liga anterior a mano.
  private readonly manualSeason = signal<number | null>(null);

  protected readonly selectedSeason = computed<number | null>(() => {
    const seasons = this.seasons();
    const manual = this.manualSeason();
    if (manual !== null && seasons.includes(manual)) return manual;
    return seasons[0] ?? null;
  });

  protected readonly selectedTeamId = signal<number | null>(null);

  private readonly standingsParams = computed(() => ({ leagueId: this.leagueId(), season: this.selectedSeason() }));

  protected readonly standings = toSignal(
    toObservable(this.standingsParams).pipe(
      switchMap(({ leagueId, season }) =>
        season === null
          ? of<Standing[]>([])
          : this.standingsService.getStandings(season, leagueId).pipe(catchError(() => of<Standing[]>([]))),
      ),
    ),
    { initialValue: [] as Standing[] },
  );

  constructor() {
    // Avisa al contenedor (Dashboard) cada vez que la temporada efectiva cambia
    // (por elección manual o porque cambió de liga y se recalculó sola).
    effect(() => this.seasonChanged.emit(this.selectedSeason()));

    // Al cambiar de liga, el equipo elegido (de la liga anterior) ya no aplica.
    effect(() => {
      this.leagueId();
      this.selectedTeamId.set(null);
      this.teamSelected.emit(null);
    });
  }

  protected onSeasonChange(value: string): void {
    const season = Number(value);
    this.manualSeason.set(season);
    this.selectedTeamId.set(null);
    this.teamSelected.emit(null);
  }

  protected selectTeam(teamId: number): void {
    const next = this.selectedTeamId() === teamId ? null : teamId;
    this.selectedTeamId.set(next);
    this.teamSelected.emit(next);
  }

  protected openProfile(teamId: number, event: Event): void {
    event.stopPropagation();
    this.teamPopup.open(teamId);
  }

  protected rowZoneClass(position: number, total: number): string {
    if (position <= 4) return 'border-l-4 border-emerald-500';
    if (position > total - 3) return 'border-l-4 border-rose-500';
    return 'border-l-4 border-transparent';
  }

  protected resultDotClass(result: MatchResult['result']): string {
    if (result === 'W') return 'bg-emerald-500';
    if (result === 'L') return 'bg-rose-500';
    return 'bg-gray-400';
  }

  protected matchSummary(equipo: Standing, m: MatchResult): string {
    const local = m.isHome ? equipo.teamName : m.opponentName;
    const visita = m.isHome ? m.opponentName : equipo.teamName;
    return `${local} ${m.homeGoals}-${m.awayGoals} ${visita}`;
  }

  // Máximos de la temporada visible, usados para normalizar el ancho (0-100%)
  // de las mini-barras de tendencia por equipo.
  protected readonly maxTrend = computed(() => {
    const rows = this.standings();
    const maxOf = (values: number[]) => Math.max(0.01, ...values, 0);
    return {
      goals: maxOf(rows.map((r) => r.goalsForAvg)),
      corners: maxOf(rows.map((r) => r.cornersAvg ?? 0)),
      cards: maxOf(rows.map((r) => r.cardsAvg ?? 0)),
    };
  });

  protected trendWidth(value: number | null, max: number): number {
    if (value === null || max <= 0) return 0;
    return Math.min(100, Math.round((value / max) * 100));
  }
}

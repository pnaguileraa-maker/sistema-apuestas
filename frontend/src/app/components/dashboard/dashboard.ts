import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { BetSlip } from '../bet-slip/bet-slip';
import { ForecastPanel } from '../forecast-panel/forecast-panel';
import { StandingsTable } from '../standings-table/standings-table';
import { TeamOverview } from '../team-overview/team-overview';
import { TeamPopup } from '../team-popup/team-popup';
import { TeamSchedule } from '../team-schedule/team-schedule';
import { TeamsStatsTable } from '../teams-stats-table/teams-stats-table';
import { MARKETS } from '../../models/market.model';
import { CompetitionFilterService } from '../../services/competition-filter.service';
import { MarketFilterService } from '../../services/market-filter.service';
import { TeamsStatsService } from '../../services/teams-stats.service';
import { getMarketView } from '../../utils/market-view.util';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    TeamsStatsTable,
    BetSlip,
    StandingsTable,
    TeamOverview,
    TeamSchedule,
    TeamPopup,
    ForecastPanel,
  ],
  templateUrl: './dashboard.html',
})
export class Dashboard {
  private readonly statsService = inject(TeamsStatsService);
  private readonly marketFilter = inject(MarketFilterService);
  protected readonly competitionFilter = inject(CompetitionFilterService);

  protected readonly stats = this.statsService.stats;
  protected readonly activeMarketDef = computed(
    () => MARKETS.find((m) => m.key === this.marketFilter.selected())!,
  );

  // La tabla de posiciones (sidebar) es la fuente de verdad del equipo/temporada
  // seleccionados; la ficha y el calendario se muestran aquí, fuera del sidebar.
  protected readonly selectedTeamId = signal<number | null>(null);
  protected readonly selectedSeason = signal<number | null>(null);

  protected readonly summary = computed(() => {
    const market = this.marketFilter.selected();
    const stats = this.stats();
    const views = stats.map((s) => ({ stat: s, view: getMarketView(s, market) }));
    const conDatos = views.filter((v) => v.view.probability !== null);

    const strictCandidates = conDatos.filter((v) => v.view.probability! >= 75).length;
    const avgPct = conDatos.length
      ? conDatos.reduce((sum, v) => sum + v.view.probability!, 0) / conDatos.length
      : 0;
    const top = conDatos.reduce<(typeof conDatos)[number] | null>(
      (best, v) => (!best || v.view.probability! > best.view.probability! ? v : best),
      null,
    );

    return {
      totalTeams: stats.length,
      strictCandidates,
      avgPct,
      topTeamName: top?.stat.teamName ?? '--',
    };
  });
}

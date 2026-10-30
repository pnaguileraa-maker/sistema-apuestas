import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LINE_MARKET_KEY, LineMarketKey, MARKET_LINES, MARKETS, MarketKey } from '../../models/market.model';
import { TeamStat } from '../../models/team-stat.model';
import { BetSlipService } from '../../services/bet-slip.service';
import { CompetitionFilterService } from '../../services/competition-filter.service';
import { MarketFilterService } from '../../services/market-filter.service';
import { TeamPopupService } from '../../services/team-popup.service';
import { TeamsStatsService } from '../../services/teams-stats.service';
import { TeamCrest } from '../team-crest/team-crest';
import { estimateOddsFromProbability } from '../../utils/odds.util';
import { getMarketView } from '../../utils/market-view.util';

const LINE_SPLITS = ['total', 'for', 'against'] as const;
type LineSplit = (typeof LINE_SPLITS)[number];

@Component({
  selector: 'app-teams-stats-table',
  standalone: true,
  imports: [CommonModule, FormsModule, TeamCrest],
  templateUrl: './teams-stats-table.html',
})
export class TeamsStatsTable {
  private readonly statsService = inject(TeamsStatsService);
  protected readonly betSlip = inject(BetSlipService);
  protected readonly marketFilter = inject(MarketFilterService);
  protected readonly teamPopup = inject(TeamPopupService);
  protected readonly competitionFilter = inject(CompetitionFilterService);

  protected readonly markets = MARKETS;
  protected readonly lineSplits = LINE_SPLITS;
  protected readonly search = signal('');
  protected readonly minPct = signal(0);

  protected readonly activeMarket = this.marketFilter.selected;

  protected readonly activeMarketDef = computed(
    () => this.markets.find((m) => m.key === this.activeMarket())!,
  );

  protected readonly lineThresholds = computed(() => MARKET_LINES[this.activeMarket()]);
  protected readonly lineMarketKey = computed<LineMarketKey>(() => LINE_MARKET_KEY[this.activeMarket()]);

  protected readonly filteredStats = computed(() => {
    const search = this.search().trim().toLowerCase();
    const minPct = this.minPct();
    const market = this.activeMarket();

    return this.statsService
      .stats()
      .filter((s) => s.teamName.toLowerCase().includes(search))
      .filter((s) => {
        const value = getMarketView(s, market).displayValue;
        return value === null ? minPct === 0 : value >= minPct;
      })
      .sort((a, b) => {
        const va = getMarketView(a, market).displayValue;
        const vb = getMarketView(b, market).displayValue;
        if (va === null) return 1;
        if (vb === null) return -1;
        return vb - va;
      });
  });

  protected selectMarket(key: MarketKey): void {
    this.marketFilter.select(key);
  }

  protected lineValue(stat: TeamStat, split: LineSplit, threshold: number): number | null {
    return stat.lines[this.lineMarketKey()][split][String(threshold)] ?? null;
  }

  protected splitLabel(split: LineSplit): string {
    if (split === 'total') return 'Total del partido';
    if (split === 'for') return 'A favor';
    return 'En contra';
  }

  protected openProfile(teamId: number, event: Event): void {
    event.stopPropagation();
    this.teamPopup.open(teamId);
  }

  protected viewFor(stat: TeamStat) {
    return getMarketView(stat, this.activeMarket());
  }

  protected pctBadgeClass(pct: number | null): string {
    if (pct === null) return 'bg-gray-100 text-gray-500 ring-1 ring-gray-200';
    if (pct >= 75) return 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200';
    if (pct >= 60) return 'bg-amber-50 text-amber-700 ring-1 ring-amber-200';
    return 'bg-gray-100 text-gray-600 ring-1 ring-gray-200';
  }

  protected formDot(result: 'W' | 'D' | 'L'): string {
    return result === 'W' ? '🟢' : result === 'D' ? '⚪' : '🔴';
  }

  protected formLabel(result: 'W' | 'D' | 'L'): string {
    return result === 'W' ? 'Victoria' : result === 'D' ? 'Empate' : 'Derrota';
  }

  protected isInSlip(stat: TeamStat): boolean {
    const view = this.viewFor(stat);
    return this.betSlip.isSelected(stat.teamId, view.betLabel);
  }

  protected toggleSelection(stat: TeamStat): void {
    const view = this.viewFor(stat);
    if (view.probability === null) return;

    this.betSlip.toggle({
      id: `${stat.teamId}-${this.activeMarket()}`,
      teamId: stat.teamId,
      teamName: stat.teamName,
      market: view.betLabel,
      probability: view.probability,
      odds: estimateOddsFromProbability(view.probability),
    });
  }
}

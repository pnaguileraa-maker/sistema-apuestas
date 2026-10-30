import { CommonModule } from '@angular/common';
import { Component, inject, input } from '@angular/core';
import { ScoutPick } from '../../models/scout-pick.model';
import { TeamPopupService } from '../../services/team-popup.service';
import { TeamCrest } from '../team-crest/team-crest';

/** Tarjeta "Scout Pick" de UN partido: escudos, abreviatura, hora/resultado,
 * el mercado estrella y sus líneas de cumplimiento. Es la entrada atómica
 * del calendario semanal — no un listado aparte. */
@Component({
  selector: 'app-scout-pick-card',
  standalone: true,
  imports: [CommonModule, TeamCrest],
  templateUrl: './scout-pick-card.html',
})
export class ScoutPickCard {
  readonly pick = input.required<ScoutPick>();

  private readonly teamPopup = inject(TeamPopupService);

  protected openProfile(teamId: number, event: Event): void {
    event.stopPropagation();
    this.teamPopup.open(teamId);
  }

  protected marcador(): string | null {
    const p = this.pick();
    return p.homeGoals !== null && p.awayGoals !== null ? `${p.homeGoals} - ${p.awayGoals}` : null;
  }

  protected barraClase(porcentaje: number | null): string {
    if (porcentaje === null) return 'bg-gray-300';
    if (porcentaje >= 80) return 'bg-emerald-500';
    if (porcentaje >= 60) return 'bg-sky-500';
    return 'bg-amber-500';
  }

  protected textoClase(porcentaje: number | null): string {
    if (porcentaje === null) return 'text-gray-400';
    if (porcentaje >= 80) return 'text-emerald-600';
    if (porcentaje >= 60) return 'text-sky-600';
    return 'text-amber-600';
  }
}

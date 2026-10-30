import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { ScoutPick } from '../../models/scout-pick.model';
import { CalendarioSemanaService } from '../../services/calendario-semana.service';
import { MatchFilterService } from '../../services/match-filter.service';
import { clasificarEstado } from '../../utils/match-status.util';
import { ScoutPickCard } from '../scout-pick-card/scout-pick-card';

interface DiaCalendario {
  fecha: string;
  partidos: ScoutPick[];
}

/** Calendario de la semana actual: Premier League + Champions League
 * (priorizada), agrupado por día, cada partido con su Scout Pick embebido.
 * El orden dentro de cada día viene ya resuelto por el backend (liga,
 * solidez y luego probabilidad) — acá solo se agrupa por fecha. */
@Component({
  selector: 'app-weekly-calendar',
  standalone: true,
  imports: [CommonModule, ScoutPickCard],
  templateUrl: './weekly-calendar.html',
})
export class WeeklyCalendar {
  private readonly calendarioService = inject(CalendarioSemanaService);
  protected readonly filters = inject(MatchFilterService);

  protected readonly loading = signal(true);
  protected readonly error = signal(false);
  private readonly partidos = signal<ScoutPick[]>([]);

  constructor() {
    this.calendarioService.getCalendarioSemana().subscribe({
      next: (data) => {
        this.partidos.set(data);
        this.loading.set(false);
      },
      error: () => {
        this.error.set(true);
        this.loading.set(false);
      },
    });
  }

  private readonly partidosFiltrados = computed<ScoutPick[]>(() => {
    const estado = this.filters.estado();
    const competicionId = this.filters.competicionId();

    return this.partidos().filter((p) => {
      if (competicionId !== null && p.leagueId !== competicionId) return false;
      if (estado === 'todos') return true;
      return clasificarEstado(p.status) === estado;
    });
  });

  protected readonly dias = computed<DiaCalendario[]>(() => {
    const grupos = new Map<string, ScoutPick[]>();
    for (const p of this.partidosFiltrados()) {
      const fecha = p.date.slice(0, 10);
      const lista = grupos.get(fecha);
      if (lista) {
        lista.push(p);
      } else {
        grupos.set(fecha, [p]);
      }
    }
    return Array.from(grupos.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([fecha, partidos]) => ({ fecha, partidos }));
  });
}

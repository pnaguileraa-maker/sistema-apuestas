import { CommonModule } from '@angular/common';
import { Component, effect, inject, signal } from '@angular/core';
import { MatchForecast } from '../../models/forecast.model';
import { CompetitionFilterService } from '../../services/competition-filter.service';
import { ForecastService } from '../../services/forecast.service';
import { TeamCrest } from '../team-crest/team-crest';

export type DiaPronostico = 'hoy' | 'manana' | 'semana';

/** Panel fijo (no modal) con los pronósticos: se mantiene siempre visible en
 * la página, con pestañas para elegir el día/periodo. La competición no se
 * elige acá — sigue al selector global del dashboard (CompetitionFilterService),
 * igual que la tabla de estadísticas, posiciones y calendario, así cambiar de
 * liga arriba actualiza todo el panel. Cada partido trae un pronóstico fijo
 * (3 opciones estadísticas + análisis de IA generado una sola vez y cacheado
 * en el backend); el botón "Regenerar" fuerza un nuevo cálculo para la
 * pestaña/liga activa. */
@Component({
  selector: 'app-forecast-panel',
  standalone: true,
  imports: [CommonModule, TeamCrest],
  templateUrl: './forecast-panel.html',
})
export class ForecastPanel {
  private readonly forecastService = inject(ForecastService);
  protected readonly competitionFilter = inject(CompetitionFilterService);

  protected readonly dia = signal<DiaPronostico>('hoy');
  protected readonly loading = signal(false);
  protected readonly forecasts = signal<MatchForecast[] | null>(null);
  protected readonly error = signal<string | null>(null);

  private cargado: { dia: DiaPronostico; leagueId: number } | null = null;

  constructor() {
    // Genera los pronósticos la primera vez que se muestra cada combinación
    // pestaña/liga; no se vuelve a pedir solo por re-renderizar (evita
    // llamadas de IA de más), pero sí al cambiar de pestaña o de competición
    // en el selector global.
    effect(() => {
      const dia = this.dia();
      const leagueId = this.competitionFilter.selectedId();
      const yaCargado = this.cargado?.dia === dia && this.cargado?.leagueId === leagueId;
      if (!yaCargado && !this.loading()) {
        this.cargar();
      }
    });
  }

  protected seleccionarDia(dia: DiaPronostico): void {
    this.dia.set(dia);
  }

  protected cargar(forzar = false): void {
    const dia = this.dia();
    const leagueId = this.competitionFilter.selectedId();
    this.loading.set(true);
    this.error.set(null);
    const pronosticos$ =
      dia === 'hoy'
        ? this.forecastService.getPronosticosHoy(leagueId, forzar)
        : dia === 'manana'
          ? this.forecastService.getPronosticosManana(leagueId, forzar)
          : this.forecastService.getPronosticosSemana(leagueId, forzar);
    pronosticos$.subscribe({
      next: (data) => {
        this.forecasts.set(data);
        this.cargado = { dia, leagueId };
        this.loading.set(false);
      },
      error: () => {
        this.error.set(
          'No se pudieron generar los pronósticos. Verifica que el backend tenga ANTHROPIC_API_KEY configurada en el .env.',
        );
        this.cargado = { dia, leagueId };
        this.loading.set(false);
      },
    });
  }

  protected titulo(): string {
    const dia = this.dia();
    if (dia === 'hoy') return 'Pronósticos de Hoy';
    if (dia === 'manana') return 'Pronósticos de Mañana';
    return 'Pronósticos de la Semana';
  }

  protected etiquetaPeriodo(): string {
    const dia = this.dia();
    if (dia === 'hoy') return 'hoy';
    if (dia === 'manana') return 'mañana';
    return 'esta semana';
  }

  protected mensajeCarga(): string {
    return 'Cargando pronósticos...';
  }
}

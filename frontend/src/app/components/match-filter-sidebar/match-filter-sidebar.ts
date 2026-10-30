import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { catchError, of } from 'rxjs';
import { Competition } from '../../models/competition.model';
import { EstadoFiltro, MatchFilterService } from '../../services/match-filter.service';
import { MatchesService } from '../../services/matches.service';

const ESTADOS: { value: EstadoFiltro; label: string; icon: string }[] = [
  { value: 'todos', label: 'Todos', icon: '📋' },
  { value: 'en-directo', label: 'En directo', icon: '🔴' },
  { value: 'proximos', label: 'Próximos', icon: '🕒' },
  { value: 'finalizados', label: 'Finalizados', icon: '✅' },
];

@Component({
  selector: 'app-match-filter-sidebar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './match-filter-sidebar.html',
})
export class MatchFilterSidebar {
  private readonly matchesService = inject(MatchesService);
  protected readonly filters = inject(MatchFilterService);

  protected readonly estados = ESTADOS;

  protected readonly competiciones = toSignal(
    this.matchesService.getCompeticiones().pipe(catchError(() => of<Competition[]>([]))),
    { initialValue: [] as Competition[] },
  );
}

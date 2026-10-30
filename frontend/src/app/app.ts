import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { Dashboard } from './components/dashboard/dashboard';
import { HomeDigest } from './components/home-digest/home-digest';

type Tab = 'inicio' | 'panel';

@Component({
  imports: [CommonModule, Dashboard, HomeDigest],
  selector: 'app-root',
  template: `
    <nav class="sticky top-0 z-10 flex justify-center gap-1 border-b border-gray-200 bg-white px-6 py-2 shadow-sm">
      <button
        type="button"
        (click)="tab.set('inicio')"
        class="rounded-lg px-4 py-1.5 text-sm font-medium transition-colors"
        [ngClass]="tab() === 'inicio' ? 'bg-emerald-600 text-white shadow-sm' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-900'"
      >
        🏠 Inicio
      </button>
      <button
        type="button"
        (click)="tab.set('panel')"
        class="rounded-lg px-4 py-1.5 text-sm font-medium transition-colors"
        [ngClass]="tab() === 'panel' ? 'bg-emerald-600 text-white shadow-sm' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-900'"
      >
        ⚽ Panel de Análisis
      </button>
    </nav>

    @if (tab() === 'inicio') {
      <app-home-digest />
    } @else {
      <app-dashboard />
    }
  `,
})
export class App {
  protected readonly tab = signal<Tab>('inicio');
}

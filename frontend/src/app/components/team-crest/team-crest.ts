import { CommonModule } from '@angular/common';
import { Component, input, signal } from '@angular/core';

const PALETTE = [
  'bg-emerald-100 text-emerald-700',
  'bg-sky-100 text-sky-700',
  'bg-amber-100 text-amber-700',
  'bg-rose-100 text-rose-700',
  'bg-violet-100 text-violet-700',
  'bg-cyan-100 text-cyan-700',
];

const SIZE_CLASSES = {
  sm: 'h-6 w-6 text-[10px]',
  md: 'h-9 w-9 text-xs',
  lg: 'h-14 w-14 text-base',
} as const;

/** Escudo de equipo con fallback a iniciales cuando no hay logo o falla la carga. */
@Component({
  selector: 'app-team-crest',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './team-crest.html',
})
export class TeamCrest {
  readonly logoUrl = input<string | null>(null);
  readonly teamName = input('');
  readonly size = input<keyof typeof SIZE_CLASSES>('md');

  protected readonly loadFailed = signal(false);

  protected get sizeClass(): string {
    return SIZE_CLASSES[this.size()];
  }

  protected get initials(): string {
    const parts = this.teamName().trim().split(/\s+/);
    const letters = parts.length > 1 ? parts[0][0] + parts[1][0] : this.teamName().slice(0, 2);
    return letters.toUpperCase();
  }

  protected get fallbackColor(): string {
    const name = this.teamName();
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
      hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    }
    return PALETTE[hash % PALETTE.length];
  }

  protected onError(): void {
    this.loadFailed.set(true);
  }
}

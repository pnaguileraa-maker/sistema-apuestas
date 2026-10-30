import { Injectable, signal } from '@angular/core';

/** Qué equipo (si hay alguno) tiene abierto el pop-up de perfil avanzado. */
@Injectable({ providedIn: 'root' })
export class TeamPopupService {
  private readonly _teamId = signal<number | null>(null);

  readonly teamId = this._teamId.asReadonly();

  open(teamId: number): void {
    this._teamId.set(teamId);
  }

  close(): void {
    this._teamId.set(null);
  }
}

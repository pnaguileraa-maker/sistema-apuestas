import { CommonModule } from '@angular/common';
import { Component, input } from '@angular/core';
import { JornadaRadar } from '../../models/match-day.model';
import { TeamCrest } from '../team-crest/team-crest';

@Component({
  selector: 'app-radar-jornada',
  standalone: true,
  imports: [CommonModule, TeamCrest],
  templateUrl: './radar-jornada.html',
})
export class RadarJornada {
  readonly radar = input<JornadaRadar | null>(null);
}

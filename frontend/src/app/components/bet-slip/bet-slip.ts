import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { BetSlipService } from '../../services/bet-slip.service';

@Component({
  selector: 'app-bet-slip',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './bet-slip.html',
})
export class BetSlip {
  constructor(protected readonly betSlip: BetSlipService) {}

  protected onStakeChange(value: string): void {
    this.betSlip.setStake(Number(value));
  }
}

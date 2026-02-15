import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class DataService {
  // Questo "canale" tiene a mente i nomi delle aziende inserite
  private targetsSource = new BehaviorSubject<string>('');
  currentTargets = this.targetsSource.asObservable();

  updateTargets(targets: string) {
    this.targetsSource.next(targets);
  }
}
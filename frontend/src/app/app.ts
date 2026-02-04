import { Component, OnInit, OnDestroy, ChangeDetectorRef, NgZone } from '@angular/core'; // <--- 1. Import NgZone
import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms'; 

// Material Imports
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatChipsModule } from '@angular/material/chips';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiService } from './services/api.service';
import { Deal, ScrapeSettings, ScrapeStatus } from './models/deal.model';
import { interval, Subscription, switchMap, catchError, of } from 'rxjs';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule, HttpClientModule, FormsModule,
    MatToolbarModule, MatButtonModule, MatTableModule, MatIconModule,
    MatProgressBarModule, MatChipsModule, MatCardModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatExpansionModule, MatTooltipModule
  ],
  templateUrl: './app.html',
  styleUrls: ['./app.scss']
})
export class AppComponent implements OnInit, OnDestroy {
  
  // Questo testo è il DEFAULT. Se l'utente lo cambia nell'HTML, vale quello dell'utente.
  settings: ScrapeSettings = {
    target_companies: 'ICEYE',
    source: 'SpaceNews',
    ai_model: 'mistral-large-latest',
    api_key: '', 
    min_year: 2020,
    max_pages: 1,
    system_prompt: `Sei un estrattore specializzato di informazioni finanziarie e industriali dal testo di news nel settore space. 
Il tuo obiettivo è determinare se l'articolo descrive un evento aziendale concreto tra: acquisizioni, merger, investimenti, IPO, partnership strategiche o grandi contratti commerciali.

Devi restituire SOLO un JSON sintatticamente valido con ESATTAMENTE le seguenti chiavi: source, url, title, published_date, section, is_relevant, relevance_score, deal_type, deal_status, acquirer, target, investors, amount, currency, valuation, stake_percent, key_assets, geography, summary, why_it_matters, entities.

REGOLE GENERALI:
- Usa esclusivamente doppi apici per stringhe JSON.
- Non aggiungere testo prima o dopo il JSON.
- Non inserire commenti.
- Se un'informazione non è presente nel testo, usa null o [].
- Non inventare dati o numeri.

DEFINIZIONE DI RILEVANZA:
- is_relevant deve essere true SOLO se l'articolo descrive un evento aziendale reale e concreto.
- Se non esiste un evento aziendale concreto, imposta:
  is_relevant=false, deal_type='none', deal_status='unknown', entities=[].

CAMPO deal_type:
- Valori ammessi: acquisition, merger, investment, partnership, contract, ipo, other, none.

CAMPO deal_status:
- Valori ammessi: rumor, announced, completed, unknown.

CAMPI ECONOMICI:
- amount, valuation e stake_percent solo se esplicitamente indicati nel testo.
- Non stimare o dedurre valori mancanti.

Il JSON prodotto deve essere sempre valido.`
  };

  deals: Deal[] = [];
  status: ScrapeStatus | null = null;
  statusSub: Subscription | null = null;
  displayedColumns: string[] = ['date', 'title', 'type', 'parties', 'amount', 'status'];
  estimatedTime = '0 sec';

  // 2. INIETTIAMO NgZone + ChangeDetectorRef
  constructor(private api: ApiService, private cdr: ChangeDetectorRef, private ngZone: NgZone) {}

  ngOnInit() {
    this.calculateTime();
  }

  ngOnDestroy() {
    this.stopPolling();
  }

  calculateTime() {
    const totalSecs = this.settings.max_pages * 20 * 2; 
    const mins = Math.floor(totalSecs / 60);
    this.estimatedTime = `${mins} min ${totalSecs % 60} sec`;
  }

  startAnalysis() {
    if (!this.settings.api_key || this.settings.api_key.trim() === '') {
      alert("ERRORE: Devi inserire una Mistral API Key per procedere!");
      return; 
    }
    
    this.deals = []; 
    this.status = { 
        is_running: true, 
        total_articles: 0, 
        processed_articles: 0, 
        current_status: 'Initializing...', 
        logs: [],
        last_update: ''
    };
    
    this.api.startScrape(this.settings).subscribe({
      next: (res) => {
        this.startPolling();
      },
      error: (err) => {
        console.error("Errore avvio:", err);
        alert("Errore di connessione! Guarda la console.");
        this.status = null;
      }
    });
  }

  // --- POLLING BLINDATO CON NGZONE ---
  startPolling() {
    this.stopPolling();

    // Eseguiamo il timer FUORI da Angular per non appesantire...
    this.ngZone.runOutsideAngular(() => {
        
        this.statusSub = interval(1000).pipe(
            switchMap(() => this.api.getStatus().pipe(
                catchError(err => {
                    console.warn("Polling glitch:", err);
                    return of(null);
                })
            ))
        ).subscribe((s) => {
            // ...ma quando arrivano i dati, RIENTRIAMO in Angular per aggiornare la UI
            this.ngZone.run(() => {
                if (s) {
                    this.status = s;
                    this.cdr.detectChanges(); // Forza aggiornamento immediato

                    if (!s.is_running) {
                        if (s.processed_articles > 0 || s.total_articles > 0) {
                            this.loadResults();
                        }
                        this.stopPolling();
                    }
                }
            });
        });

    });
  }

  stopPolling() {
    if (this.statusSub) {
        this.statusSub.unsubscribe();
        this.statusSub = null;
    }
  }

  loadResults() {
    this.api.getResults().subscribe(data => {
      this.ngZone.run(() => { // Sicurezza anche qui
          this.deals = data;
          this.deals.sort((a, b) => new Date(b.published_date).getTime() - new Date(a.published_date).getTime());
          this.cdr.detectChanges();
      });
    });
  }

  formatData(input: any): string {
    if (!input) return '-';
    if (typeof input === 'string' || typeof input === 'number') return String(input);
    if (Array.isArray(input)) return input.map(item => this.formatData(item)).join(', ');
    if (typeof input === 'object') {
        if (input.name) return input.name;
        if (input.company) return input.company;
        return Object.values(input)[0] as string || JSON.stringify(input);
    }
    return String(input);
  }
}
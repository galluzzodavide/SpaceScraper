import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http'; // Aggiunto HttpParams
import { DataService } from '../../services/data.service'; // <--- ASSICURATI CHE IL PATH SIA CORRETTO

@Component({
  selector: 'app-heatmap-grid',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './heatmap-grid.html',
  styleUrls: ['./heatmap-grid.scss'],
  styles: [`:host { display: block; width: 100%; height: 100%; }`]
})
export class HeatmapGrid implements OnInit {
  companies: any[] = [];
  logoErrors: { [key: string]: boolean } = {};
  
  // Memorizziamo l'ultimo target per ricaricamenti manuali se necessario
  currentSearchTargets: string = '';

  constructor(
    private http: HttpClient,
    private dataService: DataService, // <--- 1. INIETTA IL SERVIZIO
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    this.loadHeatmap(''); 
    // ------------------------------------------------------------
    // 2. Continua ad ascoltare I CAMBIAMENTI FUTURI (es. se premo "Start Scraper")
    this.dataService.currentTargets.subscribe(targets => {
      // Evitiamo che il BehaviorSubject (se lo usi) faccia una doppia chiamata inutile all'avvio
      if (targets !== this.currentSearchTargets) {
          console.log('HEATMAP: Ricevuti nuovi target per il filtro:', targets);
          this.currentSearchTargets = targets;
          this.loadHeatmap(targets);
      }  
    });
  }

  // 3. CARICAMENTO CON FILTRO: Passa i target al backend
  loadHeatmap(targets: string) {
    let params = new HttpParams();
    if (targets) {
      params = params.set('targets', targets);
    }

    this.http.get<any[]>('http://localhost:8000/api/dashboard/heatmap', { params }).subscribe({
      next: (data) => {
        console.log('HEATMAP DATA RECEIVED:', data);
        this.logoErrors = {}; // Reset errori ad ogni ricaricamento
        this.companies = data;
        // Inizializza stato errori loghi
        data.forEach(c => this.logoErrors[c.name] = false);
        this.cdr.detectChanges();
      },
      error: (err) => console.error('Heatmap error:', err)
    });
  }

  // --- LOGICA LOGHI (Rimane invariata ma ottimizzata) ---
  getLogoUrl(name: string): string {
    if (!name) return '';
    let clean = name.toLowerCase()
      .replace(/(\s|^)(inc|ltd|llc|corp|corporation|gmbh|spa|co)(\.|\s|$)/g, '')
      .trim();
    const domainGuess = clean.replace(/[^a-z0-9]/g, '') + '.com';
    return `https://cdn.brandfetch.io/${domainGuess}/w/500/h/500?c=1icon`;
  }

  handleImgError(event: any, companyName: string) {
    const img = event.target;
    const src = img.src;
    let clean = companyName.toLowerCase()
        .replace(/(\s|^)(inc|ltd|llc|corp|corporation|gmbh|spa|co)(\.|\s|$)/g, '')
        .trim();
    const domain = clean.replace(/[^a-z0-9]/g, '') + '.com';

    if (src.includes('brandfetch')) {
        img.src = `https://logo.clearbit.com/${domain}?size=500`;
    } else if (src.includes('clearbit')) {
        img.src = `https://www.google.com/s2/favicons?domain=${domain}&sz=128`;
    } else {
        img.style.display = 'none';
        this.logoErrors[companyName] = true; // Attiva il watermark testuale nel template
    }
  }

  // --- STILI ---
  getScoreClass(score: number): string {
    if (score >= 8) return 'score-high';
    if (score >= 4) return 'score-medium';
    return 'score-low';
  }

  getTileSizeClass(score: number): string {
    if (score >= 12) return 'tile-large';
    if (score >= 7) return 'tile-medium';
    return 'tile-small';
  }
}
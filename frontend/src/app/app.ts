import { Component, OnInit, OnDestroy, ChangeDetectorRef, NgZone } from '@angular/core';
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
import { MatButtonToggleModule } from '@angular/material/button-toggle'; 
import { MatGridListModule } from '@angular/material/grid-list'; 

import { ApiService } from './services/api.service';
import { Deal, ScrapeSettings, ScrapeStatus } from './models/deal.model';
import { interval, Subscription, switchMap, catchError, of } from 'rxjs';
import { PROMPT_TEMPLATES, PromptTemplate } from './prompts';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule, HttpClientModule, FormsModule,
    MatToolbarModule, MatButtonModule, MatTableModule, MatIconModule,
    MatProgressBarModule, MatChipsModule, MatCardModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatExpansionModule, MatTooltipModule,
    MatButtonToggleModule, MatGridListModule
  ],
  templateUrl: './app.html',
  styleUrls: ['./app.scss']
})
export class AppComponent implements OnInit, OnDestroy {
  
  viewMode: 'dashboard' | 'template-selection' = 'dashboard';
  
  templates = PROMPT_TEMPLATES;
  selectedTemplateName: string = ''; 
  selectedTemplateId: string = ''; // Used for dynamic HTML logic

  settings: ScrapeSettings = {
    target_companies: 'ICEYE',
    source: 'SpaceNews',
    ai_model: 'mistral-large-latest',
    api_key: '', 
    min_year: 2020,
    max_pages: 1,
    system_prompt: '' 
  };

  allDeals: Deal[] = [];       
  filteredDeals: Deal[] = [];  
  selectedType: string = 'ALL'; 

  get deals() { return this.filteredDeals; }

  status: ScrapeStatus | null = null;
  statusSub: Subscription | null = null;

  // --- COLUMN DEFINITIONS ---

  // 1. Financial Profile (Standard)
  financialColumns: string[] = [
    'relevance_score', 'published_date', 'source', 'title', 
    'deal_type', 'deal_status', 'acquirer', 'target', 
    'amount', 'valuation', 'stake_percent', // Economic fields
    'summary'
  ];

  // 2. Technical Profile (No money, focus on specs & impact)
  technicalColumns: string[] = [
    'relevance_score', 'published_date', 'source', 'title', 
    'deal_type', 'deal_status', 'target', 
    'key_assets',   // Will map to "Tech Specs"
    'why_it_matters', // Will map to "Tech Impact"
    'summary'
  ];

  // The actual variable used by mat-table
  displayedColumns: string[] = this.financialColumns; 

  estimatedTime = '0 sec';

  constructor(private api: ApiService, private cdr: ChangeDetectorRef, private ngZone: NgZone) {}

  ngOnInit() {
    this.calculateTime();
    
    // Default: Financial Controller
    const defaultTemplate = this.templates.find(t => t.id === 'financial-controller') || this.templates[0];
    this.selectTemplate(defaultTemplate, false); 
  }

  ngOnDestroy() {
    this.stopPolling();
  }

  changeTemplate() {
      this.viewMode = 'template-selection';
  }

  selectTemplate(template: PromptTemplate, navigateToDashboard: boolean = true) {
      this.selectedTemplateId = template.id;
      this.selectedTemplateName = template.name;
      this.settings.system_prompt = template.content;
      
      // --- DYNAMIC COLUMN SWITCHING ---
      if (template.id === 'technical-controller') {
          this.displayedColumns = this.technicalColumns;
      } else {
          // Default for Financial and others
          this.displayedColumns = this.financialColumns;
      }
      
      if (navigateToDashboard) {
          this.viewMode = 'dashboard';
      }
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
    
    this.allDeals = []; 
    this.filteredDeals = []; 
    
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

  startPolling() {
    this.stopPolling();
    this.ngZone.runOutsideAngular(() => {
        this.statusSub = interval(1000).pipe(
            switchMap(() => this.api.getStatus().pipe(
                catchError(err => {
                    console.warn("Polling glitch:", err);
                    return of(null);
                })
            ))
        ).subscribe((s) => {
            this.ngZone.run(() => {
                if (s) {
                    this.status = s;
                    this.cdr.detectChanges(); 

                    if (s.processed_articles > 0 || this.allDeals.length !== s.total_articles) {
                         this.loadResults(); 
                    }

                    if (!s.is_running) {
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
      this.ngZone.run(() => {
          if (JSON.stringify(data) !== JSON.stringify(this.allDeals)) {
              this.allDeals = data;
              this.allDeals.sort((a, b) => new Date(b.published_date).getTime() - new Date(a.published_date).getTime());
              this.applyFilter(this.selectedType);
              this.cdr.detectChanges();
          }
      });
    });
  }

  applyFilter(type: string) {
      this.selectedType = type;
      if (type === 'ALL') {
          this.filteredDeals = [...this.allDeals];
      } else {
          this.filteredDeals = this.allDeals.filter(d => 
              d.deal_type && d.deal_type.toLowerCase().includes(type.toLowerCase())
          );
      }
  }

  getScoreClass(score: any): string {
      const val = parseFloat(score);
      if (isNaN(val)) return '';
      if (val >= 0.90) return 'score-high';     
      if (val >= 0.70) return 'score-medium';   
      return 'score-low';                       
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
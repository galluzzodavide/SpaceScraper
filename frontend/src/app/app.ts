import { Component, OnInit, ChangeDetectorRef, OnDestroy } from '@angular/core'; 
import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms'; 
import * as XLSX from 'xlsx'; 

// Material Imports
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatChipsModule } from '@angular/material/chips';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatButtonToggleModule } from '@angular/material/button-toggle'; 
import { MatGridListModule } from '@angular/material/grid-list';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDividerModule } from '@angular/material/divider'; // Ensure imported here

import { ApiService } from './services/api.service';
import { Deal, ScrapeSettings, SourceType } from './models/deal.model';
import { PROMPT_TEMPLATES, PromptTemplate } from './prompts';

// --- DEFINIZIONE SORGENTI DISPONIBILI ---
const ALL_SOURCES = [
    // FINANCIAL SOURCES
    { name: SourceType.SPACENEWS, category: 'Financial', label: 'SpaceNews (Business)' },
    { name: SourceType.SNAPI, category: 'Financial', label: 'SNAPI (Aggregator)' },
    { name: SourceType.SPACEWORKS, category: 'Financial', label: 'SpaceWorks (Benchmark)' },
    { name: SourceType.EURO_SPACEFLIGHT, category: 'Financial', label: 'European Spaceflight (EU)' },
    
    // TECHNICAL SOURCES
    { name: SourceType.VIA_SATELLITE, category: 'Technical', label: 'Via Satellite (Tech)' },
    { name: SourceType.NASA_TECHPORT, category: 'Technical', label: 'NASA TechPort (R&D)' }
];

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule, HttpClientModule, FormsModule,
    MatToolbarModule, MatButtonModule, MatTableModule, MatIconModule,
    MatProgressBarModule, MatProgressSpinnerModule, 
    MatChipsModule, MatCardModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatExpansionModule, MatTooltipModule,
    MatButtonToggleModule, MatGridListModule, MatSnackBarModule,
    MatCheckboxModule, MatDividerModule // <--- ADDED THIS TO FIX NG8001 ERROR
  ],
  templateUrl: './app.html',
  styleUrls: ['./app.scss']
})
export class AppComponent implements OnInit, OnDestroy {
  
  viewMode: 'dashboard' | 'template-selection' = 'template-selection';
  
  templates = PROMPT_TEMPLATES;
  selectedTemplateName: string = ''; 
  selectedTemplateId: string = ''; 

  displayedSources: any[] = [];

  // --- ADDED THIS TO FIX TS2339 ERROR ---
  availableModels = [
    { value: 'groq/llama-3.3-70b-versatile', label: 'Groq (Llama 3.3 - 70B Versatile)' },
    { value: 'groq/llama-3.1-8b-instant', label: 'Groq (Llama 3.1 - 8B Instant)' },
    { value: 'mistral-large-latest', label: 'Mistral API (Standard)' },
    { value: 'mistral-small', label: 'Mistral API (Small)' },
    { value: 'ollama/mistral', label: 'llama Local' }
  ];
  // --------------------------------------

  settings: ScrapeSettings = {
    target_companies: 'ICEYE',
    sources: [], 
    ai_model: 'mistral-large-latest',
    api_key: '', 
    min_year: 2024,
    max_pages: 1,
    system_prompt: '',
    force_rescan: false
  };

  allDeals: Deal[] = [];       
  filteredDeals: Deal[] = [];  
  selectedType: string = 'ALL'; 
  
  get deals() { return this.filteredDeals; }

  // --- STATO CARICAMENTO ---
  isRunning = false;
  statusMessage = 'Ready';
  estimatedTime = '0 sec';
  
  // Variabili per la progress bar
  progressValue = 0;
  private progressInterval: any; // Riferimento al timer

  // --- DEFINIZIONE COLONNE ---
  financialColumns: string[] = [
    'relevance_score', 'published_date', 'source', 'title', 
    'deal_type', 'deal_status', 'amount', 'investors', 'summary'
  ];

  technicalColumns: string[] = [
    'relevance_score', 'source', 'title', 
    'technology_readiness_level', 
    'key_assets',                 
    'amount',                     
    'mission_type',               
    'summary'
  ];

  displayedColumns: string[] = this.financialColumns; 

  constructor(
    private api: ApiService, 
    private cdr: ChangeDetectorRef, // Fondamentale per aggiornare la UI durante il timer
    private snackBar: MatSnackBar
  ) {}

  ngOnInit() {}

  // Pulizia timer se il componente viene distrutto
  ngOnDestroy() {
      if (this.progressInterval) clearInterval(this.progressInterval);
  }

  toggleSource(sourceName: string, isChecked: boolean) {
    if (isChecked) {
      if (!this.settings.sources.includes(sourceName)) {
        this.settings.sources.push(sourceName);
      }
    } else {
      if (this.settings.sources.length > 1) {
        this.settings.sources = this.settings.sources.filter(s => s !== sourceName);
      } else {
        this.showNotification("Seleziona almeno una fonte!", "info");
        setTimeout(() => {
             this.settings.sources = [...this.settings.sources];
             this.cdr.detectChanges();
        }, 0);
      }
    }
    this.calculateTime();
  }

  isSourceSelected(sourceName: string): boolean {
    return this.settings.sources.includes(sourceName);
  }

  changeTemplate() {
      this.viewMode = 'template-selection';
  }

  selectTemplate(template: PromptTemplate) {
      this.selectedTemplateId = template.id;
      this.selectedTemplateName = template.name;
      this.settings.system_prompt = template.content;
      
      if (this.selectedTemplateId === 'financial-controller') {
          this.displayedSources = ALL_SOURCES.filter(s => s.category === 'Financial');
          this.displayedColumns = this.financialColumns;
          this.settings.sources = [SourceType.SPACENEWS];
      } else if (this.selectedTemplateId === 'technical-controller') {
          this.displayedSources = ALL_SOURCES.filter(s => s.category === 'Technical');
          this.displayedColumns = this.technicalColumns;
          this.settings.sources = [SourceType.VIA_SATELLITE];
      } else {
          this.displayedSources = ALL_SOURCES;
          this.displayedColumns = this.financialColumns;
          this.settings.sources = [SourceType.SPACENEWS];
      }

      this.calculateTime();
      this.viewMode = 'dashboard';
  }

  calculateTime() {
    const totalSecs = this.settings.max_pages * 10 * this.settings.sources.length; 
    const mins = Math.floor(totalSecs / 60);
    this.estimatedTime = mins > 0 ? `${mins} min ${totalSecs % 60} sec` : `${totalSecs} sec`;
  }

  // --- LOGICA DI CARICAMENTO E PROGRESSO SIMULATO ---
  startAnalysis() {
    if (!this.settings.api_key || this.settings.api_key.trim() === '') {
      this.showNotification("ERRORE: Devi inserire una Mistral API Key!", "error");
      return; 
    }
    
    this.isRunning = true;
    this.progressValue = 0; 
    this.statusMessage = `Avvio analisi (${this.selectedTemplateName})...`;
    this.allDeals = []; 
    this.filteredDeals = []; 

    // AVVIO SIMULAZIONE PROGRESSO
    // Poiché il backend non invia aggiornamenti parziali, simuliamo l'avanzamento
    // per dare feedback visivo all'utente.
    if (this.progressInterval) clearInterval(this.progressInterval);
    
    this.progressInterval = setInterval(() => {
        // Incrementa lentamente fino al 90%, poi aspetta
        if (this.progressValue < 90) {
            // Incremento variabile per sembrare "naturale"
            const increment = Math.random() * 2; 
            this.progressValue += increment;
            
            // Aggiorna messaggi in base alla % per renderlo vivo
            if (this.progressValue > 20 && this.progressValue < 40) this.statusMessage = "Scaricamento dati dalle fonti...";
            if (this.progressValue > 40 && this.progressValue < 70) this.statusMessage = "Analisi AI in corso...";
            if (this.progressValue > 70) this.statusMessage = "Finalizzazione risultati...";
            
            // IMPORTANTE: Forza l'aggiornamento della UI
            this.cdr.detectChanges();
        }
    }, 800); // Ogni 800ms
    
    // CHIAMATA API REALE
    this.api.startScrape(this.settings).subscribe({
      next: (results) => {
        // Quando arriva la risposta, fermiamo il timer e andiamo al 100%
        clearInterval(this.progressInterval);
        this.progressValue = 100;
        this.statusMessage = 'Elaborazione completata!';
        
        this.allDeals = results;
        this.allDeals.sort((a, b) => {
            const dateA = a.published_date ? new Date(a.published_date).getTime() : 0;
            const dateB = b.published_date ? new Date(b.published_date).getTime() : 0;
            return dateB - dateA;
        });
        this.applyFilter('ALL');
        this.cdr.detectChanges();
        
        // Piccolo delay per far vedere il 100% pieno prima di nascondere la barra
        setTimeout(() => {
            this.isRunning = false;
            this.cdr.detectChanges();
            
            if (results.length > 0) this.showNotification(`Analisi completata: trovati ${results.length} risultati.`, "success");
            else this.showNotification("Nessun risultato trovato.", "info");
        }, 800);
      },
      error: (err) => {
        clearInterval(this.progressInterval);
        console.error(err);
        this.progressValue = 0;
        
        setTimeout(() => {
            this.isRunning = false;
            this.statusMessage = 'Errore';
            this.showNotification("Errore durante l'analisi. Controlla la console.", "error");
            this.cdr.detectChanges();
        }, 500);
      }
    });
  }

  applyFilter(type: string) {
      this.selectedType = type;
      if (type === 'ALL') {
          this.filteredDeals = [...this.allDeals];
      } else {
          this.filteredDeals = this.allDeals.filter(d => 
              (d.deal_type && d.deal_type.toLowerCase().includes(type.toLowerCase())) ||
              (d.mission_type && d.mission_type.toLowerCase().includes(type.toLowerCase()))
          );
      }
  }

  // --- NEW EXPORT FUNCTION: EXPORT TO EXCEL ---
  exportToExcel() {
    if (this.allDeals.length === 0) {
      this.showNotification("Nessun dato da esportare.", "info");
      return;
    }

    // Precise mapping of the requested columns
    // We use 'any' to avoid type errors if the backend returns null fields
    const dataToExport = this.allDeals.map((deal: any) => ({
      source: deal.source,
      url: deal.url,
      title: deal.title,
      published_date: deal.published_date,
      section: deal.section || '',
      is_relevant: deal.is_relevant ? 'Yes' : 'No',
      relevance_score: deal.relevance_score,
      deal_type: deal.deal_type,
      deal_status: deal.deal_status,
      // acquirer: this.formatData(deal.acquirer),
      // target: this.formatData(deal.target),
      investors: this.formatData(deal.investors),
      amount: deal.amount,
      currency: deal.currency,
      // valuation: deal.valuation,
      stake_percent: deal.stake_percent,
      key_assets: this.formatData(deal.key_assets),
      geography: this.formatData(deal.geography),
      summary: deal.summary,
      why_it_matters: deal.why_it_matters,
      entities: this.formatData(deal.entities)
    }));

    // Create Workbook and Worksheet
    const ws: XLSX.WorkSheet = XLSX.utils.json_to_sheet(dataToExport);
    const wb: XLSX.WorkBook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Deals');

    // Generate file name with timestamp
    const timestamp = new Date().toISOString().slice(0,19).replace(/:/g, "-");
    const fileName = `SpaceScraper_Results_${timestamp}.xlsx`;

    // Download
    XLSX.writeFile(wb, fileName);
    this.showNotification("File Excel scaricato correttamente!", "success");
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
        if (input.amount && input.currency) return `${input.amount} ${input.currency}`;
        const firstVal = Object.values(input).find(v => typeof v === 'string');
        return (firstVal as string) || JSON.stringify(input);
    }
    return String(input);
  }

  private showNotification(message: string, type: 'success' | 'error' | 'info') {
      this.snackBar.open(message, 'Chiudi', { duration: 4000, panelClass: type === 'error' ? ['mat-toolbar', 'mat-warn'] : undefined });
  }
}
// --- ENUMS E COSTANTI ---

// Lista delle fonti disponibili (deve coincidere con il Backend)
export enum SourceType {
  // Financial Controller
  SPACENEWS = "SpaceNews",
  SNAPI = "SNAPI",
  SPACEWORKS = "SpaceWorks",
  EURO_SPACEFLIGHT = "European Spaceflight",
  
  // Technical Controller
  VIA_SATELLITE = "Via Satellite",
  NASA_TECHPORT = "NASA TechPort"
}

// --- MODELLO DEI DATI (Output AI) ---
export interface Deal {
  // Metadati di base
  source: string;
  url: string;
  title: string;
  published_date: string;
  section?: string; 

  // Metadati AI
  is_relevant: boolean;
  relevance_score?: any;
  summary?: string;
  why_it_matters?: string;

  // Dettagli Deal (Financial Controller)
  deal_type?: string;
  deal_status?: string;
  acquirer?: any;
  target?: any;
  investors?: any;
  amount?: any;
  currency?: string;
  valuation?: any;
  stake_percent?: any;
  key_assets?: any;
  geography?: any;
  
  // Dettagli Tecnici (Technical Controller - NUOVI)
  technology_readiness_level?: string; // TRL
  mission_type?: string;
  orbit?: string; // LEO, GEO, MEO
  payload_capacity?: string;
  
  // Entità coinvolte
  entities?: any[];
}

// --- CONFIGURAZIONE (Input Utente) ---
export interface ScrapeSettings {
  target_companies: string;
  
  // MODIFICA CRITICA: Ora accettiamo un array di fonti multiple
  sources: string[]; // Esempio: ["SpaceNews", "NASA TechPort"]
  
  ai_model: string;
  api_key: string;
  system_prompt: string;
  min_year: number;
  max_pages: number;
  force_rescan?: boolean;
}

// --- LOGGING (Compatibilità Legacy) ---
export interface LogEntry {
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
}

// --- STATO DEL SISTEMA (Polling) ---
export interface ScrapeStatus {
  is_running: boolean;
  total_articles: number;
  processed_articles: number;
  current_status: string;
  logs: LogEntry[];
  last_update: string; 
  
  // Campi asincroni
  task_id?: string;
  status?: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE';
  result?: Deal[];
  error?: string;
}

// Interfaccia per la risposta iniziale del backend
export interface TaskResponse {
    task_id: string;
    status: string;
    message?: string;
}
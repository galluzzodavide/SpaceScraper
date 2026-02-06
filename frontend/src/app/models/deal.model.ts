export interface Deal {
  source: string;
  url: string;
  title: string;
  published_date: string;
  // ... campi opzionali ...
  is_relevant: boolean;
  relevance_score?: any;
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
  summary?: string;
  why_it_matters?: string;
  entities: any[];
}

export interface ScrapeSettings {
    target_companies: string;
    source: string;
    ai_model: string;
    api_key: string;
    system_prompt: string;
    min_year: number;
    max_pages: number;
}

export interface LogEntry {
    timestamp: string;
    message: string;
    type: 'info' | 'success' | 'warning' | 'error';
}

export interface ScrapeStatus {
  is_running: boolean;
  total_articles: number;
  processed_articles: number;
  current_status: string;
  logs: LogEntry[];
  last_update: string; 
}
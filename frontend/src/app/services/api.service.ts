import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, timer, throwError, of } from 'rxjs';
import { switchMap, map, takeWhile, catchError, filter, take } from 'rxjs/operators';
import { Deal, ScrapeSettings } from '../models/deal.model';

// --- 1. IMPORTA IL DATASERVICE CHE ABBIAMO CREATO ---
import { DataService } from './data.service'; // Assicurati che il percorso sia giusto

export interface TaskResponse {
  task_id: string;
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE';
  result?: Deal[]; 
  error?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://127.0.0.1:8000/api';

  constructor(
    private http: HttpClient,
    private dataService: DataService // --- 2. INIETTA IL SERVIZIO QUI ---
  ) { }

  /**
   * 1. Invia la richiesta di scraping.
   * 2. Riceve un task_id.
   * 3. Inizia automaticamente a fare polling.
   * 4. Restituisce i risultati finali.
   */
  startScrape(settings: ScrapeSettings): Observable<Deal[]> {
    
    // --- 3. LA MAGIA AVVIENE QUI! ---
    // Appena viene chiamato startScrape, avvisiamo la Heatmap di ricaricarsi 
    // usando i target che l'utente ha inserito nei settings.
    if (settings && settings.target_companies) {
      console.log(`[ApiService] Avviso la Heatmap di cercare: ${settings.target_companies}`);
      this.dataService.updateTargets(settings.target_companies);
    }
    // --------------------------------

    return this.http.post<TaskResponse>(`${this.baseUrl}/start-scrape`, settings).pipe(
      switchMap(initialResponse => {
        console.log(`[ApiService] Task avviato: ${initialResponse.task_id}`);
        return this.pollTask(initialResponse.task_id);
      }),
      catchError(err => {
        console.error("[ApiService] Errore avvio:", err);
        return throwError(() => new Error("Impossibile contattare il server Cloud."));
      })
    );
  }

  // ... (Tutto il resto del file pollTask, getStatus, getResults rimane identico) ...
  private pollTask(taskId: string): Observable<Deal[]> {
    return timer(0, 2000).pipe(
      switchMap(() => this.http.get<TaskResponse>(`${this.baseUrl}/tasks/${taskId}`)),
      takeWhile(res => {
        const isRunning = res.status !== 'SUCCESS' && res.status !== 'FAILURE';
        if (isRunning) {
            console.log(`[Polling] Task ${taskId} in corso... (${res.status})`);
        }
        return isRunning;
      }, true),
      filter(res => res.status === 'SUCCESS' || res.status === 'FAILURE'),
      switchMap(res => {
        if (res.status === 'SUCCESS') {
          console.log(`[Polling] Task ${taskId} completato!`);
          
          // OPZIONALE: Se vuoi ricaricare la Heatmap anche alla FINE dello scraping 
          // per mostrare i nuovissimi dati appena scaricati:
          // this.dataService.updateTargets(settings.target_companies);
          
          return of(res.result || []); 
        } else {
          console.error(`[Polling] Task ${taskId} fallito:`, res.error);
          return throwError(() => new Error(res.error || 'Errore sconosciuto durante lo scraping'));
        }
      })
    );
  }

  getStatus(): Observable<any> {
    return this.http.get(`${this.baseUrl}/status`);
  }

  getResults(): Observable<Deal[]> {
    return this.http.get<Deal[]>(`${this.baseUrl}/results`);
  }
}
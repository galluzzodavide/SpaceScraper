import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, timer, throwError, of } from 'rxjs';
import { switchMap, map, takeWhile, catchError, filter, take } from 'rxjs/operators';
import { Deal, ScrapeSettings } from '../models/deal.model';

// Interfaccia per la risposta del Backend (il "Ticket")
export interface TaskResponse {
  task_id: string;
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE';
  result?: Deal[]; // I dati veri arrivano solo se status == SUCCESS
  error?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  // Assicurati che la porta sia quella corretta del tuo backend FastAPI (es. 8000)
  private baseUrl = 'http://127.0.0.1:8000/api';

  constructor(private http: HttpClient) { }

  /**
   * 1. Invia la richiesta di scraping.
   * 2. Riceve un task_id.
   * 3. Inizia automaticamente a fare polling (chiedere lo stato).
   * 4. Restituisce i risultati finali quando pronti.
   */
  startScrape(settings: ScrapeSettings): Observable<Deal[]> {
    return this.http.post<TaskResponse>(`${this.baseUrl}/start-scrape`, settings).pipe(
      switchMap(initialResponse => {
        // Abbiamo il task_id, ora iniziamo a monitorarlo
        console.log(`[ApiService] Task avviato: ${initialResponse.task_id}`);
        return this.pollTask(initialResponse.task_id);
      }),
      catchError(err => {
        console.error("[ApiService] Errore avvio:", err);
        return throwError(() => new Error("Impossibile contattare il server Cloud."));
      })
    );
  }

  /**
   * Logica di Polling intelligente con RxJS.
   * Controlla lo stato ogni 2 secondi (2000ms).
   */
  private pollTask(taskId: string): Observable<Deal[]> {
    return timer(0, 2000).pipe(
      // 1. Chiede lo stato al backend
      switchMap(() => this.http.get<TaskResponse>(`${this.baseUrl}/tasks/${taskId}`)),
      
      // 2. Continua a chiedere finché lo stato NON è finito (SUCCESS o FAILURE)
      takeWhile(res => {
        const isRunning = res.status !== 'SUCCESS' && res.status !== 'FAILURE';
        if (isRunning) {
            console.log(`[Polling] Task ${taskId} in corso... (${res.status})`);
        }
        return isRunning;
      }, true), // 'true' include l'ultimo valore (quello di successo o errore) nel flusso

      // 3. Filtra solo quando è finito (ignora i messaggi "PENDING" intermedi)
      filter(res => res.status === 'SUCCESS' || res.status === 'FAILURE'),

      // 4. Gestisce il risultato finale
      switchMap(res => {
        if (res.status === 'SUCCESS') {
          console.log(`[Polling] Task ${taskId} completato!`);
          return of(res.result || []); // Restituisce l'array di Deal
        } else {
          console.error(`[Polling] Task ${taskId} fallito:`, res.error);
          return throwError(() => new Error(res.error || 'Errore sconosciuto durante lo scraping'));
        }
      })
    );
  }

  // --- Metodi Legacy (opzionali, se servono per debug) ---
  
  getStatus(): Observable<any> {
    return this.http.get(`${this.baseUrl}/status`);
  }

  getResults(): Observable<Deal[]> {
    return this.http.get<Deal[]>(`${this.baseUrl}/results`);
  }
}
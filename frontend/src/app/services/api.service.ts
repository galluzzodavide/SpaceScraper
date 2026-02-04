import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Deal, ScrapeSettings, ScrapeStatus } from '../models/deal.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private baseUrl = 'http://127.0.0.1:8000/api';

  constructor(private http: HttpClient) { }

  startScrape(settings: ScrapeSettings): Observable<any> {
    return this.http.post(`${this.baseUrl}/start-scrape`, settings);
  }

  getStatus(): Observable<ScrapeStatus> {
    return this.http.get<ScrapeStatus>(`${this.baseUrl}/status`);
  }

  getResults(): Observable<Deal[]> {
    return this.http.get<Deal[]>(`${this.baseUrl}/results`);
  }
}
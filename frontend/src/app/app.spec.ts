import { TestBed } from '@angular/core/testing';
import { AppComponent } from './app'; // <--- CORRETTO: La classe si chiama App, non AppComponent
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { RouterTestingModule } from '@angular/router/testing'; // <--- FONDAMENTALE per <router-outlet>
import { MatDividerModule } from '@angular/material/divider';
import { MatSnackBarModule } from '@angular/material/snack-bar';

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        AppComponent,                     // Il tuo componente Standalone
        HttpClientTestingModule, // Mock per le chiamate HTTP (anche quelle della Heatmap!)
        NoopAnimationsModule,    // Disabilita animazioni
        RouterTestingModule,
        MatDividerModule,         // Necessario per <mat-divider>
        MatSnackBarModule         // Necessario per le notifiche (MatSnackBar)      // Gestisce il routing nei test
      ],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the correct title in toolbar', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges(); 
    const compiled = fixture.nativeElement as HTMLElement;
    
    // Verifica il titolo nella toolbar
    const toolbarText = compiled.querySelector('.main-toolbar span')?.textContent;
    expect(toolbarText).toContain('SpaceScraper Deal Intelligence');
  });

  it('should have correct default AI model configured', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    
    // Verifica il modello (assicurati che corrisponda al default in app.ts)
    // Se hai cambiato il default in app.ts, aggiorna anche questa stringa!
    expect(app.settings.ai_model).toContain('mistral-large-latest'); 
  });
});
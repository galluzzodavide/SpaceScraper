import { TestBed } from '@angular/core/testing';
import { AppComponent } from './app';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MatDividerModule } from '@angular/material/divider';
import { MatSnackBarModule } from '@angular/material/snack-bar';

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        AppComponent,             // Il tuo componente Standalone
        HttpClientTestingModule,  // Mock per le chiamate HTTP (evita errori ApiService)
        NoopAnimationsModule,     // Gestisce le animazioni di Angular Material nei test
        MatDividerModule,         // Necessario per <mat-divider>
        MatSnackBarModule         // Necessario per le notifiche (MatSnackBar)
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
    fixture.detectChanges(); // Scatena l'aggiornamento dell'HTML
    const compiled = fixture.nativeElement as HTMLElement;
    
    // Cerchiamo il testo dentro la toolbar
    const toolbarText = compiled.querySelector('.main-toolbar span')?.textContent;
    expect(toolbarText).toContain('SpaceScraper Deal Intelligence');
  });

  it('should have correct default AI model configured', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    
    // Verifica che il default sia impostato sul nuovo modello Groq Llama 3.3
    expect(app.settings.ai_model).toBe('groq/llama-3.3-70b-versatile');
  });
});
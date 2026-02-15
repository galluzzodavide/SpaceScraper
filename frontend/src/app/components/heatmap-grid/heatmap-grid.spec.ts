import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing'; // <--- IMPORT FONDAMENTALE
import { HeatmapGrid } from './heatmap-grid';

describe('HeatmapGrid', () => {
  let component: HeatmapGrid;
  let fixture: ComponentFixture<HeatmapGrid>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        HeatmapGrid, 
        HttpClientTestingModule // <--- AGGIUNGI QUESTO
      ] 
    })
    .compileComponents();

    fixture = TestBed.createComponent(HeatmapGrid);
    component = fixture.componentInstance;
    
    // Rileva i cambiamenti (fa partire ngOnInit)
    fixture.detectChanges(); 
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
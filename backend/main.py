# backend/main.py
import os
import json
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import DealData, ScrapeResponse
from .scraper_service import SpaceScraperService

# Inizializzazione App
app = FastAPI(title="SpaceNews Scraper API")

# Configurazione CORS (Cruciale per sviluppo Angular locale)
# Permette al frontend su localhost:4200 di chiamare localhost:8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In prod, restringi a "http://localhost:4200" o simili
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurazione Service
API_KEY = os.getenv("MISTRAL_API_KEY")
service = SpaceScraperService(api_key=API_KEY)

# Database "File-based" semplice per iniziare
DB_FILE = "db_deals.json"

def load_db() -> List[DealData]:
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        return [DealData(**d) for d in data]

def save_db(deals: List[DealData]):
    # Carica esistenti per non sovrascrivere
    existing = load_db()
    
    # Creiamo un dict per deduplicare tramite URL
    merged = {d.url: d for d in existing} 
    for new_d in deals:
        merged[new_d.url] = new_d
    
    final_list = list(merged.values())
    
    # Convertiamo i modelli Pydantic in dict per JSON
    with open(DB_FILE, "w", encoding="utf-8") as f:
        # model_dump() è il metodo Pydantic v2 (usa .dict() se v1)
        json.dump([d.model_dump() for d in final_list], f, indent=2, default=str)

@app.get("/api/deals", response_model=List[DealData])
def get_deals():
    """Restituisce tutti i deal salvati nel database locale."""
    return load_db()

@app.post("/api/scrape", response_model=ScrapeResponse)
def start_scraping():
    """
    Avvia lo scraping. 
    NOTA: In una app desktop reale con PySide, questo blocca il thread 
    del server se non gestito. Tuttavia, dato che PySide eseguirà FastAPI 
    in un thread separato, l'interfaccia non si bloccherà, ma questa chiamata 
    HTTP aspetterà finché lo scraping non è finito.
    """
    if not API_KEY:
        raise HTTPException(status_code=500, detail="MISTRAL_API_KEY not set on server.")

    print("Starting scraping pipeline...")
    
    try:
        # Avvia il servizio
        new_deals = service.run_pipeline()
        
        # Salva nel DB locale
        save_db(new_deals)
        
        return ScrapeResponse(
            status="completed",
            total_found=0, # Da implementare meglio col tracking
            processed=0,
            new_deals=len(new_deals),
            message="Scraping completed successfully"
        )
    except Exception as e:
        print(f"Scraping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Per avviare il server standalone per test:
# uvicorn backend.main:app --reload
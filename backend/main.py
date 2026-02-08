import logging
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from dotenv import load_dotenv

# Importa i modelli e il servizio
from .models import DealData, ScrapeSettings, ScrapeStatus
from .scraper_service import SpaceScraperService, current_status

load_dotenv()

# --- FILTRO LOG PER ZITTIRE IL POLLING (CORRETTO) ---
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        # Filtriamo ENTRAMBI gli endpoint di polling per sicurezza
        return "/api/status" not in message and "/api/results" not in message

# --- APPLICAZIONE IMMEDIATA (FUORI DA STARTUP) ---
# Lo facciamo qui, a livello globale, per essere sicuri che Uvicorn lo recepisca subito
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

app = FastAPI()

# Rimosso startup_event inutile per il logging

# Configurazione CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

last_results = []

def run_scraper_task(settings: ScrapeSettings):
    global last_results
    try:
        service = SpaceScraperService(settings)
        last_results = service.scrape()
    except Exception as e:
        print(f"Errore critico task: {e}")
        current_status["is_running"] = False
        current_status["message"] = f"Error: {str(e)}"
        if "logs" in current_status:
             current_status["logs"].insert(0, {
                 "timestamp": "", 
                 "message": f"Critical Error: {str(e)}", 
                 "type": "error"
             })

@app.post("/api/start-scrape")
async def start_scrape(settings: ScrapeSettings, background_tasks: BackgroundTasks):
    if current_status["is_running"]:
        return {"message": "Scraper is already running"}
    
    global last_results
    last_results = [] 
    
    background_tasks.add_task(run_scraper_task, settings)
    return {"message": "Scraper started successfully"}

@app.get("/api/status", response_model=ScrapeStatus)
async def get_status():
    return {
        "is_running": current_status["is_running"],
        "total_articles": current_status["total"],
        "processed_articles": current_status["processed"],
        "current_status": current_status["message"],
        "last_update": current_status["last_update"],
        "logs": current_status.get("logs", []) 
    }

@app.get("/api/results", response_model=List[DealData])
async def get_results():
    return last_results

@app.get("/")
def read_root():
    return {"status": "SpaceScraper Backend Ready"}
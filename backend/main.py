import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from celery.result import AsyncResult

# FIX IMPORT: USIAMO IMPORT ASSOLUTI
from models import ScrapeSettings
from worker import execute_scrape_task
from database import engine, Base

load_dotenv()

# --- 0. INIZIALIZZAZIONE DATABASE ---
# Crea le tabelle automaticamente se non esistono.
# NOTA: Poiché abbiamo modificato i modelli, se la tabella esiste già 
# potrebbe non aggiornarsi automaticamente senza cancellare il volume (che hai già fatto).
Base.metadata.create_all(bind=engine)

# --- 1. FILTRO LOG ---
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "/api/tasks" not in message and "/api/results" not in message

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

app = FastAPI()

# --- 2. CONFIGURAZIONE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "SpaceScraper Distributed Backend Ready"}

# --- 3. ENDPOINT: AVVIO TASK (PRODUCER) ---
@app.post("/api/start-scrape")
async def start_scrape(settings: ScrapeSettings):
    """
    Riceve la richiesta con LE MULTIPLE SORGENTI, la valida e la invia alla coda Redis.
    """
    try:
        # --- MODIFICA FONDAMENTALE ---
        # mode='json' converte gli Enum (es. SourceType.SPACENEWS) in stringhe ("SpaceNews")
        # Questo è necessario perché Celery/Redis accettano solo tipi semplici (JSON).
        settings_dict = settings.model_dump(mode='json')
        
        # Debug: Stampa cosa stiamo mandando al worker
        print(f"[Backend] Dispatching task with sources: {settings_dict.get('sources')}")

        # Lanciamo il task asincrono
        task = execute_scrape_task.delay(settings_dict)
        
        return {
            "task_id": task.id, 
            "status": "Accepted", 
            "message": "Task inviato al worker cluster"
        }
    except Exception as e:
        print(f"Errore dispatch task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 4. ENDPOINT: CONTROLLO STATO (POLLING) ---
@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    task_result = AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": task_result.status,
        "result": None
    }

    if task_result.ready():
        if task_result.successful():
            response["result"] = task_result.result
            response["status"] = "SUCCESS"
        else:
            response["status"] = "FAILURE"
            response["error"] = str(task_result.result)
    
    return response
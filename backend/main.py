import logging
from fastapi import FastAPI, Depends, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from celery.result import AsyncResult
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# --- IMPORT INTERNI ---
from models import ScrapeSettings, DealModel
from worker import execute_scrape_task
from database import engine, Base, get_db

load_dotenv()

# --- 0. INIZIALIZZAZIONE DATABASE ---
# Crea le tabelle automaticamente se non esistono.
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
        # mode='json' converte gli Enum in stringhe per Celery
        settings_dict = settings.model_dump(mode='json')
        
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

@app.get("/api/dashboard/heatmap")
def get_heatmap_data(db: Session = Depends(get_db)):
    """
    Genera i dati per la Heatmap.
    Target FISSI definiti a mano. Usa il 'Tagging alla Sorgente' (search_target)
    effettuando il filtro direttamente nel database per la massima velocità.
    """
    # 1. DEFINIAMO I TARGET FISSI
    user_targets = ["ICEYE", "CONSTELLR"]

    # 2. FACCIAMO LAVORARE IL DATABASE
    # Usiamo .in_() per dire a SQL: WHERE search_target IN ('ICEYE', 'CONSTELLR')
    valid_deals = db.query(DealModel).filter(
        DealModel.is_relevant == True,
        DealModel.search_target.in_(user_targets)
    ).order_by(DealModel.published_date.desc()).all()

    company_stats = {}

    # 3. RAGGRUPPIAMO E CALCOLIAMO I PUNTEGGI
    for deal in valid_deals:
        # Il nome lo prendiamo direttamente dall'etichetta esatta
        name = deal.search_target 
        payload = deal.analysis_payload if deal.analysis_payload else {}

        if name not in company_stats:
            company_stats[name] = {
                "score": 0.0,
                "count": 0,
                "latest_news": deal.title,
                "latest_date": deal.published_date
            }
        
        relevance = float(payload.get("relevance_score", 0.5))
        amount = float(payload.get("amount", 0))
        
        deal_points = relevance * 3.0 
        if amount > 1_000_000:
            deal_points += 2.0 
        
        company_stats[name]["score"] += deal_points
        company_stats[name]["count"] += 1
        
        # Mantiene in memoria la notizia più recente
        if deal.published_date and deal.published_date > company_stats[name]["latest_date"]:
            company_stats[name]["latest_news"] = deal.title
            company_stats[name]["latest_date"] = deal.published_date

    # 4. FORMATTAZIONE PER ANGULAR
    results = []
    for name, data in company_stats.items():
        results.append({
            "name": name, # Sarà esattamente "ICEYE" o "CONSTELLR"
            "score": round(data["score"], 1),
            "articles_count": data["count"],
            "latest_news": data["latest_news"]
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:25]

@app.get("/api/deals")
def get_historical_deals(limit: int = 100, db: Session = Depends(get_db)):
    """
    Restituisce gli ultimi N deal salvati nel DB per popolare la tabella.
    Mappa correttamente i campi del FINANCIAL_SCHEMA_DEF.
    """
    deals = db.query(DealModel).filter(
        DealModel.is_relevant == True
    ).order_by(DealModel.published_date.desc()).limit(limit).all()

    print(f"[BACKEND] Caricamento storico: trovati {len(deals)} deal.")
    
    results = []
    for d in deals:
        payload = d.analysis_payload if d.analysis_payload else {}
        
        item = {
            "id": d.id,
            "url": d.url,
            "title": d.title,
            "source": d.source,
            "published_date": d.published_date,
            "relevance_score": payload.get("relevance_score", 0),
            "deal_type": payload.get("deal_type", "N/A"),
            "deal_status": payload.get("deal_status", "N/A"),
            "amount": payload.get("amount", 0),
            "currency": payload.get("currency", "USD"),
            "investors": payload.get("investors", []),
            "stake_percent": payload.get("stake_percent", 0),
            "why_it_matters": payload.get("why_it_matters", ""),
            "summary": payload.get("summary", ""),
            "technology_readiness_level": payload.get("technology_readiness_level", ""),
            "mission_type": payload.get("mission_type", ""),
            "key_assets": payload.get("key_assets", "")
        }
        results.append(item)
        
    return results
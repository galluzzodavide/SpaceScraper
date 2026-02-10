import os
from celery import Celery

# --- FIX IMPORT: ASSOLUTI (NO PUNTI) ---
from models import ScrapeSettings
from scraper_service import SpaceScraperService

# Recuperiamo le URL di connessione
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery_app = Celery(
    "space_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

# --- TUNING PRODUZIONE ---
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_time_limit=600, 
    task_acks_late=True,
)

@celery_app.task(bind=True, name="execute_scrape_task", time_limit=3600, soft_time_limit=3600)
def execute_scrape_task(self, settings_dict: dict):
    """
    Riceve il dizionario JSON, lo riconverte in oggetto Pydantic (gestendo gli Enum)
    e lancia il servizio di scraping multi-sorgente.
    """
    try:
        # 1. Ricostruzione Oggetto Pydantic
        # Pydantic è intelligente: se 'settings_dict' contiene stringhe per le fonti (es. "SpaceNews"),
        # le convertirà automaticamente negli Enum corretti (SourceType.SPACENEWS).
        settings = ScrapeSettings(**settings_dict)
        
        # 2. Logging Avanzato (Mostra le fonti attive)
        # Estraiamo i valori leggibili dagli Enum per il log
        active_sources = [s.value for s in settings.sources]
        print(f"[Worker] Avvio task: {settings.target_companies}")
        print(f"[Worker] Fonti attive: {active_sources}")

        # 3. Esecuzione Service (Pattern Adapter)
        service = SpaceScraperService(settings)
        results = service.scrape()
        
        print(f"[Worker] Task completato. Trovati {len(results)} risultati totali.")
        return results

    except Exception as e:
        print(f"[Worker] ERRORE CRITICO: {str(e)}")
        raise e
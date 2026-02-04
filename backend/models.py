from pydantic import BaseModel
from typing import List, Optional, Any, Union

# --- MODELLO FLESSIBILE PER I DATI DEAL ---
# Usiamo 'Any' o 'Union' per evitare crash se l'IA manda numeri, liste o dizionari
class DealData(BaseModel):
    source: Optional[str] = "SpaceNews"
    url: Optional[str] = ""
    title: Optional[str] = ""
    published_date: Optional[str] = None
    section: Optional[str] = ""
    
    is_relevant: bool = False
    deal_type: Optional[str] = "none"
    deal_status: Optional[str] = "unknown"
    
    # Campi che possono essere stringhe O liste O oggetti
    acquirer: Optional[Any] = None
    target: Optional[Any] = None
    investors: Optional[Any] = None
    
    # Amount/Valuation possono essere stringhe ("$10M") o numeri (10000000)
    amount: Optional[Union[str, int, float]] = None
    currency: Optional[str] = None
    valuation: Optional[Union[str, int, float]] = None
    stake_percent: Optional[Union[str, int, float]] = None
    
    key_assets: Optional[Any] = None
    geography: Optional[Any] = None
    
    summary: Optional[str] = None
    why_it_matters: Optional[str] = None
    
    # Entities spesso arriva come lista di oggetti complessi
    entities: Optional[List[Any]] = []

# --- SETTINGS ---
class ScrapeSettings(BaseModel):
    target_companies: str
    source: str = "SpaceNews"
    ai_model: str = "mistral-large-latest"
    api_key: Optional[str] = "" 
    system_prompt: str
    min_year: int = 2020
    max_pages: int = 1

# --- LOGGING PER IL LIVE FEED ---
class LogEntry(BaseModel):
    timestamp: str
    message: str
    type: str  # 'info', 'success', 'warning', 'error'

# --- STATO DEL SISTEMA ---
class ScrapeStatus(BaseModel):
    is_running: bool
    total_articles: int
    processed_articles: int
    current_status: str
    last_update: str
    # Questa lista serve per il feed nel frontend!
    logs: List[LogEntry] = []
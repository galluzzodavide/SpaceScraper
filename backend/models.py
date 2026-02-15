from typing import List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

# --- IMPORTS PER DATABASE (SQLAlchemy) ---
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base

# ==========================================
# 0. ENUMS (Fondamentali per la separazione delle fonti)
# ==========================================
class SourceCategory(str, Enum):
    FINANCIAL = "financial"
    TECHNICAL = "technical"

class SourceType(str, Enum):
    # Financial Controller Providers
    SPACENEWS = "SpaceNews"
    SNAPI = "SNAPI"
    SPACEWORKS = "SpaceWorks"
    EURO_SPACEFLIGHT = "European Spaceflight"
    
    # Technical Controller Providers
    VIA_SATELLITE = "Via Satellite"
    NASA_TECHPORT = "NASA TechPort"

# ==========================================
# 1. MODELLO DATABASE (Tabella SQL)
# ==========================================
class DealModel(Base):
    """
    Questa classe definisce la tabella 'deals' nel database PostgreSQL.
    """
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    
    # Metadati per query veloci e indicizzazione
    url = Column(String, unique=True, index=True)
    source = Column(String, nullable=False)
    
    # Categoria per filtrare (es. mostrare solo dati Tecnici o Finanziari)
    source_category = Column(String, default="financial") 
    
    title = Column(String)
    published_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Flag di stato rapido
    is_relevant = Column(Boolean, default=False)

    # input esatto dell'utente (es. "ICEYE")
    search_target = Column(String, index=True, nullable=True)
    
    # --- IL CUORE IBRIDO: JSONB ---
    analysis_payload = Column(JSONB, nullable=False)


# ==========================================
# 2. MODELLI DATI (Pydantic - Validazione)
# ==========================================

# --- DATI DEAL FLESSIBILI (Output AI -> Frontend) ---
class DealData(BaseModel):
    source: Optional[str] = None
    url: Optional[str] = ""
    title: Optional[str] = ""
    published_date: Optional[str] = None
    section: Optional[str] = ""
    
    is_relevant: bool = False
    relevance_score: Optional[Union[float, str]] = None
    
    # --- CAMPI FINANZIARI (Financial Controller) ---
    deal_type: Optional[str] = "none"
    deal_status: Optional[str] = "unknown"
    acquirer: Optional[Any] = None
    target: Optional[Any] = None
    investors: Optional[List[str]] = []
    amount: Optional[Union[str, int, float]] = None
    currency: Optional[str] = "USD"
    valuation: Optional[Union[str, int, float]] = None
    stake_percent: Optional[Union[str, int, float]] = None
    key_assets: Optional[Any] = None
    geography: Optional[Any] = None

    
    # --- CAMPI TECNICI (Technical Controller) ---
    technology_readiness_level: Optional[str] = None # TRL (per NASA)
    mission_type: Optional[str] = None
    orbit: Optional[str] = None # LEO, GEO, MEO
    payload_capacity: Optional[str] = None
    
    # Campi Comuni
    summary: Optional[str] = None
    why_it_matters: Optional[str] = None
    entities: Optional[List[Any]] = []
    
    class Config:
        extra = "allow" 

# --- CONFIGURAZIONE SCRAPER (Input Utente) ---
class ScrapeSettings(BaseModel):
    target_companies: str
    
    # Supporto a multiple sorgenti
    sources: List[SourceType] = [SourceType.SPACENEWS] 
    
    ai_model: str = "mistral-large-latest"
    api_key: Optional[str] = "" 
    system_prompt: Optional[str] = ""
    min_year: int = 2024
    max_pages: int = 1
    
    # Opzionale: per forzare la riscrittura se l'URL esiste già nel DB
    force_rescan: bool = False

# --- LOGGING E STATO ---
class LogEntry(BaseModel):
    timestamp: str
    message: str
    type: str  # 'info', 'success', 'warning', 'error'

class ScrapeStatus(BaseModel):
    task_id: Optional[str] = None
    is_running: bool
    total_articles: int
    processed_articles: int
    current_status: str
    last_update: str
    logs: List[LogEntry] = []
    result: Optional[List[Any]] = None
    error: Optional[str] = None
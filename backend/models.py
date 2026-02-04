# backend/models.py
from typing import List, Optional
from pydantic import BaseModel

class DealData(BaseModel):
    """
    Modello che rappresenta un singolo deal/articolo processato.
    Include sia i metadati dello scraping che i dati estratti dall'LLM.
    """
    # Metadati scraping
    source: str = "SpaceNews"
    url: str
    title: str
    published_date: str
    section: Optional[str] = None

    # Dati LLM (tutti opzionali perché is_relevant potrebbe essere False)
    is_relevant: bool
    relevance_score: Optional[float] = None
    deal_type: Optional[str] = None
    deal_status: Optional[str] = None
    acquirer: Optional[str] = None
    target: Optional[str] = None
    investors: Optional[str] = None
    amount: Optional[str] = None
    currency: Optional[str] = None
    valuation: Optional[str] = None
    stake_percent: Optional[str] = None
    key_assets: Optional[str] = None
    geography: Optional[str] = None
    summary: Optional[str] = None
    why_it_matters: Optional[str] = None
    entities: List[str] = []

class ScrapeResponse(BaseModel):
    status: str
    total_found: int
    processed: int
    new_deals: int
    message: str
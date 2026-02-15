import time
import requests
import feedparser
import os
import random
import dateutil.parser
from abc import ABC, abstractmethod
from typing import List, Dict, Set
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from sqlalchemy.orm import Session
from litellm import completion
import instructor
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from database import SessionLocal
from models import ScrapeSettings, DealModel, DealData, SourceType


# ==========================================
# 1. CLASSE BASE ADAPTER
# ==========================================
class BaseAdapter(ABC):
    def __init__(self, settings: ScrapeSettings):
        self.settings = settings
        self.ua = UserAgent()
        try:
            self.headers = {"User-Agent": self.ua.random}
        except:
             self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        
    def _make_request(self, url, params=None, is_json=True):
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, headers=self.headers, timeout=15)
                if r.status_code == 200:
                    return r.json() if is_json else r.text
                elif r.status_code == 429:
                    time.sleep(5)
                else:
                    pass
            except Exception:
                pass
            time.sleep(1)
        return None

    @abstractmethod
    def fetch_articles(self) -> List[Dict]:
        pass

# ==========================================
# 2. ADAPTERS
# ==========================================
class SpaceNewsAdapter(BaseAdapter):
    def fetch_articles(self) -> List[Dict]:
        print(f"[SpaceNews] Start Fetching (RSS)...")
        articles = []
        search_query = self.settings.target_companies.split(",")[0].strip().replace(" ", "+")
        
        for page in range(1, self.settings.max_pages + 1):
            rss_url = f"https://spacenews.com/?s={search_query}&feed=rss2&paged={page}"
            try:
                feed = feedparser.parse(rss_url)
                if not feed.entries: break
                for entry in feed.entries:
                    articles.append({
                        "source": SourceType.SPACENEWS.value,
                        "url": entry.link,
                        "title": entry.title,
                        "date": getattr(entry, 'published', ''),
                        "raw_content": getattr(entry, 'content', [{'value': entry.summary}])[0]['value'] if hasattr(entry, 'content') else entry.summary
                    })
                time.sleep(1)
            except Exception:
                break
        return articles

class SnapiAdapter(BaseAdapter):
    def fetch_articles(self) -> List[Dict]:
        print(f"[SNAPI] Start Fetching (API v4)...")
        articles = []
        base_url = "https://api.spaceflightnewsapi.net/v4/articles"
        limit = 10
        total_items = self.settings.max_pages * limit
        
        for offset in range(0, total_items, limit):
            params = {"search": self.settings.target_companies, "limit": limit, "offset": offset}
            data = self._make_request(base_url, params=params)
            if not data or not data.get('results'): break
            
            for post in data['results']:
                articles.append({
                    "source": SourceType.SNAPI.value,
                    "url": post.get('url'),
                    "title": post.get('title'),
                    "date": post.get('published_at'),
                    "raw_content": post.get('summary', '') 
                })
            time.sleep(1)
        return articles

class ViaSatelliteAdapter(BaseAdapter):
    def fetch_articles(self) -> List[Dict]:
        print(f"[Via Satellite] Start Fetching (RSS)...")
        rss_url = "https://www.satellitetoday.com/feed/" 
        try:
            feed = feedparser.parse(rss_url)
            articles = []
            target = self.settings.target_companies.lower()
            
            for entry in feed.entries:
                if target in entry.title.lower() or target in entry.summary.lower():
                    content = getattr(entry, 'content', [{'value': entry.summary}])[0]['value'] if hasattr(entry, 'content') else entry.summary
                    articles.append({
                        "source": SourceType.VIA_SATELLITE.value,
                        "url": entry.link,
                        "title": entry.title,
                        "date": getattr(entry, 'published', ''),
                        "raw_content": content
                    })
            return articles
        except Exception:
            return []

class NasaTechPortAdapter(BaseAdapter):
    def fetch_articles(self) -> List[Dict]:
        print(f"[NASA TechPort] Start Fetching (API)...")
        url = "https://techport.nasa.gov/api/projects/search"
        params = {"searchQuery": self.settings.target_companies}
        data = self._make_request(url, params=params) 
        articles = []
        if data and 'projects' in data:
            for proj in data['projects'][:10]:
                articles.append({
                    "source": SourceType.NASA_TECHPORT.value,
                    "url": f"https://techport.nasa.gov/view/{proj.get('id')}",
                    "title": proj.get('title'),
                    "date": proj.get('lastUpdated'),
                    "raw_content": proj.get('description', '') 
                })
        return articles

# ==========================================
# 3. SERVICE PRINCIPALE
# ==========================================

class SpaceScraperService:
    def __init__(self, settings: ScrapeSettings):
        self.settings = settings
        self.db: Session = SessionLocal()
        
        self.adapters_map = {
            SourceType.SPACENEWS: SpaceNewsAdapter,
            SourceType.SNAPI: SnapiAdapter,
            SourceType.VIA_SATELLITE: ViaSatelliteAdapter,
            SourceType.NASA_TECHPORT: NasaTechPortAdapter,
            SourceType.SPACEWORKS: SpaceNewsAdapter, 
            SourceType.EURO_SPACEFLIGHT: SpaceNewsAdapter 
        }

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()

    def _get_adapter(self, source_type: SourceType) -> BaseAdapter:
        adapter_class = self.adapters_map.get(source_type, SpaceNewsAdapter)
        return adapter_class(self.settings)

    def _analyze_with_llm(self, text: str, meta: Dict) -> Dict:
        """ 
        Analisi AI Robust con RETRY su 429.
        """
        client = instructor.from_litellm(completion, mode=instructor.Mode.MD_JSON)
        companies_str = self.settings.target_companies
        
        # 1. Recupero Prompt
        base_prompt = self.settings.system_prompt
        # if not base_prompt or len(base_prompt.strip()) < 10:
        #    base_prompt = "You are a space economy analyst. Extract key data."

        # 2. Iniezione Contesto
        system_prompt = f"{base_prompt}\n\nCRITICAL CONTEXT: Your analysis MUST focus on the following target companies: '{companies_str}'. If the article does not mention them or is not relevant to their activities, set is_relevant=false."

        # 3. Configurazione Modello
        model_name = self.settings.ai_model.lower()
        api_key = self.settings.api_key
        api_base = None
        final_model = model_name

        if "ollama" in model_name:
            api_base = "http://host.docker.internal:11434"
            api_key = "ollama" 
        elif "groq" in model_name:
            api_base = "https://api.groq.com/openai/v1"
            clean_model = model_name.replace("groq/", "")
            final_model = f"openai/{clean_model}" 
        else:
            final_model = f"openai/{self.settings.ai_model}"
            api_base = "https://api.mistral.ai/v1"

        if not api_key and "ollama" not in model_name:
             return {"is_relevant": False, "summary": "Missing API Key"}

        kwargs = {
            "model": final_model,
            "api_key": api_key,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"URL: {meta['url']}\n\nCONTENT: {text[:18000]}"}
            ],
            "response_model": DealData,
            "max_retries": 1 # LiteLLM retries interni
        }
        
        if api_base:
            kwargs["api_base"] = api_base

        # --- CICLO DI RETRY MANUALE PER 429 ---
        # Se LiteLLM fallisce con 429, aspettiamo noi manualmente
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = client.chat.completions.create(**kwargs)
                result = resp.model_dump(exclude_none=True)
                
                # Auto-Correction
                deal_type = result.get('deal_type', 'none').lower()
                if deal_type == 'none' and result.get('is_relevant') is True:
                    result['is_relevant'] = False
                
                return result

            except Exception as e:
                err_str = str(e).lower()
                # Check se è un Rate Limit
                if "429" in err_str or "rate limit" in err_str:
                    if attempt < max_retries - 1:
                        # Backoff esponenziale: 10s, 20s, 30s...
                        wait_time = 10 * (attempt + 1)
                        print(f" [RATE LIMIT] 429 Rilevato. Pausa di {wait_time}s e riprovo...")
                        time.sleep(wait_time)
                        continue # Riprova il ciclo
                    else:
                        print(f"[LLM Error] Rate limit persistente su {meta['url']}: {e}")
                        return {"is_relevant": False, "summary": "Skipped due to API Rate Limits"}
                else:
                    # Altri errori (es. Context Length) non si retryano
                    print(f"[LLM Error] {e}")
                    return {"is_relevant": False, "summary": str(e)}

    # --- METODO FETCH SICURO ---
    def _fetch_source_safe(self, source_enum):
        try:
            adapter = self._get_adapter(source_enum)
            return adapter.fetch_articles()
        except Exception:
            return []

    def scrape(self):
        all_results = []
        raw_articles_batch = []
        processed_urls_in_batch = set()
        
        # --- DELAY ADATTIVO ---
        current_model = self.settings.ai_model.lower()
        if "groq" in current_model:
            delay_seconds = 3.0 # Groq è severo
        elif "mistral" in current_model:
            delay_seconds = 2.0 # Mistral aumentato a 2s per sicurezza
        else:
            delay_seconds = 0.1 
            
        print(f"AVVIO ANALISI - Target: {self.settings.target_companies} - Delay base: {delay_seconds}s")
        
        # 1. DOWNLOAD PARALLELO
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_source = {
                executor.submit(self._fetch_source_safe, source): source 
                for source in self.settings.sources
            }
            for future in as_completed(future_to_source):
                try:
                    articles = future.result()
                    raw_articles_batch.extend(articles)
                except Exception:
                    pass

        print(f"--- Scaricati {len(raw_articles_batch)} articoli. Inizio Analisi AI...")

        # 2. ANALISI SEQUENZIALE
        for i, art in enumerate(raw_articles_batch):
            url = art['url']
            print(f"[{i+1}/{len(raw_articles_batch)}] Processando: {url}")
            
            if url in processed_urls_in_batch: 
                print(f"    >>> SKIP: URL già processato in questo batch (Duplicato)")
                continue
            processed_urls_in_batch.add(url)

            exists = self.db.query(DealModel).filter(DealModel.url == url).first()
            if exists and not self.settings.force_rescan:
                print(f" [{i+1}/{len(raw_articles_batch)}] SALTATO: Già nel DB -> {url}")
                if exists.is_relevant:
                    all_results.append(exists.analysis_payload)
                continue

            soup = BeautifulSoup(art['raw_content'], "html.parser")
            for s in soup(["script", "style"]): s.decompose()
            clean_text = soup.get_text(separator=" ", strip=True)
            if len(clean_text) < 100: continue

            print(f" [{i+1}/{len(raw_articles_batch)}] Analisi: {url}...")
            
            # Qui chiamiamo la funzione che ora ha il retry interno
            analysis = self._analyze_with_llm(clean_text, art)
            
            if analysis.get('is_relevant'):
                print(f"   ---> RILEVANTE")
                all_results.append(analysis)
            
            analysis['source'] = art['source']
            analysis['published_date'] = art['date']
            analysis['title'] = art['title']
            analysis['url'] = url
            
            current_target = self.settings.target_companies.strip().upper()

            if exists:
                exists.analysis_payload = analysis
                exists.is_relevant = analysis.get('is_relevant', False)
                exists.title = art['title']
                exists.search_target = current_target
            else:
                new_deal = DealModel(
                    url=url, source=art['source'], title=art['title'],
                    is_relevant=analysis.get('is_relevant', False),
                    analysis_payload=analysis,
                    search_target=current_target
                )
                self.db.add(new_deal)
            self.db.commit()
            
            time.sleep(delay_seconds)

        return all_results
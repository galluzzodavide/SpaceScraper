import time
import requests
import feedparser
import os
import random
from abc import ABC, abstractmethod
from typing import List, Dict, Set
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from sqlalchemy.orm import Session
from litellm import completion
import instructor
from concurrent.futures import ThreadPoolExecutor, as_completed # <--- PER IL PARALLELISMO

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
                    print(f"[Warn] 429 Too Many Requests su {url}. Attesa 5s...")
                    time.sleep(5)
                else:
                    print(f"[Warn] HTTP {r.status_code} su {url}")
            except Exception as e:
                print(f"[Error] Request failed {url}: {e}")
            time.sleep(1)
        return None

    @abstractmethod
    def fetch_articles(self) -> List[Dict]:
        pass

# ==========================================
# 2. ADAPTERS (Invariati nella logica, ottimizzati per thread safety)
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
            except Exception as e:
                print(f"[SpaceNews] Error: {e}")
                break
        print(f"[SpaceNews] Finito. Trovati {len(articles)}.")
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
        print(f"[SNAPI] Finito. Trovati {len(articles)}.")
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
            print(f"[Via Satellite] Finito. Trovati {len(articles)}.")
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
        print(f"[NASA TechPort] Finito. Trovati {len(articles)}.")
        return articles

# ==========================================
# 3. SERVICE PRINCIPALE (Multi-Threaded)
# ==========================================

class SpaceScraperService:
    def __init__(self, settings: ScrapeSettings):
        self.settings = settings
        if not self.settings.api_key:
             raise ValueError("API Key mancante")
        
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
        """ Analisi AI (Rimane la stessa) """
        is_technical = meta['source'] in [SourceType.VIA_SATELLITE.value, SourceType.NASA_TECHPORT.value]
        client = instructor.from_litellm(completion, mode=instructor.Mode.MD_JSON)
        companies_str = self.settings.target_companies
        
        if is_technical:
             system_prompt = (f"Sei un Senior Technical Analyst spaziale. Analizza per: {companies_str}. "
                              "Estrai TRL, Mission Type, Orbit. Ignora finanza.")
        else:
             system_prompt = (f"Sei un Senior Financial Analyst. Analizza per: {companies_str}. "
                              "Estrai M&A, Contracts, Revenue. Ignora tech specs.")

        try:
            resp = client.chat.completions.create(
                model=f"openai/{self.settings.ai_model}",
                api_base="https://api.mistral.ai/v1",
                api_key=self.settings.api_key,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"URL: {meta['url']}\n\nCONTENT: {text[:15000]}"}
                ],
                response_model=DealData,
                max_retries=2
            )
            result = resp.model_dump(exclude_none=True)
            
            # Auto-Correction: Se l'AI dice 'None' ma is_relevant=True, correggiamo
            deal_type = result.get('deal_type', 'none').lower()
            if deal_type == 'none' and result.get('is_relevant') is True:
                print(f" [AUTO-FIX] {meta['url']} marcato IRRILEVANTE (Deal Type: None)")
                result['is_relevant'] = False
            return result
        except Exception as e:
            print(f"[LLM Error] {e}")
            return {"is_relevant": False, "summary": str(e)}

    # --- NUOVO METODO: DOWNLOAD PARALLELO ---
    def _fetch_source_safe(self, source_enum):
        """ Wrapper sicuro per eseguire il fetch in un thread separato """
        try:
            adapter = self._get_adapter(source_enum)
            return adapter.fetch_articles()
        except Exception as e:
            print(f"Errore thread {source_enum}: {e}")
            return []

    def scrape(self):
        all_results = []
        raw_articles_batch = []
        processed_urls_in_batch = set() # Dedup globale
        
        print(f"AVVIO PARALLELO: {[s.value for s in self.settings.sources]}")
        
        # 1. FASE DI DOWNLOAD PARALLELO (Fan-Out)
        # Usiamo ThreadPoolExecutor per lanciare tutte le richieste HTTP insieme
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Mappa future -> source
            future_to_source = {
                executor.submit(self._fetch_source_safe, source): source 
                for source in self.settings.sources
            }
            
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    articles = future.result()
                    raw_articles_batch.extend(articles) # Raccogliamo tutto in un unico calderone
                except Exception as exc:
                    print(f" {source.value} ha generato un'eccezione: {exc}")

        print(f"--- FASE 1 COMPLETATA: Scaricati {len(raw_articles_batch)} articoli totali. Inizio Analisi... ---")

        # 2. FASE DI ANALISI SEQUENZIALE (Safe DB & Rate Limits)
        # Processiamo la lista aggregata. Questo previene lock del DB e rispetta i limiti API di Mistral.
        for art in raw_articles_batch:
            url = art['url']
            
            # Dedup nel batch
            if url in processed_urls_in_batch: continue
            processed_urls_in_batch.add(url)

            # Dedup nel DB
            exists = self.db.query(DealModel).filter(DealModel.url == url).first()
            
            if exists:
                if not self.settings.force_rescan:
                    if exists.is_relevant:
                        print(f" [CACHE HIT] {url}")
                        all_results.append(exists.analysis_payload)
                    continue
                else:
                    print(f" [RESCAN] {url}")

            # Pre-processing
            soup = BeautifulSoup(art['raw_content'], "html.parser")
            for s in soup(["script", "style"]): s.decompose()
            clean_text = soup.get_text(separator=" ", strip=True)
            if len(clean_text) < 100: continue

            # Analisi AI
            print(f" [AI PROCESSING] {url} (Source: {art['source']})")
            analysis = self._analyze_with_llm(clean_text, art)
            
            analysis['source'] = art['source']
            analysis['published_date'] = art['date']
            analysis['title'] = art['title']
            analysis['url'] = url
            
            # Salvataggio DB
            if exists:
                exists.analysis_payload = analysis
                exists.is_relevant = analysis.get('is_relevant', False)
            else:
                new_deal = DealModel(
                    url=url, source=art['source'], title=art['title'],
                    is_relevant=analysis.get('is_relevant', False),
                    analysis_payload=analysis
                )
                self.db.add(new_deal)
            self.db.commit()
            
            if analysis.get('is_relevant', False):
                all_results.append(analysis)
            
            # Rate limit per non bruciare la chiave API
            time.sleep(0.5)

        return all_results
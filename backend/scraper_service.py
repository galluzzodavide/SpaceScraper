# backend/scraper_service.py
import json
import os
import re
import time
import hashlib
import requests
from pathlib import Path
from typing import List, Optional, Callable
from dateutil import parser as dtparser
from bs4 import BeautifulSoup

# Importa il modello Pydantic
from .models import DealData

class SpaceScraperService:
    def __init__(self, api_key: str, cache_dir: str = "cache_spacenews"):
        self.api_key = api_key
        self.base_url = "https://spacenews.com"
        self.target_companies = ["ICEYE"]
        self.model = "mistral-large-latest"
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.user_agent = "Mozilla/5.0 (compatible; SpaceNewsDealBot/0.1)"
        self.http_timeout = 30
        
        # Le istruzioni aggiornate con Short-Circuit
        self.system_instructions = (
            "Sei un estrattore specializzato di informazioni finanziarie e industriali dal testo di news nel settore space. "
            "Il tuo obiettivo è determinare se l'articolo descrive un evento aziendale concreto.\n\n"

            "DEFINIZIONE DI RILEVANZA E USCITA RAPIDA:\n"
            "- is_relevant deve essere true SOLO se l'articolo descrive un evento aziendale reale e concreto.\n"
            "- Se non esiste un evento aziendale concreto, o se ICEYE non è coinvolta, imposta ESATTAMENTE:\n"
            "  {\"is_relevant\": false}\n"
            "- In questo caso, NON compilare gli altri campi.\n\n"

            "SE L'ARTICOLO È RILEVANTE (is_relevant=true):\n"
            "Compila tutti i campi: source, url, title, published_date, section, is_relevant, relevance_score, "
            "deal_type, deal_status, acquirer, target, investors, amount, currency, valuation, stake_percent, "
            "key_assets, geography, summary, why_it_matters, entities.\n"
            "- deal_type: acquisition, merger, investment, partnership, contract, ipo.\n"
            "- deal_status: rumor, announced, completed.\n"
            "- entities: Includi SOLO ICEYE e le entità direttamente coinvolte.\n\n"
            "Restituisci solo JSON valido."
        )

    # --- HELPER FUNCTIONS ---
    def _txt(self, s: str) -> str:
        return re.sub(r"\s+", " ", s).strip() if s else ""

    def _sha1(self, s: str) -> str:
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{self._sha1(url)}.json"

    def _load_cached(self, url: str) -> Optional[dict]:
        p = self._cache_path(url)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def _save_cached(self, url: str, data: dict) -> None:
        self._cache_path(url).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _contains_target(self, text: str) -> bool:
        t = text.lower()
        return any(c.lower() in t for c in self.target_companies)

    # --- CORE LOGIC ---
    def discover_articles(self, year_min: int = 2020) -> List[str]:
        # Logica WP API (semplificata per brevità, stessa del tuo script)
        after = f"{year_min}-01-01T00:00:00"
        out = []
        # Limitiamo a 1 pagina per demo rapida, in prod aumenta max_pages
        api_url = f"{self.base_url}/wp-json/wp/v2/posts"
        params = {"per_page": 50, "page": 1, "after": after, "search": " ".join(self.target_companies)}
        
        try:
            r = requests.get(api_url, params=params, headers={"User-Agent": self.user_agent}, timeout=self.http_timeout)
            if r.status_code == 200:
                items = r.json()
                for it in items:
                    link = it.get("link")
                    if link and link.startswith(self.base_url):
                        out.append(link)
        except Exception as e:
            print(f"Error discovery: {e}")
            
        # Deduplica
        return list(dict.fromkeys(out))

    def fetch_article(self, url: str) -> Optional[dict]:
        try:
            r = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=self.http_timeout)
            if r.status_code != 200:
                return None
            
            soup = BeautifulSoup(r.text, "html.parser")
            h1 = soup.find("h1")
            title = self._txt(h1.get_text()) if h1 else ""
            
            # Estrazione data
            meta_pub = soup.find("meta", {"property": "article:published_time"})
            pub_date = ""
            if meta_pub and meta_pub.get("content"):
                pub_date = meta_pub["content"]

            msec = soup.find("meta", {"property": "article:section"})
            section = self._txt(msec.get("content", "")) if msec else ""

            body_parts = []
            article_tag = soup.find("article") or soup
            for p in article_tag.find_all("p"):
                t = self._txt(p.get_text(" "))
                if len(t) >= 40:
                    body_parts.append(t)
            
            return {
                "url": url, "title": title, "published_date": pub_date,
                "section": section, "text": "\n".join(body_parts)
            }
        except Exception:
            return None

    def analyze_with_mistral(self, article_data: dict) -> dict:
        user_template = (
            f"URL: {article_data['url']}\nTITLE: {article_data['title']}\n"
            f"DATE: {article_data['published_date']}\nSECTION: {article_data['section']}\n\n{article_data['text'][:18000]}"
        )
        
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self.system_instructions},
                {"role": "user", "content": user_template},
            ],
            "temperature": 0.0,
            "max_tokens": 900,
        }
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        r = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        
        content = r.json()["choices"][0]["message"]["content"]
        # Try parse
        try:
            return json.loads(content)
        except:
            # Fallback regex
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                return json.loads(match.group(0))
            raise ValueError("Invalid JSON from LLM")

    def run_pipeline(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> List[DealData]:
        urls = self.discover_articles()
        results = []
        total = len(urls)

        for i, url in enumerate(urls):
            # Notifica progresso
            if progress_callback:
                progress_callback(i + 1, total)

            # 1. Check Cache
            cached = self._load_cached(url)
            if cached:
                if cached.get("is_relevant") is True:
                    # Validiamo con Pydantic per sicurezza
                    try:
                        results.append(DealData(**cached))
                    except: pass
                continue

            # 2. Fetch
            art = self.fetch_article(url)
            time.sleep(0.5) # Gentilezza
            if not art: continue
            
            # Filtro rapido parole chiave
            if not self._contains_target(art["title"] + " " + art["text"]):
                continue

            # 3. LLM
            try:
                llm_data = self.analyze_with_mistral(art)
            except Exception as e:
                print(f"LLM Error on {url}: {e}")
                continue

            # Merge metadati + LLM
            full_data = {
                "source": "SpaceNews",
                "url": url,
                "title": art["title"],
                "published_date": art["published_date"],
                "section": art["section"],
                **llm_data
            }

            self._save_cached(url, full_data)

            # 4. Filtro Finale
            if full_data.get("is_relevant") is True:
                results.append(DealData(**full_data))
            
            time.sleep(0.5) # Rate limit LLM

        return results
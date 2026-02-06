import time
import requests
import json
import re
import hashlib
from pathlib import Path
from bs4 import BeautifulSoup
from .models import ScrapeSettings, DealData

# --- CONFIGURAZIONE CACHE ---
# Usa Path(__file__).parent per garantire che la cartella sia creata 
# dentro 'backend/cache_deals' indipendentemente da dove lanci il server.
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache_deals"
CACHE_DIR.mkdir(exist_ok=True)

# Stato globale
current_status = {
    "is_running": False,
    "total": 0,
    "processed": 0,
    "message": "Idle",
    "last_update": "",
    "logs": [] 
}

class SpaceScraperService:
    def __init__(self, settings: ScrapeSettings):
        self.settings = settings
        if not self.settings.api_key or not self.settings.api_key.strip():
            raise ValueError("API Key non fornita dall'utente!")
            
        self.companies_list = [c.strip() for c in settings.target_companies.split(",")]
        self.base_url = "https://spacenews.com"
        self.headers = {"User-Agent": "Mozilla/5.0 (compatible; SpaceNewsDealBot/0.1)"}

    # --- LOGGING ---
    def add_log(self, message, type="info"):
        timestamp = time.strftime("%H:%M:%S")
        entry = {"timestamp": timestamp, "message": message, "type": type}
        print(f"[{type.upper()}] {message}")
        current_status["logs"].insert(0, entry)
        current_status["logs"] = current_status["logs"][:150]

    def update_status(self, message, processed=None, total=None):
        current_status["message"] = message
        current_status["last_update"] = time.strftime("%H:%M:%S")
        if processed is not None: current_status["processed"] = processed
        if total is not None: current_status["total"] = total

    # --- METODI CACHE ---
    def get_cache_path(self, url: str) -> Path:
        """Genera un nome file univoco basato sull'hash dell'URL"""
        file_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{file_hash}.json"

    def load_cached(self, url: str):
        """Carica il JSON dalla cache se esiste"""
        p = self.get_cache_path(url)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except:
                return None
        return None

    def save_cached(self, url: str, data: dict):
        """Salva il JSON nella cache"""
        p = self.get_cache_path(url)
        try:
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"Errore salvataggio cache: {e}")

    # --- TEXT UTILS & SANITIZATION ---
    def _txt(self, s: str) -> str:
        return re.sub(r"\s+", " ", s).strip() if s else ""

    def _sanitize_data(self, data: dict) -> dict:
        """
        Pulisce i dati per evitare che oggetti complessi (dict/list) rompano Pydantic.
        Esempio: se stake_percent è un oggetto {'Bayanat': 54}, lo converte in stringa.
        """
        # Campi che nel modello Pydantic sono definiti come Optional[str] ma l'IA potrebbe restituire come oggetti
        keys_to_fix = ['stake_percent', 'amount', 'valuation', 'key_assets', 'currency']
        
        for key in keys_to_fix:
            if key in data:
                val = data[key]
                # Se è un dizionario o una lista, forza la conversione a stringa
                if isinstance(val, (dict, list)):
                    data[key] = str(val) # Converte {'A':1} in "{'A':1}"
                # Se è un numero, converti in stringa per sicurezza (opzionale, Pydantic di solito lo fa)
                elif isinstance(val, (int, float)):
                    data[key] = str(val)
                
        return data

    def parse_article_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        article_body = soup.find("article") or soup
        body_parts = []
        for p in article_body.find_all("p"):
            t = self._txt(p.get_text(" "))
            if len(t) >= 40:
                body_parts.append(t)
        return "\n".join(body_parts)

    def contains_target_company(self, text: str) -> bool:
        """Controllo base keywords per evitare chiamate inutili all'IA"""
        text_lower = text.lower()
        for company in self.companies_list:
            if company.lower() in text_lower:
                return True
        return False

    # --- DISCOVERY ---
    def discover_urls(self):
        urls = []
        self.add_log(f"Scanning {self.settings.max_pages} pages for {self.companies_list}...", "info")
        
        for page in range(1, self.settings.max_pages + 1):
            try:
                self.add_log(f"Fetching Page {page}...", "info")
                api_url = f"{self.base_url}/wp-json/wp/v2/posts"
                params = {
                    "per_page": 20, 
                    "page": page, 
                    "search": " ".join(self.companies_list),
                    "after": f"{self.settings.min_year}-01-01T00:00:00"
                }
                
                r = requests.get(api_url, params=params, headers=self.headers, timeout=10)
                if r.status_code == 200:
                    items = r.json()
                    self.add_log(f"Page {page}: Found {len(items)} articles.", "success")
                    for item in items:
                        urls.append(item['link'])
                else:
                    self.add_log(f"Page {page}: API Error {r.status_code}", "error")
            except Exception as e:
                self.add_log(f"Error Page {page}: {str(e)}", "error")
        
        unique_urls = list(set(urls))
        self.add_log(f"Total Unique URLs found: {len(unique_urls)}", "info")
        return unique_urls

    # --- MAIN LOOP ---
    def scrape(self):
        current_status["is_running"] = True
        current_status["logs"] = [] 
        current_status["processed"] = 0
        current_status["total"] = 0
        
        try:
            self.update_status("Starting discovery...")
            urls = self.discover_urls()
            total = len(urls)
            
            if total == 0:
                self.add_log("No articles found.", "warning")
                self.update_status("Completed (No articles)", 0, 0)
                current_status["is_running"] = False
                return []

            self.update_status(f"Processing {total} articles...", 0, total)
            self.add_log(f"Starting analysis on {total} articles...", "info")

            results = []
            
            for i, url in enumerate(urls):
                if not current_status["is_running"]: break 

                short_url = url.split('/')[-2]
                self.update_status(f"Processing: {short_url}", i+1, total)
                
                # 1. CONTROLLO CACHE
                cached_data = self.load_cached(url)
                if cached_data:
                    self.add_log(f"Loaded from cache: {short_url}", "info")
                    
                    # FIX: Puliamo anche i dati caricati dalla cache per evitare errori Pydantic
                    cached_data = self._sanitize_data(cached_data)

                    # ESTRAI is_relevant DALLA CACHE
                    if cached_data.get('is_relevant') is True:
                        results.append(cached_data)
                    continue 

                # 2. FETCH WEB
                try:
                    resp = requests.get(url, headers=self.headers, timeout=10)
                    if resp.status_code != 200: continue
                    text = self.parse_article_text(resp.text)

                    if len(text) < 100:
                        self.add_log(f"Skipped (Text too short): {short_url}", "warning")
                        continue
                    
                    # Filtro Pre-IA: Se l'azienda non è nel testo, è inutile analizzare
                    full_content = short_url + " " + text
                    if not self.contains_target_company(full_content):
                         self.add_log(f"Skipped (Target not mentioned): {short_url}", "warning")
                         # Salviamo un placeholder in cache per non riprovare in futuro
                         dummy_result = {"is_relevant": False, "url": url, "deal_type": "none"}
                         self.save_cached(url, dummy_result)
                         continue

                except Exception as e:
                    self.add_log(f"Fetch Error: {short_url}", "error")
                    continue

                # 3. AI ANALYSIS
                try:
                    self.add_log(f"Analyzing with AI: {short_url}...", "info")
                    deal_data = self.call_mistral(text, url)
                    
                    # Arricchimento dati mancanti
                    deal_data['url'] = url
                    if not deal_data.get('title'):
                        # Tentativo di recupero titolo
                        soup = BeautifulSoup(resp.text, "html.parser")
                        h1 = soup.find('h1')
                        deal_data['title'] = h1.get_text().strip() if h1 else short_url

                    # FIX: Puliamo i dati prima di salvare/usare
                    deal_data = self._sanitize_data(deal_data)

                    # 4. SALVATAGGIO IN CACHE (Qualsiasi sia il risultato)
                    self.save_cached(url, deal_data)

                    # 5. ESTRAZIONE E CONTROLLO RILEVANZA
                    is_rel = deal_data.get('is_relevant', False)
                    
                    if is_rel:
                        self.add_log(f"✅ RELEVANT DEAL: {short_url}", "success")
                        results.append(deal_data)
                    else:
                        self.add_log(f"Skipped (AI deemed irrelevant): {short_url}", "warning")
                        
                except Exception as e:
                    self.add_log(f"AI Error: {str(e)}", "error")
                
                time.sleep(1) # Rispetto per il server

            self.add_log(f"Analysis Completed. Found {len(results)} deals.", "success")
            self.update_status("Analysis Completed", total, total)
            current_status["is_running"] = False
            return results

        except Exception as e:
            self.add_log(f"FATAL ERROR: {str(e)}", "error")
            current_status["is_running"] = False
            return []

    def call_mistral(self, text, url):
        # Aggiungiamo istruzioni di focus per migliorare la precisione
        companies_str = ", ".join(self.companies_list)
        focus_instruction = (
            f"\n\nFOCUS SU: {companies_str}\n"
            f"- L'articolo è considerato rilevante (is_relevant=true) SOLO se una di queste aziende ({companies_str}) "
            "è direttamente coinvolta nel deal (acquisizione, contratto, partnership, investimento).\n"
            "- Se l'azienda è citata solo come contesto, is_relevant=false."
        )
        full_system_prompt = self.settings.system_prompt + focus_instruction

        payload = {
            "model": self.settings.ai_model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": full_system_prompt},
                {"role": "user", "content": f"URL: {url}\nTEXT: {text[:18000]}"}
            ]
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json"
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                r = requests.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers, timeout=45)
                r.raise_for_status()
                return json.loads(r.json()["choices"][0]["message"]["content"])
            except Exception as e:
                if attempt == max_retries - 1: raise e
                time.sleep((attempt + 1) * 2)
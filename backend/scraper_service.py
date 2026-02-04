import time
import requests
import json
from bs4 import BeautifulSoup
from .models import ScrapeSettings, DealData

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
        self.headers = {"User-Agent": "SpaceScraper/1.0"}

    def add_log(self, message, type="info"):
        """ Log nel Terminale E nel Frontend """
        timestamp = time.strftime("%H:%M:%S")
        entry = {"timestamp": timestamp, "message": message, "type": type}
        
        # Stampa su backend
        print(f"[{type.upper()}] {message}")
        
        # Inserisci nel feed frontend (in cima)
        current_status["logs"].insert(0, entry)
        current_status["logs"] = current_status["logs"][:150] # Limite storico

    def update_status(self, message, processed=None, total=None):
        current_status["message"] = message
        current_status["last_update"] = time.strftime("%H:%M:%S")
        if processed is not None: current_status["processed"] = processed
        if total is not None: current_status["total"] = total

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

    def scrape(self):
        current_status["is_running"] = True
        current_status["logs"] = [] 
        current_status["processed"] = 0
        current_status["total"] = 0
        
        try:
            self.update_status("Starting discovery...")
            urls = self.discover_urls()
            total = len(urls)
            
            # Appena trovati gli URL, impostiamo il totale (es. 0/40)
            if total == 0:
                self.add_log("No articles found to analyze.", "warning")
                self.update_status("Completed (No articles)", 0, 0)
                current_status["is_running"] = False
                return []

            self.update_status(f"Starting analysis of {total} articles...", 0, total)
            self.add_log(f"Starting AI Analysis on {total} articles...", "info")

            results = []
            
            for i, url in enumerate(urls):
                if not current_status["is_running"]: break 

                short_url = url.split('/')[-2]
                self.update_status(f"Analyzing: {short_url}", i+1, total)
                
                # Fetch
                try:
                    resp = requests.get(url, headers=self.headers, timeout=10)
                    if resp.status_code != 200: continue
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    text = " ".join([p.text for p in soup.find_all('p')])
                except Exception as e:
                    self.add_log(f"Fetch Error: {short_url}", "error")
                    continue

                # AI
                try:
                    deal_data = self.call_mistral(text, url)
                    is_rel = deal_data.get('is_relevant', False)
                    
                    if is_rel:
                        self.add_log(f"✅ RELEVANT DEAL: {short_url}", "success")
                        deal_data['url'] = url
                        if not deal_data.get('title'):
                            h1 = soup.find('h1')
                            deal_data['title'] = h1.get_text().strip() if h1 else "No Title"
                        results.append(deal_data)
                    else:
                        # QUI GENERIAMO IL WARNING CHE VUOI VEDERE
                        self.add_log(f"Skipped (Not relevant): {short_url}", "warning")
                        
                except Exception as e:
                    self.add_log(f"AI Error: {str(e)}", "error")
                
                time.sleep(1)

            self.add_log(f"Analysis Completed. Found {len(results)} deals.", "success")
            self.update_status("Analysis Completed", total, total)
            current_status["is_running"] = False
            return results

        except Exception as e:
            self.add_log(f"FATAL ERROR: {str(e)}", "error")
            current_status["is_running"] = False
            return []

    def call_mistral(self, text, url):
        # ... (Usa la versione con Retry che ti ho dato nel turno precedente) ...
        # (Se ti serve te la rincollo, ma è quella con il ciclo 'for attempt in range(max_retries)')
        payload = {
            "model": self.settings.ai_model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self.settings.system_prompt},
                {"role": "user", "content": f"URL: {url}\nTEXT: {text[:15000]}"}
            ]
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json"
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                r = requests.post("https://api.mistral.ai/v1/chat/completions", json=payload, headers=headers, timeout=30)
                r.raise_for_status()
                return json.loads(r.json()["choices"][0]["message"]["content"])
            except Exception as e:
                if attempt == max_retries - 1: raise e
                time.sleep((attempt + 1) * 2)
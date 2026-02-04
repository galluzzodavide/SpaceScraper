#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SpaceNews scraper + Mistral extractor (M&A / deals / acquisitions).

Pipeline:
1) discover article URLs via WP REST API (recent only)
2) fetch + parse article text
3) filter by target companies
4) call Mistral to extract structured deal info
5) save to Excel
"""

from __future__ import annotations

import json
import os
import re
import time
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests
import pandas as pd
from bs4 import BeautifulSoup
from dateutil import parser as dtparser


# ================== CONFIG ==================
BASE_URL = "https://spacenews.com"

TARGET_COMPANIES = ["ICEYE"]

OUTPUT_XLSX = "spacenews_deals.xlsx"
CACHE_DIR = Path("cache_spacenews")
CACHE_DIR.mkdir(exist_ok=True)

MODEL = "mistral-large-latest"
API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

MAX_TOKENS = 900
SLEEP_BETWEEN_FETCH = 0.7
SLEEP_BETWEEN_LLM = 0.6
HTTP_TIMEOUT = 30

USER_AGENT = "Mozilla/5.0 (compatible; SpaceNewsDealBot/0.1; +https://example.com/bot)"


# ================== SCHEMA ==================
SCHEMA = [
    "source", "url", "title", "published_date", "section",
    "is_relevant", "relevance_score",
    "deal_type", "deal_status",
    "acquirer", "target", "investors",
    "amount", "currency", "valuation", "stake_percent",
    "key_assets", "geography",
    "summary", "why_it_matters", "entities"
]

SYSTEM_INSTRUCTIONS = (
    "Sei un estrattore specializzato di informazioni finanziarie e industriali dal testo di news nel settore space. "
    "Il tuo obiettivo è determinare se l'articolo descrive un evento aziendale concreto tra: acquisizioni, merger, "
    "investimenti, IPO, partnership strategiche o grandi contratti commerciali.\n\n"

    "Devi restituire SOLO un JSON sintatticamente valido con ESATTAMENTE le seguenti chiavi: "
    + ", ".join(SCHEMA) + ".\n\n"

    "REGOLE GENERALI:\n"
    "- Usa esclusivamente doppi apici per stringhe JSON.\n"
    "- Non aggiungere testo prima o dopo il JSON.\n"
    "- Non inserire commenti.\n"
    "- Se un'informazione non è presente nel testo, usa null o [].\n"
    "- Non inventare dati o numeri.\n\n"

    "DEFINIZIONE DI RILEVANZA:\n"
    "- is_relevant deve essere true SOLO se l'articolo descrive un evento aziendale reale e concreto.\n"
    "- Se non esiste un evento aziendale concreto, imposta:\n"
    "  is_relevant=false, deal_type='none', deal_status='unknown', entities=[].\n\n"

    "FOCUS SU ICEYE:\n"
    "- L'articolo è considerato rilevante SOLO se ICEYE è direttamente coinvolta nell'evento aziendale.\n"
    "- Se ICEYE è citata solo come contesto o esempio, l'articolo NON è rilevante.\n\n"

    "CAMPO deal_type:\n"
    "- Valori ammessi: acquisition, merger, investment, partnership, contract, ipo, other, none.\n\n"

    "CAMPO deal_status:\n"
    "- Valori ammessi: rumor, announced, completed, unknown.\n\n"

    "CAMPO entities:\n"
    "- Includi SOLO ICEYE e le entità direttamente coinvolte nel deal che la riguarda.\n"
    "- Non elencare aziende, governi, agenzie o progetti citati solo come contesto.\n"
    "- Se ICEYE non è coinvolta in alcun deal, entities deve essere [].\n\n"

    "CAMPI ECONOMICI:\n"
    "- amount, valuation e stake_percent solo se esplicitamente indicati nel testo.\n"
    "- Non stimare o dedurre valori mancanti.\n\n"

    "Il JSON prodotto deve essere sempre valido e parseabile senza errori."
)


USER_TEMPLATE = (
    "URL: {url}\nTITLE: {title}\nDATE: {published_date}\nSECTION: {section}\n\n{text}"
)


# ================== UTIL ==================
def _txt(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip() if s else ""


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def http_get(url: str) -> requests.Response:
    return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)


def contains_target_company(text: str, companies: List[str]) -> bool:
    t = text.lower()
    return any(c.lower() in t for c in companies)


def is_recent(date_str: str, year_min: int) -> bool:
    if not date_str:
        return False
    return dtparser.parse(date_str).year >= year_min


def extract_published_date(soup: BeautifulSoup) -> str:
    meta_pub = soup.find("meta", {"property": "article:published_time"})
    if meta_pub and meta_pub.get("content"):
        try:
            return dtparser.parse(meta_pub["content"]).isoformat()
        except Exception:
            pass
    return ""


def dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ================== DISCOVERY (WP API) ==================
def discover_from_wp_api(year_min: int = 2020, per_page: int = 50, max_pages: int = 10) -> List[str]:
    after = f"{year_min}-01-01T00:00:00"
    out = []

    for page in range(1, max_pages + 1):
        print(f"[WP API] Request page {page}...")
        api_url = f"{BASE_URL}/wp-json/wp/v2/posts"
        params = {
            "per_page": per_page,
            "page": page,
            "after": after,
            "search": " ".join(TARGET_COMPANIES)
        }

        for attempt in range(3):
            try:
                r = requests.get(api_url, params=params, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT)
                break
            except requests.exceptions.ReadTimeout:
                print(f"[WP API] Timeout, retry {attempt+1}/3...")
                time.sleep(2)
        else:
            print("[WP API] Failed after retries, stopping.")
            break

        print(f"[WP API] Status: {r.status_code}")
        if r.status_code in (400, 404):
            break

        r.raise_for_status()
        items = r.json()
        if not items:
            break

        for it in items:
            link = it.get("link")
            if link and link.startswith(BASE_URL):
                out.append(link)

        time.sleep(0.3)

    return dedupe(out)


# ================== PARSING ARTICLES ==================
@dataclass
class Article:
    url: str
    title: str
    published_date: str
    section: str
    text: str


def parse_article_html(url: str, html: str) -> Article:
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.find("h1")
    title = _txt(h1.get_text()) if h1 else ""

    published = extract_published_date(soup)

    section = ""
    msec = soup.find("meta", {"property": "article:section"})
    if msec:
        section = _txt(msec.get("content", ""))

    body_parts = []
    article = soup.find("article") or soup
    for p in article.find_all("p"):
        t = _txt(p.get_text(" "))
        if len(t) >= 40:
            body_parts.append(t)

    text = "\n".join(body_parts)
    return Article(url, title, published, section, text)


def fetch_article(url: str) -> Optional[Article]:
    try:
        r = http_get(url)
        if r.status_code != 200:
            return None
        return parse_article_html(url, r.text)
    except Exception:
        return None


# ================== MISTRAL ==================
def call_mistral(payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    r = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]

    # Prova parsing diretto
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Fallback: estrai solo il blocco JSON
    try:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            raise ValueError("No JSON object found in LLM output")
        return json.loads(match.group(0))
    except Exception as e:
        print("\n[ERROR] JSON parsing failed")
        print("LLM raw output:\n", content)
        raise e


def build_payload(art: Article) -> dict:
    text = art.text[:18000]
    user_text = USER_TEMPLATE.format(
        url=art.url, title=art.title,
        published_date=art.published_date,
        section=art.section, text=text
    )
    return {
        "model": MODEL,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.0,
        "max_tokens": MAX_TOKENS,
    }


# ================== CACHE ==================
def cache_path_for_url(url: str) -> Path:
    return CACHE_DIR / f"{sha1(url)}.json"


def load_cached(url: str) -> Optional[dict]:
    p = cache_path_for_url(url)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def save_cached(url: str, data: dict) -> None:
    cache_path_for_url(url).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ================== OUTPUT ==================
def append_to_excel(rows: List[dict], path_xlsx: str) -> None:
    df = pd.DataFrame(rows, columns=SCHEMA)
    if os.path.exists(path_xlsx):
        existing = pd.read_excel(path_xlsx)
        df = pd.concat([existing, df], ignore_index=True).drop_duplicates(subset=["url"])
    df.to_excel(path_xlsx, index=False)


# ================== MAIN ==================
def main() -> None:
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY non impostata.")

    urls = discover_from_wp_api(year_min=2020, per_page=100, max_pages=1)

    if not urls:
        print("Nessun URL trovato.")
        return

    print(f"URL trovati: {len(urls)}")

    rows = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")

        cached = load_cached(url)
        if cached:
            rows.append(cached)
            continue

        art = fetch_article(url)
        time.sleep(SLEEP_BETWEEN_FETCH)

        if not art or not is_recent(art.published_date, 2020):
            continue

        if TARGET_COMPANIES and not contains_target_company(art.title + " " + art.text, TARGET_COMPANIES):
            continue

        payload = build_payload(art)
        data = call_mistral(payload)

        data["source"] = "SpaceNews"
        data["url"] = url
        data["title"] = art.title
        data["published_date"] = art.published_date
        data["section"] = art.section

        save_cached(url, data)
        rows.append(data)

        time.sleep(SLEEP_BETWEEN_LLM)

    if rows:
        append_to_excel(rows, OUTPUT_XLSX)
        print(f"Done. Written: {OUTPUT_XLSX} ({len(rows)} righe)")
    else:
        print("Nessuna riga estratta.")


if __name__ == "__main__":
    main()

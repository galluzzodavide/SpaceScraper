import os
from tavily import TavilyClient
from litellm import completion

# 1. Setup Strumenti
# Tavily è gratuito fino a 1000 ricerche/mese, ottimo per testare
tavily = TavilyClient(api_key="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") 

class StartupAgent:
    def __init__(self, model="mistral/mistral-large-latest"):
        self.model = model

    def investigate_company(self, company_name: str):
        print(f"AGENTE: Inizio indagine su {company_name}...")

        # PASSO 1: Ricerca Intelligente (The 'Tools')
        # Chiediamo a Tavily di cercare news recenti, escludendo risultati vecchi
        query = f"{company_name} space startup contract investment partnership 2024 2025"
        
        # Tavily cerca, entra nei siti, e ci ridà il contenuto testuale (il context)
        search_result = tavily.search(
            query=query, 
            search_depth="advanced", # Cerca in profondità
            max_results=5,           # Leggi i primi 5 siti
            include_raw_content=False
        )

        # PASSO 2: Sintesi e Estrazione (The 'Brain')
        # Uniamo i testi trovati in un unico "dossier"
        context_text = ""
        for result in search_result['results']:
            context_text += f"\n--- SOURCE: {result['url']} ---\n{result['content']}\n"

        print(f"AGENTE: Trovati dati da {len(search_result['results'])} fonti. Analisi Mistral in corso...")

        # PASSO 3: Chiamata a Mistral con il tuo Prompt "Financial Controller"
        # Usiamo il contesto recuperato dal web dinamico invece che dall'RSS
        response = completion(
            model=self.model,
            messages=[{
                "role": "system",
                "content": "Sei un Financial Controller. Analizza il testo fornito (che è una raccolta di risultati web) ed estrai l'ultimo deal rilevante in formato JSON."
            }, {
                "role": "user",
                "content": f"Dossier su {company_name}:\n{context_text}"
            }]
        )

        return response.choices[0].message.content

# Esempio di utilizzo
agent = StartupAgent()
report = agent.investigate_company("Eoliann")
print(report)
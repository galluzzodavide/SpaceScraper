# Usa una versione leggera di Python 3.10
FROM python:3.10-slim

# Evita che Python scriva file .pyc e bufferizzi l'output (utile per i log in tempo reale)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Imposta la directory di lavoro nel container
WORKDIR /app

# Installa le dipendenze di sistema necessarie per compilare psycopg2 e altre lib
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia prima solo il file dei requisiti per sfruttare la cache di Docker
COPY requirements.txt .

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il resto del codice sorgente nel container
COPY . .

# (Opzionale) Utente non-root per sicurezza in produzione
# RUN useradd -m myuser
# USER myuser

# Il comando di avvio viene specificato nel docker-compose.yml, 
# quindi qui non serve CMD obbligatorio, ma possiamo metterne uno di default.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
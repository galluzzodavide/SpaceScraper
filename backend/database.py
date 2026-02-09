import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Recupera l'URL dal docker-compose environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://space_user:space_password@db:5432/spacescraper")

# Creazione Engine
engine = create_engine(DATABASE_URL)

# Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base per i modelli ORM
Base = declarative_base()

# Dependency Injection per FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
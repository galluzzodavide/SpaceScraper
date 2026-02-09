🚀 SpaceScraper Deal Intelligence
SpaceScraper is an automated intelligence platform designed to monitor, aggregate, and analyze news from the Space Economy sector. It utilizes AI agents (LLMs) to transform unstructured data (news articles, RSS feeds, R&D databases) into structured strategic insights.

🌟 Key Features
1. 🧠 "Dual Persona" Architecture
The system adapts both the analysis logic and the user interface based on the selected user profile:

Financial Controller:

Focus: M&A, Investments, Contracts, Revenue.

Sources: SpaceNews, SNAPI, SpaceWorks, European Spaceflight.

Output Columns: Deal Type, Amount, Investors, Acquirer/Target.

Technical Officer:

Focus: R&D, TRL (Technology Readiness Level), Orbits, Mission Specs.

Sources: Via Satellite, NASA TechPort.

Output Columns: TRL, Orbit, Mission Type, Key Assets (Technology).

2. ⚡ Hybrid & Parallel Ingestion
Parallel Fetching (Multi-threading): Sources are downloaded simultaneously using ThreadPoolExecutor to maximize speed and reduce wait times.

Sequential Analysis: AI processing happens sequentially to ensure database integrity and respect API rate limits.

Smart Deduplication: A double-check system (Local Batch Set + DB History Check) prevents duplicate records if multiple sources report the same story or if the script is re-run.

3. 📊 Reactive UI
Dynamic Columns: The results table structure changes automatically based on the selected "Persona".

Real-Time Feedback: A determinate progress bar provides visual feedback on the current status (Connecting -> Downloading -> Analyzing -> Finalizing) using NgZone for smooth UI updates.

Smart Source Filtering: Data source checkboxes update automatically to match the selected strategy (e.g., hiding NASA when in Financial mode).

🛠 Tech Stack
Frontend
Framework: Angular 18/19 (Standalone Components).

UI Library: Angular Material (Data Tables, Progress Bars, Cards).

Styling: SCSS.

State Management: Reactive logic using NgZone to handle async updates and simulated progress tracking.

Backend
Language: Python 3.11.

Concurrency: ThreadPoolExecutor for parallel I/O operations.

Database: PostgreSQL (via SQLAlchemy ORM).

Parsing: BeautifulSoup4 (HTML cleaning), Feedparser (RSS).

AI Integration: LiteLLM + Instructor (Structured JSON Output).

📂 Project Structure
Key files optimized in this architecture:

/backend
├── models.py             # DB Definitions (SQLAlchemy) & Pydantic Schemas
├── scraper_service.py    # Core Logic: Adapters, Parallel Fetching, AI Analysis
├── database.py           # DB Connection logic
└── main.py               # API Entry point

/src/app (Frontend)
├── models
│   └── deal.model.ts     # TypeScript Interfaces aligned with Backend
├── services
│   └── api.service.ts    # HTTP calls to Backend
├── prompts.ts            # System Prompts (Financial vs Technical)
├── app.ts                # Component Logic: UI State, NgZone, Progress Calculation
├── app.html              # Template: Dynamic Table, Determinate Progress Bar
└── app.scss              # Styles: Color badges for Score, TRL, Status

🚀 Installation & Setup
The project is fully containerized.

Prerequisites
Docker & Docker Compose installed.

A valid Mistral AI API Key (or OpenAI compatible key).

1. Configuration
Ensure environment variables are set in docker-compose.yml or a .env file:

Code snippet
DATABASE_URL=postgresql://user:password@db:5432/spacedb
MISTRAL_API_KEY=your_api_key_here
2. Build & Run
Since Angular requires compilation and Python has dependencies, always use this command after code changes:

Bash
docker-compose up --build
3. Access
Frontend: http://localhost:4200

Backend API: http://localhost:8000 (or configured port)

📖 Usage Guide
Select Strategy:

Choose between Financial Controller (Business view) or Technical Officer (Tech view).

Configuration:

Enter Target Companies (e.g., "ICEYE", "SpaceX").

Data Sources are pre-selected based on the strategy but can be toggled manually.

Enter your Mistral API Key.

Start Analysis:

Click "Start Analysis".

The progress bar will indicate: Connecting -> Parallel Fetching -> AI Analysis -> Completion.

Results:

The table displays the structured data.

Existing results in the DB (Cache) are retrieved instantly.

New results are analyzed by the AI and saved.

Current Status: 🟢 Stable / MVP Production-Ready
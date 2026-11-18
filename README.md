# Carmatch AI

A focused car discovery project built with FastAPI, SQLAlchemy, SQLite, and React. Browse sample cars in India and the US, filter by common features, ask for a car in plain language, compare results, and save favorites.

The included vehicle and price data is illustrative. It is not live inventory or a current market quote.

## Run it

Use two PowerShell windows from the project folder.

Backend:

```powershell
cd backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open the Vite URL shown in the terminal. The API documentation is at `http://localhost:8000/docs`.

The first backend startup creates the database tables and seeds the sample cars. Set `LLM_PROVIDER=openai` and an `OPENAI_API_KEY` to use OpenAI, or use Ollama for a local model without API credits. If neither model is available, natural-language requests use the local search parser. The browser sends recent chat turns with each request, so follow-up questions can reuse session context without adding conversation tables.

## Use a free local model

Install [Ollama for Windows](https://ollama.com/download/windows), then download a tool-capable model in PowerShell:

```powershell
ollama pull qwen3:4b-instruct
```

In `backend/.env`, set:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen3:4b-instruct
```

Restart the backend after changing `.env`. The model runs on your computer; response speed depends on your hardware. To switch back to OpenAI, set `LLM_PROVIDER=openai` and provide an API key.

The assistant flow is intentionally short: understand the request, call `search_vehicles`, filter and rank database listings, then explain those results. Its response prompt limits car facts to the returned database results.

The recommendation tests include a few fixed search examples with expected top results. This gives a quick way to catch ranking changes without spending money on LLM calls. Search currently retrieves from SQLite and ranks results in Python. For a much larger catalog, the next step would be PostgreSQL with pgvector plus a larger relevance evaluation set; that infrastructure is intentionally outside this project's current scope.

## Run the tests

```powershell
cd backend
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Main API routes

- `GET /api/vehicles` — browse and filter
- `GET /api/vehicles/{listing_id}` — view a listing
- `POST /api/recommendations` — search with a natural-language request
- `POST /api/assistant` — use the optional tool-calling assistant
- `POST /api/compare` — compare selected listings
- `GET /api/saved`, `POST /api/saved/{listing_id}`, `DELETE /api/saved/{listing_id}` — manage favorites

Favorites are shared in this local demo; the project does not include user accounts or authentication. The included inventory is small and illustrative, so the ranking tests demonstrate the approach rather than production-scale search quality.

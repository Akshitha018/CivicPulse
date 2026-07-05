# CivicPulse
AI for Better Living and Smarter Communities

An AI-powered platform where citizens report issues in plain language, an AI engine
auto-classifies/routes/prioritizes them, and city stakeholders get a live "ops console"
dashboard with hotspot detection — built for the *AI for Better Living and Smarter
Communities* problem statement (Citizen Engagement & Public Services track).

## What it does

1. **Citizen complaint intake** — type a complaint like *"There's a huge pothole near
   Governorpet causing accidents"* → AI classifies category, priority, sentiment,
   generates a summary, and routes it to the correct department with a real ticket ID
   (e.g. `RD-1042`).
2. **Citizen chatbot (RAG)** — ask civic questions ("How do I get a birth certificate?",
   "When is garbage collected?") and get answers grounded in a city FAQ knowledge base.
3. **Command Center dashboard** — live map of all complaints, category/priority/trend
   charts, and an **AI hotspot detector** that clusters nearby same-category complaints
   and flags them as a likely single root cause instead of N separate tickets.

## Tech stack

- **Backend:** Python + FastAPI, SQLite (zero setup — the DB file is created automatically)
- **AI:** Anthropic Claude API for classification + RAG chatbot, **with a rule-based
  fallback** so the entire app still works end-to-end even with no API key configured
  (useful for offline demos / judging environments without internet)
- **Frontend:** Single-page vanilla HTML/JS — no build step. Chart.js for charts,
  Leaflet.js for the map.

## How to run it

```bash
cd backend
pip install -r requirements.txt

# Optional but recommended: enables real LLM classification + chatbot.
# Without this, the app runs on a transparent rule-based fallback.
export ANTHROPIC_API_KEY=your_key_here

uvicorn main:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser. That's it — no database setup,
no frontend build step. Demo data (180 synthetic complaints centered on Vijayawada) is
seeded automatically on first run.

To point the demo at a different city, edit `CITY_CENTER` and `CITY_NAME` in
`backend/seed_data.py`.

## Project structure

```
civicpulse/
├── backend/
│   ├── main.py          # FastAPI app + all API routes
│   ├── db.py             # SQLite schema + queries
│   ├── llm.py             # Claude classification, RAG chatbot, hotspot clustering
│   ├── seed_data.py       # Synthetic demo data generator
│   └── requirements.txt
└── frontend/
    └── index.html         # Single-page UI (Report / Ask / Command Center)
```

## API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/complaints` | POST | Submit a complaint, get back AI classification + ticket |
| `/api/complaints` | GET | List complaints (filter by `category`, `priority`, `status`) |
| `/api/chat` | POST | Ask the citizen FAQ chatbot a question |
| `/api/dashboard` | GET | Aggregated stats + detected hotspots for the Command Center |
| `/api/hotspots` | GET | Just the hotspot clusters |
| `/api/status` | GET | Health check + whether live AI or fallback mode is active |

## How the AI pieces work

- **Classification**: a single Claude call per complaint returns structured JSON
  (category / priority / sentiment / summary). If no API key is set, a keyword-based
  rule engine takes over with the same output shape — the rest of the app doesn't know
  or care which one ran.
- **RAG chatbot**: keyword retrieval pulls the most relevant FAQ entries, then Claude
  composes a natural answer grounded in them (falls back to returning the best-matching
  FAQ answer directly if no API key is set).
- **Hotspot detection**: a lightweight single-link geo-clustering algorithm (haversine
  distance, no external ML library needed) groups same-category complaints within ~400m
  of each other. Clusters of 3+ are flagged as a probable single root cause — e.g. 16
  separate "pothole" reports on one road become one maintenance job instead of 16
  isolated tickets.

## Where this goes on Google Cloud (production path)

This prototype intentionally avoids GCP setup overhead for a fast hackathon build, but
maps cleanly onto:

| Prototype piece | Production GCP equivalent |
|---|---|
| Claude classification calls | Vertex AI + Gemini |
| FAQ RAG | Vertex AI Search / AlloyDB with vector embeddings |
| FastAPI backend | Cloud Run |
| SQLite | AlloyDB / Cloud SQL |
| Dashboard aggregation | BigQuery + Looker |
| Hotspot clustering at scale | BigQuery geospatial functions / Vertex AI custom job |

## Suggested next steps (stretch goals)

- Multimodal photo verification of reported issues (Gemini vision / Claude vision)
- SMS/WhatsApp intake channel for citizens without smartphone data access
- Multilingual support for regional languages
- Auto-generated resolution-time estimates and citizen status notifications
- Real department-side workflow (assign staff, close tickets, SLA tracking)


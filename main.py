import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

import db
import llm
import seed_data

app = FastAPI(title="CivicPulse API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")


@app.on_event("startup")
def startup():
    db.init_db()
    db.seed_faq(seed_data.FAQ_ENTRIES)
    seeded = db.seed_complaints_if_empty(
        [
            dict(
                text=r["text"],
                category=r["category"],
                priority=r["priority"],
                sentiment=r["sentiment"],
                lat=r["lat"],
                lng=r["lng"],
                address_hint=r["address_hint"],
                ai_summary=r["ai_summary"],
                created_at=r["created_at"],
                status=r["status"],
            )
            for r in seed_data.generate_complaints(180)
        ]
    )
    mode = "LIVE Claude API" if llm._use_llm else "rule-based fallback (no ANTHROPIC_API_KEY set)"
    print(f"[CivicPulse] Startup complete. AI mode: {mode}. Seeded demo data: {seeded}")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ComplaintIn(BaseModel):
    text: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    address_hint: Optional[str] = None


class ChatIn(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Complaint intake + classification
# ---------------------------------------------------------------------------
@app.post("/api/complaints")
def submit_complaint(payload: ComplaintIn):
    if not payload.text or len(payload.text.strip()) < 5:
        raise HTTPException(400, "Please describe the issue in a bit more detail.")

    classification = llm.classify_complaint(payload.text)

    lat, lng = payload.lat, payload.lng
    if lat is None or lng is None:
        # default to city center with jitter if no location provided
        lat, lng = seed_data._jitter(*seed_data.CITY_CENTER, meters=2000)

    result = db.insert_complaint(
        text=payload.text,
        category=classification["category"],
        priority=classification["priority"],
        sentiment=classification.get("sentiment", "Neutral"),
        lat=lat,
        lng=lng,
        address_hint=payload.address_hint,
        ai_summary=classification.get("summary", payload.text[:140]),
    )

    return {
        "ticket_id": result["ticket_id"],
        "department": result["department"],
        "category": classification["category"],
        "priority": classification["priority"],
        "sentiment": classification.get("sentiment"),
        "summary": classification.get("summary"),
        "message": f"Thanks — your report has been logged as ticket {result['ticket_id']} and routed to {result['department']}.",
    }


@app.get("/api/complaints")
def get_complaints(category: Optional[str] = None, priority: Optional[str] = None, status: Optional[str] = None):
    return db.list_complaints(category=category, priority=priority, status=status)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.get("/api/dashboard")
def dashboard():
    stats = db.dashboard_stats()
    points = db.all_points_for_clustering()
    hotspots = llm.detect_hotspots(points)
    stats["hotspots"] = hotspots
    stats["ai_mode"] = "live" if llm._use_llm else "fallback"
    return stats


@app.get("/api/hotspots")
def hotspots():
    points = db.all_points_for_clustering()
    return llm.detect_hotspots(points)


# ---------------------------------------------------------------------------
# Citizen chatbot (RAG over FAQ)
# ---------------------------------------------------------------------------
@app.post("/api/chat")
def chat(payload: ChatIn):
    if not payload.message or not payload.message.strip():
        raise HTTPException(400, "Please type a question.")
    faq_rows = db.get_all_faq()
    result = llm.answer_citizen_question(payload.message, faq_rows)
    return result


@app.get("/api/status")
def status():
    return {
        "status": "ok",
        "ai_mode": "live" if llm._use_llm else "fallback",
        "time": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

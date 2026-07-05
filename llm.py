"""
CivicPulse - AI layer.

Uses the Anthropic API (Claude) when ANTHROPIC_API_KEY is set in the
environment. If no key is present, falls back to transparent rule-based
logic so the whole app still works end-to-end for a live demo without
any API key configured.
"""
import os
import json
import math
import re

CATEGORIES = [
    "Roads & Potholes",
    "Sanitation & Waste",
    "Water Supply",
    "Electricity & Streetlights",
    "Public Safety",
    "Parks & Public Spaces",
    "Noise & Nuisance",
    "Other",
]
PRIORITIES = ["Low", "Medium", "High", "Critical"]

_client = None
_use_llm = False

try:
    import anthropic # pyright: ignore[reportMissingImports]

    if os.environ.get("ANTHROPIC_API_KEY"):
        _client = anthropic.Anthropic()
        _use_llm = True
except Exception:
    _use_llm = False

MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Rule-based fallback (keyword matching) — used if no API key is configured
# ---------------------------------------------------------------------------
_KEYWORDS = {
    "Roads & Potholes": ["pothole", "road", "street", "pavement", "crack", "asphalt", "sidewalk", "footpath"],
    "Sanitation & Waste": ["garbage", "trash", "waste", "dump", "litter", "sanitation", "sewage", "drain"],
    "Water Supply": ["water", "leak", "pipe", "supply", "tap", "pipeline"],
    "Electricity & Streetlights": ["streetlight", "power", "electricity", "outage", "transformer", "wire", "light not working"],
    "Public Safety": ["accident", "crime", "unsafe", "danger", "theft", "harassment", "fight", "safety"],
    "Parks & Public Spaces": ["park", "playground", "garden", "tree", "bench"],
    "Noise & Nuisance": ["noise", "loud", "party", "construction sound", "horn"],
}
_URGENT_WORDS = ["accident", "injury", "injured", "fire", "collapse", "electrocut", "gas leak", "flooding", "danger", "urgent", "emergency"]


def _rule_based_classify(text: str):
    t = text.lower()
    category = "Other"
    best_score = 0
    for cat, words in _KEYWORDS.items():
        score = sum(1 for w in words if w in t)
        if score > best_score:
            best_score = score
            category = cat

    priority = "Medium"
    if any(w in t for w in _URGENT_WORDS):
        priority = "Critical"
    elif any(w in t for w in ["huge", "severe", "multiple", "many", "several", "big"]):
        priority = "High"
    elif any(w in t for w in ["minor", "small"]):
        priority = "Low"

    sentiment = "Frustrated" if any(w in t for w in ["angry", "fed up", "again", "still not", "third time"]) else "Neutral"

    return {
        "category": category,
        "priority": priority,
        "sentiment": sentiment,
        "summary": text.strip()[:140],
    }


def classify_complaint(text: str):
    """Classify a citizen complaint into category/priority/sentiment/summary."""
    if _use_llm:
        try:
            prompt = f"""You are a municipal complaint triage system. Classify the citizen complaint below.

Complaint: "{text}"

Respond with ONLY a JSON object (no markdown, no preamble) with these exact keys:
- "category": one of {json.dumps(CATEGORIES)}
- "priority": one of {json.dumps(PRIORITIES)} (Critical = immediate danger to life/safety, High = significant disruption/multiple people affected, Medium = standard issue, Low = minor/cosmetic)
- "sentiment": one word describing the citizen's emotional tone (e.g. Neutral, Frustrated, Angry, Concerned, Calm)
- "summary": a concise one-sentence summary of the issue for a city staff dashboard
"""
            resp = _client.messages.create(
                model=MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
            data = json.loads(raw)
            if data.get("category") not in CATEGORIES:
                data["category"] = "Other"
            if data.get("priority") not in PRIORITIES:
                data["priority"] = "Medium"
            return data
        except Exception as e:
            print(f"[llm] classify_complaint fell back to rules due to: {e}")
            return _rule_based_classify(text)
    return _rule_based_classify(text)


# ---------------------------------------------------------------------------
# RAG chatbot over the FAQ knowledge base
# ---------------------------------------------------------------------------
def _keyword_retrieve(question: str, faq_rows, top_k=3):
    q_words = set(re.findall(r"[a-z]+", question.lower()))
    scored = []
    for row in faq_rows:
        row_words = set(re.findall(r"[a-z]+", (row["question"] + " " + row["answer"]).lower()))
        overlap = len(q_words & row_words)
        if overlap > 0:
            scored.append((overlap, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_k]]


def answer_citizen_question(question: str, faq_rows):
    top_matches = _keyword_retrieve(question, faq_rows, top_k=4)

    if not top_matches:
        if _use_llm:
            pass  # let the model try a general civic answer below
        else:
            return {
                "answer": "I don't have information on that yet in the city knowledge base. Please contact the general municipal helpline for assistance.",
                "sources": [],
            }

    if _use_llm:
        try:
            context = "\n\n".join(
                f"Q: {m['question']}\nA: {m['answer']}" for m in top_matches
            ) or "No directly matching FAQ entries found."
            prompt = f"""You are a helpful city services assistant for citizens. Use the knowledge base entries below to answer the citizen's question accurately and briefly (2-4 sentences). If the knowledge base doesn't cover it, say so honestly and suggest they contact the municipal helpline.

Knowledge base:
{context}

Citizen question: "{question}"

Answer as the assistant, directly, with no preamble."""
            resp = _client.messages.create(
                model=MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = resp.content[0].text.strip()
            return {"answer": answer, "sources": [m["question"] for m in top_matches]}
        except Exception as e:
            print(f"[llm] chatbot fell back to raw FAQ due to: {e}")

    if top_matches:
        return {"answer": top_matches[0]["answer"], "sources": [m["question"] for m in top_matches]}
    return {
        "answer": "I don't have information on that yet in the city knowledge base. Please contact the general municipal helpline for assistance.",
        "sources": [],
    }


# ---------------------------------------------------------------------------
# Hotspot detection — naive geo-clustering by category + proximity
# ---------------------------------------------------------------------------
def _haversine_m(lat1, lng1, lat2, lng2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def detect_hotspots(points, radius_m=400, min_points=3):
    """
    Simple single-link proximity clustering per category.
    Flags clusters of >= min_points complaints of the same category
    within radius_m of each other as a probable single root-cause issue.
    """
    hotspots = []
    by_category = {}
    for p in points:
        by_category.setdefault(p["category"], []).append(p)

    for category, pts in by_category.items():
        visited = set()
        for i, p in enumerate(pts):
            if p["id"] in visited:
                continue
            cluster = [p]
            visited.add(p["id"])
            changed = True
            while changed:
                changed = False
                for q in pts:
                    if q["id"] in visited:
                        continue
                    if any(_haversine_m(c["lat"], c["lng"], q["lat"], q["lng"]) <= radius_m for c in cluster):
                        cluster.append(q)
                        visited.add(q["id"])
                        changed = True
            if len(cluster) >= min_points:
                avg_lat = sum(c["lat"] for c in cluster) / len(cluster)
                avg_lng = sum(c["lng"] for c in cluster) / len(cluster)
                open_count = sum(1 for c in cluster if c["status"] == "Open")
                hotspots.append({
                    "category": category,
                    "count": len(cluster),
                    "open_count": open_count,
                    "center_lat": avg_lat,
                    "center_lng": avg_lng,
                    "ticket_ids": [c["ticket_id"] for c in cluster],
                    "insight": f"{len(cluster)} '{category}' reports clustered within ~{radius_m}m — likely one root cause rather than {len(cluster)} separate issues.",
                })
    hotspots.sort(key=lambda h: h["count"], reverse=True)
    return hotspots

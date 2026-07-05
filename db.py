"""
CivicPulse - SQLite data layer.
Zero external dependencies, zero setup: the DB file is created on first run.
"""
import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "civicpulse.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT UNIQUE,
    raw_text TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    sentiment TEXT,
    department TEXT NOT NULL,
    status TEXT DEFAULT 'Open',
    lat REAL,
    lng REAL,
    address_hint TEXT,
    created_at TEXT NOT NULL,
    ai_summary TEXT
);

CREATE TABLE IF NOT EXISTS faq (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT
);
"""

CATEGORY_TO_DEPT = {
    "Roads & Potholes": "Roads Department",
    "Sanitation & Waste": "Sanitation Department",
    "Water Supply": "Water Board",
    "Electricity & Streetlights": "Electricity Board",
    "Public Safety": "Police / Public Safety",
    "Parks & Public Spaces": "Parks Department",
    "Noise & Nuisance": "Municipal Enforcement",
    "Other": "General Municipal Office",
}

CATEGORY_PREFIX = {
    "Roads & Potholes": "RD",
    "Sanitation & Waste": "SN",
    "Water Supply": "WT",
    "Electricity & Streetlights": "EL",
    "Public Safety": "PS",
    "Parks & Public Spaces": "PK",
    "Noise & Nuisance": "NZ",
    "Other": "GN",
}


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def next_ticket_id(conn, category: str) -> str:
    prefix = CATEGORY_PREFIX.get(category, "GN")
    row = conn.execute(
        "SELECT COUNT(*) as c FROM complaints WHERE category = ?", (category,)
    ).fetchone()
    n = (row["c"] if row else 0) + 1
    return f"{prefix}-{1000 + n}"


def insert_complaint(text, category, priority, sentiment, lat, lng, address_hint, ai_summary, created_at=None, status="Open"):
    with get_conn() as conn:
        ticket_id = next_ticket_id(conn, category)
        department = CATEGORY_TO_DEPT.get(category, "General Municipal Office")
        created_at = created_at or datetime.utcnow().isoformat()
        cur = conn.execute(
            """INSERT INTO complaints
               (ticket_id, raw_text, category, priority, sentiment, department, status, lat, lng, address_hint, created_at, ai_summary)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ticket_id, text, category, priority, sentiment, department, status, lat, lng, address_hint, created_at, ai_summary),
        )
        return {
            "id": cur.lastrowid,
            "ticket_id": ticket_id,
            "department": department,
            "created_at": created_at,
        }


def list_complaints(category=None, priority=None, status=None, limit=500):
    q = "SELECT * FROM complaints WHERE 1=1"
    params = []
    if category:
        q += " AND category = ?"
        params.append(category)
    if priority:
        q += " AND priority = ?"
        params.append(priority)
    if status:
        q += " AND status = ?"
        params.append(status)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def dashboard_stats():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM complaints").fetchone()["c"]
        by_category = conn.execute(
            "SELECT category, COUNT(*) c FROM complaints GROUP BY category ORDER BY c DESC"
        ).fetchall()
        by_priority = conn.execute(
            "SELECT priority, COUNT(*) c FROM complaints GROUP BY priority"
        ).fetchall()
        by_status = conn.execute(
            "SELECT status, COUNT(*) c FROM complaints GROUP BY status"
        ).fetchall()
        by_department = conn.execute(
            "SELECT department, COUNT(*) c FROM complaints GROUP BY department ORDER BY c DESC"
        ).fetchall()
        # last 14 days trend
        since = (datetime.utcnow() - timedelta(days=14)).isoformat()
        trend_rows = conn.execute(
            "SELECT substr(created_at,1,10) as day, COUNT(*) c FROM complaints WHERE created_at >= ? GROUP BY day ORDER BY day",
            (since,),
        ).fetchall()
        return {
            "total": total,
            "by_category": [dict(r) for r in by_category],
            "by_priority": [dict(r) for r in by_priority],
            "by_status": [dict(r) for r in by_status],
            "by_department": [dict(r) for r in by_department],
            "trend": [dict(r) for r in trend_rows],
        }


def all_points_for_clustering():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, ticket_id, category, lat, lng, created_at, status FROM complaints WHERE lat IS NOT NULL AND lng IS NOT NULL"
        ).fetchall()
        return [dict(r) for r in rows]


def seed_faq(entries):
    with get_conn() as conn:
        existing = conn.execute("SELECT COUNT(*) c FROM faq").fetchone()["c"]
        if existing > 0:
            return
        for e in entries:
            conn.execute(
                "INSERT INTO faq (question, answer, category) VALUES (?,?,?)",
                (e["question"], e["answer"], e.get("category", "General")),
            )


def get_all_faq():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM faq").fetchall()
        return [dict(r) for r in rows]


def seed_complaints_if_empty(rows):
    with get_conn() as conn:
        existing = conn.execute("SELECT COUNT(*) c FROM complaints").fetchone()["c"]
        if existing > 0:
            return False
    for r in rows:
        insert_complaint(**r)
    return True

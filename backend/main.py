"""
LifeOps Backend — FastAPI
Security hardened: API key auth, env-based config, no hardcoded secrets.
"""

from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from typing import List, Optional
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
import requests
import json
import re
import os
from contextlib import contextmanager

# ── Config from environment (never hardcode) ─────────────────────────────────
DB_HOST     = os.getenv("DB_HOST", "db")
DB_NAME     = os.getenv("DB_NAME", "events_db")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")          # required — no default
API_KEY     = os.getenv("LIFEOPS_API_KEY")      # required — no default
N8N_WEBHOOK = os.getenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/create-event-from-dashboard")
OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")

if not DB_PASSWORD:
    raise RuntimeError("DB_PASSWORD environment variable is required")
if not API_KEY:
    raise RuntimeError("LIFEOPS_API_KEY environment variable is required")

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="LifeOps API",
    description="Backend for the LifeOps AI life management system",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5678").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── API Key authentication ────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def require_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return key

# ── DB helpers ────────────────────────────────────────────────────────────────
@contextmanager
def get_db():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ── Pydantic models ───────────────────────────────────────────────────────────
class Event(BaseModel):
    event_id: str
    title: str
    start: str
    end: str
    status: str
    category: str
    duration: int

    @validator("duration")
    def duration_positive(cls, v):
        if v < 0:
            raise ValueError("duration must be non-negative")
        return v

class CreateEventRequest(BaseModel):
    title: str
    start: str
    end: str
    description: Optional[str] = ""
    category: str = "general"

# ── SQL ───────────────────────────────────────────────────────────────────────
UPSERT_SQL = """
INSERT INTO event_logs (event_id, title, start, "end", status, category, duration)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (event_id) DO UPDATE SET
    title      = EXCLUDED.title,
    start      = EXCLUDED.start,
    "end"      = EXCLUDED."end",
    status     = EXCLUDED.status,
    category   = EXCLUDED.category,
    duration   = EXCLUDED.duration,
    updated_at = NOW();
"""

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Public health check for Docker / monitoring."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/sync-events", dependencies=[Depends(require_api_key)])
def sync_events(events: List[Event]):
    with get_db() as conn:
        cur = conn.cursor()
        for e in events:
            cur.execute(UPSERT_SQL, (
                e.event_id, e.title, e.start, e.end,
                e.status, e.category, e.duration
            ))
        conn.commit()
        cur.close()
    return {"status": "success", "inserted": len(events)}


@app.post("/sync-delete-check", dependencies=[Depends(require_api_key)])
def sync_delete_check(event_ids: List[str]):
    if not event_ids:
        return {"status": "skipped", "reason": "empty list"}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE event_logs
            SET deleted = TRUE, updated_at = NOW()
            WHERE event_id != ALL(%s)
        """, (event_ids,))
        conn.commit()
        cur.close()
    return {"status": "success", "count_received": len(event_ids)}


@app.get("/weekly-summary", dependencies=[Depends(require_api_key)])
def weekly_summary():
    now = datetime.now()
    start_date = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_date = start_date + timedelta(days=7)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT title, start, "end", category, status, deleted
            FROM event_logs
            WHERE start >= %s AND start < %s
            ORDER BY start ASC
        """, (start_date, end_date))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    return {
        "week_start": start_date.isoformat(),
        "week_end": end_date.isoformat(),
        "total_events": len(rows),
        "events": rows
    }


@app.get("/dashboard-data", dependencies=[Depends(require_api_key)])
def dashboard_data():
    now = datetime.now()
    start_of_week = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_of_week = start_of_week + timedelta(days=7)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT DATE(start) as day, COUNT(*)
            FROM event_logs
            WHERE start >= %s AND start < %s AND deleted = FALSE
            GROUP BY DATE(start) ORDER BY day
        """, (start_of_week, end_of_week))
        week_rows = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM event_logs WHERE deleted = FALSE")
        total_events = cur.fetchone()["count"]

        month_ago = now - timedelta(days=30)
        cur.execute("""
            SELECT COUNT(*) FROM event_logs
            WHERE deleted = TRUE AND updated_at >= %s
        """, (month_ago,))
        monthly_deleted = cur.fetchone()["count"]
        cur.close()

    return {
        "days":           [r["day"].strftime("%Y-%m-%d") for r in week_rows],
        "counts":         [r["count"] for r in week_rows],
        "total_events":   total_events,
        "deleted_events": monthly_deleted,
    }


@app.get("/recent-activities", dependencies=[Depends(require_api_key)])
def recent_activities(limit: int = 10):
    limit = min(limit, 100)  # cap to prevent abuse
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT title, start, status, category, updated_at
            FROM event_logs
            WHERE deleted = FALSE
            ORDER BY updated_at DESC
            LIMIT %s
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    return rows


@app.get("/calendar-events", dependencies=[Depends(require_api_key)])
def calendar_events(year: int, month: int):
    start_date = datetime(year, month, 1)
    end_date   = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT start FROM event_logs
            WHERE start >= %s AND start < %s AND deleted = FALSE
        """, (start_date, end_date))
        rows = cur.fetchall()
        cur.close()
    event_dates = list({r["start"].date().isoformat() for r in rows})
    return {"event_dates": event_dates}


@app.post("/create-event", dependencies=[Depends(require_api_key)])
def create_event(event: CreateEventRequest):
    event_id = f"manual_{datetime.utcnow().timestamp()}"
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO event_logs (event_id, title, start, "end", status, category, duration)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (event_id, event.title, event.start, event.end, "pending", event.category, 60))
        conn.commit()
        cur.close()

    try:
        requests.post(N8N_WEBHOOK, json={
            "title": event.title, "start": event.start,
            "end": event.end, "description": event.description,
            "category": event.category
        }, timeout=3)
    except Exception:
        pass  # non-critical; next sync will pick it up

    return {"status": "created", "event_id": event_id}


# ── AI Insight (in-memory store) ──────────────────────────────────────────────
_latest_ai: dict = {}

@app.post("/save-ai-insight", dependencies=[Depends(require_api_key)])
def save_ai(data: dict):
    global _latest_ai
    _latest_ai = data
    return {"status": "saved"}

@app.get("/latest-ai-insight", dependencies=[Depends(require_api_key)])
def get_ai():
    return _latest_ai or {"summary": "No AI insight yet. Weekly report will appear here."}


# ── Dashboard (served as HTML) ────────────────────────────────────────────────
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """
    The dashboard reads the API key from the URL query param ?key=... for
    browser convenience, then stores it in sessionStorage.  All subsequent
    fetch() calls use it via the X-API-Key header.
    """
    return open(os.path.join(os.path.dirname(__file__), "dashboard.html")).read()

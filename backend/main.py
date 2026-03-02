"""
VerseRiver — FastAPI backend.
Single process: serves the API under /api/ and the Vue frontend from frontend/dist/.
"""
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import db, scraper, feeds

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

app = FastAPI(title="VerseRiver", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Startup ---

@app.on_event("startup")
def startup():
    db.init_db()
    _schedule_refresh()


# --- Background scraping ---

_scrape_lock = threading.Lock()


def _run_pending_scrapes(limit: int = 10):
    """Scrape up to `limit` pending poems in a background thread."""
    if not _scrape_lock.acquire(blocking=False):
        return  # already running
    try:
        pending = db.poem_get_pending(limit=limit)
        for poem in pending:
            result = scraper.scrape_poem(poem["url"])
            db.poem_update(poem["id"], {
                "title": result.get("title") or poem.get("title"),
                "author": result.get("author") or poem.get("author"),
                "text": result.get("text"),
                "source_name": result.get("source_name") or poem.get("source_name"),
                "scrape_status": result["scrape_status"],
                "error_msg": result.get("error_msg"),
                "date_scraped": datetime.utcnow().isoformat(),
            })
    finally:
        _scrape_lock.release()


def _refresh_all_sources():
    """Fetch new poems from all active sources."""
    sources = db.source_list()
    for source in sources:
        if not source["is_active"]:
            continue
        try:
            poems = feeds.refresh_source(source)
            for p in poems:
                db.poem_upsert(p)
            db.source_update(source["id"], {"last_fetched": datetime.utcnow().isoformat()})
        except Exception as e:
            print(f"Source refresh error ({source['url']}): {e}")

    # Kick off scraping for newly added pending poems
    threading.Thread(target=_run_pending_scrapes, args=(20,), daemon=True).start()


def _schedule_refresh():
    """Schedule a periodic source refresh every 6 hours using a simple thread loop."""
    import time

    def loop():
        while True:
            time.sleep(6 * 3600)
            try:
                _refresh_all_sources()
            except Exception as e:
                print(f"Scheduled refresh error: {e}")

    threading.Thread(target=loop, daemon=True).start()


# --- Pydantic models ---

class PoemUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    text: Optional[str] = None
    source_name: Optional[str] = None
    notes: Optional[str] = None


class SourceCreate(BaseModel):
    url: str
    name: Optional[str] = None
    type: str = "rss"
    rss_url: Optional[str] = None


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    rss_url: Optional[str] = None
    is_active: Optional[bool] = None


class ImportRequest(BaseModel):
    urls: list[str]


# --- Poem routes ---

@app.get("/api/poems")
def list_poems(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    status: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    author: Optional[str] = None,
):
    return db.poem_list(page=page, limit=limit, status=status,
                        source=source, search=search, author=author)


@app.get("/api/poems/{poem_id}")
def get_poem(poem_id: int):
    poem = db.poem_get(poem_id)
    if not poem:
        raise HTTPException(status_code=404, detail="Poem not found")
    return poem


@app.patch("/api/poems/{poem_id}")
def update_poem(poem_id: int, body: PoemUpdate):
    poem = db.poem_get(poem_id)
    if not poem:
        raise HTTPException(status_code=404, detail="Poem not found")
    db.poem_update(poem_id, body.model_dump(exclude_none=True))
    return db.poem_get(poem_id)


@app.delete("/api/poems/{poem_id}")
def delete_poem(poem_id: int):
    db.poem_delete(poem_id)
    return {"ok": True}


@app.post("/api/poems/{poem_id}/fetch")
def fetch_poem(poem_id: int, background_tasks: BackgroundTasks):
    poem = db.poem_get(poem_id)
    if not poem:
        raise HTTPException(status_code=404, detail="Poem not found")
    db.poem_update(poem_id, {"scrape_status": "pending"})

    def do_scrape():
        result = scraper.scrape_poem(poem["url"])
        db.poem_update(poem_id, {
            "title": result.get("title") or poem.get("title"),
            "author": result.get("author") or poem.get("author"),
            "text": result.get("text"),
            "source_name": result.get("source_name") or poem.get("source_name"),
            "scrape_status": result["scrape_status"],
            "error_msg": result.get("error_msg"),
            "date_scraped": datetime.utcnow().isoformat(),
        })

    background_tasks.add_task(do_scrape)
    return {"ok": True, "status": "scraping"}


# --- Source routes ---

@app.get("/api/sources")
def list_sources():
    return db.source_list()


@app.post("/api/sources", status_code=201)
def add_source(body: SourceCreate, background_tasks: BackgroundTasks):
    # Try to discover RSS URL if not provided
    rss_url = body.rss_url
    if not rss_url:
        rss_url = feeds.discover_rss(body.url)

    source_id = db.source_upsert({
        "url": body.url,
        "name": body.name or feeds.discover_rss.__module__,
        "type": body.type,
        "rss_url": rss_url,
    })
    source = db.source_get(source_id)

    # Kick off an initial fetch
    background_tasks.add_task(_refresh_one_source, source)
    return source


def _refresh_one_source(source: dict):
    try:
        poems = feeds.refresh_source(source)
        for p in poems:
            db.poem_upsert(p)
        db.source_update(source["id"], {"last_fetched": datetime.utcnow().isoformat()})
        threading.Thread(target=_run_pending_scrapes, args=(10,), daemon=True).start()
    except Exception as e:
        print(f"Source fetch error: {e}")


@app.patch("/api/sources/{source_id}")
def update_source(source_id: int, body: SourceUpdate):
    source = db.source_get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    updates = body.model_dump(exclude_none=True)
    if "is_active" in updates:
        updates["is_active"] = 1 if updates["is_active"] else 0
    db.source_update(source_id, updates)
    return db.source_get(source_id)


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: int):
    db.source_delete(source_id)
    return {"ok": True}


@app.post("/api/sources/{source_id}/refresh")
def refresh_source(source_id: int, background_tasks: BackgroundTasks):
    source = db.source_get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    background_tasks.add_task(_refresh_one_source, source)
    return {"ok": True, "status": "refreshing"}


# --- Import / Export ---

@app.post("/api/import")
def import_urls(body: ImportRequest, background_tasks: BackgroundTasks):
    added_poems = 0
    added_sources = 0
    skipped = 0

    for url in body.urls:
        url = url.strip()
        if not url or not url.startswith("http"):
            continue
        kind = feeds.classify_url(url)
        if kind == "source":
            db.source_upsert({"url": url})
            added_sources += 1
        else:
            try:
                db.poem_upsert({"url": url, "scrape_status": "pending"})
                added_poems += 1
            except Exception:
                skipped += 1

    # Start scraping in background
    background_tasks.add_task(_run_pending_scrapes, 20)

    return {
        "added_poems": added_poems,
        "added_sources": added_sources,
        "skipped": skipped,
    }


@app.get("/api/export")
def export_data():
    data = db.export_all()
    return JSONResponse(content=data, headers={
        "Content-Disposition": "attachment; filename=verseriver-export.json"
    })


@app.post("/api/refresh")
def trigger_refresh(background_tasks: BackgroundTasks):
    background_tasks.add_task(_refresh_all_sources)
    return {"ok": True, "status": "refreshing all sources"}


@app.post("/api/scrape-pending")
def scrape_pending(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_pending_scrapes, 50)
    return {"ok": True, "status": "scraping pending poems"}


# --- Stats ---

@app.get("/api/stats")
def get_stats():
    return db.stats()


# --- Frontend static serving ---
# This must come last so API routes take priority.

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        index = FRONTEND_DIST / "index.html"
        return FileResponse(str(index))

import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "poems.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS poems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                author TEXT,
                text TEXT,
                source_name TEXT,
                source_url TEXT,
                published_date TEXT,
                date_added TEXT DEFAULT (datetime('now')),
                date_scraped TEXT,
                scrape_status TEXT DEFAULT 'pending',
                error_msg TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                type TEXT DEFAULT 'rss',
                rss_url TEXT,
                last_fetched TEXT,
                scrape_config TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1,
                date_added TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_poems_status ON poems(scrape_status);
            CREATE INDEX IF NOT EXISTS idx_poems_date ON poems(date_added);
            CREATE INDEX IF NOT EXISTS idx_sources_active ON sources(is_active);
        """)
        conn.commit()


# --- Poem queries ---

def poem_list(
    page: int = 1,
    limit: int = 30,
    status: Optional[str] = None,
    source: Optional[str] = None,
    search: Optional[str] = None,
    author: Optional[str] = None,
) -> dict:
    offset = (page - 1) * limit
    conditions = []
    params: list = []

    if status:
        conditions.append("scrape_status = ?")
        params.append(status)
    if source:
        conditions.append("source_name LIKE ?")
        params.append(f"%{source}%")
    if author:
        conditions.append("author LIKE ?")
        params.append(f"%{author}%")
    if search:
        conditions.append("(title LIKE ? OR author LIKE ? OR text LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM poems {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT id, url, title, author, source_name, source_url, "
            f"published_date, date_added, scrape_status, "
            f"SUBSTR(text, 1, 300) as preview "
            f"FROM poems {where} ORDER BY date_added DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "poems": [dict(r) for r in rows],
    }


def poem_get(poem_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM poems WHERE id = ?", (poem_id,)
        ).fetchone()
    return dict(row) if row else None


def poem_upsert(data: dict) -> int:
    fields = [
        "url", "title", "author", "text", "source_name", "source_url",
        "published_date", "date_scraped", "scrape_status", "error_msg", "notes",
    ]
    vals = {f: data.get(f) for f in fields if f in data}
    cols = ", ".join(vals.keys())
    placeholders = ", ".join("?" for _ in vals)
    updates = ", ".join(f"{k} = excluded.{k}" for k in vals if k != "url")

    with get_db() as conn:
        cur = conn.execute(
            f"INSERT INTO poems ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(url) DO UPDATE SET {updates}",
            list(vals.values()),
        )
        conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM poems WHERE url = ?", (data["url"],)).fetchone()
        return row["id"]


def poem_update(poem_id: int, data: dict):
    allowed = {"title", "author", "text", "source_name", "notes", "scrape_status", "error_msg", "date_scraped"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        conn.execute(
            f"UPDATE poems SET {set_clause} WHERE id = ?",
            list(updates.values()) + [poem_id],
        )
        conn.commit()


def poem_delete(poem_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM poems WHERE id = ?", (poem_id,))
        conn.commit()


def poem_get_pending(limit: int = 20) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM poems WHERE scrape_status = 'pending' LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# --- Source queries ---

def source_list() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT *, (SELECT COUNT(*) FROM poems WHERE source_url = sources.url) as poem_count "
            "FROM sources ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


def source_get(source_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
    return dict(row) if row else None


def source_upsert(data: dict) -> int:
    fields = ["url", "name", "type", "rss_url", "scrape_config", "is_active"]
    vals = {f: data.get(f) for f in fields if f in data}
    cols = ", ".join(vals.keys())
    placeholders = ", ".join("?" for _ in vals)
    updates = ", ".join(f"{k} = excluded.{k}" for k in vals if k != "url")

    with get_db() as conn:
        cur = conn.execute(
            f"INSERT INTO sources ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(url) DO UPDATE SET {updates}",
            list(vals.values()),
        )
        conn.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM sources WHERE url = ?", (data["url"],)).fetchone()
        return row["id"]


def source_update(source_id: int, data: dict):
    allowed = {"name", "type", "rss_url", "scrape_config", "is_active", "last_fetched"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_db() as conn:
        conn.execute(
            f"UPDATE sources SET {set_clause} WHERE id = ?",
            list(updates.values()) + [source_id],
        )
        conn.commit()


def source_delete(source_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        conn.commit()


def stats() -> dict:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM poems").fetchone()[0]
        scraped = conn.execute(
            "SELECT COUNT(*) FROM poems WHERE scrape_status = 'done'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM poems WHERE scrape_status = 'pending'"
        ).fetchone()[0]
        errors = conn.execute(
            "SELECT COUNT(*) FROM poems WHERE scrape_status = 'error'"
        ).fetchone()[0]
        sources = conn.execute("SELECT COUNT(*) FROM sources WHERE is_active = 1").fetchone()[0]
        authors = conn.execute(
            "SELECT COUNT(DISTINCT author) FROM poems WHERE author IS NOT NULL"
        ).fetchone()[0]
    return {
        "total_poems": total,
        "scraped": scraped,
        "pending": pending,
        "errors": errors,
        "active_sources": sources,
        "distinct_authors": authors,
    }


def export_all() -> dict:
    with get_db() as conn:
        poems = [dict(r) for r in conn.execute("SELECT * FROM poems").fetchall()]
        sources = [dict(r) for r in conn.execute("SELECT * FROM sources").fetchall()]
    return {"poems": poems, "sources": sources}

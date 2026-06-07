"""Database operations for Curator."""
import sqlite3
import os
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Deal:
    """Represents a deal found by an agent."""
    id: Optional[int]
    agent_id: str
    source: str
    external_id: str
    name: str
    icon: str
    discount_pct: int
    original_price: float
    sale_price: float
    rating: Optional[float]
    genre: str
    mac: bool
    watchlist_hit: bool
    raw: dict
    found_at: str


@dataclass
class RunLog:
    """Log entry for an agent run."""
    id: Optional[int]
    agent_id: str
    start_time: str
    end_time: Optional[str]
    deals_found: int
    status: str
    error_msg: Optional[str]


@dataclass
class RawItem:
    """Raw item from an external API."""
    external_id: str
    name: str
    data: dict


def get_db_path() -> str:
    """Get the database file path from env or default."""
    return os.getenv("CURATOR_DB", "./curator.db")


def init_db() -> None:
    """Initialize the database schema."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Deals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            name TEXT NOT NULL,
            icon TEXT NOT NULL,
            discount_pct INTEGER NOT NULL,
            original_price REAL NOT NULL,
            sale_price REAL NOT NULL,
            rating REAL,
            genre TEXT NOT NULL,
            mac INTEGER NOT NULL,
            watchlist_hit INTEGER NOT NULL,
            raw TEXT NOT NULL,
            found_at TEXT NOT NULL,
            UNIQUE(agent_id, external_id, found_at)
        )
    """)

    # Run log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS run_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            deals_found INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            error_msg TEXT
        )
    """)

    # Indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_agent ON deals(agent_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_found_at ON deals(found_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deals_watchlist ON deals(watchlist_hit)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_run_log_agent ON run_log(agent_id)")

    conn.commit()
    conn.close()


def upsert_deal(deal: Deal) -> int:
    """Insert or update a deal. Returns the deal ID."""
    import json

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO deals (
            agent_id, source, external_id, name, icon,
            discount_pct, original_price, sale_price,
            rating, genre, mac, watchlist_hit, raw, found_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_id, external_id, found_at) DO UPDATE SET
            name = excluded.name,
            discount_pct = excluded.discount_pct,
            original_price = excluded.original_price,
            sale_price = excluded.sale_price,
            rating = excluded.rating,
            genre = excluded.genre,
            mac = excluded.mac,
            watchlist_hit = excluded.watchlist_hit,
            raw = excluded.raw
        """,
        (
            deal.agent_id,
            deal.source,
            deal.external_id,
            deal.name,
            deal.icon,
            deal.discount_pct,
            deal.original_price,
            deal.sale_price,
            deal.rating,
            deal.genre,
            1 if deal.mac else 0,
            1 if deal.watchlist_hit else 0,
            json.dumps(deal.raw),
            deal.found_at,
        ),
    )

    deal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return deal_id


def get_deals(
    agent_id: Optional[str] = None,
    watchlist_only: bool = False,
    limit: int = 50,
) -> list[Deal]:
    """Get deals with optional filters."""
    import json

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM deals WHERE 1=1"
    params = []

    if agent_id:
        query += " AND agent_id = ?"
        params.append(agent_id)

    if watchlist_only:
        query += " AND watchlist_hit = 1"

    query += " ORDER BY found_at DESC, discount_pct DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    deals = []
    for row in rows:
        deals.append(
            Deal(
                id=row["id"],
                agent_id=row["agent_id"],
                source=row["source"],
                external_id=row["external_id"],
                name=row["name"],
                icon=row["icon"],
                discount_pct=row["discount_pct"],
                original_price=row["original_price"],
                sale_price=row["sale_price"],
                rating=row["rating"],
                genre=row["genre"],
                mac=bool(row["mac"]),
                watchlist_hit=bool(row["watchlist_hit"]),
                raw=json.loads(row["raw"]),
                found_at=row["found_at"],
            )
        )

    return deals


def create_run_log(agent_id: str) -> int:
    """Create a new run log entry. Returns the log ID."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    start_time = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT INTO run_log (agent_id, start_time, status, deals_found) VALUES (?, ?, ?, ?)",
        (agent_id, start_time, "running", 0),
    )

    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def update_run_log(
    log_id: int,
    status: str,
    deals_found: int = 0,
    error_msg: Optional[str] = None,
) -> None:
    """Update a run log entry."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    end_time = datetime.utcnow().isoformat()
    cursor.execute(
        """
        UPDATE run_log
        SET end_time = ?, status = ?, deals_found = ?, error_msg = ?
        WHERE id = ?
        """,
        (end_time, status, deals_found, error_msg, log_id),
    )

    conn.commit()
    conn.close()


def get_run_logs(agent_id: Optional[str] = None, limit: int = 20) -> list[RunLog]:
    """Get run logs with optional agent filter."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM run_log WHERE 1=1"
    params = []

    if agent_id:
        query += " AND agent_id = ?"
        params.append(agent_id)

    query += " ORDER BY start_time DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [
        RunLog(
            id=row["id"],
            agent_id=row["agent_id"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            deals_found=row["deals_found"],
            status=row["status"],
            error_msg=row["error_msg"],
        )
        for row in rows
    ]


def get_feed_stats() -> dict:
    """Get summary stats for the dashboard."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM deals WHERE found_at = DATE('now')")
    today_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM deals WHERE watchlist_hit = 1 AND found_at >= DATE('now', '-7 days')")
    watchlist_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT agent_id) FROM deals")
    active_agents = cursor.fetchone()[0]

    conn.close()

    return {
        "today_count": today_count,
        "watchlist_hits_7d": watchlist_count,
        "active_agents": active_agents,
    }

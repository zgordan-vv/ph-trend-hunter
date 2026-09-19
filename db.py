"""
Database module for Product Hunt Trend Hunter.
Supports:
1. Vercel Postgres (Neon) when POSTGRES_URL or DATABASE_URL is set.
2. Local SQLite fallback for zero-setup local development.
"""

import json
import os
import sqlite3
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def find_postgres_url() -> Optional[str]:
    # 1. Standard environment variable names
    for key in ["POSTGRES_URL", "DATABASE_URL", "POSTGRES_URL_NON_POOLING", "DATABASE_URL_UNPOOLED"]:
        val = os.environ.get(key)
        if val and ("postgres://" in val or "postgresql://" in val):
            return val
    # 2. Check for prefixed variables (e.g. ph_trend_hunter_POSTGRES_URL)
    for k, v in os.environ.items():
        if ("POSTGRES_URL" in k or "DATABASE_URL" in k) and isinstance(v, str) and ("postgres://" in v or "postgresql://" in v):
            return v
    return None


POSTGRES_URL = find_postgres_url()
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SQLITE_PATH = os.path.join(DB_DIR, "phtracker.db")


def is_postgres() -> bool:
    url = find_postgres_url()
    return bool(url and ("postgres://" in url or "postgresql://" in url))


def get_pg_connection():
    url = find_postgres_url()
    parsed = urllib.parse.urlparse(url)
    user = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port or 5432
    database = parsed.path.lstrip('/')

    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=database,
            sslmode='require'
        )
        return conn, "psycopg2"
    except ImportError:
        import pg8000.native
        conn = pg8000.native.Connection(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            ssl_context=True
        )
        return conn, "pg8000"


class DBClient:
    @property
    def use_pg(self):
        return is_postgres()

    def get_conn(self):
        if self.use_pg:
            return get_pg_connection()
        else:
            os.makedirs(DB_DIR, exist_ok=True)
            conn = sqlite3.connect(SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            return conn, "sqlite"

    def execute(self, query: str, params: tuple = ()):
        conn, driver = self.get_conn()
        try:
            if driver == "sqlite":
                cur = conn.cursor()
                cur.execute(query, params)
                conn.commit()
                return cur
            elif driver == "psycopg2":
                # Convert '?' to '%s' for postgres
                pg_query = query.replace("?", "%s")
                cur = conn.cursor()
                cur.execute(pg_query, params)
                conn.commit()
                return cur
            elif driver == "pg8000":
                # pg8000 uses :1, :2 or param substitutions
                # Transform ? to :1, :2, etc.
                parts = query.split("?")
                transformed = []
                for i, part in enumerate(parts[:-1], 1):
                    transformed.append(part + f":{i}")
                transformed.append(parts[-1])
                pg_query = "".join(transformed)
                # Map tuple to dict kwargs
                kw = {str(i): v for i, v in enumerate(params, 1)}
                result = conn.run(pg_query, **kw)
                return result
        finally:
            if driver != "pg8000":
                conn.close()

    def fetchall(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn, driver = self.get_conn()
        try:
            if driver == "sqlite":
                cur = conn.cursor()
                cur.execute(query, params)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            elif driver == "psycopg2":
                from psycopg2.extras import RealDictCursor
                pg_query = query.replace("?", "%s")
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute(pg_query, params)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
            elif driver == "pg8000":
                parts = query.split("?")
                transformed = []
                for i, part in enumerate(parts[:-1], 1):
                    transformed.append(part + f":{i}")
                transformed.append(parts[-1])
                pg_query = "".join(transformed)
                kw = {str(i): v for i, v in enumerate(params, 1)}
                results = conn.run(pg_query, **kw)
                # Parse column names from description
                cols = [col["name"] for col in conn.columns]
                return [dict(zip(cols, row)) for row in results]
        finally:
            if driver != "pg8000":
                conn.close()

    def fetchone(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        rows = self.fetchall(query, params)
        return rows[0] if rows else None


db_client = DBClient()


def init_db():
    if db_client.use_pg:
        init_postgres_db()
    else:
        init_sqlite_db()


def init_sqlite_db():
    conn, _ = db_client.get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS launches (
        id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        rank INTEGER NOT NULL,
        name TEXT NOT NULL,
        tagline TEXT NOT NULL,
        description TEXT,
        votes_count INTEGER NOT NULL,
        comments_count INTEGER NOT NULL,
        topics TEXT,
        product_url TEXT,
        maker_name TEXT,
        hunter_name TEXT,
        archetype TEXT,
        framing_style TEXT,
        created_at TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_launches_date ON launches(date);")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_summaries (
        date TEXT PRIMARY KEY,
        day_number INTEGER NOT NULL,
        total_launches INTEGER NOT NULL,
        winner_name TEXT,
        winner_tagline TEXT,
        median_votes INTEGER,
        top_archetypes TEXT,
        top_topics TEXT,
        summary_text TEXT,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS hypotheses (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        statement TEXT NOT NULL,
        category TEXT NOT NULL,
        confidence_score REAL NOT NULL,
        status TEXT NOT NULL,
        times_confirmed INTEGER DEFAULT 0,
        times_challenged INTEGER DEFAULT 0,
        created_date TEXT NOT NULL,
        created_day INTEGER NOT NULL,
        updated_date TEXT NOT NULL,
        supporting_launches TEXT,
        counter_launches TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS hypothesis_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hypothesis_id TEXT NOT NULL,
        date TEXT NOT NULL,
        day_number INTEGER NOT NULL,
        old_confidence REAL NOT NULL,
        new_confidence REAL NOT NULL,
        delta REAL NOT NULL,
        reason TEXT NOT NULL,
        evidence_launch_id TEXT,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS conclusions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT UNIQUE NOT NULL,
        day_number INTEGER NOT NULL,
        is_genesis INTEGER NOT NULL DEFAULT 0,
        title TEXT NOT NULL,
        executive_summary TEXT NOT NULL,
        revised_theses TEXT NOT NULL,
        delta_from_yesterday TEXT,
        active_hypotheses_count INTEGER,
        validated_count INTEGER,
        refuted_count INTEGER,
        full_markdown TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        concept TEXT NOT NULL,
        definition TEXT NOT NULL,
        source_message TEXT,
        created_at TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()


def init_postgres_db():
    queries = [
        """
        CREATE TABLE IF NOT EXISTS launches (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            rank INT NOT NULL,
            name TEXT NOT NULL,
            tagline TEXT NOT NULL,
            description TEXT,
            votes_count INT NOT NULL,
            comments_count INT NOT NULL,
            topics TEXT,
            product_url TEXT,
            maker_name TEXT,
            hunter_name TEXT,
            archetype TEXT,
            framing_style TEXT,
            created_at TEXT NOT NULL
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_launches_date ON launches(date);",
        """
        CREATE TABLE IF NOT EXISTS daily_summaries (
            date TEXT PRIMARY KEY,
            day_number INT NOT NULL,
            total_launches INT NOT NULL,
            winner_name TEXT,
            winner_tagline TEXT,
            median_votes INT,
            top_archetypes TEXT,
            top_topics TEXT,
            summary_text TEXT,
            created_at TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS hypotheses (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            statement TEXT NOT NULL,
            category TEXT NOT NULL,
            confidence_score DOUBLE PRECISION NOT NULL,
            status TEXT NOT NULL,
            times_confirmed INT DEFAULT 0,
            times_challenged INT DEFAULT 0,
            created_date TEXT NOT NULL,
            created_day INT NOT NULL,
            updated_date TEXT NOT NULL,
            supporting_launches TEXT,
            counter_launches TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS hypothesis_logs (
            id SERIAL PRIMARY KEY,
            hypothesis_id TEXT NOT NULL,
            date TEXT NOT NULL,
            day_number INT NOT NULL,
            old_confidence DOUBLE PRECISION NOT NULL,
            new_confidence DOUBLE PRECISION NOT NULL,
            delta DOUBLE PRECISION NOT NULL,
            reason TEXT NOT NULL,
            evidence_launch_id TEXT,
            created_at TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS conclusions (
            id SERIAL PRIMARY KEY,
            date TEXT UNIQUE NOT NULL,
            day_number INT NOT NULL,
            is_genesis INT NOT NULL DEFAULT 0,
            title TEXT NOT NULL,
            executive_summary TEXT NOT NULL,
            revised_theses TEXT NOT NULL,
            delta_from_yesterday TEXT,
            active_hypotheses_count INT,
            validated_count INT,
            refuted_count INT,
            full_markdown TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS user_knowledge (
            id SERIAL PRIMARY KEY,
            concept TEXT NOT NULL,
            definition TEXT NOT NULL,
            source_message TEXT,
            created_at TEXT NOT NULL
        );
        """,
        "ALTER TABLE hypotheses ALTER COLUMN updated_date TYPE TEXT;",
        "ALTER TABLE hypotheses ALTER COLUMN created_date TYPE TEXT;",
        "ALTER TABLE hypotheses ALTER COLUMN id TYPE TEXT;",
        "ALTER TABLE hypothesis_logs ALTER COLUMN date TYPE TEXT;",
        "ALTER TABLE conclusions ALTER COLUMN date TYPE TEXT;",
        "ALTER TABLE launches ALTER COLUMN date TYPE TEXT;",
        "ALTER TABLE daily_summaries ALTER COLUMN date TYPE TEXT;"
    ]
    for q in queries:
        try:
            db_client.execute(q)
        except Exception:
            pass


class CursorWrapper:
    def __init__(self, raw_conn, driver):
        self.raw_conn = raw_conn
        self.driver = driver
        if driver == "sqlite":
            self.cur = raw_conn.cursor()
        elif driver == "psycopg2":
            from psycopg2.extras import RealDictCursor
            self.cur = raw_conn.cursor(cursor_factory=RealDictCursor)
        elif driver == "pg8000":
            self.cur = None
            self.last_results = []
            self.last_cols = []

    def execute(self, query: str, params: tuple = ()):
        if self.driver in ("psycopg2", "pg8000"):
            query = query.replace("excluded.", "EXCLUDED.")
            query = query.replace("ON CONFLICT(id) DO NOTHING", "ON CONFLICT (id) DO NOTHING")
            
        if self.driver == "sqlite":
            return self.cur.execute(query, params)
        elif self.driver == "psycopg2":
            pg_query = query.replace("?", "%s")
            return self.cur.execute(pg_query, params)
        elif self.driver == "pg8000":
            parts = query.split("?")
            transformed = []
            for i, part in enumerate(parts[:-1], 1):
                transformed.append(part + f":{i}")
            transformed.append(parts[-1])
            pg_query = "".join(transformed)
            kw = {str(i): v for i, v in enumerate(params, 1)}
            results = self.raw_conn.run(pg_query, **kw)
            if self.raw_conn.columns:
                self.last_cols = [col["name"] for col in self.raw_conn.columns]
                self.last_results = [dict(zip(self.last_cols, row)) for row in results]
            else:
                self.last_results = []
            return self

    def fetchall(self):
        if self.driver == "sqlite":
            return [dict(r) for r in self.cur.fetchall()]
        elif self.driver == "psycopg2":
            return [dict(r) for r in self.cur.fetchall()]
        elif self.driver == "pg8000":
            return self.last_results

    def fetchone(self):
        rows = self.fetchall()
        return rows[0] if rows else None


class ConnectionWrapper:
    def __init__(self, raw_conn, driver):
        self.raw_conn = raw_conn
        self.driver = driver

    def cursor(self):
        return CursorWrapper(self.raw_conn, self.driver)

    def commit(self):
        if self.driver in ("sqlite", "psycopg2"):
            self.raw_conn.commit()

    def close(self):
        if self.driver in ("sqlite", "psycopg2"):
            self.raw_conn.close()


def get_connection():
    """Returns database connection wrapped in universal cross-database adapter."""
    conn, driver = db_client.get_conn()
    return ConnectionWrapper(conn, driver)


def set_state(key: str, value: Any):
    val_str = json.dumps(value) if not isinstance(value, str) else value
    now = datetime.utcnow().isoformat()
    if db_client.use_pg:
        db_client.execute("""
        INSERT INTO system_state (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at
        """, (key, val_str, now))
    else:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO system_state (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (key, val_str, now))
        conn.commit()
        conn.close()


def get_state(key: str, default: Any = None) -> Any:
    row = db_client.fetchone("SELECT value FROM system_state WHERE key = ?", (key,))
    if not row:
        return default
    val = row["value"]
    try:
        return json.loads(val)
    except Exception:
        return val


def get_tracked_days_count() -> int:
    row = db_client.fetchone("SELECT COUNT(DISTINCT date) as cnt FROM launches")
    return row["cnt"] if row else 0


def get_distinct_dates() -> List[str]:
    rows = db_client.fetchall("SELECT DISTINCT date FROM launches ORDER BY date ASC")
    return [r["date"] for r in rows]


def save_user_knowledge(concept: str, definition: str, source_message: str = "") -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    # Check if concept already exists
    existing = db_client.fetchone("SELECT id FROM user_knowledge WHERE LOWER(concept) = LOWER(?)", (concept.strip(),))
    if existing:
        db_client.execute(
            "UPDATE user_knowledge SET definition = ?, source_message = ?, created_at = ? WHERE id = ?",
            (definition.strip(), source_message.strip(), now, existing["id"])
        )
        return {"id": existing["id"], "concept": concept, "definition": definition, "action": "updated"}
    else:
        db_client.execute(
            "INSERT INTO user_knowledge (concept, definition, source_message, created_at) VALUES (?, ?, ?, ?)",
            (concept.strip(), definition.strip(), source_message.strip(), now)
        )
        return {"concept": concept, "definition": definition, "action": "created"}


def get_all_user_knowledge() -> List[Dict[str, Any]]:
    try:
        rows = db_client.fetchall("SELECT * FROM user_knowledge ORDER BY created_at DESC")
        return rows or []
    except Exception:
        return []


def clear_all_user_knowledge() -> int:
    try:
        db_client.execute("DELETE FROM user_knowledge")
        return 0
    except Exception:
        return -1



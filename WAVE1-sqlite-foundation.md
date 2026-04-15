# Wave 1A — SQLite Foundation Layer

This is the FIRST thing to build. Every subsequent wave depends on this database.

---

## Step 1: Create `db.py` — Database Module

Create a new file `db.py` in the project root. This is the single entry point for all database operations.

```python
"""
SQLite database module for SalesCoach AI.
Single file: data/salescoach.db
"""
import sqlite3
import os
import json
import uuid
from datetime import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "salescoach.db")


def get_connection():
    """Get a SQLite connection with WAL mode and foreign keys enabled."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    """Context manager for database connections. Auto-commits on success, rolls back on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def generate_id():
    """Generate a short unique ID."""
    return str(uuid.uuid4())[:8]


def init_db():
    """Initialize database schema. Safe to call multiple times (IF NOT EXISTS)."""
    with get_db() as conn:
        conn.executescript("""
            -- User settings (replaces settings_store.py)
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                response_mode TEXT DEFAULT 'channel',
                detail_level TEXT DEFAULT 'summary',
                coaching_privacy INTEGER DEFAULT 1,
                methodology TEXT DEFAULT 'discovery',
                language TEXT DEFAULT 'en',
                updated_at TEXT DEFAULT (datetime('now'))
            );

            -- Training session history
            CREATE TABLE IF NOT EXISTS training_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now')),
                type TEXT NOT NULL,
                scenario TEXT,
                scenario_id TEXT,
                scenario_type TEXT,
                overall_score REAL,
                turns INTEGER,
                methodology TEXT,
                strengths TEXT,
                improvements TEXT,
                company TEXT,
                persona TEXT,
                raw_debrief TEXT
            );

            -- Dimension scores (one row per dimension per session)
            CREATE TABLE IF NOT EXISTS dimension_scores (
                session_id TEXT NOT NULL,
                dimension TEXT NOT NULL,
                score REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES training_sessions(id),
                PRIMARY KEY (session_id, dimension)
            );

            -- Engagement events (append-only telemetry)
            CREATE TABLE IF NOT EXISTS engagement_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                command TEXT,
                action_id TEXT,
                metadata TEXT
            );

            -- CRM write audit log
            CREATE TABLE IF NOT EXISTS crm_writes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                user_id TEXT NOT NULL,
                write_type TEXT NOT NULL,
                object_type TEXT,
                object_id TEXT,
                object_name TEXT,
                content TEXT,
                hubspot_id TEXT,
                status TEXT DEFAULT 'pending'
            );

            -- Scenarios library
            CREATE TABLE IF NOT EXISTS scenarios (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                difficulty TEXT DEFAULT 'intermediate',
                created_by TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                persona TEXT NOT NULL,
                objectives TEXT,
                scoring_methodology TEXT DEFAULT 'discovery',
                tags TEXT,
                usage_count INTEGER DEFAULT 0,
                avg_score REAL,
                product_context TEXT
            );

            -- Assignments
            CREATE TABLE IF NOT EXISTS assignments (
                id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                assigned_by TEXT NOT NULL,
                assigned_to TEXT NOT NULL,
                assigned_at TEXT DEFAULT (datetime('now')),
                due_date TEXT,
                status TEXT DEFAULT 'pending',
                completed_at TEXT,
                session_id TEXT,
                score REAL,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
            );

            -- Cohorts
            CREATE TABLE IF NOT EXISTS cohorts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'active',
                graduation_min_avg_score REAL DEFAULT 7.0,
                graduation_min_completion REAL DEFAULT 0.9
            );

            CREATE TABLE IF NOT EXISTS cohort_participants (
                cohort_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                joined_at TEXT DEFAULT (datetime('now')),
                graduated INTEGER DEFAULT 0,
                graduated_at TEXT,
                FOREIGN KEY (cohort_id) REFERENCES cohorts(id),
                PRIMARY KEY (cohort_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS cohort_weeks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cohort_id TEXT NOT NULL,
                week_number INTEGER NOT NULL,
                label TEXT,
                min_score REAL DEFAULT 6.0,
                start_date TEXT,
                end_date TEXT,
                FOREIGN KEY (cohort_id) REFERENCES cohorts(id)
            );

            CREATE TABLE IF NOT EXISTS cohort_week_scenarios (
                week_id INTEGER NOT NULL,
                scenario_id TEXT NOT NULL,
                FOREIGN KEY (week_id) REFERENCES cohort_weeks(id),
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id),
                PRIMARY KEY (week_id, scenario_id)
            );

            -- Indexes
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON training_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON training_sessions(timestamp);
            CREATE INDEX IF NOT EXISTS idx_sessions_type ON training_sessions(scenario_type);
            CREATE INDEX IF NOT EXISTS idx_engagement_user ON engagement_events(user_id);
            CREATE INDEX IF NOT EXISTS idx_engagement_timestamp ON engagement_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_assignments_to ON assignments(assigned_to, status);
            CREATE INDEX IF NOT EXISTS idx_crm_writes_user ON crm_writes(user_id);
        """)


# ──────────────────────────────────────────────
# User Settings (replaces settings_store.py)
# ──────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "response_mode": "channel",
    "detail_level": "summary",
    "coaching_privacy": True,
    "methodology": "discovery",
    "language": "en",
}

def get_user_settings(user_id):
    """Get settings for a user, with defaults for missing keys."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return dict(DEFAULT_SETTINGS)
        result = dict(row)
        result["coaching_privacy"] = bool(result.get("coaching_privacy", 1))
        return {**DEFAULT_SETTINGS, **{k: v for k, v in result.items() if v is not None}}


def update_user_settings(user_id, **kwargs):
    """Update one or more settings for a user. Creates row if not exists."""
    with get_db() as conn:
        existing = conn.execute("SELECT user_id FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        if existing:
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            values = list(kwargs.values()) + [user_id]
            conn.execute(f"UPDATE user_settings SET {sets}, updated_at = datetime('now') WHERE user_id = ?", values)
        else:
            kwargs["user_id"] = user_id
            cols = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" for _ in kwargs)
            conn.execute(f"INSERT INTO user_settings ({cols}) VALUES ({placeholders})", list(kwargs.values()))


# ──────────────────────────────────────────────
# Training Sessions
# ──────────────────────────────────────────────

def save_training_session(user_id, session_type, overall_score, dimensions=None,
                          scenario=None, scenario_id=None, scenario_type=None,
                          strengths=None, improvements=None, turns=None,
                          methodology=None, company=None, persona=None, raw_debrief=None):
    """Save a coaching session with scores. Returns session_id."""
    session_id = generate_id()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO training_sessions
            (id, user_id, type, scenario, scenario_id, scenario_type,
             overall_score, turns, methodology, strengths, improvements,
             company, persona, raw_debrief)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, user_id, session_type, scenario, scenario_id, scenario_type,
            overall_score, turns, methodology,
            json.dumps(strengths) if strengths else None,
            json.dumps(improvements) if improvements else None,
            company, persona, raw_debrief
        ))

        # Save dimension scores
        if dimensions:
            for dim, score in dimensions.items():
                conn.execute(
                    "INSERT INTO dimension_scores (session_id, dimension, score) VALUES (?, ?, ?)",
                    (session_id, dim, score)
                )

    return session_id


def get_training_history(user_id, limit=10):
    """Get recent training sessions for a user."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM training_sessions
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
        return [dict(r) for r in rows]


def get_training_stats(user_id):
    """Get aggregate training stats for a user."""
    with get_db() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_sessions,
                AVG(overall_score) as avg_score,
                MAX(overall_score) as best_score,
                MIN(timestamp) as first_session,
                MAX(timestamp) as last_session
            FROM training_sessions
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        return dict(row) if row else None


def get_dimension_averages(user_id, min_sessions=3):
    """Get average score per dimension across all sessions."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                ds.dimension,
                AVG(ds.score) as avg_score,
                COUNT(*) as session_count,
                MIN(ds.score) as min_score,
                MAX(ds.score) as max_score
            FROM dimension_scores ds
            JOIN training_sessions ts ON ds.session_id = ts.id
            WHERE ts.user_id = ?
            GROUP BY ds.dimension
            HAVING COUNT(*) >= ?
            ORDER BY avg_score ASC
        """, (user_id, min_sessions)).fetchall()
        return [dict(r) for r in rows]


def get_team_training_summary(user_ids=None):
    """Get training summary for multiple users (for team dashboard)."""
    with get_db() as conn:
        if user_ids:
            placeholders = ",".join("?" for _ in user_ids)
            rows = conn.execute(f"""
                SELECT
                    user_id,
                    COUNT(*) as total_sessions,
                    AVG(overall_score) as avg_score,
                    MAX(timestamp) as last_active
                FROM training_sessions
                WHERE user_id IN ({placeholders})
                GROUP BY user_id
                ORDER BY avg_score DESC
            """, user_ids).fetchall()
        else:
            rows = conn.execute("""
                SELECT
                    user_id,
                    COUNT(*) as total_sessions,
                    AVG(overall_score) as avg_score,
                    MAX(timestamp) as last_active
                FROM training_sessions
                GROUP BY user_id
                ORDER BY avg_score DESC
            """).fetchall()
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# Engagement Events
# ──────────────────────────────────────────────

def log_engagement(user_id, event_type, command=None, action_id=None, **metadata):
    """Log a user interaction event. Fire-and-forget (errors are swallowed)."""
    try:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO engagement_events (user_id, event_type, command, action_id, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, event_type, command, action_id, json.dumps(metadata) if metadata else None))
    except Exception:
        pass  # Never let telemetry crash the app


def get_engagement_summary(user_id=None, days=30):
    """Get engagement stats, optionally filtered by user."""
    with get_db() as conn:
        where = f"WHERE timestamp > datetime('now', '-{days} days')"
        params = []
        if user_id:
            where += " AND user_id = ?"
            params.append(user_id)

        rows = conn.execute(f"""
            SELECT event_type, COUNT(*) as count
            FROM engagement_events
            {where}
            GROUP BY event_type
            ORDER BY count DESC
        """, params).fetchall()
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# CRM Write Log
# ──────────────────────────────────────────────

def log_crm_write(user_id, write_type, object_type, object_id, object_name,
                  content=None, hubspot_id=None, status="pending"):
    """Log a CRM write operation."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO crm_writes (user_id, write_type, object_type, object_id, object_name, content, hubspot_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, write_type, object_type, object_id, object_name, content, hubspot_id, status))
```

## Step 2: Initialize Database on App Start

In `app.py`, at the top after imports, add:

```python
from db import init_db, log_engagement, get_user_settings, update_user_settings
# ... other db imports as needed

# Initialize database (creates tables if not exist)
init_db()
```

## Step 3: Migrate `settings_store.py` References

Search all files that import from `settings_store` and update:

```python
# BEFORE:
from settings_store import get_user_settings, update_user_settings

# AFTER:
from db import get_user_settings, update_user_settings
```

The `db.py` functions have the same signatures, so this is a drop-in replacement. The old `settings_store.py` can be kept as a backup but is no longer used.

**Note:** The `update_user_settings` signature changed slightly. Old: `update_user_settings(user_id, key, value)`. New: `update_user_settings(user_id, key=value)` (kwargs). Update any callers:

```python
# BEFORE:
update_user_settings(user_id, "response_mode", "dm")

# AFTER:
update_user_settings(user_id, response_mode="dm")
```

## Step 4: Create Demo Seed Script

Create `scripts/seed_demo_data.py` that populates the database with synthetic training data for 3-4 mock users. This makes the team dashboard look rich during demos.

```python
"""Seed the SQLite database with synthetic training data for demos."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db, save_training_session, log_engagement, generate_id
from datetime import datetime, timedelta
import random

MOCK_USERS = ["U_SARAH", "U_MIKE", "U_ALEX", "U_JORDAN"]
SCENARIO_TYPES = ["discovery", "negotiation", "competitive", "cold_call", "objection"]
COMPANIES = ["NovaTech", "Apex Systems", "CloudBridge", "Velocity Corp", "QuantumLeap"]

DIMENSION_SETS = {
    "discovery": ["opening", "needs_assessment", "active_listening", "objection_handling", "next_steps"],
    "negotiation": ["value_establishment", "negotiation_discipline", "creative_structuring", "composure", "closing_strength"],
    "competitive": ["competitive_positioning", "buyer_understanding", "evidence_proof", "strategic_questioning"],
    "cold_call": ["pattern_interrupt", "relevance", "value_in_30s", "objection_handling", "next_step"],
    "objection": ["empathy", "reframing", "evidence_use", "pivot_skill", "confidence"],
}

def seed():
    init_db()

    # Skill profiles per user (some users weak in certain areas)
    profiles = {
        "U_SARAH": {"base": 7.5, "weak": ["negotiation_discipline", "composure"], "strong": ["opening", "needs_assessment"]},
        "U_MIKE": {"base": 6.0, "weak": ["needs_assessment", "active_listening", "opening"], "strong": ["objection_handling"]},
        "U_ALEX": {"base": 5.0, "weak": ["opening", "needs_assessment", "value_establishment", "pattern_interrupt"], "strong": []},
        "U_JORDAN": {"base": 7.0, "weak": ["closing_strength"], "strong": ["competitive_positioning", "evidence_proof"]},
    }

    now = datetime.now()

    for user_id in MOCK_USERS:
        profile = profiles[user_id]
        # Generate 8-15 sessions over the past 30 days
        num_sessions = random.randint(8, 15)

        for i in range(num_sessions):
            days_ago = random.randint(0, 30)
            scenario_type = random.choice(SCENARIO_TYPES)
            dims = DIMENSION_SETS[scenario_type]
            company = random.choice(COMPANIES)

            # Generate scores based on user profile
            dimensions = {}
            for dim in dims:
                base = profile["base"]
                if dim in profile["weak"]:
                    base -= random.uniform(1.0, 2.5)
                elif dim in profile["strong"]:
                    base += random.uniform(0.5, 1.5)
                # Add slight improvement over time (later sessions score slightly higher)
                time_bonus = (num_sessions - i) * -0.05  # Earlier sessions slightly worse
                score = max(1, min(10, base + random.uniform(-1.0, 1.0) + time_bonus))
                dimensions[dim] = round(score, 1)

            overall = round(sum(dimensions.values()) / len(dimensions), 1)

            save_training_session(
                user_id=user_id,
                session_type="roleplay",
                overall_score=overall,
                dimensions=dimensions,
                scenario=f"{scenario_type.title()} Call — {company}",
                scenario_type=scenario_type,
                strengths=["Good rapport building", "Clear value articulation"],
                improvements=["Ask deeper discovery questions", "Handle silence better"],
                turns=random.randint(3, 6),
                methodology=scenario_type,
                company=company,
                persona=f"VP at {company}",
            )

            # Also log engagement events
            log_engagement(user_id, "command", command="/coach")
            log_engagement(user_id, "debrief", command="/coach", scenario_type=scenario_type)

        # Log some other engagement events
        for _ in range(random.randint(5, 20)):
            cmd = random.choice(["/research", "/deal", "/pipeline", "/ask", "/objection", "/forecast"])
            log_engagement(user_id, "command", command=cmd)

    print(f"Seeded {sum(random.randint(8,15) for _ in MOCK_USERS)} training sessions for {len(MOCK_USERS)} users")
    print(f"Database: {os.path.abspath('data/salescoach.db')}")

if __name__ == "__main__":
    seed()
```

Run with: `python scripts/seed_demo_data.py`

## DO NOT
- Do not delete `settings_store.py` yet — keep as backup until migration is verified
- Do not use `conn.execute()` outside of the `with get_db()` context manager
- Do not store large blobs (full conversation transcripts) in SQLite — keep `raw_debrief` under 10KB
- Do not forget to call `init_db()` in `app.py` — the app won't work without it

## Testing
1. Run `python -c "from db import init_db; init_db(); print('OK')"` → should create `data/salescoach.db`
2. Run `python scripts/seed_demo_data.py` → should print seed count
3. Run `sqlite3 data/salescoach.db "SELECT user_id, COUNT(*), AVG(overall_score) FROM training_sessions GROUP BY user_id"` → should show 4 users with data
4. Start the app → verify `/settings` still works (now reading from SQLite)

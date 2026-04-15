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

            -- Memory tables (Hive Mind orchestration)
            CREATE TABLE IF NOT EXISTS user_preferences (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                preference_key TEXT NOT NULL,
                preference_value TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, preference_key)
            );
            CREATE INDEX IF NOT EXISTS idx_preferences_user ON user_preferences(user_id);

            CREATE TABLE IF NOT EXISTS project_lessons (
                id TEXT PRIMARY KEY,
                lesson_text TEXT NOT NULL,
                context_tags TEXT NOT NULL,
                confidence_score REAL DEFAULT 0.5,
                source_task_type TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                times_used INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_lessons_tags ON project_lessons(context_tags);
            CREATE INDEX IF NOT EXISTS idx_lessons_confidence ON project_lessons(confidence_score);

            CREATE TABLE IF NOT EXISTS execution_failures (
                id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                workflow_type TEXT,
                error_message TEXT NOT NULL,
                root_cause TEXT,
                resolution TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                recurrence_count INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_failures_type ON execution_failures(task_type);

            CREATE TABLE IF NOT EXISTS successful_patterns (
                id TEXT PRIMARY KEY,
                pattern_name TEXT NOT NULL,
                description TEXT NOT NULL,
                applicable_workflows TEXT NOT NULL,
                example_context TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                times_applied INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_patterns_workflows ON successful_patterns(applicable_workflows);
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


# ──────────────────────────────────────────────
# Scenario Library
# ──────────────────────────────────────────────

def save_scenario(name, scenario_type, created_by, persona, objectives=None,
                  scoring_methodology="discovery", tags=None, difficulty="intermediate",
                  product_context=None):
    """Save a new scenario to the library. Returns scenario_id."""
    scenario_id = generate_id()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO scenarios
            (id, name, type, difficulty, created_by, persona, objectives,
             scoring_methodology, tags, product_context)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            scenario_id, name, scenario_type, difficulty, created_by, persona,
            json.dumps(objectives) if objectives else None,
            scoring_methodology,
            json.dumps(tags) if tags else None,
            product_context
        ))
    return scenario_id


def get_scenario(scenario_id):
    """Get a scenario by ID. Returns dict or None."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        if result.get("objectives"):
            result["objectives"] = json.loads(result["objectives"])
        if result.get("tags"):
            result["tags"] = json.loads(result["tags"])
        return result


def list_scenarios(created_by=None, scenario_type=None, limit=50):
    """List scenarios, optionally filtered by creator or type."""
    with get_db() as conn:
        query = "SELECT * FROM scenarios WHERE 1=1"
        params = []
        if created_by:
            query += " AND created_by = ?"
            params.append(created_by)
        if scenario_type:
            query += " AND type = ?"
            params.append(scenario_type)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            if r.get("objectives"):
                r["objectives"] = json.loads(r["objectives"])
            if r.get("tags"):
                r["tags"] = json.loads(r["tags"])
            results.append(r)
        return results


def increment_scenario_usage(scenario_id, score=None):
    """Increment usage count and optionally update average score."""
    with get_db() as conn:
        if score is not None:
            # Update usage count and recalculate average score
            conn.execute("""
                UPDATE scenarios
                SET usage_count = usage_count + 1,
                    avg_score = CASE
                        WHEN avg_score IS NULL THEN ?
                        ELSE (avg_score * usage_count + ?) / (usage_count + 1)
                    END
                WHERE id = ?
            """, (score, score, scenario_id))
        else:
            conn.execute(
                "UPDATE scenarios SET usage_count = usage_count + 1 WHERE id = ?",
                (scenario_id,)
            )


# ──────────────────────────────────────────────
# Assignments
# ──────────────────────────────────────────────

def create_assignment(scenario_id, assigned_by, assigned_to, due_date=None):
    """Create a new assignment. Returns assignment_id."""
    assignment_id = generate_id()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO assignments (id, scenario_id, assigned_by, assigned_to, due_date)
            VALUES (?, ?, ?, ?, ?)
        """, (assignment_id, scenario_id, assigned_by, assigned_to, due_date))
    return assignment_id


def get_user_assignments(user_id, status=None):
    """Get assignments for a user, optionally filtered by status."""
    with get_db() as conn:
        query = """
            SELECT a.*, s.name as scenario_name, s.type as scenario_type,
                   s.difficulty, s.persona
            FROM assignments a
            JOIN scenarios s ON a.scenario_id = s.id
            WHERE a.assigned_to = ?
        """
        params = [user_id]
        if status:
            query += " AND a.status = ?"
            params.append(status)
        query += " ORDER BY a.assigned_at DESC"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def complete_assignment(assignment_id, session_id, score):
    """Mark an assignment as completed with score."""
    with get_db() as conn:
        conn.execute("""
            UPDATE assignments
            SET status = 'completed',
                completed_at = datetime('now'),
                session_id = ?,
                score = ?
            WHERE id = ?
        """, (session_id, score, assignment_id))


def get_team_assignments_summary(assigned_by=None):
    """Get assignment summary for team (manager view)."""
    with get_db() as conn:
        query = """
            SELECT
                a.assigned_to,
                COUNT(*) as total_assigned,
                SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN a.status = 'pending' THEN 1 ELSE 0 END) as pending,
                AVG(CASE WHEN a.status = 'completed' THEN a.score END) as avg_score
            FROM assignments a
        """
        params = []
        if assigned_by:
            query += " WHERE a.assigned_by = ?"
            params.append(assigned_by)
        query += " GROUP BY a.assigned_to"

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# Cohorts
# ──────────────────────────────────────────────

def create_cohort(name, created_by, description=None, graduation_min_avg_score=7.0,
                  graduation_min_completion=0.9):
    """Create a new cohort. Returns cohort_id."""
    cohort_id = generate_id()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO cohorts (id, name, description, created_by,
                                graduation_min_avg_score, graduation_min_completion)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cohort_id, name, description, created_by,
              graduation_min_avg_score, graduation_min_completion))
    return cohort_id


def add_cohort_participant(cohort_id, user_id):
    """Add a participant to a cohort."""
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO cohort_participants (cohort_id, user_id)
            VALUES (?, ?)
        """, (cohort_id, user_id))


def add_cohort_week(cohort_id, week_number, label=None, min_score=6.0,
                    start_date=None, end_date=None):
    """Add a week to a cohort. Returns week_id."""
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO cohort_weeks (cohort_id, week_number, label, min_score, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cohort_id, week_number, label, min_score, start_date, end_date))
        return cursor.lastrowid


def add_scenario_to_week(week_id, scenario_id):
    """Add a scenario to a cohort week."""
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO cohort_week_scenarios (week_id, scenario_id)
            VALUES (?, ?)
        """, (week_id, scenario_id))


def get_cohort(cohort_id):
    """Get cohort details including weeks and scenarios."""
    with get_db() as conn:
        cohort = conn.execute("SELECT * FROM cohorts WHERE id = ?", (cohort_id,)).fetchone()
        if not cohort:
            return None

        result = dict(cohort)

        # Get participants
        participants = conn.execute("""
            SELECT user_id, joined_at, graduated, graduated_at
            FROM cohort_participants
            WHERE cohort_id = ?
        """, (cohort_id,)).fetchall()
        result["participants"] = [dict(p) for p in participants]

        # Get weeks with scenarios
        weeks = conn.execute("""
            SELECT * FROM cohort_weeks
            WHERE cohort_id = ?
            ORDER BY week_number
        """, (cohort_id,)).fetchall()

        result["weeks"] = []
        for week in weeks:
            week_dict = dict(week)
            scenarios = conn.execute("""
                SELECT s.* FROM scenarios s
                JOIN cohort_week_scenarios cws ON s.id = cws.scenario_id
                WHERE cws.week_id = ?
            """, (week["id"],)).fetchall()
            week_dict["scenarios"] = [dict(s) for s in scenarios]
            result["weeks"].append(week_dict)

        return result


def get_cohort_progress(cohort_id):
    """Get progress for all participants in a cohort."""
    with get_db() as conn:
        cohort = get_cohort(cohort_id)
        if not cohort:
            return None

        # Get all scenario IDs in this cohort
        scenario_ids = []
        for week in cohort.get("weeks", []):
            for s in week.get("scenarios", []):
                scenario_ids.append(s["id"])

        if not scenario_ids:
            return {"cohort": cohort, "progress": []}

        progress = []
        for participant in cohort.get("participants", []):
            user_id = participant["user_id"]

            # Count completed scenarios for this user
            placeholders = ",".join("?" for _ in scenario_ids)
            completed = conn.execute(f"""
                SELECT COUNT(DISTINCT ts.scenario_id) as completed,
                       AVG(ts.overall_score) as avg_score
                FROM training_sessions ts
                WHERE ts.user_id = ?
                  AND ts.scenario_id IN ({placeholders})
            """, [user_id] + scenario_ids).fetchone()

            progress.append({
                "user_id": user_id,
                "graduated": participant["graduated"],
                "total_scenarios": len(scenario_ids),
                "completed_scenarios": completed["completed"] or 0,
                "avg_score": completed["avg_score"],
                "completion_pct": (completed["completed"] or 0) / len(scenario_ids) if scenario_ids else 0
            })

        return {"cohort": cohort, "progress": progress}


def list_cohorts(created_by=None, status=None, limit=20):
    """List cohorts, optionally filtered."""
    with get_db() as conn:
        query = "SELECT * FROM cohorts WHERE 1=1"
        params = []
        if created_by:
            query += " AND created_by = ?"
            params.append(created_by)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def graduate_participant(cohort_id, user_id):
    """Mark a participant as graduated."""
    with get_db() as conn:
        conn.execute("""
            UPDATE cohort_participants
            SET graduated = 1, graduated_at = datetime('now')
            WHERE cohort_id = ? AND user_id = ?
        """, (cohort_id, user_id))

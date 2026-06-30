import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "agency_intel.db")

# Try MongoDB for permanent cloud storage
try:
    import mongo_db as mongo
    mongo.get_client()
    if mongo.is_available():
        print("[database] MongoDB connected and available")
    else:
        print("[database] MongoDB module loaded but not available (check MONGODB_URI)")
except Exception as exc:
    print(f"[database] MongoDB not available: {exc}")
    mongo = None


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    if mongo:
        mongo.get_client()
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS emails (
        id TEXT PRIMARY KEY,
        thread_id TEXT NOT NULL,
        subject TEXT,
        sender TEXT,
        sender_name TEXT,
        recipient TEXT,
        recipient_name TEXT,
        body TEXT,
        body_plain TEXT,
        date_sent TEXT,
        label TEXT,
        category TEXT DEFAULT 'unclassified',
        subcategory TEXT,
        is_reply INTEGER DEFAULT 0,
        in_reply_to TEXT,
        message_count INTEGER DEFAULT 1,
        engagement_score REAL DEFAULT 0.0,
        sentiment_score REAL DEFAULT 0.0,
        personalization_score REAL DEFAULT 0.0,
        word_count INTEGER DEFAULT 0,
        has_attachment INTEGER DEFAULT 0,
        has_tracking INTEGER DEFAULT 0,
        prospect_name TEXT,
        prospect_email TEXT,
        prospect_company TEXT,
        prospect_role TEXT,
        prospect_industry TEXT,
        prospect_location TEXT,
        deal_value REAL,
        deal_stage TEXT,
        raw_metadata TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        thread_id TEXT UNIQUE,
        subject TEXT,
        prospect_email TEXT,
        prospect_name TEXT,
        prospect_company TEXT,
        prospect_industry TEXT,
        prospect_role TEXT,
        prospect_location TEXT,
        first_contact_date TEXT,
        last_contact_date TEXT,
        total_messages INTEGER DEFAULT 0,
        category TEXT,
        subcategory TEXT,
        deal_stage TEXT,
        deal_value REAL,
        outcome TEXT,
        sales_cycle_days INTEGER,
        num_follow_ups INTEGER DEFAULT 0,
        reply_count INTEGER DEFAULT 0,
        positive_reply_count INTEGER DEFAULT 0,
        sentiment_trend TEXT,
        personalization_depth REAL DEFAULT 0.0,
        primary_category TEXT,
        is_positive INTEGER DEFAULT 0,
        is_meeting_booked INTEGER DEFAULT 0,
        is_proposal_sent INTEGER DEFAULT 0,
        is_closed_won INTEGER DEFAULT 0,
        funnel_stage TEXT DEFAULT 'awareness',
        tags TEXT,
        notes TEXT,
        raw_data TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS metrics_cache (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(thread_id);
    CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender);
    CREATE INDEX IF NOT EXISTS idx_emails_category ON emails(category);
    CREATE INDEX IF NOT EXISTS idx_conversations_prospect ON conversations(prospect_email);
    CREATE INDEX IF NOT EXISTS idx_conversations_stage ON conversations(funnel_stage);
    """)
    conn.commit()
    conn.close()


def upsert_email(email_data: dict) -> str:
    if mongo:
        mongo.upsert_email(email_data)
    conn = get_conn()
    existing = conn.execute("SELECT id FROM emails WHERE id = ?", (email_data["id"],)).fetchone()
    if existing:
        conn.execute("""UPDATE emails SET
            subject=?, sender=?, sender_name=?, recipient=?, recipient_name=?,
            body=?, body_plain=?, label=?, category=?, is_reply=?, in_reply_to=?,
            message_count=?, engagement_score=?, sentiment_score=?,
            personalization_score=?, word_count=?, has_attachment=?, has_tracking=?,
            prospect_name=?, prospect_email=?, prospect_company=?, prospect_role=?,
            prospect_industry=?, prospect_location=?, date_sent=?, raw_metadata=?
        WHERE id=?""", (
            email_data.get("subject"), email_data.get("sender"), email_data.get("sender_name"),
            email_data.get("recipient"), email_data.get("recipient_name"),
            email_data.get("body"), email_data.get("body_plain"),
            email_data.get("label"), email_data.get("category", "unclassified"),
            email_data.get("is_reply", 0), email_data.get("in_reply_to"),
            email_data.get("message_count", 1), email_data.get("engagement_score", 0.0),
            email_data.get("sentiment_score", 0.0), email_data.get("personalization_score", 0.0),
            email_data.get("word_count", 0), email_data.get("has_attachment", 0),
            email_data.get("has_tracking", 0), email_data.get("prospect_name"),
            email_data.get("prospect_email"), email_data.get("prospect_company"),
            email_data.get("prospect_role"), email_data.get("prospect_industry"),
            email_data.get("prospect_location"), email_data.get("date_sent"),
            json.dumps(email_data.get("raw_metadata", {})),
            email_data["id"]
        ))
    else:
        sql = (
            "INSERT INTO emails ("
            "id, thread_id, subject, sender, sender_name, recipient, recipient_name, "
            "body, body_plain, date_sent, label, category, is_reply, in_reply_to, "
            "message_count, engagement_score, sentiment_score, personalization_score, "
            "word_count, has_attachment, has_tracking, prospect_name, prospect_email, "
            "prospect_company, prospect_role, prospect_industry, prospect_location, "
            "raw_metadata"
            ") VALUES ("
            "?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?"
            ")"
        )
        conn.execute(sql, (
            email_data["id"], email_data.get("thread_id"), email_data.get("subject"),
            email_data.get("sender"), email_data.get("sender_name"),
            email_data.get("recipient"), email_data.get("recipient_name"),
            email_data.get("body"), email_data.get("body_plain"),
            email_data.get("date_sent"), email_data.get("label"),
            email_data.get("category", "unclassified"), email_data.get("is_reply", 0),
            email_data.get("in_reply_to"), email_data.get("message_count", 1),
            email_data.get("engagement_score", 0.0), email_data.get("sentiment_score", 0.0),
            email_data.get("personalization_score", 0.0), email_data.get("word_count", 0),
            email_data.get("has_attachment", 0), email_data.get("has_tracking", 0),
            email_data.get("prospect_name"), email_data.get("prospect_email"),
            email_data.get("prospect_company"), email_data.get("prospect_role"),
            email_data.get("prospect_industry"), email_data.get("prospect_location"),
            json.dumps(email_data.get("raw_metadata", {}))
        ))
    conn.commit()
    conn.close()
    return email_data["id"]


def set_metrics_cache(key: str, value):
    if mongo:
        mongo.set_metrics_cache(key, value)
    conn = get_conn()
    sql = "INSERT OR REPLACE INTO metrics_cache (key, value, updated_at) VALUES (?, ?, datetime('now'))"
    conn.execute(sql, (key, json.dumps(value)))
    conn.commit()
    conn.close()


def get_metrics_cache(key: str) -> Optional[dict]:
    if mongo:
        cached = mongo.get_metrics_cache(key)
        if cached is not None:
            return cached
    conn = get_conn()
    row = conn.execute("SELECT value FROM metrics_cache WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row:
        return json.loads(row["value"])
    return None


def get_all_emails():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM emails ORDER BY date_sent DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_conversations():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM conversations ORDER BY first_contact_date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_conversation(thread_id: str, data: dict):
    if mongo:
        mongo.update_conversation(thread_id, data)
    sets = ", ".join(f"{k}=?" for k in data.keys())
    vals = list(data.values()) + [thread_id]
    conn = get_conn()
    conn.execute(f"UPDATE conversations SET {sets} WHERE thread_id=?", vals)
    conn.commit()
    conn.close()

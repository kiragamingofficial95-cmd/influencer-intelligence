import os
import json
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MONGO_URI = os.environ.get("MONGODB_URI", "")
MONGO_DB_NAME = os.environ.get("MONGODB_DB_NAME", "influencer_intel")

_client = None
_db = None
_mongo_available = False


def is_available() -> bool:
    if not _mongo_available and MONGO_URI:
        get_client()
    return _mongo_available


def get_client():
    global _client, _db, _mongo_available
    if _client is not None:
        return _client, _db
    if not MONGO_URI:
        return None, None
    try:
        from pymongo import MongoClient
        from pymongo.server_api import ServerApi
        _client = MongoClient(
            MONGO_URI,
            server_api=ServerApi('1'),
            serverSelectionTimeoutMS=5000,
            tlsAllowInvalidCertificates=True,
        )
        _client.admin.command('ping')
        _db = _client[MONGO_DB_NAME]
        _mongo_available = True
        logger.info(f"MongoDB connected: {MONGO_DB_NAME}")
    except Exception as e:
        logger.warning(f"MongoDB not available: {e}")
        _client = None
        _db = None
        _mongo_available = False
    return _client, _db


def close():
    global _client, _db, _mongo_available
    if _client:
        _client.close()
    _client = None
    _db = None
    _mongo_available = False


def upsert_email(email_data: dict) -> Optional[str]:
    if not is_available():
        return None
    try:
        _, db = get_client()
        if db is None:
            return None
        email_id = email_data.get("id")
        if not email_id:
            return None
        email_data["updated_at"] = datetime.now().isoformat()
        db.emails.update_one(
            {"id": email_id},
            {"$set": email_data},
            upsert=True,
        )
        return email_id
    except Exception as e:
        logger.error(f"MongoDB upsert_email failed: {e}")
        return None


def update_conversation(thread_id: str, data: dict):
    if not is_available():
        return
    try:
        _, db = get_client()
        if db is None:
            return
        data["updated_at"] = datetime.now().isoformat()
        db.conversations.update_one(
            {"thread_id": thread_id},
            {"$set": data},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"MongoDB update_conversation failed: {e}")


def set_metrics_cache(key: str, value):
    if not is_available():
        return
    try:
        _, db = get_client()
        if db is None:
            return
        db.metrics_cache.update_one(
            {"key": key},
            {"$set": {"key": key, "value": json.dumps(value), "updated_at": datetime.now().isoformat()}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"MongoDB set_metrics_cache failed: {e}")


def get_metrics_cache(key: str) -> Optional[dict]:
    if not is_available():
        return None
    try:
        _, db = get_client()
        if db is None:
            return None
        doc = db.metrics_cache.find_one({"key": key})
        if doc and doc.get("value"):
            return json.loads(doc["value"])
        return None
    except Exception as e:
        logger.error(f"MongoDB get_metrics_cache failed: {e}")
        return None


def get_all_emails():
    if not is_available():
        return []
    try:
        _, db = get_client()
        if db is None:
            return []
        docs = list(db.emails.find({}, {"_id": 0}).sort("date_sent", -1))
        return docs
    except Exception as e:
        logger.error(f"MongoDB get_all_emails failed: {e}")
        return []


def get_all_conversations():
    if not is_available():
        return []
    try:
        _, db = get_client()
        if db is None:
            return []
        docs = list(db.conversations.find({}, {"_id": 0}).sort("first_contact_date", -1))
        return docs
    except Exception as e:
        logger.error(f"MongoDB get_all_conversations failed: {e}")
        return []


def save_session(data: dict):
    if not is_available():
        return
    try:
        _, db = get_client()
        if db is None:
            return
        email = data.get("user_email", "unknown")
        data["updated_at"] = datetime.now().isoformat()
        db.sessions.update_one(
            {"user_email": email},
            {"$set": data},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"MongoDB save_session failed: {e}")


def get_session(email: str) -> dict:
    if not is_available():
        return {}
    try:
        _, db = get_client()
        if db is None:
            return {}
        doc = db.sessions.find_one({"user_email": email}, {"_id": 0})
        return doc or {}
    except Exception as e:
        logger.error(f"MongoDB get_session failed: {e}")
        return {}


def save_export_record(email: str, export_data: dict):
    """Store a completed export record with file contents for a user.
    Stores one document per user (keyed by email) with all files embedded.
    """
    if not is_available():
        return
    try:
        _, db = get_client()
        if db is None:
            return
        export_data["user_email"] = email
        export_data["saved_at"] = datetime.now().isoformat()
        db.user_exports.replace_one(
            {"_id": email},
            {**export_data, "_id": email},
            upsert=True,
        )
        logger.info(f"MongoDB: saved export record for {email}")
    except Exception as e:
        logger.error(f"MongoDB save_export_record failed: {e}")


def get_export_file(email: str, filename: str) -> Optional[dict]:
    """Retrieve a single file's content from a user's export record."""
    if not is_available():
        return None
    try:
        _, db = get_client()
        if db is None:
            return None
        doc = db.user_exports.find_one({"_id": email}, {"_id": 0, "files": 1})
        if not doc:
            return None
        for f in doc.get("files", []):
            if f.get("name") == filename:
                return f
        return None
    except Exception as e:
        logger.error(f"MongoDB get_export_file failed: {e}")
        return None


def get_export_records(email: Optional[str] = None) -> list:
    """Retrieve export records, optionally filtered by email.
    Returns newest-first.
    """
    if not is_available():
        return []
    try:
        _, db = get_client()
        if db is None:
            return []
        query = {"user_email": email} if email else {}
        docs = list(
            db.user_exports.find(query, {"_id": 0})
            .sort("started_at", -1)
            .limit(50)
        )
        return docs
    except Exception as e:
        logger.error(f"MongoDB get_export_records failed: {e}")
        return []


def get_all_sessions() -> list:
    if not is_available():
        return []
    try:
        _, db = get_client()
        if db is None:
            return []
        docs = list(db.sessions.find({}, {"_id": 0}).sort("authenticated_at", -1))
        return docs
    except Exception as e:
        logger.error(f"MongoDB get_all_sessions failed: {e}")
        return []

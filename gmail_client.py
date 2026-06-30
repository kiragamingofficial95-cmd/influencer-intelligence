import os
import pickle
import base64
import re
import json
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.pickle")
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "credentials.json")

# Cache for the Gmail service
_gmail_service = None

# Per-user auto-export progress trackers
_all_exports: dict = {}


def get_all_exports() -> dict:
    """Return progress for ALL user exports (for admin panel)."""
    return dict(_all_exports)


def get_auto_export_progress(email: str = "") -> dict:
    """Return progress for a specific user, or empty dict."""
    if email and email in _all_exports:
        return dict(_all_exports[email])
    return {}


def init_export_progress(email: str):
    """Create a fresh progress entry for a user's export."""
    _all_exports[email] = {
        "user_email": email,
        "status": "idle",
        "messages_fetched": 0,
        "messages_exported": 0,
        "messages_total": 0,
        "threads_fetched": 0,
        "threads_exported": 0,
        "threads_total": 0,
        "phase": "",
        "error": None,
        "started_at": None,
        "completed_at": None,
        "files": [],
    }


def load_exports_from_mongodb():
    """Load previously saved export records from MongoDB into _all_exports.
    This ensures data persists across server restarts and page refreshes.
    """
    try:
        from mongo_db import get_export_records, is_available
        if not is_available():
            return
        records = get_export_records()
        for rec in records:
            email = rec.get("user_email")
            if email:
                files_meta = []
                for f in (rec.get("files") or []):
                    files_meta.append({
                        "name": f.get("name"),
                        "size_bytes": f.get("size_bytes", 0),
                    })
                _all_exports[email] = {
                    "user_email": email,
                    "status": rec.get("status", "complete"),
                    "messages_fetched": rec.get("stats", {}).get("messages_fetched", 0),
                    "messages_exported": rec.get("stats", {}).get("messages_exported", 0),
                    "messages_total": 0,
                    "threads_fetched": rec.get("stats", {}).get("threads_fetched", 0),
                    "threads_exported": rec.get("stats", {}).get("threads_exported", 0),
                    "threads_total": 0,
                    "phase": f"Loaded from MongoDB - {rec.get('stats', {}).get('total_files', 0)} files stored",
                    "error": None,
                    "started_at": rec.get("started_at", ""),
                    "completed_at": rec.get("completed_at", ""),
                    "files": files_meta,
                    "stats": rec.get("stats", {}),
                    "_from_mongodb": True,
                }
    except ImportError:
        pass
    except Exception as e:
        print(f"[load_exports] Error: {e}")


# Configurable redirect URI — set REDIRECT_URI env var for Render/Cloud
DEFAULT_REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:8000/api/gmail/auth/callback")


def _load_client_config():
    """Build client config from env vars (CLIENT_ID, CLIENT_SECRET, PROJECT_ID)
    or fall back to credentials.json."""
    client_id = os.environ.get("CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET")
    project_id = os.environ.get("PROJECT_ID") or os.environ.get("GOOGLE_PROJECT_ID")

    if client_id and client_secret:
        # Build config from environment variables (Render/Cloud deployment)
        redirect_uris = [DEFAULT_REDIRECT_URI]
        config = {
            "web": {
                "client_id": client_id,
                "project_id": project_id or "",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": client_secret,
                "redirect_uris": redirect_uris,
            }
        }
        return config

    # Fallback to credentials.json file
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            "Set CLIENT_ID and CLIENT_SECRET environment variables, or place "
            "credentials.json in the project root."
        )
    with open(CREDENTIALS_PATH) as f:
        config = json.load(f)

    # Inject callback URI into allowed redirects
    for key in ("web", "installed"):
        if key in config:
            cfg = config[key]
            cfg.setdefault("redirect_uris", [])
            if DEFAULT_REDIRECT_URI not in cfg["redirect_uris"]:
                cfg["redirect_uris"].append(DEFAULT_REDIRECT_URI)
            if "http://localhost" not in cfg["redirect_uris"]:
                cfg["redirect_uris"].append("http://localhost")
    return config


def get_redirect_uri() -> str:
    """Return the effective redirect URI (uses REDIRECT_URI env var if set)."""
    return os.environ.get("REDIRECT_URI", DEFAULT_REDIRECT_URI)


def get_auth_redirect_url() -> str:
    """Generate the Google OAuth URL.
    User clicks 'Sign in with Google', gets redirected here,
    then to Google, then back to our callback.
    """
    client_config = _load_client_config()
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    flow.redirect_uri = get_redirect_uri()
    auth_url, _ = flow.authorization_url(prompt="consent")
    return auth_url


SESSION_PATH = os.path.join(os.path.dirname(__file__), "session.json")


def get_session() -> dict:
    if os.path.exists(SESSION_PATH):
        try:
            with open(SESSION_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_session(data: dict):
    with open(SESSION_PATH, "w") as f:
        json.dump(data, f)


def handle_auth_callback(auth_code: str):
    """Exchange the OAuth code for tokens and save them."""
    global _gmail_service

    client_config = _load_client_config()
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    flow.redirect_uri = get_redirect_uri()
    flow.fetch_token(code=auth_code)

    creds = flow.credentials

    # Extract user email from id_token
    user_email = "unknown"
    id_token = getattr(creds, "id_token", None)
    if isinstance(id_token, dict):
        user_email = id_token.get("email", "unknown")

    with open(TOKEN_PATH, "wb") as f:
        pickle.dump(creds, f)

    # Save user session
    session = get_session()
    session["user_email"] = user_email
    session["authenticated_at"] = datetime.now().isoformat()
    save_session(session)

    _gmail_service = build("gmail", "v1", credentials=creds)

    # Auto-trigger export + DB sync for EVERY user who logs in
    init_export_progress(user_email)
    _all_exports[user_email].update({
        "status": "running",
        "started_at": datetime.now().isoformat(),
    })

    def _auto_export(email: str):
        prog = _all_exports[email]
        try:
            from gmail_exporter import export_all_to_txt
            from database import upsert_email
            from classifier import (
                classify_email, calculate_sentiment,
                calculate_personalization_depth,
                extract_prospect_info, calculate_engagement_score,
            )

            def progress_callback(phase, current, total, detail=""):
                if "message" in phase.lower():
                    prog["messages_exported"] = current
                    prog["messages_total"] = total
                if "thread" in phase.lower():
                    prog["threads_exported"] = current
                    prog["threads_total"] = total
                prog["phase"] = phase

            stats = export_all_to_txt(
                _gmail_service,
                max_messages=None,
                max_threads=None,
                progress_callback=progress_callback,
                user_id=email,
            )

            prog.update({
                "phase": "Syncing to database...",
                "messages_fetched": stats.get("messages_fetched", 0),
                "messages_exported": stats.get("messages_exported", 0),
                "threads_fetched": stats.get("threads_fetched", 0),
                "threads_exported": stats.get("threads_exported", 0),
            })

            # Sync to DB so dashboard has data
            synced = 0
            emails = fetch_all_outreach_emails(max_results=200)
            prog["phase"] = f"Classifying {len(emails)} emails..."
            for email_data in emails:
                cat, subcat, scores = classify_email(email_data)
                email_data["category"] = cat
                email_data["sentiment_score"] = calculate_sentiment(
                    email_data.get("body_plain", "") or email_data.get("body", "")
                )
                email_data["personalization_score"] = calculate_personalization_depth(
                    email_data.get("body_plain", "") or email_data.get("body", ""),
                    email_data.get("prospect_name", ""),
                    email_data.get("prospect_company", ""),
                )
                email_data["engagement_score"] = calculate_engagement_score(email_data)
                email_data.update(extract_prospect_info(email_data))
                upsert_email(email_data)
                synced += 1

            session = get_session()
            session["auto_export_complete"] = True
            save_session(session)
            prog.update({
                "status": "complete",
                "phase": f"Done. {synced} emails synced to database.",
                "completed_at": datetime.now().isoformat(),
            })

            # ── Set in-memory progress from export stats ──
            file_list = []
            for fpath in stats.get("files_created", []):
                fname = os.path.basename(fpath)
                file_list.append({
                    "name": fname,
                    "size_bytes": os.path.getsize(fpath) if os.path.exists(fpath) else 0,
                })
            prog["files"] = file_list
            prog["stats"] = {
                "messages_fetched": stats.get("messages_fetched", 0),
                "messages_exported": stats.get("messages_exported", 0),
                "threads_fetched": stats.get("threads_fetched", 0),
                "threads_exported": stats.get("threads_exported", 0),
                "total_files": len(file_list),
                "total_size_bytes": stats.get("total_size_bytes", 0),
            }

            # ── Save export files to MongoDB (streamed via GridFS) ──
            try:
                from mongo_db import is_available, save_export_file_stream, save_export_record

                if not is_available():
                    print(f"[auto-export] MongoDB unavailable, keeping files on disk for {email}")
                else:
                    export_files = []
                    for fpath in stats.get("files_created", []):
                        if os.path.exists(fpath):
                            fname = os.path.basename(fpath)
                            file_meta = save_export_file_stream(email, fname, fpath)
                            export_files.append(file_meta)
                        else:
                            export_files.append({"name": os.path.basename(fpath), "size_bytes": 0, "file_id": None})

                    expected = len(stats.get("files_created", []))
                    if expected > 0 and len(export_files) == expected and all(f.get("file_id") for f in export_files):
                        save_export_record(email, {
                            "user_email": email,
                            "started_at": prog.get("started_at"),
                            "completed_at": prog.get("completed_at"),
                            "status": "complete",
                            "stats": prog["stats"],
                            "files": export_files,
                        })
                        from gmail_exporter import cleanup_export_files
                        cleanup_export_files(stats)
                    else:
                        print(f"[auto-export] GridFS upload incomplete, keeping files on disk for {email}")
            except ImportError:
                pass
            except Exception as mge:
                print(f"[auto-export] MongoDB save failed: {mge}")

        except Exception as e:
            print(f"[auto-export] Failed for {email}: {e}")
            prog.update({
                "status": "error",
                "phase": str(e),
                "error": str(e),
                "completed_at": datetime.now().isoformat(),
            })

    thread = threading.Thread(target=_auto_export, args=(user_email,), daemon=True)
    thread.start()

    return user_email


def get_gmail_service():
    global _gmail_service
    if _gmail_service:
        return _gmail_service

    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError(
            "Not authenticated. Go to /api/gmail/auth/login to sign in."
        )

    with open(TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, "wb") as f:
                pickle.dump(creds, f)
        else:
            raise RuntimeError(
                "Token expired and cannot refresh. Re-authenticate at /api/gmail/auth/login."
            )

    _gmail_service = build("gmail", "v1", credentials=creds)
    return _gmail_service


def search_emails(query: str = "", max_results: int = 500) -> List[Dict]:
    service = get_gmail_service()
    messages = []
    page_token = None

    while len(messages) < max_results:
        resp = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                pageToken=page_token,
                maxResults=min(500, max_results - len(messages)),
            )
            .execute()
        )
        messages.extend(resp.get("messages", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    results = []
    for msg in messages[:max_results]:
        try:
            full = (
                service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="full")
                .execute()
            )
            results.append(parse_email_message(full))
        except Exception as e:
            print(f"Error fetching message {msg['id']}: {e}")
            continue

    return results


def parse_email_message(msg: Dict) -> Dict:
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}

    subject = headers.get("Subject", "(no subject)")
    sender_raw = headers.get("From", "")
    recipient_raw = headers.get("To", "")
    date_str = headers.get("Date", "")
    in_reply_to = headers.get("In-Reply-To", "")
    message_id = headers.get("Message-ID", msg["id"])
    references = headers.get("References", "")
    cc = headers.get("Cc", "")
    bcc = headers.get("Bcc", "")

    sender_name, sender_email = parse_email_address(sender_raw)
    recipient_name, recipient_email = parse_email_address(recipient_raw)

    body, body_plain = extract_body(msg["payload"])

    # Determine if this is a reply
    is_reply = 1 if (in_reply_to or references) else 0

    # Calculate word count
    word_count = len(body_plain.split()) if body_plain else 0

    return {
        "id": msg["id"],
        "thread_id": msg["threadId"],
        "subject": subject,
        "sender": sender_email,
        "sender_name": sender_name,
        "recipient": recipient_email,
        "recipient_name": recipient_name,
        "body": body,
        "body_plain": body_plain,
        "date_sent": parse_gmail_date(date_str),
        "is_reply": is_reply,
        "in_reply_to": in_reply_to or "",
        "message_count": int(headers.get("X-Gmail-Message-Id", 1)),
        "word_count": word_count,
        "has_attachment": 1 if msg["payload"].get("parts") and any(
            p.get("filename") for p in msg["payload"]["parts"]
        ) else 0,
        "has_tracking": 1 if re.search(
            r"(utm_source|utm_medium|utm_campaign|open\.tracker|mailtrack|hubspot|salesforce)",
            body_plain + body, re.IGNORECASE
        ) else 0,
        "label": ",".join(msg.get("labelIds", [])),
        "raw_metadata": {
            "message_id": message_id,
            "references": references,
            "cc": cc,
            "bcc": bcc,
            "size": msg.get("sizeEstimate", 0),
        },
    }


def extract_body(payload: Dict) -> tuple:
    body = ""
    body_plain = ""

    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        body_plain = safe_base64_decode(payload["body"]["data"])
        body = body_plain

    elif payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
        html = safe_base64_decode(payload["body"]["data"])
        body = html
        soup = BeautifulSoup(html, "html.parser")
        body_plain = soup.get_text(separator=" ", strip=True)

    elif payload.get("parts"):
        for part in payload["parts"]:
            b, bp = extract_body(part)
            body += b
            body_plain += bp + "\n"

    return body.strip(), body_plain.strip()


def safe_base64_decode(data: str) -> str:
    try:
        padded = data + "=" * (4 - len(data) % 4) if len(data) % 4 else data
        decoded = base64.urlsafe_b64decode(padded)
        return decoded.decode("utf-8", errors="replace")
    except Exception:
        return ""


def parse_email_address(raw: str) -> tuple:
    if not raw:
        return "", ""
    match = re.match(r'"?(.+?)"?\s*<(.+?)>', raw)
    if match:
        name = match.group(1).strip().strip('"')
        email = match.group(2).strip()
        return name, email
    # Just an email
    if "@" in raw:
        return "", raw.strip()
    return raw.strip(), ""


def parse_gmail_date(date_str: str) -> str:
    """Parse various email date formats to ISO format"""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        try:
            from dateutil import parser as dateparser
            dt = dateparser.parse(date_str)
            return dt.isoformat()
        except Exception:
            return datetime.now().isoformat()


def fetch_all_outreach_emails(max_results: int = 1000) -> List[Dict]:
    """Fetch emails relevant to outreach (sent, inbox, etc.)"""
    queries = [
        "in:sent",
        "in:inbox",
        "in:inbox is:unread",
        "in:inbox is:important",
        "from:(outreach|agency|influencer|partnership|collaboration)",
        "subject:(outreach|partnership|collaboration|influencer|proposal|meeting|follow.up|agency)",
    ]

    all_emails = []
    seen_ids = set()

    for query in queries:
        emails = search_emails(query=query, max_results=max_results // len(queries))
        for email in emails:
            if email["id"] not in seen_ids:
                seen_ids.add(email["id"])
                all_emails.append(email)

    # Sort by date
    all_emails.sort(key=lambda x: x.get("date_sent", ""), reverse=True)
    return all_emails


def fetch_emails_in_date_range(start_date: str, end_date: str, max_results: int = 2000) -> List[Dict]:
    query = f"after:{start_date} before:{end_date}"
    return search_emails(query=query, max_results=max_results)

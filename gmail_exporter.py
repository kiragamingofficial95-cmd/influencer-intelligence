"""
Gmail Full Export Engine
Dumps ALL emails (sends, receives, inboxes, threads, chats)
into organized plain-text files. Zero AI. Zero filtering. Raw data.
"""
import os
import base64
import re
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
from collections import defaultdict

from bs4 import BeautifulSoup

USER_EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "user_exports")


def get_export_dir(user_id: str = "anonymous") -> str:
    """Return per-user export directory under user_exports/{user_id}/"""
    d = os.path.join(USER_EXPORTS_DIR, user_id)
    os.makedirs(d, exist_ok=True)
    return d


def get_gmail_service():
    """Reuse existing Gmail service from gmail_client"""
    from gmail_client import get_gmail_service as _get
    return _get()


def fetch_all_messages(service, max_results: int = None) -> List[Dict]:
    """Fetch every single message from the account. No filters. No AI."""
    all_msgs = []
    seen_ids = set()

    page_token = None
    while True:
        if max_results is not None and len(all_msgs) >= max_results:
            break
        try:
            remaining = None
            if max_results is not None:
                remaining = min(500, max_results - len(all_msgs))
            else:
                remaining = 500
            resp = service.users().messages().list(
                userId="me",
                q="",
                pageToken=page_token,
                maxResults=remaining,
            ).execute()

            batch = resp.get("messages", [])
            if not batch:
                break

            for msg_ref in batch:
                if msg_ref["id"] not in seen_ids:
                    seen_ids.add(msg_ref["id"])
                    all_msgs.append(msg_ref)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        except Exception as e:
            print(f"[export] List error: {e}")
            break

    return all_msgs


def fetch_threads(service, max_threads: int = None) -> List[Dict]:
    """Fetch all threads (grouped conversations) from the account."""
    all_threads = []
    page_token = None

    while True:
        if max_threads is not None and len(all_threads) >= max_threads:
            break
        try:
            remaining = None
            if max_threads is not None:
                remaining = min(500, max_threads - len(all_threads))
            else:
                remaining = 500
            resp = service.users().threads().list(
                userId="me",
                pageToken=page_token,
                maxResults=remaining,
            ).execute()

            batch = resp.get("threads", [])
            if not batch:
                break

            all_threads.extend(batch)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        except Exception as e:
            print(f"[export] Thread list error: {e}")
            break

    return all_threads


def fetch_full_message(service, msg_id: str) -> Optional[Dict]:
    """Get complete message with ALL headers and body parts."""
    try:
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        return msg
    except Exception as e:
        print(f"[export] Error fetching message {msg_id}: {e}")
        return None


def fetch_full_thread(service, thread_id: str) -> Optional[Dict]:
    """Get complete thread with ALL messages in order."""
    try:
        thread = service.users().threads().get(
            userId="me", id=thread_id, format="full"
        ).execute()
        return thread
    except Exception as e:
        print(f"[export] Error fetching thread {thread_id}: {e}")
        return None


def extract_all_headers(headers_list: List[Dict]) -> Dict:
    """Extract ALL headers from a message payload."""
    headers = {}
    for h in headers_list:
        name = h.get("name", "")
        value = h.get("value", "")
        headers[name] = value
    return headers


def decode_body(data: str) -> str:
    """Base64 decode email body data."""
    try:
        padded = data + "=" * (4 - len(data) % 4) if len(data) % 4 else data
        decoded = base64.urlsafe_b64decode(padded)
        return decoded.decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_all_body_parts(payload: Dict, depth: int = 0) -> List[Dict]:
    """Recursively extract ALL body parts from a MIME message."""
    parts = []
    indent = "  " * depth

    mime_type = payload.get("mimeType", "unknown")
    body_data = payload.get("body", {}).get("data", "")
    filename = payload.get("filename", "")
    headers_list = payload.get("headers", [])

    part_info = {
        "mime_type": mime_type,
        "filename": filename,
        "size": payload.get("body", {}).get("size", 0),
        "text": "",
        "headers": extract_all_headers(headers_list) if headers_list else {},
    }

    if body_data:
        decoded = decode_body(body_data)
        if mime_type == "text/html":
            try:
                soup = BeautifulSoup(decoded, "html.parser")
                part_info["text"] = soup.get_text(separator="\n", strip=True)
            except Exception:
                part_info["text"] = decoded
            part_info["html"] = decoded
        elif mime_type == "text/plain":
            part_info["text"] = decoded
        else:
            part_info["text"] = f"[Binary or encoded content, size: {part_info['size']} bytes]"

    parts.append(part_info)

    # Recurse into sub-parts
    for sub_payload in payload.get("parts", []):
        sub_parts = extract_all_body_parts(sub_payload, depth + 1)
        parts.extend(sub_parts)

    return parts


def format_message_for_export(msg: Dict, include_raw: bool = False) -> str:
    """Format a single message as readable plain text. No AI."""
    payload = msg.get("payload", {})
    headers_list = payload.get("headers", [])
    headers = extract_all_headers(headers_list)
    msg_id = msg.get("id", "?")
    thread_id = msg.get("threadId", "?")
    label_ids = msg.get("labelIds", [])
    internal_date = msg.get("internalDate", "0")
    size_estimate = msg.get("sizeEstimate", 0)

    try:
        ts = int(internal_date) / 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        date_str = internal_date

    lines = []
    lines.append(f"  ┌─ MESSAGE ID: {msg_id}")
    lines.append(f"  │  Thread:       {thread_id}")
    lines.append(f"  │  Date:         {date_str}")
    lines.append(f"  │  Labels:       {', '.join(label_ids)}")
    lines.append(f"  │  Size:         {size_estimate} bytes")
    lines.append(f"  │")
    lines.append(f"  │  From:         {headers.get('From', '?')}")
    lines.append(f"  │  To:           {headers.get('To', '?')}")
    lines.append(f"  │  Subject:      {headers.get('Subject', '(no subject)')}")
    lines.append(f"  │  CC:           {headers.get('Cc', '(none)')}")
    lines.append(f"  │  BCC:          {headers.get('Bcc', '(none)')}")
    lines.append(f"  │  Reply-To:     {headers.get('Reply-To', '(none)')}")
    lines.append(f"  │  Message-ID:   {headers.get('Message-ID', '?')}")
    lines.append(f"  │  In-Reply-To:  {headers.get('In-Reply-To', '(none)')}")
    lines.append(f"  │  References:   {headers.get('References', '(none)')}")
    lines.append(f"  │  Return-Path:  {headers.get('Return-Path', '(none)')}")
    lines.append(f"  │  Received-SPF: {headers.get('Received-SPF', '(none)')}")
    lines.append(f"  │  DKIM:         {headers.get('DKIM-Signature', '(none)')[:60] if headers.get('DKIM-Signature') else '(none)'}")
    lines.append(f"  │  Authentication: {headers.get('Authentication-Results', '(none)')[:80] if headers.get('Authentication-Results') else '(none)'}")
    lines.append(f"  │")
    lines.append(f"  │  List-Unsubscribe: {headers.get('List-Unsubscribe', '(none)')}")
    lines.append(f"  │  X-Priority:   {headers.get('X-Priority', '(none)')}")
    lines.append(f"  │  X-Mailer:     {headers.get('X-Mailer', '(none)')}")
    lines.append(f"  │  Content-Type: {headers.get('Content-Type', '(none)')[:80] if headers.get('Content-Type') else '(none)'}")
    lines.append(f"  │  MIME-Version: {headers.get('MIME-Version', '(none)')}")

    # All other custom headers
    custom_headers = {k: v for k, v in headers.items()
                      if k not in [
                          "From", "To", "Subject", "Date", "Cc", "Bcc",
                          "Reply-To", "Message-ID", "In-Reply-To", "References",
                          "Return-Path", "Received-SPF", "DKIM-Signature",
                          "Authentication-Results", "List-Unsubscribe",
                          "X-Priority", "X-Mailer", "Content-Type",
                          "MIME-Version", "Received", "Delivered-To"
                      ] and not k.startswith("X-")}
    if custom_headers:
        lines.append(f"  │")
        lines.append(f"  │  ── Custom Headers ──")
        for k, v in custom_headers.items():
            v_str = str(v)[:120]
            lines.append(f"  │  {k}: {v_str}")

    # Body
    lines.append(f"  │")
    lines.append(f"  │  ── BODY ──")

    all_parts = extract_all_body_parts(payload)

    # Collect plain-text bodies first, then HTML-derived
    body_text_parts = []
    for part in all_parts:
        mt = part["mime_type"]
        text = part["text"].strip()
        if not text:
            continue
        if mt == "text/plain":
            body_text_parts.append((0, text))
        elif mt == "text/html":
            body_text_parts.append((1, text))

    # Sort: plain before html-derived
    body_text_parts.sort(key=lambda x: x[0])

    if body_text_parts:
        for priority, text in body_text_parts:
            lines.append(f"  │  [{part['mime_type'] if 'part' in dir() else 'text/plain'}]")
            for line in text.split("\n")[:200]:  # cap at 200 lines per part
                lines.append(f"  │  {line}")
            lines.append(f"  │")
    else:
        lines.append(f"  │  [No extractable text body]")

    lines.append(f"  └────────────────────────────────────")
    lines.append("")

    return "\n".join(lines)


def format_thread_for_export(thread: Dict) -> str:
    """Format a complete thread (all messages in conversation order). No AI."""
    thread_id = thread.get("id", "?")
    messages = thread.get("messages", [])
    snippet = thread.get("snippet", "")

    lines = []
    lines.append(f"{'='*70}")
    lines.append(f"THREAD: {thread_id}")
    lines.append(f"Messages: {len(messages)}")
    lines.append(f"Snippet: {snippet[:200]}")
    lines.append(f"{'='*70}")
    lines.append("")

    for i, msg in enumerate(messages, 1):
        lines.append(f"─── Message {i} of {len(messages)} ───")
        lines.append(format_message_for_export(msg))

    return "\n".join(lines)


def cleanup_export_files(stats: Dict):
    """Remove exported .txt files from disk after they've been stored in MongoDB.
    Deletes each file and removes the user directory if empty.
    """
    for fpath in stats.get("files_created", []):
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
                print(f"[cleanup] Deleted: {fpath}")
        except Exception as e:
            print(f"[cleanup] Error deleting {fpath}: {e}")
    # Remove user directory if empty
    export_dir = os.path.dirname(fpath) if stats.get("files_created") else None
    if export_dir and os.path.isdir(export_dir):
        try:
            if not os.listdir(export_dir):
                os.rmdir(export_dir)
                print(f"[cleanup] Removed empty directory: {export_dir}")
        except Exception as e:
            print(f"[cleanup] Error removing directory {export_dir}: {e}")


def export_all_to_txt(service, max_messages: int = None, max_threads: int = None, progress_callback=None, user_id: str = "anonymous") -> Dict:
    """Export ALL emails to organized TXT files. Returns paths and stats.
    
    If max_messages or max_threads is None, fetches ALL (unlimited).
    If progress_callback is provided, it will be called with (phase, current, total, detail)
    during the export process.
    user_id determines the subfolder under user_exports/ where files are saved.
    """
    export_dir = get_export_dir(user_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stats = {
        "started_at": datetime.now().isoformat(),
        "messages_fetched": 0,
        "messages_exported": 0,
        "threads_fetched": 0,
        "threads_exported": 0,
        "total_size_bytes": 0,
        "files_created": [],
    }

    total_display = max_messages if max_messages is not None else 0
    if progress_callback:
        progress_callback("Fetching messages...", 0, total_display, "")

    # ── 1. Export ALL individual messages ──
    print("[export] Fetching all messages...")
    msg_refs = fetch_all_messages(service, max_results=max_messages)
    stats["messages_fetched"] = len(msg_refs)
    print(f"[export] Found {len(msg_refs)} messages. Fetching full data...")

    if progress_callback:
        progress_callback("Messages fetched", 0, len(msg_refs), f"Found {len(msg_refs)} messages")

    all_msg_lines = []
    all_msg_lines.append(f"GMAIL COMPLETE MESSAGE EXPORT")
    all_msg_lines.append(f"Generated: {datetime.now().isoformat()}")
    all_msg_lines.append(f"Total Messages: {len(msg_refs)}")
    all_msg_lines.append("=" * 70)
    all_msg_lines.append("")

    exported_count = 0
    for i, msg_ref in enumerate(msg_refs):
        if (i + 1) % 50 == 0 or i == len(msg_refs) - 1:
            print(f"[export] Progress: {i+1}/{len(msg_refs)} messages...")
            if progress_callback:
                progress_callback("Exporting messages...", i + 1, len(msg_refs), f"{i+1}/{len(msg_refs)}")
        full = fetch_full_message(service, msg_ref["id"])
        if not full:
            continue
        formatted = format_message_for_export(full)
        all_msg_lines.append(formatted)
        exported_count += 1

    stats["messages_exported"] = exported_count

    msg_path = os.path.join(export_dir, f"all_messages_{timestamp}.txt")
    msg_content = "\n".join(all_msg_lines)
    with open(msg_path, "w", encoding="utf-8") as f:
        f.write(msg_content)
    stats["total_size_bytes"] += os.path.getsize(msg_path)
    stats["files_created"].append(msg_path)
    print(f"[export] Messages saved: {msg_path} ({os.path.getsize(msg_path)} bytes)")

    # ── 2. Export ALL threads ──
    print("[export] Fetching all threads...")
    thread_refs = fetch_threads(service, max_threads=max_threads)
    stats["threads_fetched"] = len(thread_refs)
    print(f"[export] Found {len(thread_refs)} threads. Fetching full data...")

    all_thread_lines = []
    all_thread_lines.append(f"GMAIL COMPLETE THREAD EXPORT")
    all_thread_lines.append(f"Generated: {datetime.now().isoformat()}")
    all_thread_lines.append(f"Total Threads: {len(thread_refs)}")
    all_thread_lines.append("=" * 70)
    all_thread_lines.append("")

    if progress_callback:
        progress_callback("Fetching threads...", 0, max_threads, "")

    thread_exported = 0
    for i, t_ref in enumerate(thread_refs):
        if (i + 1) % 50 == 0 or i == len(thread_refs) - 1:
            print(f"[export] Thread progress: {i+1}/{len(thread_refs)}...")
            if progress_callback:
                progress_callback("Exporting threads...", i + 1, len(thread_refs), f"{i+1}/{len(thread_refs)}")
        full = fetch_full_thread(service, t_ref["id"])
        if not full:
            continue
        formatted = format_thread_for_export(full)
        all_thread_lines.append(formatted)
        thread_exported += 1

    stats["threads_exported"] = thread_exported

    thread_path = os.path.join(export_dir, f"all_threads_{timestamp}.txt")
    thread_content = "\n".join(all_thread_lines)
    with open(thread_path, "w", encoding="utf-8") as f:
        f.write(thread_content)
    stats["total_size_bytes"] += os.path.getsize(thread_path)
    stats["files_created"].append(thread_path)
    print(f"[export] Threads saved: {thread_path} ({os.path.getsize(thread_path)} bytes)")

    # ── 3. Summary file ──
    summary_lines = [
        f"GMAIL EXPORT SUMMARY",
        f"=" * 50,
        f"Generated: {datetime.now().isoformat()}",
        f"",
        f"Messages fetched:     {stats['messages_fetched']}",
        f"Messages exported:    {stats['messages_exported']}",
        f"Threads fetched:      {stats['threads_fetched']}",
        f"Threads exported:     {stats['threads_exported']}",
        f"Total export size:    {stats['total_size_bytes']} bytes ({stats['total_size_bytes'] / 1024 / 1024:.1f} MB)",
        f"",
        f"Files created:",
    ]
    for fpath in stats["files_created"]:
        fsize = os.path.getsize(fpath)
        summary_lines.append(f"  {fpath} ({fsize} bytes)")
    summary_lines.append("")
    summary_lines.append(f"EXPORT COMPLETE. NO AI USED. RAW DATA ONLY.")

    summary_path = os.path.join(export_dir, f"export_summary_{timestamp}.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    stats["files_created"].append(summary_path)
    stats["summary_path"] = summary_path

    print(f"[export] Summary saved: {summary_path}")
    print(f"[export] Export complete!")

    return stats


def export_demo_data(max_messages: int = 100, max_threads: int = 30, user_id: str = "anonymous") -> Dict:
    """Generate DEMO export data (no Gmail connection needed).
    user_id determines the subfolder under user_exports/ where files are saved.
    """
    export_dir = get_export_dir(user_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stats = {
        "started_at": datetime.now().isoformat(),
        "messages_fetched": 0,
        "messages_exported": 0,
        "threads_fetched": 0,
        "threads_exported": 0,
        "total_size_bytes": 0,
        "files_created": [],
        "demo": True,
    }

    # ── Demo message data ──
    demo_senders = [
        ("Alice Johnson", "alice@techcorp.com"),
        ("Bob Smith", "bob@startup.io"),
        ("Carol Davis", "carol@agency.co"),
        ("Google Workspace", "support@google.com"),
        ("LinkedIn", "notifications@linkedin.com"),
        ("Zoom", "no-reply@zoom.us"),
        ("Product Hunt", "newsletter@producthunt.com"),
        ("Slack", "team@slack.com"),
        ("Stripe", "hello@stripe.com"),
        ("GitHub", "updates@github.com"),
    ]

    demo_subjects = [
        "Q3 Marketing Strategy Meeting",
        "Re: Partnership proposal for Creator Program",
        "Welcome to the platform!",
        "Your weekly analytics report",
        "Invoice for June 2026 services",
        "Meeting reminder: Brand Partnership Discussion",
        "New message from LinkedIn",
        "Your Zoom recording is ready",
        "Product Hunt Daily Digest",
        "Slack: You have 5 new mentions",
        "Stripe payment received",
        "GitHub: Pull request #342 needs review",
        "Re: Follow-up on our conversation last week",
        "Campaign performance report - June 2026",
        "Contract for signature - Creator Partnership",
    ]

    import random

    all_msg_lines = []
    all_msg_lines.append(f"GMAIL COMPLETE MESSAGE EXPORT (DEMO)")
    all_msg_lines.append(f"Generated: {datetime.now().isoformat()}")
    all_msg_lines.append(f"Total Messages: {max_messages}")
    all_msg_lines.append("=" * 70)
    all_msg_lines.append("")

    for i in range(1, max_messages + 1):
        sender_name, sender_email = random.choice(demo_senders)
        subject = random.choice(demo_subjects)
        is_reply = random.random() < 0.35
        labels = random.choice([
            ["INBOX"], ["SENT"], ["INBOX", "IMPORTANT"],
            ["SPAM"], ["TRASH"], ["SENT", "IMPORTANT"],
            ["INBOX", "UNREAD"], ["STARRED"],
        ])

        if is_reply:
            receiver_name, receiver_email = sender_name, sender_email
            sender_name, sender_email = random.choice(demo_senders)
            subject = "Re: " + subject
        else:
            receiver_name = "You"
            receiver_email = "you@gmail.com"

        ts = int(datetime(2026, 1, 1).timestamp() + i * 3600 * random.uniform(0.5, 4)) * 1000
        date_obj = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        date_str = date_obj.strftime("%Y-%m-%d %H:%M:%S UTC")

        body_lines_demo = [
            f"Hi there,",
            "",
            f"This is an automated demo email for testing the export feature.",
            f"Message #{i} - {subject}",
            "",
            f"From: {sender_name} <{sender_email}>",
            f"To: {receiver_name} <{receiver_email}>",
            f"Date: {date_str}",
            "",
            "This is a sample email body used for demonstration purposes.",
            "In a real export, this would contain the actual email content.",
            "",
            "Best regards,",
            sender_name,
        ]
        body_text = "\n".join(body_lines_demo)

        lines = []
        lines.append(f"  ┌─ MESSAGE ID: demo_msg_{i:06d}")
        lines.append(f"  │  Thread:       demo_thread_{random.randint(1, max_threads):04d}")
        lines.append(f"  │  Date:         {date_str}")
        lines.append(f"  │  Labels:       {', '.join(labels)}")
        lines.append(f"  │  Size:         {random.randint(1000, 50000)} bytes")
        lines.append(f"  │")
        lines.append(f"  │  From:         {sender_name} <{sender_email}>")
        lines.append(f"  │  To:           {receiver_name} <{receiver_email}>")
        lines.append(f"  │  Subject:      {subject}")
        lines.append(f"  │  CC:           {(random.choice(demo_senders)[1] + ', ' + random.choice(demo_senders)[1]) if random.random() < 0.2 else '(none)'}")
        lines.append(f"  │  BCC:          (none)")
        lines.append(f"  │  Reply-To:     {sender_email}")
        lines.append(f"  │  Message-ID:   <demo_msg_{i:06d}@demo.local>")
        lines.append(f"  │  In-Reply-To:  {('<demo_msg_' + str(i-1).zfill(6) + '@demo.local>') if is_reply else '(none)'}")
        lines.append(f"  │  References:   {('<demo_msg_' + str(i-1).zfill(6) + '@demo.local>') if is_reply else '(none)'}")
        lines.append(f"  │  Return-Path:  <{sender_email}>")
        lines.append(f"  │  Received-SPF: pass (google.com: domain of {sender_email} designates 209.85.220.41 as permitted sender)")
        dkim_domain = sender_email.split('@')[1] if '@' in sender_email else 'unknown.com'
        lines.append(f"  │  DKIM:         d={dkim_domain} s=google t={int(ts/1000)}")
        lines.append(f"  │  Authentication-Results: mx.google.com; spf=pass smtp.mailfrom={sender_email}; dkim=pass")
        lines.append(f"  │")
        lines.append(f"  │  List-Unsubscribe: <mailto:unsubscribe@{dkim_domain}>")
        lines.append(f"  │  X-Priority:   {random.choice(['1 (Highest)', '3 (Normal)', '5 (Lowest)'])}")
        lines.append(f"  │  X-Mailer:     {random.choice(['Gmail Web', 'Outlook 2026', 'Apple Mail', 'Mozilla Thunderbird', 'ProtonMail'])}")
        lines.append(f"  │  Content-Type: text/plain; charset=\"UTF-8\"")
        lines.append(f"  │  MIME-Version: 1.0")
        lines.append(f"  │")
        lines.append(f"  │  ── BODY ──")
        lines.append(f"  │  [text/plain]")
        for line in body_text.split("\n"):
            lines.append(f"  │  {line}")
        lines.append(f"  │")
        lines.append(f"  └────────────────────────────────────")
        lines.append("")

        all_msg_lines.append("\n".join(lines))

    stats["messages_exported"] = max_messages
    stats["messages_fetched"] = max_messages

    msg_path = os.path.join(export_dir, f"all_messages_demo_{timestamp}.txt")
    with open(msg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_msg_lines))
    stats["total_size_bytes"] += os.path.getsize(msg_path)
    stats["files_created"].append(msg_path)

    # ── Demo thread data ──
    all_thread_lines = []
    all_thread_lines.append(f"GMAIL COMPLETE THREAD EXPORT (DEMO)")
    all_thread_lines.append(f"Generated: {datetime.now().isoformat()}")
    all_thread_lines.append(f"Total Threads: {max_threads}")
    all_thread_lines.append("=" * 70)
    all_thread_lines.append("")

    for t in range(1, max_threads + 1):
        num_msgs_in_thread = random.randint(1, 6)
        thread_msgs = []

        for mi in range(1, num_msgs_in_thread + 1):
            sender_name_t, sender_email_t = random.choice(demo_senders)
            receiver_name_t = random.choice(demo_senders)[0]
            subject_t = random.choice(demo_subjects)
            if mi > 1:
                subject_t = "Re: " + subject_t
                sender_name_t, sender_email_t = random.choice(demo_senders)

            ts_t = int(datetime(2026, 1, 1).timestamp() + t * 7200 + mi * 1800) * 1000
            date_obj_t = datetime.fromtimestamp(ts_t / 1000, tz=timezone.utc)

            inner = []
            inner.append(f"  ┌─ MESSAGE ID: demo_threadmsg_{t:04d}_{mi:02d}")
            inner.append(f"  │  Thread:       demo_thread_{t:04d}")
            inner.append(f"  │  Date:         {date_obj_t.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            inner.append(f"  │  Labels:       {'INBOX, SENT' if mi == 1 else 'INBOX'}")
            inner.append(f"  │  Size:         {random.randint(1500, 35000)} bytes")
            inner.append(f"  │")
            inner.append(f"  │  From:         {sender_name_t} <{sender_email_t}>")
            inner.append(f"  │  To:           {receiver_name_t} <{receiver_name_t.lower().replace(' ', '.')}@company.com>")
            inner.append(f"  │  Subject:      {subject_t}")
            inner.append(f"  │  CC:           (none)")
            inner.append(f"  │  Message-ID:   <demo_threadmsg_{t:04d}_{mi:02d}@demo.local>")
            inner.append(f"  │  In-Reply-To:  {'<demo_threadmsg_' + str(t).zfill(4) + '_' + str(mi-1).zfill(2) + '@demo.local>' if mi > 1 else '(first message)'}")
            inner.append(f"  │")
            inner.append(f"  │  ── BODY ──")
            inner.append(f"  │  [text/plain]")
            body_content = [
                f"Message {mi} in thread {t}.",
                f"From: {sender_name_t}",
                f"This is part of a threaded conversation.",
                "",
                f"Previous context: {'Yes - replying to message ' + str(mi-1) if mi > 1 else 'This is the first message in the thread.'}"
            ]
            for bl in body_content:
                inner.append(f"  │  {bl}")
            inner.append(f"  │")
            inner.append(f"  └────────────────────────────────────")
            inner.append("")

            thread_msgs.append("\n".join(inner))

        all_thread_lines.append(f"{'='*70}")
        all_thread_lines.append(f"THREAD: demo_thread_{t:04d}")
        all_thread_lines.append(f"Messages: {num_msgs_in_thread}")
        all_thread_lines.append(f"Snippet: Thread conversation about {random.choice(demo_subjects)}")
        all_thread_lines.append(f"{'='*70}")
        all_thread_lines.append("")

        for mi, msg_content in enumerate(thread_msgs, 1):
            all_thread_lines.append(f"─── Message {mi} of {num_msgs_in_thread} ───")
            all_thread_lines.append(msg_content)

    stats["threads_exported"] = max_threads
    stats["threads_fetched"] = max_threads

    thread_path = os.path.join(export_dir, f"all_threads_demo_{timestamp}.txt")
    with open(thread_path, "w", encoding="utf-8") as f:
        f.write("\n".join(all_thread_lines))
    stats["total_size_bytes"] += os.path.getsize(thread_path)
    stats["files_created"].append(thread_path)

    # ── Demo summary ──
    summary_lines = [
        "GMAIL EXPORT SUMMARY (DEMO)",
        "=" * 50,
        f"Generated: {datetime.now().isoformat()}",
        "",
        "NOTE: This is DEMO data. No real Gmail account was accessed.",
        "",
        f"Messages fetched:     {stats['messages_fetched']}",
        f"Messages exported:    {stats['messages_exported']}",
        f"Threads fetched:      {stats['threads_fetched']}",
        f"Threads exported:     {stats['threads_exported']}",
        f"Total export size:    {stats['total_size_bytes']} bytes ({stats['total_size_bytes'] / 1024 / 1024:.1f} MB)",
        "",
        "Files created:",
    ]
    for fpath in stats["files_created"]:
        fsize = os.path.getsize(fpath)
        summary_lines.append(f"  {fpath} ({fsize} bytes)")
    summary_lines.append("")
    summary_lines.append("EXPORT COMPLETE. NO AI USED. RAW DATA ONLY.")

    summary_path = os.path.join(export_dir, f"export_summary_demo_{timestamp}.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    stats["files_created"].append(summary_path)
    stats["summary_path"] = summary_path

    print(f"[export] Demo export complete: {len(stats['files_created'])} files, "
          f"{stats['total_size_bytes'] / 1024:.1f} KB total")

    return stats

"""
Influencer Marketing Agency Intelligence System
A comprehensive analytics platform for agency growth optimization
"""
import os
import json
import logging
import traceback
import uuid
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from database import init_db, get_all_emails, get_all_conversations, set_metrics_cache, get_metrics_cache
from classifier import (
    classify_email, calculate_sentiment, calculate_personalization_depth,
    extract_prospect_info, calculate_engagement_score
)
from analytics import AgencyAnalytics
from forecaster import RevenueForecaster, StrategicReport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Load previous export records from MongoDB into memory
    try:
        from gmail_client import load_exports_from_mongodb
        load_exports_from_mongodb()
        logger.info("Loaded export records from MongoDB")
    except Exception as e:
        logger.warning(f"Could not load exports from MongoDB: {e}")
    logger.info("Database initialized")
    yield


app = FastAPI(title="Agency Intelligence System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)


# ============ API ENDPOINTS ============

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/dashboard/summary")
async def dashboard_summary():
    analytics = AgencyAnalytics()
    cache_hit = get_metrics_cache("dashboard_summary")
    if cache_hit:
        return cache_hit

    result = {
        "pipeline": analytics.get_pipeline_summary(),
        "funnel": analytics.get_funnel_conversion(),
        "metrics": analytics.calculate_advanced_metrics(),
        "health": analytics.calculate_health_score(),
        "updated_at": datetime.now().isoformat(),
    }
    set_metrics_cache("dashboard_summary", result)
    return result


@app.get("/api/pipeline/timeline")
async def pipeline_timeline():
    analytics = AgencyAnalytics()
    return {"timeline": analytics.build_pipeline_timeline()}


@app.get("/api/pipeline/conversion")
async def pipeline_conversion():
    analytics = AgencyAnalytics()
    return {"funnel": analytics.get_funnel_conversion()}


@app.get("/api/metrics/advanced")
async def advanced_metrics():
    analytics = AgencyAnalytics()
    return {"metrics": analytics.calculate_advanced_metrics()}


@app.get("/api/segments")
async def segments():
    analytics = AgencyAnalytics()
    return {"segments": analytics.analyze_segments()}


@app.get("/api/signals")
async def buying_signals():
    analytics = AgencyAnalytics()
    return {"signals": analytics.detect_buying_signals()}


@app.get("/api/campaigns")
async def campaign_analysis():
    analytics = AgencyAnalytics()
    return {"campaigns": analytics.analyze_campaigns()}


@app.get("/api/followups")
async def followup_analysis():
    analytics = AgencyAnalytics()
    return {"followups": analytics.analyze_follow_ups()}


@app.get("/api/positioning")
async def market_positioning():
    analytics = AgencyAnalytics()
    return {"positioning": analytics.analyze_market_positioning()}


@app.get("/api/forecast")
async def revenue_forecast():
    forecaster = RevenueForecaster()
    return forecaster.forecast()


@app.get("/api/report")
async def strategic_report():
    report = StrategicReport()
    return report.generate()


@app.get("/api/health-scores")
async def health_scores():
    analytics = AgencyAnalytics()
    return {"health": analytics.calculate_health_score()}


@app.get("/api/emissions/data")
async def full_dataset():
    """Return the full dataset for debugging/exploration"""
    return {
        "emails": get_all_emails()[:50],
        "conversations": get_all_conversations(),
        "total_emails": len(get_all_emails()),
        "total_conversations": len(get_all_conversations()),
    }


@app.get("/api/refresh")
async def refresh_analysis():
    """Clear cache and re-analyze"""
    set_metrics_cache("dashboard_summary", None)
    analytics = AgencyAnalytics()
    result = {
        "pipeline": analytics.get_pipeline_summary(),
        "funnel": analytics.get_funnel_conversion(),
        "metrics": analytics.calculate_advanced_metrics(),
        "health": analytics.calculate_health_score(),
        "updated_at": datetime.now().isoformat(),
    }
    set_metrics_cache("dashboard_summary", result)
    return {"message": "Analysis refreshed", "data": result}


# ============ FRONTEND ============

@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
async def dashboard():
    html_path = os.path.join(templates_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    return HTMLResponse("<h1>Dashboard not found. Run: python demo_data.py first.</h1>")


@app.get("/demo/init")
async def init_demo():
    """Initialize demo data"""
    try:
        from demo_data import generate_demo_data
        generate_demo_data()
        return {"message": "Demo data generated successfully", "status": "ok"}
    except Exception as e:
        logger.error(f"Demo data generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ GMAIL INTEGRATION (One-Click Sign in with Google) ============

@app.get("/api/gmail/auth/login")
async def gmail_auth_login():
    """Step 1: Redirect user to Google's OAuth consent page.
       User clicks → goes to Google → authorizes → comes back to /callback
    """
    try:
        from gmail_client import get_auth_redirect_url
        auth_url = get_auth_redirect_url()
        return RedirectResponse(auth_url)
    except Exception as e:
        logger.error(f"Auth login failed: {e}")
        return HTMLResponse(f"<html><body><h2>Error</h2><p>{e}</p></body></html>", status_code=500)


@app.get("/api/gmail/auth/callback")
async def gmail_auth_callback(
    code: str = Query(None),
    error: str = Query(None),
):
    """Step 2: Google redirects here after user authorizes.
       We exchange the code for tokens and redirect to the dashboard.
    """
    if error:
        return HTMLResponse(
            f"<html><body><h2>Authorization denied</h2><p>{error}</p>"
            f"<a href='/'>Back to dashboard</a></body></html>"
        )
    if not code:
        return HTMLResponse(
            "<html><body><h2>No authorization code received</h2>"
            "<a href='/api/gmail/auth/login'>Try again</a></body></html>"
        )

    try:
        from gmail_client import handle_auth_callback, get_session
        user_email = handle_auth_callback(code)

        # Auto-redirect to admin panel for admin user
        if user_email == "kiragamingofficial95@gmail.com":
            return RedirectResponse("/admin")

        return HTMLResponse(
            "<html><body style='font-family:sans-serif;background:#0f0f1a;color:#e0e0e0;display:flex;align-items:center;justify-content:center;height:100vh'>"
            "<div style='text-align:center;padding:40px;background:#1a1a2e;border-radius:16px;border:1px solid #2a2a4a;max-width:500px'>"
            "<div style='font-size:48px;margin-bottom:16px'>✅</div>"
            "<h2 style='color:#48bb78;margin-bottom:8px'>Gmail Connected!</h2>"
            "<p style='color:#888;margin-bottom:24px'>Your account has been authorized. You can now export all emails.</p>"
            "<a href='/' style='display:inline-block;padding:12px 32px;background:linear-gradient(135deg,#667eea,#764ba2);color:white;border-radius:8px;text-decoration:none;font-weight:600'>Return to Dashboard →</a>"
            "</div></body></html>"
        )
    except Exception as e:
        logger.error(f"Auth callback failed: {e}")
        return HTMLResponse(
            f"<html><body><h2>Authorization failed</h2><p>{e}</p>"
            f"<a href='/api/gmail/auth/login'>Try again</a></body></html>",
            status_code=400,
        )


@app.get("/api/gmail/auth/logout")
async def gmail_logout():
    """Delete token.pickle and session to sign out"""
    from gmail_client import TOKEN_PATH, SESSION_PATH
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)
    if os.path.exists(SESSION_PATH):
        os.remove(SESSION_PATH)
    return RedirectResponse("/")


@app.get("/api/gmail/status")
async def gmail_status():
    """Check current Gmail auth status"""
    import pickle
    from gmail_client import TOKEN_PATH, get_session
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds_path = os.path.join(os.path.dirname(__file__), "credentials.json")
    has_creds_file = os.path.exists(creds_path)
    has_env_creds = bool(os.environ.get("CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID"))
    status = {
        "has_credentials": has_creds_file or has_env_creds,
        "has_credentials_file": has_creds_file,
        "has_env_credentials": has_env_creds,
        "authenticated": os.path.exists(TOKEN_PATH),
    }

    # Add session info
    session = get_session()
    status["user_email"] = session.get("user_email", None)
    status["auto_export_complete"] = session.get("auto_export_complete", False)

    if status["authenticated"]:
        try:
            with open(TOKEN_PATH, "rb") as f:
                creds = pickle.load(f)
            status["token_valid"] = creds.valid
            status["token_expired"] = creds.expired
            status["has_refresh_token"] = bool(creds.refresh_token)
            if creds.valid and not status.get("user_email"):
                id_token = getattr(creds, "id_token", None)
                if id_token and isinstance(id_token, dict):
                    status["user_email"] = id_token.get("email", "unknown")
            # Auto-refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_PATH, "wb") as f:
                    pickle.dump(creds, f)
                status["token_refreshed"] = True
                status["token_valid"] = True
        except Exception as e:
            status["token_error"] = str(e)

    return status


@app.post("/api/gmail/sync")
async def sync_gmail(max_results: int = Query(200, description="Max emails to fetch")):
    """Fetch and analyze Gmail emails"""
    try:
        from gmail_client import fetch_all_outreach_emails
        from database import upsert_email, update_conversation

        emails = fetch_all_outreach_emails(max_results=max_results)
        stored = 0

        for email in emails:
            # Classify
            category, subcategory, scores = classify_email(email)
            email["category"] = category
            email["sentiment_score"] = calculate_sentiment(
                email.get("body_plain", "") or email.get("body", "")
            )
            email["personalization_score"] = calculate_personalization_depth(
                email.get("body_plain", "") or email.get("body", ""),
                email.get("prospect_name", ""),
                email.get("prospect_company", ""),
            )
            email["engagement_score"] = calculate_engagement_score(email)

            # Extract prospect info
            info = extract_prospect_info(email)
            email.update(info)

            upsert_email(email)
            stored += 1

        set_metrics_cache("dashboard_summary", None)
        return {
            "message": f"Synced and analyzed {stored} emails",
            "total_fetched": len(emails),
            "categories": list(set(e["category"] for e in emails)),
        }
    except ImportError as e:
        raise HTTPException(status_code=400, detail=f"Gmail integration not available: {str(e)}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ GMAIL EXPORT (Raw Data - No AI) ============

@app.get("/api/export/status")
async def export_status():
    """Check if a real Gmail connection is available"""
    from gmail_exporter import USER_EXPORTS_DIR
    has_credentials = os.path.exists(
        os.path.join(os.path.dirname(__file__), "credentials.json")
    )
    has_token = os.path.exists(
        os.path.join(os.path.dirname(__file__), "token.pickle")
    )
    existing_exports = []
    if os.path.exists(USER_EXPORTS_DIR):
        for user_dir in sorted(os.listdir(USER_EXPORTS_DIR), reverse=True):
            user_path = os.path.join(USER_EXPORTS_DIR, user_dir)
            if os.path.isdir(user_path):
                for fname in sorted(os.listdir(user_path), reverse=True)[:5]:
                    if fname.endswith(".txt"):
                        existing_exports.append(f"{user_dir}/{fname}")

    return {
        "has_credentials": has_credentials,
        "has_token": has_token,
        "can_export_real": has_credentials,
        "existing_exports": existing_exports,
        "export_dir": USER_EXPORTS_DIR,
        "note": "No AI used. Raw data export only.",
    }


@app.get("/api/export/run-demo")
async def export_demo(
    messages: int = Query(100, description="Number of demo messages"),
    threads: int = Query(30, description="Number of demo threads"),
):
    """Generate demo export data (no Gmail needed)"""
    try:
        from gmail_exporter import export_demo_data
        from gmail_client import get_session
        session = get_session()
        user_email = session.get("user_email", "demo_user")
        logger.info(f"Running demo export for {user_email}: messages={messages}, threads={threads}")
        stats = export_demo_data(
            max_messages=min(messages, 500),
            max_threads=min(threads, 100),
            user_id=user_email,
        )
        # Read summary
        summary_text = ""
        if stats.get("summary_path") and os.path.exists(stats["summary_path"]):
            with open(stats["summary_path"], "r", encoding="utf-8") as f:
                summary_text = f.read()

        # ── Save demo export to MongoDB ──
        try:
            from mongo_db import save_export_record
            export_files = []
            for fpath in stats.get("files_created", []):
                if os.path.exists(fpath):
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                    export_files.append({
                        "name": os.path.basename(fpath),
                        "size_bytes": len(content.encode("utf-8")),
                        "content": content,
                    })
            export_record = {
                "user_email": user_email,
                "started_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "status": "complete",
                "demo": True,
                "stats": {
                    "messages_fetched": stats.get("messages_fetched", 0),
                    "messages_exported": stats.get("messages_exported", 0),
                    "threads_fetched": stats.get("threads_fetched", 0),
                    "threads_exported": stats.get("threads_exported", 0),
                    "total_files": len(export_files),
                    "total_size_bytes": sum(f["size_bytes"] for f in export_files),
                },
                "files": export_files,
            }
            save_export_record(user_email, export_record)
            logger.info(f"Saved demo export to MongoDB for {user_email}")
        except Exception as mge:
            logger.warning(f"Could not save demo export to MongoDB: {mge}")

        return {
            "status": "complete",
            "stats": {
                "messages": stats["messages_exported"],
                "threads": stats["threads_exported"],
                "total_size_bytes": stats["total_size_bytes"],
                "total_size_mb": round(stats["total_size_bytes"] / 1024 / 1024, 2),
                "files_created": stats["files_created"],
            },
            "summary": summary_text,
            "demo": True,
            "note": "Demo data. No real Gmail account was accessed. No AI used.",
        }
    except Exception as e:
        logger.error(f"Demo export failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# In-memory store for background export tasks
_export_tasks: dict = {}


@app.get("/api/export/run-live")
async def export_live(
    messages: int = Query(500, description="Max messages to export"),
    threads: int = Query(200, description="Max threads to export"),
):
    """Start a background Gmail export (avoids Render's 60s timeout)."""
    from gmail_exporter import get_gmail_service
    from gmail_client import get_session

    service = get_gmail_service()
    session = get_session()
    user_email = session.get("user_email", "unknown")
    task_id = str(uuid.uuid4())
    _export_tasks[task_id] = {
        "status": "running",
        "progress": "Starting export...",
        "started_at": datetime.now().isoformat(),
        "stats": None,
        "error": None,
        "user_email": user_email,
    }

    def _run():
        try:
            from gmail_exporter import export_all_to_txt
            _export_tasks[task_id]["progress"] = "Fetching messages from Gmail..."
            stats = export_all_to_txt(
                service,
                max_messages=min(messages, 20000),
                max_threads=min(threads, 5000),
                user_id=user_email,
            )
            summary_text = ""
            if stats.get("summary_path") and os.path.exists(stats["summary_path"]):
                with open(stats["summary_path"], "r", encoding="utf-8") as f:
                    summary_text = f.read()
            _export_tasks[task_id].update({
                "status": "complete",
                "progress": "Export complete",
                "stats": {
                    "messages": stats["messages_exported"],
                    "threads": stats["threads_exported"],
                    "total_size_bytes": stats["total_size_bytes"],
                    "total_size_mb": round(stats["total_size_bytes"] / 1024 / 1024, 2),
                    "files_created": stats["files_created"],
                },
                "summary": summary_text,
            })

            # ── Save export files to MongoDB ──
            try:
                from mongo_db import save_export_record
                export_files = []
                for fpath in stats.get("files_created", []):
                    if os.path.exists(fpath):
                        with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                            content = fh.read()
                        export_files.append({
                            "name": os.path.basename(fpath),
                            "size_bytes": len(content.encode("utf-8")),
                            "content": content,
                        })
                    else:
                        export_files.append({
                            "name": os.path.basename(fpath),
                            "size_bytes": 0,
                            "content": "[file not found]",
                        })
                export_record = {
                    "user_email": user_email,
                    "started_at": _export_tasks[task_id].get("started_at"),
                    "completed_at": datetime.now().isoformat(),
                    "status": "complete",
                    "stats": {
                        "messages_fetched": stats.get("messages_fetched", 0),
                        "messages_exported": stats.get("messages_exported", 0),
                        "threads_fetched": stats.get("threads_fetched", 0),
                        "threads_exported": stats.get("threads_exported", 0),
                        "total_files": len(export_files),
                        "total_size_bytes": sum(f["size_bytes"] for f in export_files),
                    },
                    "files": export_files,
                }
                save_export_record(user_email, export_record)
                logger.info(f"Saved live export to MongoDB for {user_email}")
            except Exception as mge:
                logger.warning(f"Could not save live export to MongoDB: {mge}")

        except Exception as e:
            logger.error(f"Background export failed: {e}\n{traceback.format_exc()}")
            _export_tasks[task_id].update({
                "status": "error",
                "progress": str(e),
                "error": str(e),
            })

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"task_id": task_id, "status": "started", "note": "Export running in background. Poll /api/export/task/{task_id} for progress."}


@app.get("/api/export/task/{task_id}")
async def get_export_task(task_id: str):
    """Poll the progress of a background export task."""
    task = _export_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/api/export/files")
async def list_export_files():
    """List all generated export files, organized by user"""
    from gmail_exporter import USER_EXPORTS_DIR
    files = []
    if os.path.exists(USER_EXPORTS_DIR):
        for user_dir in sorted(os.listdir(USER_EXPORTS_DIR), reverse=True):
            user_path = os.path.join(USER_EXPORTS_DIR, user_dir)
            if os.path.isdir(user_path):
                for fname in sorted(os.listdir(user_path), reverse=True):
                    fpath = os.path.join(user_path, fname)
                    if os.path.isfile(fpath) and fname.endswith(".txt"):
                        files.append({
                            "name": fname,
                            "user": user_dir,
                            "path": fpath,
                            "size_bytes": os.path.getsize(fpath),
                            "size_mb": round(os.path.getsize(fpath) / 1024 / 1024, 2),
                            "modified": datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
                        })
    return {"files": files, "export_dir": USER_EXPORTS_DIR, "count": len(files)}


@app.get("/api/export/download/{filename:path}")
async def download_export_file(filename: str, user: str = Query("", description="User email subfolder")):
    """Download a specific export file"""
    from fastapi.responses import FileResponse
    from gmail_exporter import USER_EXPORTS_DIR

    # If user is specified, look in that user's directory
    if user:
        fpath = os.path.join(USER_EXPORTS_DIR, user, filename)
        if os.path.exists(fpath) and fpath.startswith(os.path.abspath(USER_EXPORTS_DIR)):
            return FileResponse(
                path=fpath,
                filename=filename,
                media_type="text/plain",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

    # Fallback: search all user directories
    if os.path.exists(USER_EXPORTS_DIR):
        for user_dir in os.listdir(USER_EXPORTS_DIR):
            fpath = os.path.join(USER_EXPORTS_DIR, user_dir, filename)
            if os.path.exists(fpath) and fpath.startswith(os.path.abspath(USER_EXPORTS_DIR)):
                return FileResponse(
                    path=fpath,
                    filename=filename,
                    media_type="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )

    raise HTTPException(status_code=404, detail="File not found")


# ============ ADMIN PANEL ============

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "kiradiesnever")


def _is_admin():
    """Check if the request has admin access (password or Google auth)."""
    from gmail_client import get_session
    session = get_session()
    email = session.get("user_email", "")
    if email == "kiragamingofficial95@gmail.com":
        return True
    if session.get("admin_password_verified"):
        return True
    return False


@app.get("/api/admin/password-login")
async def admin_password_login(password: str = Query("")):
    """Login to admin panel with a password."""
    from gmail_client import get_session, save_session
    if password == ADMIN_PASSWORD:
        session = get_session()
        session["admin_password_verified"] = True
        session["authenticated_at"] = datetime.now().isoformat()
        save_session(session)
        return {"success": True, "message": "Admin access granted"}
    return {"success": False, "error": "Invalid password"}


@app.get("/api/admin/password-logout")
async def admin_password_logout():
    """Logout from password-based admin access."""
    from gmail_client import get_session, save_session
    session = get_session()
    session["admin_password_verified"] = False
    save_session(session)
    return RedirectResponse("/admin")


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Admin panel - requires Google sign-in or password."""
    from gmail_client import get_session
    session = get_session()

    if not _is_admin():
        html_path = os.path.join(templates_dir, "admin_login.html")
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        return HTMLResponse("""<html><body style="background:#0f0f1a;color:#e0e0e0;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh">
<div style="text-align:center;padding:40px;background:#1a1a2e;border-radius:16px;border:1px solid #2a2a4a;max-width:400px">
<h2 style="color:#e0e0e0;margin-bottom:16px">🔒 Admin Panel</h2>
<p style="color:#888;margin-bottom:24px">Enter the admin password.</p>
<input type="password" id="pw" style="width:100%;padding:12px;border:1px solid #2a2a4a;border-radius:8px;background:#16213e;color:#e0e0e0;font-size:15px;outline:none;box-sizing:border-box" placeholder="Password" autocomplete="off">
<div id="err" style="color:#fc8181;font-size:13px;margin-top:8px;display:none"></div>
<button onclick="login()" style="width:100%;margin-top:12px;padding:14px;border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff">Unlock →</button>
</div>
<script>
document.getElementById('pw').value='';
function login(){fetch('/api/admin/password-login?password='+encodeURIComponent(document.getElementById('pw').value)).then(r=>r.json()).then(d=>{if(d.success)window.location.href='/admin';else{document.getElementById('err').textContent='Wrong password';document.getElementById('err').style.display='block'}})}
</script></body></html>""")

    # Admin is authenticated - show admin panel
    auth_email = session.get("user_email", "")
    is_password_auth = session.get("admin_password_verified", False)

    admin_html = os.path.join(templates_dir, "admin.html")
    if os.path.exists(admin_html):
        with open(admin_html, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse(f"""<html><head><title>Admin Panel</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0f0f1a;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:20px}}
.header{{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:24px 32px;border-radius:16px;margin-bottom:24px;border:1px solid #2a2a4a}}
.header h1{{font-size:24px;font-weight:700;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.card{{background:#1a1a2e;border-radius:12px;padding:24px;margin-bottom:20px;border:1px solid #2a2a4a}}
.card h2{{font-size:18px;margin-bottom:16px;color:#ccc}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid #2a2a4a}}
th{{color:#888;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:1px}}
tr:hover{{background:#16213e}}
.btn{{display:inline-block;padding:10px 20px;border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;text-decoration:none;transition:all .2s}}
.btn-primary{{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}}
.btn-danger{{background:#522224;color:#fc8181}}
.btn-download{{background:#22543d;color:#48bb78;padding:4px 12px;font-size:12px;text-decoration:none;border-radius:6px}}
.alert{{background:#22543d;color:#48bb78;padding:12px 20px;border-radius:8px;margin-bottom:16px;border:1px solid #276749}}
.flex-between{{display:flex;justify-content:space-between;align-items:center}}
.mt-4{{margin-top:16px}}
</style></head><body>
<div class="header flex-between">
<div><h1>🔐 Admin Panel</h1></div>
<div style="display:flex;gap:12px;align-items:center">
<span style="color:#48bb78">{'🔑 Password Login' if is_password_auth else 'USER: ' + auth_email}</span>
{'<a href="/api/admin/password-logout" class="btn btn-danger">Sign Out</a>' if is_password_auth else '<a href="/api/gmail/auth/logout" class="btn btn-danger">Sign Out</a>'}
<a href="/" class="btn btn-primary">Dashboard</a>
</div>
</div>
<div class="card" id="adminStatus">
<h2>Loading admin data...</h2>
</div>
<div class="card" id="exportProgress" style="border-color:#667eea">
<h2>Users' Auto-Exports <span style="font-size:13px;color:#888;font-weight:400">(live, updates every 2s)</span></h2>
<p style="color:#888">Checking export status...</p>
</div>
<div class="card">
<h2>Export Files (Messages & Threads)</h2>
<div id="exportFileList"><p style="color:#888">Loading exports...</p></div>
</div>
<div class="card">
<h2>User Sessions</h2>
<div id="userSessions"><p style="color:#888">Loading...</p></div>
</div>
<script>
window.onerror = function(msg, url, line) {{
  var el = document.getElementById('adminStatus');
  if (el) el.innerHTML = '<div class="alert" style="background:#522224;color:#fc8181">❌ JS Error: ' + escapeHtml(msg) + ' (line ' + line + ')</div>';
}};

const EXPORT_POLL_INTERVAL = 2000;
let exportPollTimer = null;

function setStatus(id, html) {{
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}}

function apiFetch(path) {{
  const ctrl = new AbortController();
  setTimeout(function() {{ ctrl.abort(); }}, 8000);
  return fetch(path, {{ signal: ctrl.signal }});
}}

// Show "still loading" fallback after 8 seconds
setTimeout(function() {{
  var el = document.getElementById('adminStatus');
  if (el && el.innerHTML.indexOf('Loading') > -1)
    el.innerHTML = '<div class="alert" style="background:#522224;color:#fc8181">⚠️ Still loading... Check console (F12) for errors. Try refreshing the page.</div>';
  var el2 = document.getElementById('exportProgress');
  if (el2 && el2.innerHTML.indexOf('Checking') > -1)
    el2.innerHTML = '<p style="color:#fc8181">⚠️ Still loading... Check console (F12) for errors.</p>';
}}, 8000);

async function loadAdminData(){{
  try {{
    const r = await apiFetch('/api/admin/data');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    setStatus('adminStatus', '<div class="alert">✅ Admin access granted' + (d.user_email ? ' (' + d.user_email + ')' : '') + '</div>');
  }} catch(e) {{
    setStatus('adminStatus', '<div class="alert" style="background:#522224;color:#fc8181">❌ ' + escapeHtml(e.message) + '</div>');
  }}
  loadExportFiles();
  updateSessions();
}}

async function updateSessions() {{
  try {{
    const r = await fetch('/api/admin/sessions');
    const d = await r.json();
    let html = '<table><thead><tr><th>Email</th><th>Authenticated At</th><th>Auto Export</th></tr></thead><tbody>';
    if (d.sessions && d.sessions.length) {{
      d.sessions.forEach(s => {{
        html += '<tr><td>' + s.email + '</td><td>' + s.time + '</td><td>' + (s.exported ? '✅ Done' : '⏳ Running...') + '</td></tr>';
      }});
    }} else {{
      html += '<tr><td colspan="3" style="text-align:center">No sessions</td></tr>';
    }}
    html += '</tbody></table>';
    document.getElementById('userSessions').innerHTML = html;
  }} catch(e) {{ console.error(e); }}
}}

async function pollExportProgress() {{
  try {{
    const r = await apiFetch('/api/admin/export-progress');
    if (!r.ok) {{
      setStatus('exportProgress', '<div class="alert" style="background:#522224;color:#fc8181">❌ Export API error: HTTP ' + r.status + '</div>');
      return;
    }}
    const d = await r.json();
    const exports = d.exports || [];
    const running = exports.filter(e => e.status === 'running');
    const completed = exports.filter(e => e.status === 'complete');
    const errors = exports.filter(e => e.status === 'error');

    let html = '';
    if (exports.length === 0) {{
      html = '<p style="color:#888">No exports started yet. Ask users to sign in with Google.</p>';
    }}

    // Running exports
    running.forEach(p => {{
      let pct = 0;
      let detail = 'Phase: ' + escapeHtml(p.phase || 'starting...');
      if (p.messages_total > 0) {{
        pct = Math.round((p.messages_exported / p.messages_total) * 100);
        detail += '<div style="margin:6px 0"><div class="flex-between"><span>Messages exported:</span><span>' +
          p.messages_exported + ' / ' + p.messages_total + ' (' + pct + '%)</span></div>' +
          '<div class="progress-bar"><div class="progress-fill" style="width:' + pct + '%;background:#667eea"></div></div></div>';
      }}
      if (p.threads_total > 0) {{
        const tpct = Math.round((p.threads_exported / p.threads_total) * 100);
        detail += '<div style="margin:6px 0"><div class="flex-between"><span>Threads exported:</span><span>' +
          p.threads_exported + ' / ' + p.threads_total + ' (' + tpct + '%)</span></div>' +
          '<div class="progress-bar"><div class="progress-fill" style="width:' + tpct + '%;background:#764ba2"></div></div></div>';
      }}
      html += '<div class="alert" style="background:#2a4365;border-color:#63b3ed">' +
        '⏳ <strong>' + escapeHtml(p.user_email) + '</strong> — ' + detail +
        '</div>';
    }});

    // Completed exports
    completed.forEach(p => {{
      const fileCount = (p.file_list || []).length;
      const fileInfo = fileCount > 0 ? ' · ' + fileCount + ' files stored in DB' : '';
      html += '<div class="alert" style="background:#22543d;border-color:#48bb78">' +
        '✅ <strong>' + escapeHtml(p.user_email) + '</strong> — Export complete! ' +
        (p.messages_exported||0) + ' messages · ' + (p.threads_exported||0) + ' threads' +
        (p.messages_fetched ? ' · ' + p.messages_fetched + ' synced to DB' : '') +
        fileInfo +
        (fileCount > 0 ? ' <a href="#" onclick="viewExportFiles(\\'' + escapeHtml(p.user_email) + '\\');return false" style="color:#68d391;margin-left:8px">📁 View Files</a>' : '') +
        '</div>';
    }});

    // Failed exports
    errors.forEach(p => {{
      html += '<div class="alert" style="background:#522224;color:#fc8181">' +
        '❌ <strong>' + escapeHtml(p.user_email) + '</strong> — Failed: ' + escapeHtml(p.error || 'Unknown') +
        '</div>';
    }});

    document.getElementById('exportProgress').innerHTML = html;

    if (running.length === 0 && exportPollTimer) {{
      // keep polling but less frequently if nothing is running
    }}
  }} catch(e) {{ console.error('pollExportProgress error:', e); }}
}}

function escapeHtml(str) {{
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function loadExportFiles() {{
  apiFetch('/api/export/files').then(r=>r.json()).then(d => {{
    let html = '';
    if (d.files && d.files.length) {{
      html = '<table><thead><tr><th>User</th><th>File</th><th>Size</th><th>Modified</th><th>Download</th></tr></thead><tbody>';
      d.files.forEach(f => {{
        html += '<tr><td style="color:#667eea;font-size:12px">' + escapeHtml(f.user || '?') + '</td><td>' + escapeHtml(f.name) + '</td><td>' +
          (f.size_mb > 1 ? f.size_mb.toFixed(1) + ' MB' : (f.size_bytes/1024).toFixed(1) + ' KB') +
          '</td><td>' + new Date(f.modified).toLocaleString() + '</td>' +
          '<td><a href="/api/export/download/' + encodeURIComponent(f.name) + '?user=' + encodeURIComponent(f.user || '') + '" class="btn-download">⬇ Download</a></td></tr>';
      }});
      html += '</tbody></table>';
    }} else {{
      html = '<p style="color:#888">No exports yet. Auto-export runs on admin login.</p>';
    }}
    document.getElementById('exportFileList').innerHTML = html;
  }}).catch(e => console.error(e));
}}

function viewExportFiles(email) {{
  apiFetch('/api/admin/export-files/' + encodeURIComponent(email)).then(r=>r.json()).then(d => {{
    var box = document.createElement('div');
    box.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px';
    box.onclick = function(){{ document.body.removeChild(box); }};
    var inner = document.createElement('div');
    inner.style.cssText = 'background:#1a1a2e;border:1px solid #2a2a4a;border-radius:16px;padding:24px;max-width:90%;max-height:90%;overflow:auto';
    inner.onclick = function(e){{ e.stopPropagation(); }};
    var header = document.createElement('div');
    header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px';
    var title = document.createElement('h2');
    title.style.cssText = 'color:#ccc';
    title.textContent = '📁 Export Files - ' + d.user_email;
    var closeBtn = document.createElement('button');
    closeBtn.textContent = '✕ Close';
    closeBtn.style.cssText = 'background:#522224;color:#fc8181;border:none;border-radius:8px;padding:8px 16px;cursor:pointer;font-weight:600';
    closeBtn.onclick = function(){{ document.body.removeChild(box); }};
    header.appendChild(title);
    header.appendChild(closeBtn);
    inner.appendChild(header);
    if (d.files && d.files.length) {{
      d.files.forEach(function(f) {{
        var fileDiv = document.createElement('div');
        fileDiv.style.cssText = 'background:#16213e;border-radius:8px;padding:16px;margin-bottom:12px;border:1px solid #2a2a4a';
        var fheader = document.createElement('div');
        fheader.style.cssText = 'display:flex;justify-content:space-between;margin-bottom:8px';
        var fname = document.createElement('strong');
        fname.style.cssText = 'color:#667eea';
        fname.textContent = f.name;
        var fsize = document.createElement('span');
        fsize.style.cssText = 'color:#888;font-size:12px';
        fsize.textContent = (f.size_bytes / 1024).toFixed(1) + ' KB';
        fheader.appendChild(fname);
        fheader.appendChild(fsize);
        fileDiv.appendChild(fheader);
        var pre = document.createElement('pre');
        pre.style.cssText = 'font-size:11px;color:#aaa;max-height:300px;overflow:auto;background:#0f0f1a;padding:12px;border-radius:6px;white-space:pre-wrap';
        var content = f.content || '';
        pre.textContent = content.substring(0, 5000);
        fileDiv.appendChild(pre);
        if (content.length > 5000) {{
          var note = document.createElement('p');
          note.style.cssText = 'color:#888;font-size:12px;margin-top:4px';
          note.textContent = '... (showing first 5000 of ' + content.length + ' chars)';
          fileDiv.appendChild(note);
        }}
        inner.appendChild(fileDiv);
      }});
    }} else {{
      var nofiles = document.createElement('p');
      nofiles.style.cssText = 'color:#888';
      nofiles.textContent = 'No files stored for this export.';
      inner.appendChild(nofiles);
    }}
    box.appendChild(inner);
    document.body.appendChild(box);
  }}).catch(function(e) {{ alert('Error loading files: ' + e.message); }});
}}

loadAdminData();
pollExportProgress();
exportPollTimer = setInterval(pollExportProgress, EXPORT_POLL_INTERVAL);
</script>
</body></html>""")


def _require_admin_api():
    if not _is_admin():
        raise HTTPException(status_code=403, detail="Forbidden")


@app.get("/api/admin/data")
async def admin_data():
    """Admin API - returns user session and auth info"""
    from gmail_client import get_session
    _require_admin_api()
    session = get_session()
    email = session.get("user_email", "")
    return {
        "user_email": email,
        "authenticated_at": session.get("authenticated_at", ""),
        "auto_export_complete": session.get("auto_export_complete", False),
        "is_admin": True,
    }


@app.get("/api/admin/sessions")
async def admin_sessions():
    """Admin API - returns all user session data"""
    from gmail_client import get_session
    _require_admin_api()
    session = get_session()
    return {
        "sessions": [{
            "email": session.get("user_email", "N/A"),
            "time": session.get("authenticated_at", "N/A"),
            "exported": session.get("auto_export_complete", False),
        }]
    }


@app.get("/api/admin/export-progress")
async def admin_export_progress():
    """Admin API - returns real-time auto-export progress for ALL users
    with file contents for permanent storage access.
    """
    from gmail_client import get_all_exports
    _require_admin_api()
    exports = get_all_exports()
    # Return file list (without full content to keep response small)
    export_list = []
    for ex in exports.values():
        entry = dict(ex)
        if "files" in entry:
            entry["file_list"] = [
                {"name": f.get("name"), "size_bytes": f.get("size_bytes", 0)}
                for f in (entry.get("files") or [])
            ]
            del entry["files"]
        export_list.append(entry)
    return {
        "exports": export_list,
        "total_exports": len(exports),
    }


@app.get("/api/admin/export-files/{email}")
async def admin_export_files(email: str):
    """Admin API - returns full file contents for a user's export."""
    from gmail_client import get_all_exports
    _require_admin_api()
    exports = get_all_exports()
    entry = exports.get(email)
    if not entry:
        raise HTTPException(status_code=404, detail="No export found for this user")
    return {
        "user_email": email,
        "status": entry.get("status"),
        "files": entry.get("files", []),
        "stats": entry.get("stats", {}),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"\n{'='*60}")
    print(f"  Agency Intelligence System")
    print(f"{'='*60}")
    print(f"  Dashboard: http://localhost:{port}")
    print(f"  API Docs:  http://localhost:{port}/docs")
    print(f"  Demo Data: http://localhost:{port}/demo/init")
    print(f"{'='*60}\n")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, log_level="info")

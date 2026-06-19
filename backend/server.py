"""BagnShop Social Manager — FastAPI backend."""
from __future__ import annotations
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from models import (
    BrandProfile, Competitor, Post, CalendarSlot,
    to_mongo, from_mongo, now_utc, new_id,
)
from seeds import COMPETITORS_SEED
from agents import (
    run_audit_agent, run_strategist_agent, run_creative_for_slot,
    run_publisher_agent, run_optimizer_agent, fetch_shopify_products,
)
from scheduler import build_scheduler, send_email, SCHED_ENABLED, check_health_and_alert
from canva import build_router as build_canva_router

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="BagnShop Social Manager")
api = APIRouter(prefix="/api")
security = HTTPBearer()

UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


# ---------- Auth ----------
class LoginReq(BaseModel):
    email: EmailStr
    password: str


def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _verify_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception:
        return False


def _make_token(email: str) -> str:
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def require_admin(creds: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(401, "Invalid token")
        return email
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")


@api.post("/auth/login")
async def login(req: LoginReq):
    admin = await db.admins.find_one({"email": req.email}, {"_id": 0})
    if not admin or not _verify_pw(req.password, admin["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    return {"token": _make_token(req.email), "email": req.email}


@api.get("/auth/me")
async def me(email: str = Depends(require_admin)):
    return {"email": email}


# ---------- Health ----------
@api.get("/")
async def root():
    return {"ok": True, "service": "BagnShop Social Manager"}


# ---------- Brand profile ----------
@api.get("/brand")
async def get_brand(email: str = Depends(require_admin)):
    doc = from_mongo(await db.brand_profile.find_one())
    return doc or BrandProfile().model_dump()


@api.put("/brand")
async def update_brand(payload: dict, email: str = Depends(require_admin)):
    payload["updated_at"] = now_utc().isoformat()
    existing = await db.brand_profile.find_one()
    if existing:
        await db.brand_profile.update_one({"id": existing["id"]}, {"$set": payload})
    else:
        bp = BrandProfile(**payload)
        await db.brand_profile.insert_one(to_mongo(bp))
    return from_mongo(await db.brand_profile.find_one())


# ---------- Competitors ----------
@api.get("/competitors")
async def list_competitors(email: str = Depends(require_admin)):
    docs = await db.competitors.find({}, {"_id": 0}).to_list(100)
    return docs


@api.get("/competitor-content")
async def list_competitor_content(limit: int = 50, email: str = Depends(require_admin)):
    docs = await db.competitor_content.find({}, {"_id": 0})\
        .sort("engagement_rate", -1).limit(limit).to_list(limit)
    return docs


@api.get("/hook-patterns")
async def hook_patterns(email: str = Depends(require_admin)):
    """Returns most recent strategist hook patterns + content gaps."""
    doc = await db.strategist_reports.find_one({}, {"_id": 0},
                                               sort=[("created_at", -1)])
    if not doc:
        return {"hook_patterns": [], "content_gaps": [], "pillars": []}
    return {
        "hook_patterns": doc.get("hook_patterns", []),
        "content_gaps": doc.get("content_gaps", []),
        "pillars": doc.get("pillars", []),
    }


# ---------- Calendar ----------
@api.get("/calendar")
async def get_calendar(email: str = Depends(require_admin)):
    docs = await db.content_calendar.find({}, {"_id": 0})\
        .sort("scheduled_datetime", 1).to_list(500)
    return docs


# ---------- Posts (the approval queue) ----------
@api.get("/posts")
async def list_posts(status: Optional[str] = None, platform: Optional[str] = None,
                     email: str = Depends(require_admin)):
    q: dict = {}
    if status:
        q["status"] = status
    if platform:
        q["platform"] = platform
    docs = await db.posts.find(q, {"_id": 0})\
        .sort("scheduled_datetime", 1).to_list(500)
    return docs


@api.get("/posts/{post_id}")
async def get_post(post_id: str, email: str = Depends(require_admin)):
    doc = await db.posts.find_one({"id": post_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Post not found")
    return doc


class PostUpdate(BaseModel):
    caption: Optional[str] = None
    scheduled_datetime: Optional[datetime] = None
    hashtags: Optional[List[str]] = None
    image_urls: Optional[List[str]] = None


@api.put("/posts/{post_id}")
async def update_post(post_id: str, body: PostUpdate, email: str = Depends(require_admin)):
    update = body.model_dump(exclude_unset=True)
    if "scheduled_datetime" in update and update["scheduled_datetime"]:
        update["scheduled_datetime"] = update["scheduled_datetime"].isoformat()
    update["updated_at"] = now_utc().isoformat()
    res = await db.posts.update_one({"id": post_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Post not found")
    return await db.posts.find_one({"id": post_id}, {"_id": 0})


class StatusUpdate(BaseModel):
    status: str  # approved | rejected | needs_edit | pending_approval


@api.post("/posts/{post_id}/status")
async def change_status(post_id: str, body: StatusUpdate,
                        email: str = Depends(require_admin)):
    allowed = {"approved", "rejected", "needs_edit", "pending_approval"}
    if body.status not in allowed:
        raise HTTPException(400, f"Invalid status. Must be one of {allowed}")
    update = {"status": body.status, "updated_at": now_utc().isoformat()}
    if body.status == "approved":
        update["approval_timestamp"] = now_utc().isoformat()
    res = await db.posts.update_one({"id": post_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Post not found")
    await db.audit_log.insert_one({
        "id": new_id(), "post_id": post_id, "action": f"status_change:{body.status}",
        "by": email, "at": now_utc().isoformat(),
    })
    return await db.posts.find_one({"id": post_id}, {"_id": 0})


class BulkApprove(BaseModel):
    post_ids: List[str] = []
    platform: Optional[str] = None  # if set, approve all pending for this platform


@api.post("/posts/bulk-approve")
async def bulk_approve(body: BulkApprove, email: str = Depends(require_admin)):
    q: dict = {"status": "pending_approval"}
    if body.post_ids:
        q["id"] = {"$in": body.post_ids}
    if body.platform:
        q["platform"] = body.platform
    res = await db.posts.update_many(
        q,
        {"$set": {"status": "approved",
                  "approval_timestamp": now_utc().isoformat(),
                  "updated_at": now_utc().isoformat()}},
    )
    return {"approved_count": res.modified_count}


@api.post("/posts/{post_id}/regenerate")
async def regenerate_post(post_id: str, email: str = Depends(require_admin)):
    doc = await db.posts.find_one({"id": post_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Post not found")
    slot_id = doc.get("calendar_slot_id")
    if not slot_id:
        raise HTTPException(400, "Post has no calendar slot to regenerate from")
    # Delete old post + regenerate
    await db.posts.delete_one({"id": post_id})
    result = await run_creative_for_slot(db, slot_id)
    return result or {"status": "error"}


# ---------- Insights ----------
@api.get("/insights")
async def insights(email: str = Depends(require_admin)):
    analytics = await db.my_analytics.find({}, {"_id": 0})\
        .sort("created_at", -1).limit(3).to_list(3)
    latest_learning = await db.learnings.find_one({}, {"_id": 0},
                                                  sort=[("created_at", -1)])
    # Aggregate published post performance
    published = await db.posts.find({"status": "published"}, {"_id": 0})\
        .sort("published_at", -1).limit(20).to_list(20)
    return {
        "analytics": analytics,
        "learning": latest_learning,
        "recent_published": published,
    }


# ---------- Shopify products ----------
@api.get("/shopify/products")
async def shopify_products(email: str = Depends(require_admin)):
    return await fetch_shopify_products(limit=20)


# ---------- Agent triggers (manual + scheduler) ----------
@api.post("/agents/audit/run")
async def trigger_audit(bg: BackgroundTasks, email: str = Depends(require_admin)):
    return await run_audit_agent(db)


@api.post("/agents/strategist/run")
async def trigger_strategist(days: int = 7, email: str = Depends(require_admin)):
    return await run_strategist_agent(db, days=days)


class CreativeReq(BaseModel):
    limit: int = 7  # generate creatives for next N upcoming slots without posts


@api.post("/agents/creative/run")
async def trigger_creative(body: CreativeReq, email: str = Depends(require_admin)):
    # Find slots without generated posts
    slots = await db.content_calendar.find(
        {"status": "planned"}, {"_id": 0}
    ).sort("scheduled_datetime", 1).limit(body.limit).to_list(body.limit)
    results = []
    for s in slots:
        r = await run_creative_for_slot(db, s["id"])
        if r:
            results.append(r)
    return {"generated": len(results), "results": results}


@api.post("/agents/publisher/run")
async def trigger_publisher(email: str = Depends(require_admin)):
    return await run_publisher_agent(db)


@api.post("/agents/optimizer/run")
async def trigger_optimizer(email: str = Depends(require_admin)):
    return await run_optimizer_agent(db)


@api.post("/agents/full-cycle/run")
async def trigger_full_cycle(days: int = 7, creative_count: int = 7,
                             email: str = Depends(require_admin)):
    """Run audit -> strategist -> creative for the next week."""
    a = await run_audit_agent(db)
    s = await run_strategist_agent(db, days=days)
    slots = await db.content_calendar.find(
        {"status": "planned"}, {"_id": 0}
    ).sort("scheduled_datetime", 1).limit(creative_count).to_list(creative_count)
    creatives = []
    for slot in slots:
        r = await run_creative_for_slot(db, slot["id"])
        if r:
            creatives.append(r)
    return {"audit": a, "strategist": s, "creatives_generated": len(creatives)}


@api.post("/notifications/test")
async def notifications_test(email: str = Depends(require_admin)):
    ok = await send_email(
        "BagnShop AI — test email",
        "<p>If you got this, MailerSend is wired up correctly.</p>",
    )
    return {"sent": ok, "to": os.environ.get("NOTIFY_EMAIL", "")}


@api.get("/integrations/postproxy/diagnose")
async def postproxy_diagnose(email: str = Depends(require_admin)):
    import httpx
    key = os.environ.get("POSTPROXY_API_KEY", "")
    base = os.environ.get("POSTPROXY_BASE_URL", "https://api.postproxy.dev/api").rstrip("/")
    pg = os.environ.get("POSTPROXY_PROFILE_GROUP_ID", "")
    url = f"{base}/posts"
    if not key:
        return {"success": False, "error": "POSTPROXY_API_KEY missing in .env",
                "url": url, "status_code": None, "body": None,
                "key_present": False, "key_length": 0}
    # try X-API-Key first, fallback to Bearer
    headers_variants = [
        {"X-API-Key": key},
        {"Authorization": f"Bearer {key}"},
    ]
    last = None
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            for h in headers_variants:
                r = await cli.get(url, headers=h)
                last = r
                if r.status_code != 401:
                    break
        r = last
        try:
            body = r.json()
        except Exception:
            body = r.text[:1000]
        return {
            "success": 200 <= r.status_code < 300,
            "status_code": r.status_code,
            "url": url,
            "auth_header": list((headers_variants[0] if r is headers_variants else headers_variants[-1]).keys())[0]
                if hasattr(headers_variants, "keys") else "X-API-Key or Authorization",
            "profile_group_id": pg,
            "key_length": len(key),
            "key_preview": f"{key[:6]}...{key[-4:]}",
            "body": body,
            "response_headers": dict(r.headers),
        }
    except httpx.RequestError as e:
        return {"success": False, "status_code": None, "url": url,
                "key_length": len(key),
                "key_preview": f"{key[:6]}...{key[-4:]}",
                "error": f"Network error: {type(e).__name__}: {e}",
                "body": None}
    except Exception as e:
        return {"success": False, "status_code": None, "url": url,
                "key_length": len(key),
                "key_preview": f"{key[:6]}...{key[-4:]}",
                "error": f"Unexpected: {type(e).__name__}: {e}",
                "body": None}


async def _collect_integrations_health(db_obj) -> dict:
    """Compute health snapshot for every external integration. Reusable by endpoint + scheduler."""
    import httpx
    results: dict = {}

    # Postproxy
    pk = os.environ.get("POSTPROXY_API_KEY", "")
    pbase = os.environ.get("POSTPROXY_BASE_URL", "https://api.postproxy.dev/api").rstrip("/")
    if not pk:
        results["postproxy"] = {"ok": False, "detail": "POSTPROXY_API_KEY missing"}
    else:
        try:
            async with httpx.AsyncClient(timeout=10) as cli:
                # try X-API-Key first then Bearer
                r = await cli.get(f"{pbase}/posts", headers={"X-API-Key": pk})
                if r.status_code == 401:
                    r = await cli.get(f"{pbase}/posts", headers={"Authorization": f"Bearer {pk}"})
            detail = ""
            try:
                jd = r.json()
                detail = (jd.get("error") or jd.get("message") or "")[:80] if isinstance(jd, dict) else ""
            except Exception:
                detail = r.text[:80]
            results["postproxy"] = {"ok": 200 <= r.status_code < 300,
                                    "status": r.status_code,
                                    "detail": detail or ("OK" if 200 <= r.status_code < 300 else "Error")}
        except Exception as e:
            results["postproxy"] = {"ok": False, "detail": f"Network: {e}"}

    # MailerSend
    mk = os.environ.get("MAILERSEND_API_KEY", "")
    mfrom = os.environ.get("MAILERSEND_FROM_EMAIL", "")
    if not mk:
        results["mailersend"] = {"ok": False, "detail": "MAILERSEND_API_KEY missing"}
    else:
        try:
            async with httpx.AsyncClient(timeout=10) as cli:
                r = await cli.get("https://api.mailersend.com/v1/domains",
                                  headers={"Authorization": f"Bearer {mk}"})
            if r.status_code == 200:
                detail = "Authenticated" + ("" if mfrom else " (MAILERSEND_FROM_EMAIL not set)")
                ok = bool(mfrom)
            else:
                detail = r.text[:80]
                ok = False
            results["mailersend"] = {"ok": ok, "status": r.status_code, "detail": detail}
        except Exception as e:
            results["mailersend"] = {"ok": False, "detail": f"Network: {e}"}

    # Apify
    ak = os.environ.get("APIFY_TOKEN", "")
    if not ak:
        results["apify"] = {"ok": False, "detail": "APIFY_TOKEN missing"}
    else:
        try:
            async with httpx.AsyncClient(timeout=10) as cli:
                r = await cli.get(f"https://api.apify.com/v2/users/me?token={ak}")
            results["apify"] = {"ok": r.status_code == 200, "status": r.status_code,
                                "detail": "Authenticated" if r.status_code == 200 else r.text[:80]}
        except Exception as e:
            results["apify"] = {"ok": False, "detail": f"Network: {e}"}

    # Shopify
    sk = os.environ.get("SHOPIFY_ADMIN_TOKEN", "")
    su = os.environ.get("SHOPIFY_STORE_URL", "").rstrip("/")
    if not sk or not su:
        results["shopify"] = {"ok": False, "detail": "Token/URL missing"}
    else:
        try:
            async with httpx.AsyncClient(timeout=10) as cli:
                r = await cli.get(f"{su}/admin/api/2024-01/shop.json",
                                  headers={"X-Shopify-Access-Token": sk})
            results["shopify"] = {"ok": r.status_code == 200, "status": r.status_code,
                                  "detail": "Authenticated" if r.status_code == 200 else r.text[:80]}
        except Exception as e:
            results["shopify"] = {"ok": False, "detail": f"Network: {e}"}

    # Emergent LLM
    ek = os.environ.get("EMERGENT_LLM_KEY", "")
    results["emergent_llm"] = {"ok": bool(ek),
                               "detail": "Configured" if ek else "EMERGENT_LLM_KEY missing"}

    # Canva
    cid = os.environ.get("CANVA_CLIENT_ID", "")
    csec = os.environ.get("CANVA_CLIENT_SECRET", "")
    if not (cid and csec):
        results["canva"] = {"ok": False, "detail": "CANVA_CLIENT_ID/SECRET missing"}
    else:
        tok_doc = await db_obj.canva_tokens.find_one({"id": "canva_admin"}, {"_id": 0})
        if tok_doc and tok_doc.get("access_token"):
            results["canva"] = {"ok": True, "detail": "OAuth connected"}
        else:
            results["canva"] = {"ok": False, "detail": "Credentials stored; click Connect to authorize"}

    # Slack webhook
    sw = os.environ.get("SLACK_WEBHOOK_URL", "")
    results["slack_alerts"] = {"ok": bool(sw),
                               "detail": "Webhook configured" if sw else "SLACK_WEBHOOK_URL missing"}

    return results


@api.get("/integrations/health")
async def integrations_health(email: str = Depends(require_admin)):
    """One-shot health check for every external integration. Also triggers Slack/Discord
    alerts on any green->red flip (30-min dedupe per service)."""
    results = await _collect_integrations_health(db)
    try:
        alerts = await check_health_and_alert(db, results)
        results["_meta"] = {"alerts": alerts}
    except Exception as e:
        logger.warning("Health alert check failed: %s", e)
    return results


# ---------- Audit log ----------
@api.get("/audit-log")
async def audit_log(limit: int = 50, email: str = Depends(require_admin)):
    docs = await db.audit_log.find({}, {"_id": 0})\
        .sort("at", -1).limit(limit).to_list(limit)
    return docs


# ---------- Startup: seed ----------
@app.on_event("startup")
async def on_startup():
    # Seed admin
    admin = await db.admins.find_one({"email": ADMIN_EMAIL})
    if not admin:
        await db.admins.insert_one({
            "id": new_id(),
            "email": ADMIN_EMAIL,
            "password_hash": _hash_pw(ADMIN_PASSWORD),
            "created_at": now_utc().isoformat(),
        })
        logger.info("Seeded admin %s", ADMIN_EMAIL)

    # Seed brand profile
    if not await db.brand_profile.find_one():
        await db.brand_profile.insert_one(to_mongo(BrandProfile()))
        logger.info("Seeded brand profile")

    # Seed competitors
    if await db.competitors.count_documents({}) == 0:
        for c in COMPETITORS_SEED:
            comp = Competitor(name=c["name"], handles=c["handles"])
            await db.competitors.insert_one(to_mongo(comp))
        logger.info("Seeded %d competitors", len(COMPETITORS_SEED))

    # Start scheduler
    if SCHED_ENABLED:
        app.state.scheduler = build_scheduler(
            db, run_audit_agent, run_strategist_agent, run_creative_for_slot,
            run_publisher_agent, run_optimizer_agent,
            health_fn=_collect_integrations_health,
        )
        app.state.scheduler.start()
        logger.info("Scheduler started (Sat 6am IST research, */15min publisher, Sun 7am optimizer, */5min health alerts)")


@app.on_event("shutdown")
async def on_shutdown():
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=False)
    client.close()


app.include_router(api)
app.include_router(build_canva_router(db, require_admin))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

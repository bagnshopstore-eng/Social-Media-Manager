"""Email notification + APScheduler weekly cron."""
from __future__ import annotations
import os
import logging
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
NOTIFY_EMAILS = [e.strip() for e in os.environ.get("NOTIFY_EMAIL", "").split(",") if e.strip()]
PUBLIC_URL = os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/")
SCHED_TZ = os.environ.get("SCHEDULER_TZ", "Asia/Kolkata")
SCHED_ENABLED = os.environ.get("SCHEDULER_ENABLED", "true").lower() == "true"


async def send_email(subject: str, html: str, to: list[str] | None = None) -> bool:
    to = to or NOTIFY_EMAILS
    if not RESEND_KEY:
        logger.warning("RESEND_API_KEY missing — would have sent: %s to %s", subject, to)
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_KEY}",
                         "Content-Type": "application/json"},
                json={"from": "BagnShop AI <onboarding@resend.dev>",
                      "to": to, "subject": subject, "html": html},
            )
            if r.status_code in (200, 202):
                return True
            logger.warning("Resend %s: %s", r.status_code, r.text[:300])
    except Exception as e:
        logger.warning("Resend exception: %s", e)
    return False


def build_scheduler(db, audit_fn, strategist_fn, creative_fn, publisher_fn, optimizer_fn) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=SCHED_TZ)

    async def weekly_research_and_creative():
        logger.info("[SCHED] weekly cycle starting")
        try:
            await audit_fn(db)
            await strategist_fn(db, days=7)
            slots = await db.content_calendar.find(
                {"status": "planned"}, {"_id": 0}
            ).sort("scheduled_datetime", 1).limit(12).to_list(12)
            count = 0
            for s in slots:
                r = await creative_fn(db, s["id"])
                if r:
                    count += 1
            pending = await db.posts.count_documents({"status": "pending_approval"})
            link = f"{PUBLIC_URL}/" if PUBLIC_URL else "(open the BagnShop AI dashboard)"
            html = (f"<h2 style='font-family:sans-serif'>Your week of {count} posts is ready to review.</h2>"
                    f"<p>Pending approval: <strong>{pending}</strong></p>"
                    f"<p><a href='{link}' style='background:#09090b;color:#fff;padding:10px 18px;text-decoration:none;border-radius:6px;'>Open dashboard</a></p>")
            await send_email("BagnShop AI — Your week is ready to review", html)
            logger.info("[SCHED] weekly cycle complete (%d posts)", count)
        except Exception as e:
            logger.exception("[SCHED] weekly cycle failed: %s", e)

    async def publish_tick():
        try:
            await publisher_fn(db)
        except Exception as e:
            logger.exception("[SCHED] publisher tick failed: %s", e)

    async def optimizer_weekly():
        try:
            await optimizer_fn(db)
        except Exception as e:
            logger.exception("[SCHED] optimizer failed: %s", e)

    # Saturday 6:00 AM IST — research + creative + notify
    sched.add_job(weekly_research_and_creative, CronTrigger(day_of_week="sat", hour=6, minute=0))
    # Every 15 minutes — publish approved posts
    sched.add_job(publish_tick, CronTrigger(minute="*/15"))
    # Sunday 7:00 AM IST — optimizer rollup
    sched.add_job(optimizer_weekly, CronTrigger(day_of_week="sun", hour=7, minute=0))
    return sched

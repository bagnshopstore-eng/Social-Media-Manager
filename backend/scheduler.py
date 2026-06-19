"""Email (MailerSend) + Slack/Discord alerts + APScheduler weekly cron."""
from __future__ import annotations
import os
import logging
import httpx
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

MAILERSEND_KEY = os.environ.get("MAILERSEND_API_KEY", "")
MAILERSEND_FROM = os.environ.get("MAILERSEND_FROM_EMAIL", "")
NOTIFY_EMAILS = [e.strip() for e in os.environ.get("NOTIFY_EMAIL", "").split(",") if e.strip()]
PUBLIC_URL = os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/")
SCHED_TZ = os.environ.get("SCHEDULER_TZ", "Asia/Kolkata")
SCHED_ENABLED = os.environ.get("SCHEDULER_ENABLED", "true").lower() == "true"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
ALERT_DEDUPE_MINUTES = int(os.environ.get("ALERT_DEDUPE_MINUTES", "30"))


async def send_email(subject: str, html: str, to: list[str] | None = None) -> bool:
    """Send transactional email via MailerSend."""
    to = to or NOTIFY_EMAILS
    if not MAILERSEND_KEY:
        logger.warning("MAILERSEND_API_KEY missing — would have sent: %s to %s", subject, to)
        return False
    if not MAILERSEND_FROM:
        logger.warning("MAILERSEND_FROM_EMAIL missing — cannot send: %s", subject)
        return False
    if not to:
        logger.warning("No NOTIFY_EMAIL recipients — would have sent: %s", subject)
        return False
    payload = {
        "from": {"email": MAILERSEND_FROM, "name": "BagnShop AI"},
        "to": [{"email": e} for e in to],
        "subject": subject,
        "html": html,
        "text": _html_to_text(html),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(
                "https://api.mailersend.com/v1/email",
                headers={
                    "Authorization": f"Bearer {MAILERSEND_KEY}",
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                json=payload,
            )
            if r.status_code in (200, 202):
                return True
            logger.warning("MailerSend %s: %s", r.status_code, r.text[:300])
    except Exception as e:
        logger.warning("MailerSend exception: %s", e)
    return False


def _html_to_text(html: str) -> str:
    import re
    txt = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", txt).strip()


# ----------------------------------------------------------------
# Slack / Discord alerts on health red flips (30-min dedupe)
# ----------------------------------------------------------------
async def post_slack(text: str, blocks: list[dict] | None = None) -> bool:
    if not SLACK_WEBHOOK_URL:
        return False
    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.post(SLACK_WEBHOOK_URL, json=payload)
            if r.status_code in (200, 204):
                return True
            logger.warning("Slack webhook %s: %s", r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("Slack webhook exception: %s", e)
    return False


async def post_discord(text: str) -> bool:
    if not DISCORD_WEBHOOK_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.post(DISCORD_WEBHOOK_URL, json={"content": text})
            return r.status_code in (200, 204)
    except Exception as e:
        logger.warning("Discord webhook exception: %s", e)
        return False


async def check_health_and_alert(db, current_results: dict) -> dict:
    """Compare current health snapshot to last stored state.
    For services that flip green->red, post Slack/Discord alert (30-min dedupe per service).
    Persists current state for next comparison.

    Returns: {"flips": [...], "alerted": [...], "deduped": [...]}.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=ALERT_DEDUPE_MINUTES)
    flips: list[str] = []
    alerted: list[str] = []
    deduped: list[str] = []

    for name, payload in current_results.items():
        if not isinstance(payload, dict):
            continue
        ok_now = bool(payload.get("ok"))
        prev = await db.health_state.find_one({"service": name}, {"_id": 0})
        ok_prev = bool(prev.get("ok")) if prev else True  # assume previously green

        if prev is None:
            await db.health_state.insert_one({
                "service": name, "ok": ok_now, "detail": payload.get("detail", ""),
                "status_code": payload.get("status"),
                "last_change_at": now.isoformat(),
                "last_alert_at": None,
            })
            continue

        if ok_prev and not ok_now:
            # green -> red flip
            flips.append(name)
            last_alert = prev.get("last_alert_at")
            should_alert = True
            if last_alert:
                try:
                    if datetime.fromisoformat(last_alert) > cutoff:
                        should_alert = False
                except Exception:
                    pass
            if should_alert:
                msg = (
                    f":rotating_light: *BagnShop AI — `{name}` went RED*\n"
                    f"> {payload.get('detail', 'no detail')}\n"
                    f"> Status: `{payload.get('status', 'n/a')}`\n"
                    f"> Dashboard: {PUBLIC_URL or '(set PUBLIC_BACKEND_URL)'}/settings"
                )
                sent_slack = await post_slack(msg)
                sent_disc = await post_discord(msg)
                if sent_slack or sent_disc:
                    alerted.append(name)
                    await db.health_state.update_one(
                        {"service": name},
                        {"$set": {
                            "ok": ok_now,
                            "detail": payload.get("detail", ""),
                            "status_code": payload.get("status"),
                            "last_change_at": now.isoformat(),
                            "last_alert_at": now.isoformat(),
                        }},
                    )
                    continue
            else:
                deduped.append(name)

        # update stored state for any change
        if ok_prev != ok_now:
            await db.health_state.update_one(
                {"service": name},
                {"$set": {
                    "ok": ok_now,
                    "detail": payload.get("detail", ""),
                    "status_code": payload.get("status"),
                    "last_change_at": now.isoformat(),
                }},
            )
        else:
            # only refresh detail
            await db.health_state.update_one(
                {"service": name},
                {"$set": {
                    "detail": payload.get("detail", ""),
                    "status_code": payload.get("status"),
                }},
            )

    return {"flips": flips, "alerted": alerted, "deduped": deduped}


# ----------------------------------------------------------------
# Cron scheduler
# ----------------------------------------------------------------
def build_scheduler(db, audit_fn, strategist_fn, creative_fn, publisher_fn, optimizer_fn,
                    health_fn=None) -> AsyncIOScheduler:
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

    async def health_tick():
        if not health_fn:
            return
        try:
            res = await health_fn(db)
            await check_health_and_alert(db, res)
        except Exception as e:
            logger.exception("[SCHED] health tick failed: %s", e)

    # Saturday 6:00 AM IST — research + creative + notify
    sched.add_job(weekly_research_and_creative, CronTrigger(day_of_week="sat", hour=6, minute=0))
    # Every 15 minutes — publish approved posts
    sched.add_job(publish_tick, CronTrigger(minute="*/15"))
    # Sunday 7:00 AM IST — optimizer rollup
    sched.add_job(optimizer_weekly, CronTrigger(day_of_week="sun", hour=7, minute=0))
    # Every 5 minutes — health check + alerts
    if health_fn:
        sched.add_job(health_tick, CronTrigger(minute="*/5"))
    return sched

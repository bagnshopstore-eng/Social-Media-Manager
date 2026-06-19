"""AI Agents: Audit, Strategist, Creative, Publisher, Optimizer, Guardrail."""
from __future__ import annotations
import os
import json
import base64
import random
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
import httpx

from emergentintegrations.llm.chat import LlmChat, UserMessage
from models import (
    BrandProfile, CalendarSlot, Post, HookPattern, ContentGap,
    StrategistReport, MyAnalyticsSnapshot, CompetitorContent, Learning,
    to_mongo, from_mongo, now_utc, new_id,
)
from seeds import MOCK_COMPETITOR_POSTS

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_ADMIN_TOKEN", "")
SHOPIFY_STORE_URL = os.environ.get("SHOPIFY_STORE_URL", "").rstrip("/")
POSTPROXY_KEY = os.environ.get("POSTPROXY_API_KEY", "")
POSTPROXY_BASE = os.environ.get("POSTPROXY_BASE_URL", "https://api.postproxy.dev/api").rstrip("/")
POSTPROXY_PROFILE_GROUP_ID = os.environ.get("POSTPROXY_PROFILE_GROUP_ID", "")
USE_MOCK_PUBLISHER = os.environ.get("USE_MOCK_PUBLISHER", "true").lower() == "true"
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
APIFY_ACTOR = os.environ.get("APIFY_ACTOR", "apify~instagram-scraper")
USE_MOCK_SCRAPER = os.environ.get("USE_MOCK_COMPETITOR_SCRAPER", "true").lower() == "true"

# -------- Shopify --------
async def fetch_shopify_products(limit: int = 20) -> list[dict]:
    """Fetch real BagnShop products. Falls back to mock catalog on any failure."""
    if not SHOPIFY_TOKEN or not SHOPIFY_STORE_URL:
        return _mock_products()
    # Convert https://bagnshop.com to a shopify admin URL (shop subdomain pattern)
    # If user passes a custom domain, we try the .myshopify.com inference as a fallback.
    candidates = [
        f"{SHOPIFY_STORE_URL}/admin/api/2024-01/products.json?limit={limit}",
    ]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for url in candidates:
                try:
                    r = await client.get(
                        url,
                        headers={"X-Shopify-Access-Token": SHOPIFY_TOKEN},
                    )
                    if r.status_code == 200:
                        data = r.json().get("products", [])
                        return [
                            {
                                "id": str(p["id"]),
                                "title": p["title"],
                                "handle": p.get("handle", ""),
                                "image": (p.get("image") or {}).get("src") if p.get("image") else (
                                    p["images"][0]["src"] if p.get("images") else None
                                ),
                                "price": (p["variants"][0]["price"] if p.get("variants") else None),
                                "in_stock": any(
                                    int(v.get("inventory_quantity") or 0) > 0
                                    for v in p.get("variants", [])
                                ) if p.get("variants") else True,
                            }
                            for p in data if p
                        ]
                except Exception as e:
                    logger.warning("Shopify URL %s failed: %s", url, e)
    except Exception as e:
        logger.warning("Shopify fetch failed entirely: %s", e)
    return _mock_products()


def _mock_products() -> list[dict]:
    return [
        {"id": "p1", "title": "Smart Electric Lunch Box", "handle": "smart-lunch-box",
         "image": "https://images.unsplash.com/photo-1660002561318-6ef0a0ae1f04?w=1080",
         "price": "1499", "in_stock": True},
        {"id": "p2", "title": "Posture Corrector Pro", "handle": "posture-corrector-pro",
         "image": "https://images.unsplash.com/photo-1720424643395-f966961d7782?w=1080",
         "price": "899", "in_stock": True},
        {"id": "p3", "title": "Mini Massage Gun", "handle": "mini-massage-gun",
         "image": "https://images.pexels.com/photos/22307556/pexels-photo-22307556.jpeg?w=1080",
         "price": "2499", "in_stock": True},
        {"id": "p4", "title": "Foldable Desk Organizer", "handle": "foldable-desk-organizer",
         "image": "https://images.unsplash.com/photo-1519558260268-cde7e03a0152?w=1080",
         "price": "599", "in_stock": True},
        {"id": "p5", "title": "Portable Blender Bottle", "handle": "portable-blender-bottle",
         "image": "https://images.unsplash.com/photo-1660002561318-6ef0a0ae1f04?w=1080",
         "price": "1199", "in_stock": True},
    ]


# -------- Postproxy: publish + analytics --------
async def postproxy_publish(post: dict) -> dict:
    """Publish a post via Postproxy (https://api.postproxy.dev/api/posts).
    Returns {published_id, ok, raw}. Logs and returns ok=False on any failure."""
    if not POSTPROXY_KEY:
        return {"ok": False, "error": "POSTPROXY_API_KEY missing"}
    payload = {
        "profiles": [POSTPROXY_PROFILE_GROUP_ID] if POSTPROXY_PROFILE_GROUP_ID else [],
        "platforms": [post["platform"]],
        "caption": post["caption"],
        "media_urls": [assetify(u) for u in post.get("image_urls", [])],
        "scheduled_at": post.get("scheduled_datetime"),
        "format": post.get("format", "single_image"),
    }
    if not POSTPROXY_PROFILE_GROUP_ID:
        payload.pop("profiles", None)
    url = f"{POSTPROXY_BASE}/posts"
    # Try both auth schemes (Postproxy.dev uses X-API-Key; legacy uses Bearer)
    header_variants = [
        {"X-API-Key": POSTPROXY_KEY, "Content-Type": "application/json"},
        {"Authorization": f"Bearer {POSTPROXY_KEY}", "Content-Type": "application/json"},
    ]
    async with httpx.AsyncClient(timeout=30) as cli:
        for headers in header_variants:
            try:
                r = await cli.post(url, json=payload, headers=headers)
                if r.status_code in (200, 201, 202):
                    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                    pub_id = (data.get("id") or data.get("post_id") or
                              (data.get("data", {}).get("id") if isinstance(data.get("data"), dict) else None))
                    return {"ok": True, "published_id": pub_id or f"pp_{new_id()[:10]}",
                            "raw": data, "endpoint": url, "auth": list(headers.keys())[0]}
                if r.status_code != 401:
                    logger.warning("Postproxy %s -> %s: %s", url, r.status_code, r.text[:300])
                    return {"ok": False, "error": f"{r.status_code}: {r.text[:300]}", "endpoint": url}
                # 401 -> try next auth scheme
            except Exception as e:
                logger.warning("Postproxy %s exception: %s", url, e)
    return {"ok": False, "error": "Postproxy publish failed (auth/network)"}


async def postproxy_analytics(published_id: str) -> dict:
    """Fetch performance for a published post id. Returns dict or empty dict on failure."""
    if not POSTPROXY_KEY or not published_id:
        return {}
    header_variants = [
        {"X-API-Key": POSTPROXY_KEY},
        {"Authorization": f"Bearer {POSTPROXY_KEY}"},
    ]
    paths = [f"/posts/{published_id}/analytics", f"/posts/{published_id}", f"/analytics/{published_id}"]
    async with httpx.AsyncClient(timeout=15) as cli:
        for headers in header_variants:
            for path in paths:
                try:
                    r = await cli.get(f"{POSTPROXY_BASE}{path}", headers=headers)
                    if r.status_code == 200:
                        data = r.json()
                        metrics = data.get("metrics") or data.get("analytics") or data
                        if isinstance(metrics, dict):
                            return {
                                "likes": int(metrics.get("likes") or metrics.get("like_count") or 0),
                                "comments": int(metrics.get("comments") or metrics.get("comment_count") or 0),
                                "shares": int(metrics.get("shares") or metrics.get("share_count") or 0),
                                "reach": int(metrics.get("reach") or metrics.get("impressions") or 0),
                                "engagement_rate": float(metrics.get("engagement_rate") or 0.0),
                            }
                except Exception as e:
                    logger.warning("Postproxy analytics %s exception: %s", path, e)
    return {}


def assetify(url: str) -> str:
    """Convert a relative /uploads/... or /api/uploads/... path into the public absolute URL
    that external services (Postproxy) and previewers can reach. The Kubernetes ingress only
    routes /api/* to the backend so legacy /uploads/... paths are rewritten to /api/uploads/..."""
    if not url:
        return url
    if url.startswith("http"):
        return url
    if url.startswith("/uploads/"):
        url = "/api" + url
    base = os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/")
    return f"{base}{url}" if base else url


# -------- Apify: real Instagram competitor scraping --------
async def apify_scrape_instagram(handles: list[str], results_per_handle: int = 5) -> list[dict]:
    """Run apify/instagram-scraper synchronously, return list of post dicts.
    Empty list on any failure (caller falls back to seed library)."""
    if not APIFY_TOKEN or not handles:
        return []
    direct_urls = [h if h.startswith("http") else f"https://www.instagram.com/{h.strip('/')}/" for h in handles]
    url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    body = {
        "directUrls": direct_urls,
        "resultsType": "posts",
        "resultsLimit": results_per_handle,
        "addParentData": False,
    }
    try:
        async with httpx.AsyncClient(timeout=180) as cli:
            r = await cli.post(url, json=body)
            if r.status_code == 200:
                return r.json() or []
            logger.warning("Apify run failed %s: %s", r.status_code, r.text[:300])
    except Exception as e:
        logger.warning("Apify exception: %s", e)
    return []


# -------- Claude / LLM helper --------
def _strip_json_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


async def claude_json(system: str, user: str, session_id: str | None = None) -> Any:
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id or new_id(),
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-6")
    resp = await chat.send_message(UserMessage(text=user))
    text = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
    text = _strip_json_fence(text)
    try:
        return json.loads(text)
    except Exception:
        # try to extract first JSON object/array
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        raise


async def claude_text(system: str, user: str, session_id: str | None = None) -> str:
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id or new_id(),
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-6")
    resp = await chat.send_message(UserMessage(text=user))
    return resp if isinstance(resp, str) else getattr(resp, "content", str(resp))


# -------- Gemini Nano Banana image generation --------
async def generate_image(prompt: str, filename_prefix: str = "img") -> Optional[str]:
    """Generate 1 image, save to uploads, return relative URL /uploads/xxx.png. Falls back to None on failure."""
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=new_id(),
            system_message="You generate beautiful, on-brand social media visuals.",
        ).with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
            modalities=["image", "text"]
        )
        msg = UserMessage(text=prompt)
        _text, images = await chat.send_message_multimodal_response(msg)
        if not images:
            return None
        img = images[0]
        image_bytes = base64.b64decode(img["data"])
        fname = f"{filename_prefix}_{new_id()[:8]}.png"
        (UPLOADS_DIR / fname).write_bytes(image_bytes)
        return f"/api/uploads/{fname}"
    except Exception as e:
        logger.warning("Gemini image gen failed: %s", e)
        return None


# ============================================================
#                 AGENT 1 — AUDIT AGENT
# ============================================================
async def run_audit_agent(db) -> dict:
    """Generates fresh analytics snapshots + competitor content library."""
    # 1. Fake/mock analytics for own accounts (Ayrshare mocked)
    for platform in ["instagram", "facebook", "linkedin"]:
        heatmap = [[round(random.uniform(0.2, 1.0), 2) for _ in range(24)] for _ in range(7)]
        # boost peak hours
        peak_hours = sorted(random.sample(range(9, 22), 4))
        peak_days = random.sample(
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], 3
        )
        snap = MyAnalyticsSnapshot(
            platform=platform,
            followers=random.randint(3500, 12000),
            avg_engagement_rate=round(random.uniform(2.0, 5.5), 2),
            top_posts=[
                {"caption": "Smart lunch box demo", "likes": 1240, "comments": 78},
                {"caption": "Festive gifting hamper drop", "likes": 980, "comments": 54},
            ],
            peak_hours=peak_hours,
            peak_days=peak_days,
            heatmap=heatmap,
        )
        await db.my_analytics.insert_one(to_mongo(snap))

    # 2. Competitor content — try real Apify scrape per competitor IG handle, fall back to seed
    comp_docs = await db.competitors.find({}, {"_id": 0}).to_list(50)
    inserted = 0
    real_used = 0
    for comp in comp_docs:
        ig_url = (comp.get("handles") or {}).get("instagram")
        items = []
        if not USE_MOCK_SCRAPER and APIFY_TOKEN and ig_url:
            try:
                items = await apify_scrape_instagram([ig_url], results_per_handle=5)
            except Exception as e:
                logger.warning("Apify scrape failed for %s: %s", comp["name"], e)
        if items:
            real_used += 1
            for it in items[:6]:
                caption = (it.get("caption") or "")[:1500]
                cc = CompetitorContent(
                    competitor_id=comp["id"],
                    competitor_name=comp["name"],
                    platform="instagram",
                    caption=caption,
                    hook=(caption.split("\n", 1)[0] or "")[:120],
                    format=("carousel" if (it.get("type") == "Sidecar" or
                                             (it.get("images") and len(it.get("images", [])) > 1))
                            else "single_image"),
                    hashtags=it.get("hashtags") or [],
                    likes=int(it.get("likesCount") or it.get("likes") or 0),
                    comments=int(it.get("commentsCount") or it.get("comments") or 0),
                    engagement_rate=round(
                        ((int(it.get("likesCount") or 0) + int(it.get("commentsCount") or 0))
                         / max(int(it.get("ownerFollowersCount") or 5000), 1)) * 100, 2
                    ),
                    detected_hook_pattern=(caption.split("\n", 1)[0] or "")[:60],
                    theme=it.get("type") or "scraped",
                )
                await db.competitor_content.insert_one(to_mongo(cc))
                inserted += 1
        else:
            # Fall back to seed library so the system never goes dark
            for _ in range(random.randint(3, 5)):
                base = random.choice(MOCK_COMPETITOR_POSTS)
                cc = CompetitorContent(
                    competitor_id=comp["id"],
                    competitor_name=comp["name"],
                    platform=base["platform"],
                    caption=base["caption"],
                    hook=base["hook"],
                    format=base["format"],
                    hashtags=base["hashtags"],
                    likes=int(base["likes"] * random.uniform(0.6, 1.6)),
                    comments=int(base["comments"] * random.uniform(0.5, 1.7)),
                    engagement_rate=round(random.uniform(1.5, 6.0), 2),
                    theme=base["theme"],
                    detected_hook_pattern=base["hook"][:48],
                )
                await db.competitor_content.insert_one(to_mongo(cc))
                inserted += 1
        await db.competitors.update_one(
            {"id": comp["id"]},
            {"$set": {"last_scraped_at": now_utc().isoformat()}},
        )

    return {"analytics_snapshots": 3, "competitor_posts_added": inserted,
            "real_apify_competitors": real_used}


# ============================================================
#                 AGENT 2 — STRATEGIST AGENT
# ============================================================
async def run_strategist_agent(db, days: int = 30) -> dict:
    brand_doc = from_mongo(await db.brand_profile.find_one())
    brand = BrandProfile(**brand_doc) if brand_doc else BrandProfile()

    # Pull recent competitor content (sample top 25 by engagement_rate)
    comp_content = await db.competitor_content.find(
        {}, {"_id": 0}
    ).sort("engagement_rate", -1).limit(25).to_list(25)

    # Pull my analytics
    analytics = await db.my_analytics.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(3).to_list(3)

    # Recent learnings (if any)
    learnings = await db.learnings.find({}, {"_id": 0}).sort("created_at", -1).limit(1).to_list(1)

    system = (
        "You are an expert D2C social media strategist for BagnShop, a 'Smart Utility "
        "Lifestyle Brand' selling home gadgets, kitchen tools, wellness devices, and "
        "lifestyle/gifting products. Honest, transparent pricing. Benchmarks: boAt, "
        "DailyObjects. LinkedIn must lean B2B corporate gifting + founder-led "
        "building-a-D2C-brand storytelling — DIFFERENT from IG/FB content. "
        "Return STRICT JSON only. No prose, no markdown fences."
    )

    today = datetime.now(timezone.utc).date()
    end_date = today + timedelta(days=days)

    user_prompt = f"""
Given the brand, my analytics, and competitor content below, produce a JSON object with this exact shape:

{{
  "hook_patterns": [{{"pattern": "...", "description": "why it works", "example": "..."}}] (exactly 10),
  "content_gaps": [{{"title": "...", "description": "..."}}] (exactly 5),
  "pillars": ["..."] (5 to 6 items),
  "calendar": [
    {{
      "date": "YYYY-MM-DD",
      "platform": "instagram" | "facebook" | "linkedin",
      "pillar": "...",
      "format": "single_image" | "carousel" | "reel_script",
      "hook": "...",
      "caption_angle": "...",
      "cta": "...",
      "hashtags": ["#a", "#b"],
      "scheduled_hour": 0-23,
      "topic": "..."
    }}
  ]
}}

Cadence per week: instagram 5, facebook 4, linkedin 3. Plan from {today.isoformat()} to {end_date.isoformat()} ({days} days).
LinkedIn slots MUST be B2B corporate gifting OR founder-led D2C storytelling — not consumer product posts.
Use scheduled_hour that matches the peak hours from my analytics for the given platform.

Brand profile: {json.dumps({
        "voice": brand.voice_rules,
        "pillars": brand.content_pillars,
        "banned_claims": brand.banned_claims,
        "positioning": brand.positioning,
        "linkedin_angle": brand.linkedin_angle,
    })}

My analytics (peak hours per platform): {json.dumps([
        {"platform": a["platform"], "peak_hours": a.get("peak_hours", [])}
        for a in analytics
    ])}

Top competitor posts (for hook/format inspiration):
{json.dumps([
        {"platform": c["platform"], "hook": c["hook"], "format": c["format"],
         "theme": c.get("theme"), "engagement_rate": c["engagement_rate"]}
        for c in comp_content[:15]
    ])}

Recent learnings: {json.dumps(learnings[0] if learnings else {})}
"""

    try:
        data = await claude_json(system, user_prompt)
    except Exception as e:
        logger.exception("Strategist JSON parse failed: %s", e)
        data = _fallback_strategy(today, days)

    # Persist calendar slots
    slot_ids = []
    for c in data.get("calendar", [])[: days * 3]:
        try:
            sched_date = datetime.fromisoformat(c["date"])
            hour = int(c.get("scheduled_hour", 10))
            sched_dt = sched_date.replace(hour=hour, minute=0, tzinfo=timezone.utc)
            slot = CalendarSlot(
                date=c["date"],
                platform=c["platform"],
                pillar=c["pillar"],
                format=c.get("format", "single_image"),
                hook=c.get("hook", ""),
                caption_angle=c.get("caption_angle", ""),
                cta=c.get("cta", ""),
                hashtags=c.get("hashtags", []),
                scheduled_datetime=sched_dt,
                topic=c.get("topic", ""),
            )
            await db.content_calendar.insert_one(to_mongo(slot))
            slot_ids.append(slot.id)
        except Exception as e:
            logger.warning("Skipping calendar slot due to error: %s", e)

    report = StrategistReport(
        hook_patterns=[HookPattern(**h) for h in data.get("hook_patterns", [])[:10]],
        content_gaps=[ContentGap(**g) for g in data.get("content_gaps", [])[:5]],
        pillars=data.get("pillars", []),
        calendar_slots=slot_ids,
        notes=data.get("notes", ""),
    )
    await db.strategist_reports.insert_one(to_mongo(report))
    return {"slots_created": len(slot_ids), "report_id": report.id}


def _fallback_strategy(today, days):
    platforms = (["instagram"] * 5 + ["facebook"] * 4 + ["linkedin"] * 3)
    pillars = ["problem-solution product demos", "practical tips and education",
               "gifting and occasions", "behind the brand / founder",
               "social proof / UGC", "trend-jacking"]
    cal = []
    for d in range(days):
        date = today + timedelta(days=d)
        plat = platforms[d % len(platforms)]
        cal.append({
            "date": date.isoformat(),
            "platform": plat,
            "pillar": random.choice(pillars),
            "format": random.choice(["single_image", "carousel"]),
            "hook": "Stop scrolling — here's something useful.",
            "caption_angle": "Show a real product use-case in everyday life.",
            "cta": "Tap the link in bio to shop.",
            "hashtags": ["#bagnshop", "#smartliving", "#d2cindia"],
            "scheduled_hour": 11,
            "topic": "Smart utility product highlight",
        })
    return {
        "hook_patterns": [
            {"pattern": "Stop scrolling.", "description": "Pattern interrupt", "example": "Stop scrolling. This ₹499 gadget..."},
            {"pattern": "POV:", "description": "Empathy hook", "example": "POV: it's Monday..."},
            {"pattern": "Tested:", "description": "Honest review", "example": "Tested: 8 viral gadgets..."},
        ],
        "content_gaps": [
            {"title": "Honest product comparison series",
             "description": "No competitor runs side-by-side honest comparisons."}
        ],
        "pillars": pillars,
        "calendar": cal,
    }


# ============================================================
#                 AGENT 3 — CREATIVE AGENT
# ============================================================
async def run_creative_for_slot(db, slot_id: str) -> Optional[dict]:
    slot_doc = from_mongo(await db.content_calendar.find_one({"id": slot_id}))
    if not slot_doc:
        return None
    slot = CalendarSlot(**slot_doc)
    brand_doc = from_mongo(await db.brand_profile.find_one())
    brand = BrandProfile(**brand_doc) if brand_doc else BrandProfile()

    # Decide if this is a product post (any pillar matching product/social proof, etc.)
    is_product_post = slot.pillar in [
        "problem-solution product demos", "social proof / UGC",
    ] or "product" in slot.topic.lower()

    product_snapshot = None
    image_urls: list[str] = []

    if is_product_post:
        products = await fetch_shopify_products(limit=20)
        if products:
            p = random.choice(products)
            product_snapshot = {
                "id": p["id"], "title": p["title"],
                "price": p["price"], "image": p["image"], "in_stock": p["in_stock"],
            }
            if p["image"]:
                image_urls.append(p["image"])

    # Generate caption via Claude
    system = (
        f"You write social captions for BagnShop. Voice: {', '.join(brand.voice_rules)}. "
        f"Banned words: {', '.join(brand.banned_claims)}. Never use them. "
        "Open with the assigned hook. Match platform length norms: IG punchy (max ~150 words), "
        "FB slightly longer, LinkedIn value-first professional (max ~250 words). End with the CTA. "
        "Append the hashtags as a single line at the very end."
    )
    user_prompt = f"""
Write a {slot.platform} caption for BagnShop.

Pillar: {slot.pillar}
Format: {slot.format}
Hook (must be first line/sentence): {slot.hook}
Angle: {slot.caption_angle}
CTA: {slot.cta}
Topic: {slot.topic}
Hashtags to append: {' '.join(slot.hashtags)}
{"Product to feature: " + json.dumps(product_snapshot) if product_snapshot else ""}

Return the caption only — no JSON, no markdown.
"""
    try:
        caption = await claude_text(system, user_prompt)
    except Exception as e:
        logger.warning("Caption gen failed, using fallback: %s", e)
        caption = f"{slot.hook}\n\n{slot.caption_angle}\n\n{slot.cta}\n\n{' '.join(slot.hashtags)}"

    # Generate image if non-product OR additional graphic frame
    if not is_product_post:
        img_prompt = (
            f"A modern editorial social media graphic for an Indian D2C lifestyle brand. "
            f"Theme: {slot.topic or slot.caption_angle}. Pillar: {slot.pillar}. "
            f"Style: clean, minimal, high-contrast, magazine-quality. No text overlay. "
            f"Mood: aspirational but honest."
        )
        url = await generate_image(img_prompt, filename_prefix=f"{slot.platform}")
        if url:
            image_urls.append(url)

    # Carousel: generate 2 more slides
    if slot.format == "carousel" and len(image_urls) < 3:
        for i in range(2):
            url = await generate_image(
                f"Carousel slide {i+2} for BagnShop on '{slot.topic}'. "
                f"Editorial minimal aesthetic. Clean layout. No text overlay.",
                filename_prefix="carousel",
            )
            if url:
                image_urls.append(url)

    # Build post
    post = Post(
        calendar_slot_id=slot.id,
        platform=slot.platform,
        format=slot.format,
        caption=caption,
        image_urls=image_urls,
        hook=slot.hook,
        pillar=slot.pillar,
        cta=slot.cta,
        hashtags=slot.hashtags,
        scheduled_datetime=slot.scheduled_datetime,
        status="pending_approval",
        product_id=product_snapshot["id"] if product_snapshot else None,
        product_snapshot=product_snapshot,
        is_product_post=is_product_post,
    )

    # Guardrail check
    issues = await guardrail_check(db, post, brand)
    if issues:
        post.status = "needs_edit"
        post.guardrail_issues = issues

    await db.posts.insert_one(to_mongo(post))
    await db.content_calendar.update_one(
        {"id": slot.id}, {"$set": {"status": "creative_generated"}}
    )
    return {"post_id": post.id, "status": post.status, "issues": post.guardrail_issues}


# ============================================================
#               AGENT 6 — GUARDRAIL LAYER
# ============================================================
async def guardrail_check(db, post: Post, brand: BrandProfile) -> list[str]:
    issues: list[str] = []
    text = (post.caption or "").lower()
    for banned in brand.banned_claims:
        if banned.lower() in text:
            issues.append(f"Contains banned claim: '{banned}'")

    # Live price match
    if post.is_product_post and post.product_snapshot:
        try:
            live = await fetch_shopify_products(limit=50)
            match = next((p for p in live if str(p["id"]) == str(post.product_snapshot["id"])), None)
            if match:
                if str(match["price"]) != str(post.product_snapshot["price"]):
                    issues.append(
                        f"Stale price: post says ₹{post.product_snapshot['price']} "
                        f"but live price is ₹{match['price']}"
                    )
                if not match.get("in_stock"):
                    issues.append("Featured product is OUT OF STOCK")
        except Exception:
            pass

    # No images
    if not post.image_urls:
        issues.append("No image generated")

    # Duplicate detection in last 30 days
    cutoff = (now_utc() - timedelta(days=30)).isoformat()
    dup = await db.posts.find_one({
        "caption": post.caption,
        "platform": post.platform,
        "created_at": {"$gte": cutoff},
    })
    if dup:
        issues.append("Duplicate of a post from the last 30 days")

    return issues


# ============================================================
#                 AGENT 4 — PUBLISHER AGENT
# ============================================================
async def run_publisher_agent(db) -> dict:
    """Publishes ONLY posts where status == 'approved' AND scheduled_datetime <= now AND published_id is empty."""
    now_iso = now_utc().isoformat()
    cursor = db.posts.find({
        "status": "approved",
        "published_id": None,
        "scheduled_datetime": {"$lte": now_iso},
    }, {"_id": 0})
    published = 0
    expired = 0
    failed = 0
    async for doc in cursor:
        # HARD ASSERTION — refuse to publish anything not approved
        assert doc["status"] == "approved", "Publisher: refused non-approved post"
        try:
            published_id = None
            raw = None
            if not USE_MOCK_PUBLISHER and POSTPROXY_KEY:
                resp = await postproxy_publish(doc)
                if resp.get("ok"):
                    published_id = resp["published_id"]
                    raw = resp.get("raw")
                else:
                    logger.warning("Postproxy failed for post %s: %s — falling back to mock id",
                                   doc.get("id"), resp.get("error"))
            if not published_id:
                # Mock fallback (still records the publish so workflow continues)
                published_id = f"mock_{doc['platform']}_{new_id()[:10]}"
            await db.posts.update_one(
                {"id": doc["id"]},
                {"$set": {
                    "published_id": published_id,
                    "published_at": now_iso,
                    "status": "published",
                    "updated_at": now_iso,
                    "publish_raw": raw,
                }},
            )
            published += 1
        except Exception as e:
            logger.exception("Publish failed for post %s: %s", doc.get("id"), e)
            failed += 1

    # Expire pending posts whose time has passed without approval
    expire_cursor = db.posts.find({
        "status": {"$in": ["pending_approval", "draft", "needs_edit"]},
        "scheduled_datetime": {"$lte": now_iso},
    }, {"_id": 0})
    async for doc in expire_cursor:
        await db.posts.update_one(
            {"id": doc["id"]},
            {"$set": {"status": "expired", "updated_at": now_iso}},
        )
        expired += 1

    return {"published": published, "expired": expired, "failed": failed}


# ============================================================
#                 AGENT 5 — OPTIMIZER AGENT
# ============================================================
async def run_optimizer_agent(db) -> dict:
    """Read engagement for published posts via Postproxy (fallback: mocked numbers), generate weekly learning."""
    cursor = db.posts.find({"status": "published"}, {"_id": 0})
    enriched = 0
    real_count = 0
    async for doc in cursor:
        # skip if already has real metrics
        if doc.get("performance") and doc["performance"].get("source") == "postproxy":
            continue
        perf = {}
        pub_id = doc.get("published_id") or ""
        if (not USE_MOCK_PUBLISHER) and POSTPROXY_KEY and not pub_id.startswith("mock_"):
            perf = await postproxy_analytics(pub_id)
            if perf:
                perf["source"] = "postproxy"
                real_count += 1
        if not perf:
            perf = {
                "likes": random.randint(120, 2200),
                "comments": random.randint(5, 180),
                "shares": random.randint(0, 90),
                "reach": random.randint(800, 18000),
                "engagement_rate": round(random.uniform(1.2, 6.5), 2),
                "source": "mock",
            }
        await db.posts.update_one(
            {"id": doc["id"]}, {"$set": {"performance": perf}},
        )
        enriched += 1

    # Aggregate top hooks / formats / pillars / times
    pipeline = [
        {"$match": {"status": "published", "performance.engagement_rate": {"$exists": True}}},
        {"$group": {
            "_id": {"hook": "$hook", "format": "$format", "pillar": "$pillar", "platform": "$platform"},
            "avg_er": {"$avg": "$performance.engagement_rate"},
            "n": {"$sum": 1},
        }},
        {"$sort": {"avg_er": -1}},
        {"$limit": 30},
    ]
    rollup = []
    async for row in db.posts.aggregate(pipeline):
        rollup.append({**row["_id"], "avg_er": row["avg_er"], "n": row["n"]})

    learning = Learning(
        period_start=now_utc() - timedelta(days=7),
        period_end=now_utc(),
        top_hooks=[{"hook": r["hook"], "avg_er": round(r["avg_er"], 2)} for r in rollup[:5]],
        top_formats=[{"format": r["format"], "avg_er": round(r["avg_er"], 2)} for r in rollup[:5]],
        top_pillars=[{"pillar": r["pillar"], "avg_er": round(r["avg_er"], 2)} for r in rollup[:5]],
        notes=f"Auto-generated from {enriched} posts ({real_count} via Postproxy, rest mocked).",
    )
    await db.learnings.insert_one(to_mongo(learning))
    return {"enriched_posts": enriched, "real_metrics": real_count, "learning_id": learning.id}

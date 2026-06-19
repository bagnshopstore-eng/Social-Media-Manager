"""Canva Connect API: OAuth (PKCE) + Brand Templates + Autofill + Exports."""
from __future__ import annotations
import os
import base64
import hashlib
import secrets
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from models import now_utc, new_id

logger = logging.getLogger(__name__)

CANVA_CLIENT_ID = os.environ.get("CANVA_CLIENT_ID", "")
CANVA_CLIENT_SECRET = os.environ.get("CANVA_CLIENT_SECRET", "")
CANVA_REDIRECT_URI = os.environ.get("CANVA_REDIRECT_URI", "")
PUBLIC_URL = os.environ.get("PUBLIC_BACKEND_URL", "").rstrip("/")
UPLOADS_DIR = Path(__file__).parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

CANVA_AUTH_URL = "https://www.canva.com/api/oauth/authorize"
CANVA_TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
CANVA_API = "https://api.canva.com/rest/v1"
SCOPES = (
    "brandtemplate:meta:read brandtemplate:content:read "
    "design:meta:read design:content:read design:content:write "
    "asset:read asset:write"
)


class AutofillReq(BaseModel):
    template_id: str
    data: dict  # {field_name: {type:"text"|"image", text?:str, asset_id?:str}}
    title: Optional[str] = None


class CreatePostFromTemplateReq(BaseModel):
    slot_id: str
    template_id: str
    fields: dict  # {field_name: text_value}
    title: Optional[str] = None


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    return verifier, challenge


def _basic_auth_header() -> str:
    raw = f"{CANVA_CLIENT_ID}:{CANVA_CLIENT_SECRET}".encode()
    return "Basic " + base64.b64encode(raw).decode()


async def _save_tokens(db, tokens: dict) -> None:
    expires_in = int(tokens.get("expires_in", 14400))
    doc = {
        "id": "canva_admin",
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "token_type": tokens.get("token_type", "Bearer"),
        "scope": tokens.get("scope", SCOPES),
        "expires_at": (now_utc() + timedelta(seconds=expires_in - 60)).isoformat(),
        "updated_at": now_utc().isoformat(),
    }
    await db.canva_tokens.update_one(
        {"id": "canva_admin"}, {"$set": doc}, upsert=True
    )


async def _get_valid_token(db) -> Optional[str]:
    doc = await db.canva_tokens.find_one({"id": "canva_admin"}, {"_id": 0})
    if not doc:
        return None
    expires_at = doc.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
            if exp > now_utc():
                return doc["access_token"]
        except Exception:
            pass
    # refresh
    rt = doc.get("refresh_token")
    if not rt:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(
                CANVA_TOKEN_URL,
                headers={
                    "Authorization": _basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "refresh_token", "refresh_token": rt},
            )
        if r.status_code == 200:
            await _save_tokens(db, r.json())
            return r.json().get("access_token")
        logger.warning("Canva refresh failed %s: %s", r.status_code, r.text[:200])
    except Exception as e:
        logger.warning("Canva refresh exception: %s", e)
    return None


def build_router(db, require_admin) -> APIRouter:
    router = APIRouter(prefix="/api/canva", tags=["canva"])

    @router.get("/status")
    async def status(email: str = Depends(require_admin)):
        doc = await db.canva_tokens.find_one({"id": "canva_admin"}, {"_id": 0})
        if not doc:
            return {"connected": False, "configured": bool(CANVA_CLIENT_ID and CANVA_CLIENT_SECRET)}
        expires_at = doc.get("expires_at")
        return {
            "connected": True,
            "configured": True,
            "expires_at": expires_at,
            "scope": doc.get("scope"),
        }

    @router.get("/connect")
    async def connect(email: str = Depends(require_admin)):
        if not CANVA_CLIENT_ID:
            raise HTTPException(400, "CANVA_CLIENT_ID missing")
        verifier, challenge = _pkce()
        state = secrets.token_urlsafe(24)
        await db.canva_oauth_states.insert_one({
            "state": state, "code_verifier": verifier,
            "admin_email": email,
            "created_at": now_utc().isoformat(),
        })
        redirect = CANVA_REDIRECT_URI or f"{PUBLIC_URL}/api/canva/callback"
        from urllib.parse import urlencode
        params = {
            "code_challenge": challenge,
            "code_challenge_method": "s256",
            "scope": SCOPES,
            "response_type": "code",
            "client_id": CANVA_CLIENT_ID,
            "redirect_uri": redirect,
            "state": state,
        }
        url = f"{CANVA_AUTH_URL}?{urlencode(params)}"
        return {"authorize_url": url, "state": state}

    @router.get("/callback")
    async def callback(code: str = Query(...), state: str = Query(...)):
        st = await db.canva_oauth_states.find_one({"state": state}, {"_id": 0})
        if not st:
            raise HTTPException(400, "Invalid state")
        redirect = CANVA_REDIRECT_URI or f"{PUBLIC_URL}/api/canva/callback"
        try:
            async with httpx.AsyncClient(timeout=15) as cli:
                r = await cli.post(
                    CANVA_TOKEN_URL,
                    headers={
                        "Authorization": _basic_auth_header(),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "code_verifier": st["code_verifier"],
                        "redirect_uri": redirect,
                    },
                )
            if r.status_code != 200:
                logger.warning("Canva token exchange failed: %s %s", r.status_code, r.text[:300])
                fe = f"{PUBLIC_URL}/settings?canva=error&detail={r.status_code}"
                return RedirectResponse(fe)
            await _save_tokens(db, r.json())
            await db.canva_oauth_states.delete_one({"state": state})
        except Exception as e:
            logger.exception("Canva callback failed: %s", e)
            return RedirectResponse(f"{PUBLIC_URL}/settings?canva=error")
        return RedirectResponse(f"{PUBLIC_URL}/settings?canva=success")

    @router.post("/disconnect")
    async def disconnect(email: str = Depends(require_admin)):
        await db.canva_tokens.delete_many({"id": "canva_admin"})
        return {"disconnected": True}

    @router.get("/templates")
    async def list_templates(email: str = Depends(require_admin)):
        token = await _get_valid_token(db)
        if not token:
            raise HTTPException(401, "Canva not connected")
        try:
            async with httpx.AsyncClient(timeout=20) as cli:
                r = await cli.get(
                    f"{CANVA_API}/brand-templates",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if r.status_code == 200:
                data = r.json()
                items = data.get("items") or data.get("brand_templates") or []
                normalized = [{
                    "id": t.get("id"),
                    "title": t.get("title") or t.get("name") or "Untitled",
                    "thumbnail_url": (t.get("thumbnail") or {}).get("url"),
                    "view_url": t.get("view_url") or t.get("url"),
                } for t in items if t.get("id")]
                return {"items": normalized, "count": len(normalized)}
            return {"items": [], "error": f"{r.status_code}: {r.text[:200]}"}
        except Exception as e:
            logger.exception("Canva list templates failed: %s", e)
            raise HTTPException(502, f"Canva error: {e}")

    @router.get("/templates/{template_id}/dataset")
    async def template_dataset(template_id: str, email: str = Depends(require_admin)):
        token = await _get_valid_token(db)
        if not token:
            raise HTTPException(401, "Canva not connected")
        async with httpx.AsyncClient(timeout=20) as cli:
            r = await cli.get(
                f"{CANVA_API}/brand-templates/{template_id}/dataset",
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.text[:300])
        return r.json()

    @router.post("/autofill")
    async def autofill(body: AutofillReq, email: str = Depends(require_admin)):
        token = await _get_valid_token(db)
        if not token:
            raise HTTPException(401, "Canva not connected")
        payload = {"brand_template_id": body.template_id, "data": body.data}
        if body.title:
            payload["title"] = body.title
        async with httpx.AsyncClient(timeout=30) as cli:
            r = await cli.post(
                f"{CANVA_API}/autofills",
                json=payload,
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
            )
        if r.status_code not in (200, 201, 202):
            raise HTTPException(r.status_code, r.text[:500])
        job = r.json().get("job") or r.json()
        job_id = job.get("id")
        # Poll up to ~30s
        result = await _poll_autofill_job(db, job_id, token)
        return {"job_id": job_id, "result": result}

    @router.get("/autofill/{job_id}")
    async def autofill_status(job_id: str, email: str = Depends(require_admin)):
        token = await _get_valid_token(db)
        if not token:
            raise HTTPException(401, "Canva not connected")
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.get(
                f"{CANVA_API}/autofills/{job_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.text[:300])
        return r.json()

    @router.post("/create-post")
    async def create_post_from_template(
        body: CreatePostFromTemplateReq,
        email: str = Depends(require_admin),
    ):
        """Run Canva autofill + caption generation, then create a Post for the calendar slot.
        The Canva design's thumbnail URL is used as the post's image_url."""
        from models import Post, BrandProfile, CalendarSlot, to_mongo, from_mongo
        from agents import claude_text, guardrail_check

        slot_doc = from_mongo(await db.content_calendar.find_one({"id": body.slot_id}))
        if not slot_doc:
            raise HTTPException(404, "Calendar slot not found")
        slot = CalendarSlot(**slot_doc)
        brand_doc = from_mongo(await db.brand_profile.find_one())
        brand = BrandProfile(**brand_doc) if brand_doc else BrandProfile()

        token = await _get_valid_token(db)
        if not token:
            raise HTTPException(401, "Canva not connected")

        data = {k: {"type": "text", "text": str(v)} for k, v in body.fields.items() if v}
        if not data:
            data = {"title": {"type": "text", "text": slot.hook or slot.topic or "BagnShop"}}
        payload = {
            "brand_template_id": body.template_id,
            "data": data,
            "title": body.title or f"BagnShop AI — {slot.platform} {slot.date}",
        }
        async with httpx.AsyncClient(timeout=30) as cli:
            r = await cli.post(
                f"{CANVA_API}/autofills", json=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
        if r.status_code not in (200, 201, 202):
            raise HTTPException(r.status_code, f"Canva autofill failed: {r.text[:300]}")
        job = (r.json().get("job") or r.json())
        job_id = job.get("id")
        final = await _poll_autofill_job(db, job_id, token, attempts=15)
        design = (final.get("result") or {}).get("design") or {}
        design_id = design.get("id")
        design_url = design.get("url")
        thumb_url = (design.get("thumbnail") or {}).get("url") or design_url
        if not design_id and not thumb_url:
            raise HTTPException(504, f"Canva autofill did not complete in time. Job: {job_id}")

        # Try to export as high-res PNG → falls back to thumbnail URL if export fails
        png_local_url = await export_design_png(design_id, token) if design_id else None
        image_url = png_local_url or thumb_url
        if not image_url:
            raise HTTPException(504, f"Canva autofill did not produce an image. Job: {job_id}")

        system = (
            f"You write social captions for BagnShop. Voice: {', '.join(brand.voice_rules)}. "
            f"Banned words: {', '.join(brand.banned_claims)}. Never use them. "
            "Open with the assigned hook. Match platform length norms. End with CTA. "
            "Append the hashtags as a single line at the very end."
        )
        user_prompt = (
            f"Write a {slot.platform} caption for BagnShop.\n\n"
            f"Pillar: {slot.pillar}\nFormat: {slot.format}\n"
            f"Hook: {slot.hook}\nAngle: {slot.caption_angle}\n"
            f"CTA: {slot.cta}\nTopic: {slot.topic}\n"
            f"Hashtags to append: {' '.join(slot.hashtags)}\n\n"
            "Return the caption only — no JSON, no markdown."
        )
        try:
            caption = await claude_text(system, user_prompt)
        except Exception as e:
            logger.warning("Caption gen failed: %s", e)
            caption = f"{slot.hook}\n\n{slot.caption_angle}\n\n{slot.cta}\n\n{' '.join(slot.hashtags)}"

        post = Post(
            calendar_slot_id=slot.id,
            platform=slot.platform,
            format=slot.format,
            caption=caption,
            image_urls=[image_url],
            hook=slot.hook,
            pillar=slot.pillar,
            cta=slot.cta,
            hashtags=slot.hashtags,
            scheduled_datetime=slot.scheduled_datetime,
            status="pending_approval",
            is_product_post=False,
        )
        issues = await guardrail_check(db, post, brand)
        if issues:
            post.status = "needs_edit"
            post.guardrail_issues = issues

        post_doc = to_mongo(post)
        post_doc["source"] = "canva"
        post_doc["canva"] = {
            "template_id": body.template_id,
            "job_id": job_id,
            "design_id": design_id,
            "design_url": design_url,
            "thumbnail_url": thumb_url,
            "exported_png": png_local_url,
        }
        await db.posts.insert_one(post_doc)
        await db.content_calendar.update_one(
            {"id": slot.id}, {"$set": {"status": "creative_generated"}}
        )
        return {
            "post_id": post.id,
            "status": post.status,
            "issues": post.guardrail_issues,
            "image_url": image_url,
            "exported_png": png_local_url,
            "design_url": design_url,
        }

    return router


async def _poll_autofill_job(db, job_id: str, token: str, attempts: int = 10) -> dict:
    if not job_id:
        return {"status": "unknown"}
    for i in range(attempts):
        await asyncio.sleep(2 + i * 0.5)  # backoff: 2,2.5,3,3.5...
        try:
            async with httpx.AsyncClient(timeout=15) as cli:
                r = await cli.get(
                    f"{CANVA_API}/autofills/{job_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if r.status_code != 200:
                continue
            data = r.json()
            job = data.get("job", data)
            status = job.get("status")
            if status in ("success", "failed", "completed"):
                return job
        except Exception as e:
            logger.warning("Canva poll exception: %s", e)
    return {"status": "in_progress", "job_id": job_id}


async def export_design_png(design_id: str, token: str, attempts: int = 15) -> Optional[str]:
    """Export a Canva design as PNG, download it, save to /uploads, return relative URL.
    Returns None on failure — caller should fall back to thumbnail URL."""
    if not design_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as cli:
            r = await cli.post(
                f"{CANVA_API}/exports",
                json={"design_id": design_id, "format": {"type": "png"}},
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
            )
        if r.status_code not in (200, 201, 202):
            logger.warning("Canva export start %s: %s", r.status_code, r.text[:200])
            return None
        job = (r.json().get("job") or r.json())
        job_id = job.get("id")
        if not job_id:
            return None
        # poll
        download_urls: list[str] = []
        for i in range(attempts):
            await asyncio.sleep(2 + i * 0.3)
            try:
                async with httpx.AsyncClient(timeout=15) as cli:
                    pr = await cli.get(
                        f"{CANVA_API}/exports/{job_id}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                if pr.status_code != 200:
                    continue
                data = pr.json()
                jj = data.get("job", data)
                if jj.get("status") in ("failed", "error"):
                    logger.warning("Canva export job failed: %s", jj)
                    return None
                if jj.get("status") in ("success", "completed"):
                    download_urls = jj.get("urls") or []
                    break
            except Exception as e:
                logger.warning("Canva export poll exception: %s", e)
        if not download_urls:
            return None
        # download first PNG and persist
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as cli:
            dr = await cli.get(download_urls[0])
        if dr.status_code != 200 or not dr.content:
            return None
        fname = f"canva_{design_id[:10]}_{new_id()[:6]}.png"
        path = UPLOADS_DIR / fname
        path.write_bytes(dr.content)
        return f"/uploads/{fname}"
    except Exception as e:
        logger.exception("Canva export_design_png exception: %s", e)
        return None

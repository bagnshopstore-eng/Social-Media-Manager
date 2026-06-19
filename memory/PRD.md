# BagnShop Social Manager — PRD

## Problem Statement
Approval-gated autonomous social media manager for D2C brand BagnShop (Smart Utility Lifestyle Brand selling home gadgets, kitchen tools, wellness devices, lifestyle/gifting). Six AI agents (Audit, Strategist, Creative, Publisher, Optimizer, Guardrail) research, plan, write, design and queue content across Instagram, Facebook, LinkedIn. Single admin reviews on phone in ~2 min/day; NOTHING publishes without per-post approval.

## User Persona
Single brand owner (Mehul) — admin login, mobile-first approval UX.

## Stack
FastAPI · React · MongoDB · APScheduler · Emergent LLM key (Claude Sonnet 4.6 + Gemini Nano Banana) · Shopify Admin · Postproxy (publish + analytics) · Apify (Instagram scraper) · MailerSend (email) · Canva Connect (M6) · Slack webhook alerts.

## Architecture
- **Backend** `/app/backend/`: `server.py` (routes), `agents.py` (6 agents), `models.py`, `seeds.py`, `scheduler.py` (cron + email + Slack alerts), `canva.py` (OAuth + templates + autofill). JWT single-admin auth. `/uploads` static mount. Mongo collections: `admins`, `brand_profile`, `competitors`, `competitor_content`, `my_analytics`, `content_calendar`, `posts`, `strategist_reports`, `learnings`, `audit_log`, `canva_tokens`, `canva_oauth_states`, `health_state`.
- **Frontend** `/app/frontend/src/`: 5 pages (Dashboard/Approvals, Calendar, Insights, Competitor Intel, Settings) + Login + Canva picker dialog.

## Implemented
### M1–M5 (2026-02)
- ✅ JWT admin login (seeded from .env)
- ✅ Brand profile + Settings UI
- ✅ 10 seeded competitors
- ✅ Audit Agent (own analytics + Apify competitor scraping w/ seed fallback)
- ✅ Strategist Agent (Claude Sonnet 4.6 — 10 hooks, 5 gaps, 5-6 pillars, peak-hour calendar, LinkedIn B2B/founder)
- ✅ Creative Agent (Claude caption + Gemini Nano Banana images + Shopify product fetch + guardrails)
- ✅ Guardrail Layer (banned-claims, live price match, OOS, duplicate)
- ✅ Publisher Agent (HARD assertion approved-only; expire pending past-time)
- ✅ Optimizer Agent (engagement enrich + weekly learning rollup)
- ✅ Approval Dashboard (group by date, filters, bulk approve, edit, regenerate)
- ✅ Calendar month grid · Insights · Competitor Intel · Audit log
- ✅ Editorial mobile-first UI

### M6 + Iteration 2 (2026-06-19)
- ✅ Postproxy publishing migrated to `https://api.postproxy.dev/api/posts` with `profiles=[POSTPROXY_PROFILE_GROUP_ID]` (60FLY0) in payload + X-API-Key auth (Bearer fallback)
- ✅ MailerSend replaces Resend (`scheduler.send_email` → POST `https://api.mailersend.com/v1/email` Bearer auth, FROM=hello@bagnshop.com); live test email sent OK (HTTP 202)
- ✅ Canva Connect M6: OAuth (PKCE s256), brand templates list, autofill w/ job polling, token refresh, disconnect — endpoints `/api/canva/{status,connect,callback,disconnect,templates,autofill}` + Connect button in Settings + Canva Template picker dialog in Dashboard
- ✅ Slack/Discord webhook alerts on `/api/integrations/health` green→red flips with 30-min per-service dedupe; auto-scheduled every 5 minutes
- ✅ /api/integrations/health swapped `resend` → `mailersend` + added `slack_alerts` tile + `_meta.alerts`
- ✅ Backend 100% test pass (26/26 pytest cases)

### Iteration 3 (2026-06-19, same day)
- ✅ New endpoint **POST `/api/canva/create-post`**: pick a brand template + a calendar slot → backend runs Canva autofill, polls the job, generates the caption via Claude, and creates a `Post` document tagged `source="canva"` with the Canva design's thumbnail URL as `image_urls[0]` and status `pending_approval`
- ✅ `CanvaTemplatePicker` dialog now accepts `slots` prop and shows a slot-selector + "Create post for slot" CTA when a planned slot exists
- ✅ Dashboard loads `/api/calendar` (filtered to status=planned) and passes slots to the picker; on post creation it reloads posts and switches the filter to Pending
- ✅ Fixed Postproxy 400 "Missing profiles parameter" by sending `profiles: [60FLY0]` (array) instead of `profile_group_id`
- ✅ Updated MailerSend `.env`: `MAILERSEND_FROM_EMAIL=hello@bagnshop.com` — sending now works
- ✅ Updated Shopify URL to `https://ajy6hu-sh.myshopify.com` (token still pending a fresh `shpat_…` custom app token)
- ✅ Backend 100% test pass (33/33 pytest cases — 7 new tests this iteration)

### Iteration 4 (2026-06-19, same day) — P2 follow-ups
- ✅ **Canva `/v1/exports` integration** — new module-level helper `export_design_png(design_id, token)` POSTs to `/v1/exports`, polls, downloads the first signed URL with redirects, persists to `/app/backend/uploads/canva_<id>_<rand>.png` and returns the relative `/uploads/...` URL. `create_post_from_template` now prefers the exported PNG and falls back to the thumbnail URL on any failure (logged via `logger.info`). Post metadata stores all four: `design_id`, `design_url`, `thumbnail_url`, `exported_png`.
- ✅ **Per-slot "Generate with Canva"** — CalendarPage planned-slot pills are now clickable + show a hover Palette button (`data-testid="cal-slot-canva-<id>"`). Clicking opens `CanvaTemplatePicker` pre-selected to that slot (1-slot launches skip the slot dropdown). Only `status==='planned'` slots launch the flow; other statuses show a toast and no-op.
- ✅ Backend 100% test pass (45/45 pytest cases — 12 new tests this iteration)

## Test Credentials
See `/app/memory/test_credentials.md`. Admin: bagnshopstore@gmail.com / BagnShop@2026.

## Prioritized Backlog
- **P0** User to click **Connect Canva** in Settings — Canva credentials are configured + redirect URI is whitelisted, just needs the one-time OAuth click. After that, brand-templates + autofill + create-post + PNG export all light up end-to-end (live test pending).
- **P0** User to generate a fresh **Shopify Custom App Admin token** (`shpat_…`) — the two tokens supplied so far (atkn_, shpss_) are not Admin API tokens; both 401. Without this the product-aware creative agent falls back to non-product posts only.
- **P1** Optional: `SLACK_WEBHOOK_URL` — deferred by user
- **P2** Per-slot "Use Canva" override flag on each Calendar slot, so the **weekly autonomous cycle** (Sat 6 am IST) picks Canva instead of Gemini for branded slots automatically
- **P2** Telegram approval taps
- **P2** Per-platform image dimensions (1:1, 4:5, 9:16)
- **P3** Multi-brand, multi-admin

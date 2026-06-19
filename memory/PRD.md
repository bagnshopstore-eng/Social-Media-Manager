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
- ✅ Postproxy publishing migrated to `https://api.postproxy.dev/api/posts` + `POSTPROXY_PROFILE_GROUP_ID=60FLY0` in payload + X-API-Key auth (Bearer fallback)
- ✅ MailerSend replaces Resend (`scheduler.send_email` → POST `https://api.mailersend.com/v1/email` Bearer auth, graceful no-op when FROM_EMAIL empty)
- ✅ Canva Connect M6: OAuth (PKCE s256), brand templates list, autofill w/ job polling, token refresh, disconnect — endpoints `/api/canva/{status,connect,callback,disconnect,templates,autofill}` + Connect button in Settings + Canva Template picker dialog in Dashboard
- ✅ Slack/Discord webhook alerts on `/api/integrations/health` green→red flips with 30-min per-service dedupe; auto-scheduled every 5 minutes
- ✅ /api/integrations/health swapped `resend` → `mailersend` + added `slack_alerts` tile + `_meta.alerts`
- ✅ Backend 100% test pass (26/26 pytest cases)

## Test Credentials
See `/app/memory/test_credentials.md`. Admin: bagnshopstore@gmail.com / BagnShop@2026.

## Prioritized Backlog
- **P0** User to populate `MAILERSEND_FROM_EMAIL` (verified sender domain) + `SLACK_WEBHOOK_URL` in `.env` to activate email + Slack alerts
- **P0** User to whitelist `https://bagnshop-ai-build-1.preview.emergentagent.com/api/canva/callback` as Canva redirect URI in Canva Developer Portal, then click Connect Canva in Settings
- **P1** Wire Canva autofill outputs as image_urls into newly-created posts (currently picker returns design URL; full Creative-Agent integration where Canva-rendered design replaces Gemini image is the next step)
- **P1** Shopify health check is red — store URL format `https://admin.shopify.com/store/ajy6hu-sh` may need to be the `.myshopify.com` admin subdomain instead
- **P2** Approve via Telegram tap
- **P2** Per-platform image dimensions (1:1, 4:5, 9:16)
- **P3** Multi-brand, multi-admin

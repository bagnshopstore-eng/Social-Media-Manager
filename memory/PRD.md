# BagnShop Social Manager — PRD

## Problem Statement
Approval-gated autonomous social media manager for D2C brand BagnShop (Smart Utility Lifestyle Brand selling home gadgets, kitchen tools, wellness devices, lifestyle/gifting). Six AI agents (Audit, Strategist, Creative, Publisher, Optimizer, Guardrail) research, plan, write, design and queue content across Instagram, Facebook, LinkedIn. Single admin reviews on phone in ~2 min/day; NOTHING publishes without per-post approval.

## User Persona
Single brand owner (Mehul) — admin login, mobile-first approval UX.

## Stack
FastAPI · React · MongoDB · APScheduler-ready · Emergent LLM key (Claude Sonnet 4.6 + Gemini Nano Banana) · Shopify Admin · Ayrshare/Apify MOCKED in M1-M3.

## Architecture (built — M1+M2+M3)
- **Backend** `/app/backend/`: `server.py` (routes), `agents.py` (all 6 agents), `models.py`, `seeds.py`. JWT single-admin auth. `/uploads` static mount for generated images. Mongo collections: `admins`, `brand_profile`, `competitors`, `competitor_content`, `my_analytics`, `content_calendar`, `posts`, `strategist_reports`, `learnings`, `audit_log`.
- **Frontend** `/app/frontend/src/`: 5 pages (Dashboard/Approvals, Calendar, Insights, Competitor Intel, Settings) + Login. Modern editorial Linear/Notion aesthetic, Outfit+Manrope fonts, mobile-first.

## Implemented (2026-02)
- ✅ JWT admin login (seeded from .env)
- ✅ Brand profile + Settings UI (editable voice rules, banned claims, pillars, cadence)
- ✅ 10 seeded competitors with all 4 handle types
- ✅ Audit Agent: mock own analytics + heatmap + competitor scraping from realistic seed library
- ✅ Strategist Agent: Claude Sonnet 4.6 generates strict JSON (10 hook patterns + 5 content gaps + 5-6 pillars + N-day calendar with peak-hour scheduling and LinkedIn B2B/founder distinction)
- ✅ Creative Agent: Claude caption + Gemini Nano Banana image generation, real Shopify product fetch (with mock fallback), guardrail-checked
- ✅ Guardrail Layer: banned-claims, live price match, OOS check, duplicate detection
- ✅ Publisher Agent: HARD assertion `status=='approved'`, mock Ayrshare publish IDs, auto-expire pending past-time posts
- ✅ Optimizer Agent: enrich published with mocked engagement, weekly learning rollup (top hooks/formats/pillars)
- ✅ Approval Dashboard: cards grouped by date, status filters, bulk approve (all / per platform), edit dialog, regenerate
- ✅ Calendar month grid with status colors
- ✅ Insights: platform snapshot, heatmap, optimizer learnings, recent published
- ✅ Competitor Intel: tracked accounts + hook patterns + content gaps + top posts
- ✅ Audit log of every status change
- ✅ Editorial mobile-first UI with Outfit+Manrope fonts
- ✅ End-to-end tested (14/15 backend + frontend rendering)

## Prioritized Backlog
- **P0 (M4 — Publishing)** Real Ayrshare OAuth + publish call. Email/Telegram notifications. Background scheduler.
- **P1 (M5 — Learning loop)** Real Ayrshare analytics pull; richer learning weights fed back into Strategist prompt.
- **P1** Real Apify Instagram scraper actor for competitor content.
- **P2 (M6)** Reels/video script generation; Sora 2 video gen integration.
- **P2** Per-platform image dimensions (1:1, 4:5, 9:16).
- **P2** Approve via Telegram tap.
- **P3** Multi-brand, multi-admin support.

## Test Credentials
See `/app/memory/test_credentials.md`. Admin: bagnshopstore@gmail.com / BagnShop@2026.

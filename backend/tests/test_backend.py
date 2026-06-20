"""BagnShop AI — backend regression tests (iteration 2).

Covers: auth, integrations/health (with postproxy/mailersend/canva/slack_alerts keys + _meta.alerts),
canva router (status/connect/templates/disconnect), postproxy diagnose, MailerSend wiring (no crash
when FROM email empty), scheduler health flip detection wiring, and regression sanity on existing
endpoints.
"""
from __future__ import annotations
import os
import re
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://bagnshop-ai-build-1.preview.emergentagent.com",
).rstrip("/")

ADMIN_EMAIL = "bagnshopstore@gmail.com"
ADMIN_PASSWORD = "BagnShop@2026"


# ----------------------------- fixtures -----------------------------
@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def token(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 20
    assert data["email"] == ADMIN_EMAIL
    return data["token"]


@pytest.fixture(scope="session")
def auth(api, token):
    api.headers.update({"Authorization": f"Bearer {token}"})
    return api


# --------------------------- auth tests -----------------------------
class TestAuth:
    def test_login_invalid_password(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login",
                     json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_auth_me(self, auth):
        r = auth.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_auth_me_no_token(self, api):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code in (401, 403)


# ----------------------- integrations/health ------------------------
class TestIntegrationsHealth:
    def test_health_keys_present(self, auth):
        r = auth.get(f"{BASE_URL}/api/integrations/health")
        assert r.status_code == 200
        data = r.json()
        expected = {"postproxy", "mailersend", "apify", "shopify",
                    "emergent_llm", "canva", "slack_alerts"}
        missing = expected - set(data.keys())
        assert not missing, f"missing keys: {missing}"
        assert "resend" not in data, "resend key should have been removed"

    def test_health_meta_alerts_present(self, auth):
        r = auth.get(f"{BASE_URL}/api/integrations/health")
        data = r.json()
        assert "_meta" in data, "_meta field missing"
        meta = data["_meta"]
        assert "alerts" in meta
        alerts = meta["alerts"]
        for k in ("flips", "alerted", "deduped"):
            assert k in alerts and isinstance(alerts[k], list), f"{k} missing/not list"

    def test_health_slack_alerts_off_by_default(self, auth):
        r = auth.get(f"{BASE_URL}/api/integrations/health")
        data = r.json()
        assert data["slack_alerts"]["ok"] is False
        assert "missing" in data["slack_alerts"]["detail"].lower()


# --------------------------- Canva router ---------------------------
class TestCanva:
    def test_canva_status_initial(self, auth):
        auth.post(f"{BASE_URL}/api/canva/disconnect")
        r = auth.get(f"{BASE_URL}/api/canva/status")
        assert r.status_code == 200
        data = r.json()
        assert data["connected"] is False
        assert data["configured"] is True

    def test_canva_connect_authorize_url(self, auth):
        r = auth.get(f"{BASE_URL}/api/canva/connect")
        assert r.status_code == 200
        data = r.json()
        url = data.get("authorize_url", "")
        assert "canva.com/api/oauth/authorize" in url
        assert "client_id=OC-AZ7fmu8hwU0b" in url
        assert "code_challenge_method=s256" in url
        assert "redirect_uri=" in url
        assert "bagnshop-ai-build-1.preview.emergentagent.com" in url
        assert "code_challenge=" in url
        assert "state=" in url
        assert "brandtemplate" in url
        assert isinstance(data.get("state"), str) and len(data["state"]) > 10

    def test_canva_templates_unauth_returns_401(self, auth):
        auth.post(f"{BASE_URL}/api/canva/disconnect")
        r = auth.get(f"{BASE_URL}/api/canva/templates")
        assert r.status_code == 401
        body = r.json()
        detail = body.get("detail") or body.get("message") or ""
        assert "canva not connected" in str(detail).lower()

    def test_canva_disconnect_clears_status(self, auth):
        r = auth.post(f"{BASE_URL}/api/canva/disconnect")
        assert r.status_code == 200
        assert r.json().get("disconnected") is True
        s = auth.get(f"{BASE_URL}/api/canva/status")
        assert s.json()["connected"] is False


# ------------------------- Postproxy diagnose -----------------------
class TestPostproxy:
    def test_postproxy_diagnose(self, auth):
        r = auth.get(f"{BASE_URL}/api/integrations/postproxy/diagnose")
        assert r.status_code == 200
        data = r.json()
        assert data["url"] == "https://api.postproxy.dev/api/posts"
        assert data["key_length"] > 10
        # Per request statement: should be 200 and success=true
        assert data.get("status_code") in (200, 201), \
            f"expected 200/201, got {data.get('status_code')} body={data.get('body')}"
        assert data["success"] is True

    def test_agents_postproxy_publish_signature(self):
        src = open("/app/backend/agents.py").read()
        assert "POSTPROXY_BASE" in src
        assert re.search(r"url\s*=\s*f['\"]\{POSTPROXY_BASE\}/posts['\"]", src), \
            "postproxy_publish URL must be {POSTPROXY_BASE}/posts"
        # Iteration 3 fix: payload key is 'profiles' (array), env var name still POSTPROXY_PROFILE_GROUP_ID
        assert "POSTPROXY_PROFILE_GROUP_ID" in src
        assert '"profiles"' in src or "'profiles'" in src
        # X-API-Key tried before Bearer (header_variants order)
        idx_xkey = src.find("X-API-Key")
        idx_bearer = src.find("Authorization\": f\"Bearer")
        assert 0 <= idx_xkey < idx_bearer, "X-API-Key should appear before Bearer"


# ------------------------- MailerSend wiring ------------------------
class TestMailerSend:
    def test_notifications_test_no_crash(self, auth):
        r = auth.post(f"{BASE_URL}/api/notifications/test")
        assert r.status_code == 200
        data = r.json()
        # Either sent=True (FROM email configured) or sent=False (gracefully no-op). No crash either way.
        assert "sent" in data and isinstance(data["sent"], bool)
        assert "to" in data

    def test_scheduler_uses_mailersend(self):
        src = open("/app/backend/scheduler.py").read()
        assert "api.mailersend.com/v1/email" in src
        assert "Bearer" in src
        assert "MAILERSEND_FROM_EMAIL" in src
        # Resend must be gone from scheduler
        # (allow 'resend' inside python keyword like 'resend' substring rare check)
        assert "api.resend.com" not in src
        assert "RESEND_API_KEY" not in src


# -------------------- Slack alert flip detection --------------------
class TestSlackAlerts:
    def test_scheduler_dedupe_and_health_fn_wired(self):
        src = open("/app/backend/scheduler.py").read()
        assert "ALERT_DEDUPE_MINUTES" in src
        assert "check_health_and_alert" in src
        assert "health_fn" in src
        assert '"*/5"' in src or "'*/5'" in src

    def test_server_passes_health_fn_to_scheduler(self):
        src = open("/app/backend/server.py").read()
        assert "_collect_integrations_health" in src
        assert "health_fn=_collect_integrations_health" in src

    def test_health_flip_detection_logic(self, auth):
        r1 = auth.get(f"{BASE_URL}/api/integrations/health")
        assert r1.status_code == 200
        r2 = auth.get(f"{BASE_URL}/api/integrations/health")
        flips = r2.json()["_meta"]["alerts"]["flips"]
        assert isinstance(flips, list)
        alerted = r2.json()["_meta"]["alerts"]["alerted"]
        # Slack webhook empty -> alerted list must be empty even on flips
        assert alerted == []


# ------------------ Iteration 3: Canva create-post -----------------
class TestCanvaCreatePost:
    """POST /api/canva/create-post — slot validation, body validation, OAuth gate."""

    def test_create_post_missing_body_returns_422(self, auth):
        # No JSON body -> FastAPI/Pydantic should reject with 422
        r = auth.post(f"{BASE_URL}/api/canva/create-post")
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text[:200]}"

    def test_create_post_missing_required_fields_returns_422(self, auth):
        # Missing slot_id/template_id/fields
        r = auth.post(f"{BASE_URL}/api/canva/create-post", json={"title": "x"})
        assert r.status_code == 422

    def test_create_post_slot_not_found_returns_404(self, auth):
        # Ensure canva disconnected so we don't accidentally hit live API
        auth.post(f"{BASE_URL}/api/canva/disconnect")
        r = auth.post(f"{BASE_URL}/api/canva/create-post", json={
            "slot_id": "does-not-exist-xyz-TEST",
            "template_id": "tpl_dummy",
            "fields": {"title": "Hello"},
        })
        assert r.status_code == 404
        body = r.json()
        detail = (body.get("detail") or body.get("message") or "").lower()
        assert "calendar slot not found" in detail, f"detail={detail}"

    def test_create_post_valid_slot_no_canva_returns_401(self, auth):
        # Slot exists, but canva not connected -> 401 'Canva not connected'
        auth.post(f"{BASE_URL}/api/canva/disconnect")
        cal = auth.get(f"{BASE_URL}/api/calendar")
        assert cal.status_code == 200
        slots = cal.json()
        assert isinstance(slots, list) and len(slots) > 0, "need at least 1 calendar slot seeded"
        slot_id = slots[0]["id"]

        r = auth.post(f"{BASE_URL}/api/canva/create-post", json={
            "slot_id": slot_id,
            "template_id": "tpl_dummy_TEST",
            "fields": {"title": "Hello"},
        })
        assert r.status_code == 401, f"expected 401 after slot validation, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        detail = (body.get("detail") or body.get("message") or "").lower()
        assert "canva not connected" in detail, f"detail={detail}"


# ------ Iteration 3: static code checks (profiles + module-level model) ------
class TestIteration3StaticChecks:
    def test_postproxy_publish_uses_profiles_array(self):
        src = open("/app/backend/agents.py").read()
        # The fix: 'profiles': [POSTPROXY_PROFILE_GROUP_ID]
        assert re.search(
            r'["\']profiles["\']\s*:\s*\[\s*POSTPROXY_PROFILE_GROUP_ID',
            src,
        ), "postproxy payload must send 'profiles': [POSTPROXY_PROFILE_GROUP_ID]"
        # Must NOT use profile_group_id as a payload key any more
        assert not re.search(
            r'payload\s*\[\s*["\']profile_group_id["\']\s*\]', src
        ), "payload['profile_group_id'] must not be used"
        # Body must not assign profile_group_id directly as a key in payload dict literal
        assert not re.search(
            r'["\']profile_group_id["\']\s*:\s*POSTPROXY_PROFILE_GROUP_ID', src
        ), "'profile_group_id' must not be a JSON key in payload"

    def test_create_post_req_model_module_level(self):
        src = open("/app/backend/canva.py").read()
        # Find class definition position
        class_idx = src.find("class CreatePostFromTemplateReq")
        assert class_idx != -1, "CreatePostFromTemplateReq class missing"
        build_router_idx = src.find("def build_router(")
        assert build_router_idx != -1
        assert class_idx < build_router_idx, (
            "CreatePostFromTemplateReq must be defined at module level, "
            "BEFORE build_router(), so FastAPI body parsing works."
        )
        # Confirm it inherits from BaseModel
        snippet = src[class_idx:class_idx + 400]
        assert "BaseModel" in snippet
        assert "slot_id" in snippet
        assert "template_id" in snippet
        assert "fields" in snippet

    def test_create_post_route_registered(self):
        src = open("/app/backend/canva.py").read()
        assert '@router.post("/create-post")' in src
        # Slot lookup happens BEFORE token check
        handler_idx = src.find("async def create_post_from_template")
        assert handler_idx > 0
        slot_idx = src.find("Calendar slot not found", handler_idx)
        token_idx = src.find("Canva not connected", handler_idx)
        assert 0 < slot_idx < token_idx, (
            "Slot 404 must be raised BEFORE 401 token check (request statement)"
        )


# ----------------------- Regression sanity --------------------------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/brand",
        "/api/competitors",
        "/api/competitor-content",
        "/api/hook-patterns",
        "/api/calendar",
        "/api/posts",
        "/api/insights",
        "/api/audit-log",
    ])
    def test_get_endpoints_200(self, auth, path):
        r = auth.get(f"{BASE_URL}{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"

    def test_canva_router_mounted(self, auth):
        r = auth.get(f"{BASE_URL}/api/canva/status")
        assert r.status_code == 200
        r2 = auth.get(f"{BASE_URL}/api/canva/templates")
        assert r2.status_code in (401, 403, 502)
        r3 = auth.get(f"{BASE_URL}/api/canva/connect")
        assert r3.status_code == 200


# --- Iteration 4: export_design_png + clickable Calendar slot static checks ---
class TestIteration4ExportPng:
    """Static structural verification of the iteration-4 deliverables:
    - export_design_png() helper in canva.py
    - create_post_from_template uses it with fallback to thumbnail
    - CalendarPage clickable planned slots + picker integration
    - CanvaTemplatePicker 1-slot pre-selection
    """

    def test_export_design_png_helper_exists(self):
        src = open("/app/backend/canva.py").read()
        assert "async def export_design_png(" in src, (
            "module-level helper export_design_png must exist"
        )
        # Module-level (not nested inside build_router)
        helper_idx = src.find("async def export_design_png(")
        build_router_idx = src.find("def build_router(")
        # Helper must be defined OUTSIDE build_router (either before or after, at col 0)
        # Find indent of the helper line
        line_start = src.rfind("\n", 0, helper_idx) + 1
        helper_indent = helper_idx - line_start
        assert helper_indent == 0, (
            f"export_design_png must be at module level (indent 0), got {helper_indent}"
        )
        # Confirm signature with attempts default
        assert re.search(
            r"async def export_design_png\(\s*design_id[^)]*token[^)]*attempts[^)]*\)",
            src,
        ), "signature should be (design_id, token, attempts=...)"

    def test_export_design_png_posts_to_exports_endpoint(self):
        src = open("/app/backend/canva.py").read()
        # Isolate the helper body
        helper_idx = src.find("async def export_design_png(")
        helper_body = src[helper_idx:helper_idx + 3000]
        # Must POST to /exports with PNG format
        assert "/exports" in helper_body
        assert re.search(r"format.*png", helper_body, re.IGNORECASE), (
            "must specify format type png in export payload"
        )
        assert '"design_id"' in helper_body or "'design_id'" in helper_body

    def test_export_design_png_polls_and_downloads(self):
        src = open("/app/backend/canva.py").read()
        helper_idx = src.find("async def export_design_png(")
        helper_body = src[helper_idx:helper_idx + 3000]
        # Polls GET /exports/{job_id}
        assert re.search(r"/exports/.+job_id", helper_body) or re.search(
            r'/exports/\{job_id\}', helper_body
        ) or 'f"{CANVA_API}/exports/' in helper_body, (
            "must poll GET /exports/{job_id}"
        )
        # Downloads to /uploads/ with canva_ prefix
        assert "UPLOADS_DIR" in helper_body or "/uploads/" in helper_body
        assert 'canva_' in helper_body, "saved filename should use canva_ prefix"
        # Returns relative /uploads/... or /api/uploads/... URL string (iter5: ingress
        # only routes /api/*, so canva helper now returns /api/uploads/<fname>)
        assert re.search(r'return\s+f["\']/(api/)?uploads/', helper_body), (
            "must return relative /uploads/<fname> or /api/uploads/<fname> URL on success"
        )
        # Returns None on failure paths
        assert helper_body.count("return None") >= 2, (
            "should return None on multiple failure paths"
        )

    def test_create_post_uses_export_with_thumbnail_fallback(self):
        src = open("/app/backend/canva.py").read()
        handler_idx = src.find("async def create_post_from_template")
        assert handler_idx > 0
        handler_body = src[handler_idx:handler_idx + 6000]
        # Captures design_id from autofill result
        assert re.search(r"design_id\s*=\s*design\.get\(", handler_body), (
            "must capture design_id from final.result.design.id"
        )
        # Calls export_design_png and assigns to png_local_url
        assert re.search(
            r"png_local_url\s*=\s*await\s+export_design_png\(", handler_body
        ), "must call await export_design_png(...) -> png_local_url"
        # Falls back: image_url = png_local_url or thumb_url
        assert re.search(
            r"image_url\s*=\s*png_local_url\s+or\s+thumb_url", handler_body
        ), "image_url must fall back to thumb_url when png_local_url is None"
        # Canva metadata persisted with all four fields
        for key in ("design_id", "design_url", "thumbnail_url", "exported_png"):
            assert f'"{key}"' in handler_body, (
                f"post.canva metadata must include '{key}'"
            )

    def test_calendar_page_clickable_slots_and_picker(self):
        src = open("/app/frontend/src/pages/CalendarPage.jsx").read()
        # Imports CanvaTemplatePicker
        assert "import CanvaTemplatePicker" in src
        # Picker state
        assert "pickerSlots" in src and "setPickerSlots" in src
        assert "pickerOpen" in src and "setPickerOpen" in src
        # openCanvaForSlot only opens for planned status
        assert "openCanvaForSlot" in src
        assert re.search(
            r"openCanvaForSlot\s*=\s*\(slot\)\s*=>", src
        ), "openCanvaForSlot must be a function of slot"
        m = re.search(
            r"openCanvaForSlot\s*=\s*\(slot\)\s*=>\s*\{[^}]*?status\s*!==\s*[\"']planned[\"']",
            src, re.DOTALL,
        )
        assert m, "openCanvaForSlot must guard on status === 'planned' (early-return otherwise)"
        # Renders <CanvaTemplatePicker slots={pickerSlots} ... />
        # (arrow functions in JSX contain `>` so [^>] would break — use DOTALL .*?)
        assert re.search(
            r"<CanvaTemplatePicker\b.*?slots=\{pickerSlots\}", src, re.DOTALL
        ), "must render <CanvaTemplatePicker slots={pickerSlots} ... />"
        # data-testid pattern for slot pill and inner button
        assert "`cal-slot-${item.id}`" in src, (
            "each planned pill needs data-testid `cal-slot-${item.id}`"
        )
        assert "`cal-slot-canva-${item.id}`" in src, (
            "hover-button needs data-testid `cal-slot-canva-${item.id}`"
        )

    def test_canva_picker_preselects_single_slot(self):
        src = open("/app/frontend/src/components/CanvaTemplatePicker.jsx").read()
        # Must run a useEffect that depends on [open, slots]
        assert re.search(r"\[\s*open\s*,\s*slots\s*\]", src), (
            "useEffect must depend on [open, slots]"
        )
        # When slots.length === 1, setChosenSlot to that slot's id
        assert re.search(
            r"slots\.length\s*===\s*1[^}]*setChosenSlot\(\s*slots\[0\]\.id\s*\)",
            src, re.DOTALL,
        ), "must pre-select chosenSlot to slots[0].id when slots.length === 1"


# --- Iteration 4: regression -- /api/canva/create-post negative paths still OK ---
class TestIteration4CreatePostRegression:
    def test_create_post_invalid_slot_still_404(self, auth):
        auth.post(f"{BASE_URL}/api/canva/disconnect")
        r = auth.post(f"{BASE_URL}/api/canva/create-post", json={
            "slot_id": "iter4-bogus-slot-TEST",
            "template_id": "tpl_iter4_TEST",
            "fields": {"title": "iter4"},
        })
        assert r.status_code == 404
        detail = (r.json().get("detail") or "").lower()
        assert "calendar slot not found" in detail

    def test_create_post_valid_slot_no_canva_still_401(self, auth):
        auth.post(f"{BASE_URL}/api/canva/disconnect")
        cal = auth.get(f"{BASE_URL}/api/calendar")
        assert cal.status_code == 200
        slots = cal.json()
        assert len(slots) > 0
        r = auth.post(f"{BASE_URL}/api/canva/create-post", json={
            "slot_id": slots[0]["id"],
            "template_id": "tpl_iter4_TEST",
            "fields": {"title": "iter4"},
        })
        assert r.status_code == 401
        detail = (r.json().get("detail") or "").lower()
        assert "canva not connected" in detail

    def test_canva_status_shape(self, auth):
        r = auth.get(f"{BASE_URL}/api/canva/status")
        assert r.status_code == 200
        body = r.json()
        assert "connected" in body and "configured" in body
        assert isinstance(body["connected"], bool)
        assert isinstance(body["configured"], bool)

    def test_canva_connect_returns_authorize_url(self, auth):
        r = auth.get(f"{BASE_URL}/api/canva/connect")
        assert r.status_code == 200
        body = r.json()
        assert "authorize_url" in body and body["authorize_url"].startswith("https://")
        assert "state" in body and len(body["state"]) > 10

    def test_canva_templates_401_when_disconnected(self, auth):
        auth.post(f"{BASE_URL}/api/canva/disconnect")
        r = auth.get(f"{BASE_URL}/api/canva/templates")
        assert r.status_code == 401
        detail = (r.json().get("detail") or "").lower()
        assert "canva not connected" in detail

    def test_integrations_health_still_complete(self, auth):
        r = auth.get(f"{BASE_URL}/api/integrations/health")
        assert r.status_code == 200
        body = r.json()
        for key in ("postproxy", "mailersend", "canva", "slack_alerts"):
            assert key in body, f"missing integrations.health key: {key}"
        assert "_meta" in body and "alerts" in body["_meta"]

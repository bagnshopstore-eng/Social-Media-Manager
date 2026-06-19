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
        assert "profile_group_id" in src
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
        # FROM email is intentionally empty -> sent should be False, no crash
        assert data.get("sent") is False
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

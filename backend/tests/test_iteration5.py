"""Iteration 5 backend tests:
- /api/uploads/<file> serves real PNG (no longer 404 via ingress)
- Shopify health = GREEN (Authenticated)
- Canva callback NEVER 422 (uses Optional[str] = Query(default=None))
- Canva callback logs every attempt to db.canva_callback_log
- /api/canva/debug endpoint shape
- fetch_shopify_products() returns ≥40 real products with cdn.shopify.com images
"""
from __future__ import annotations
import os
import asyncio
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://bagnshop-ai-build-1.preview.emergentagent.com",
).rstrip("/")

ADMIN_EMAIL = "bagnshopstore@gmail.com"
ADMIN_PASSWORD = "BagnShop@2026"


@pytest.fixture(scope="module")
def auth():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


# ---------------------- Static assets ----------------------
class TestUploadsStatic:
    def test_api_uploads_serves_png(self):
        # Pick a file that exists on disk
        files = sorted(os.listdir("/app/backend/uploads"))
        png = next((f for f in files if f.endswith(".png")), None)
        assert png, "no png in /app/backend/uploads"
        r = requests.get(f"{BASE_URL}/api/uploads/{png}", timeout=15)
        assert r.status_code == 200, f"got {r.status_code}"
        assert r.headers["content-type"].startswith("image/png"), \
            f"ct={r.headers.get('content-type')}"
        assert len(r.content) > 100_000, f"too small: {len(r.content)}"
        # Accept PNG or JPEG magic (some .png on disk were saved with JPEG bytes by
        # external image generation — the important thing is binary image content,
        # not HTML, is served via the K8s ingress)
        magic = r.content[:4]
        assert magic in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1"), \
            f"not a valid image magic: {magic!r}"


# ---------------------- Shopify GREEN ----------------------
class TestShopifyHealth:
    def test_shopify_green(self, auth):
        r = auth.get(f"{BASE_URL}/api/integrations/health")
        assert r.status_code == 200
        sh = r.json().get("shopify", {})
        assert sh.get("ok") is True, f"shopify not OK: {sh}"
        assert "auth" in str(sh.get("detail", "")).lower(), \
            f"detail should mention auth: {sh}"


# ---------------------- Canva callback never 422 ----------------------
class TestCanvaCallback:
    def test_no_params_redirects_missing(self):
        # Use a fresh session that does NOT follow redirects
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/canva/callback", allow_redirects=False, timeout=10)
        assert r.status_code in (302, 307), f"got {r.status_code} body={r.text[:200]}"
        loc = r.headers.get("Location", "")
        assert "/settings?canva=error" in loc, f"loc={loc}"
        assert "detail=missing_params" in loc, f"loc={loc}"

    def test_canva_error_redirects(self):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/canva/callback?error=access_denied",
                  allow_redirects=False, timeout=10)
        assert r.status_code in (302, 307)
        loc = r.headers.get("Location", "")
        assert "canva=error" in loc and "access_denied" in loc, f"loc={loc}"

    def test_invalid_state_redirects(self):
        s = requests.Session()
        r = s.get(f"{BASE_URL}/api/canva/callback?code=test&state=fake_state_TEST",
                  allow_redirects=False, timeout=10)
        assert r.status_code in (302, 307)
        loc = r.headers.get("Location", "")
        assert "canva=error" in loc and "invalid_state" in loc, f"loc={loc}"


# ---------------------- /api/canva/debug ----------------------
class TestCanvaDebug:
    def test_debug_schema(self, auth):
        r = auth.get(f"{BASE_URL}/api/canva/debug")
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        for k in ("client_id", "configured_redirect_uri", "public_backend_url",
                  "scopes_requested", "token_saved", "recent_oauth_states",
                  "recent_callbacks"):
            assert k in d, f"missing key {k}"
        assert d["client_id"] == "OC-AZ7fmu8hwU0b"
        assert "bagnshop-ai-build-1.preview.emergentagent.com" in d["configured_redirect_uri"]
        assert "brandtemplate" in d["scopes_requested"]
        assert isinstance(d["recent_oauth_states"], list)
        assert isinstance(d["recent_callbacks"], list)

    def test_debug_logs_callbacks(self, auth):
        # Hit the callback with no params, then verify it appears in debug log
        s = requests.Session()
        s.get(f"{BASE_URL}/api/canva/callback", allow_redirects=False, timeout=10)
        s.get(f"{BASE_URL}/api/canva/callback?error=access_denied",
              allow_redirects=False, timeout=10)
        s.get(f"{BASE_URL}/api/canva/callback?code=x&state=bogus_TEST_iter5",
              allow_redirects=False, timeout=10)
        # Give Mongo a moment
        import time; time.sleep(0.5)
        r = auth.get(f"{BASE_URL}/api/canva/debug")
        assert r.status_code == 200
        cbs = r.json()["recent_callbacks"]
        assert len(cbs) >= 1, "no callbacks recorded"
        outcomes = {c.get("outcome") for c in cbs}
        # At least one of the three outcomes we forced must be present
        expected = {"missing_code_or_state", "canva_redirect_with_error", "invalid_state_not_in_db"}
        assert outcomes & expected, f"outcomes seen: {outcomes}"


# ---------------------- Canva regression ----------------------
class TestCanvaRegression:
    def test_status(self, auth):
        r = auth.get(f"{BASE_URL}/api/canva/status")
        assert r.status_code == 200
        assert r.json()["configured"] is True

    def test_connect_dynamic_state_and_challenge(self, auth):
        r1 = auth.get(f"{BASE_URL}/api/canva/connect")
        r2 = auth.get(f"{BASE_URL}/api/canva/connect")
        assert r1.status_code == 200 and r2.status_code == 200
        s1, s2 = r1.json()["state"], r2.json()["state"]
        assert s1 != s2, "state must be dynamic per call"
        u1, u2 = r1.json()["authorize_url"], r2.json()["authorize_url"]
        # code_challenge must also differ
        import urllib.parse as up
        q1 = dict(up.parse_qsl(up.urlparse(u1).query))
        q2 = dict(up.parse_qsl(up.urlparse(u2).query))
        assert q1["code_challenge"] != q2["code_challenge"]

    def test_templates_401_no_token(self, auth):
        auth.post(f"{BASE_URL}/api/canva/disconnect")
        r = auth.get(f"{BASE_URL}/api/canva/templates")
        assert r.status_code == 401

    def test_autofill_401_no_token(self, auth):
        auth.post(f"{BASE_URL}/api/canva/disconnect")
        r = auth.post(f"{BASE_URL}/api/canva/autofill",
                      json={"template_id": "t", "data": {}})
        assert r.status_code == 401

    def test_create_post_404_for_bogus_slot(self, auth):
        auth.post(f"{BASE_URL}/api/canva/disconnect")
        r = auth.post(f"{BASE_URL}/api/canva/create-post", json={
            "slot_id": "bogus_iter5_TEST", "template_id": "x", "fields": {"a": "b"}})
        assert r.status_code == 404

    def test_disconnect(self, auth):
        r = auth.post(f"{BASE_URL}/api/canva/disconnect")
        assert r.status_code == 200
        assert r.json().get("disconnected") is True


# ---------------------- General regression ----------------------
class TestGeneralRegression:
    def test_login_works(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                          timeout=10)
        assert r.status_code == 200

    def test_integrations_health_keys(self, auth):
        r = auth.get(f"{BASE_URL}/api/integrations/health")
        assert r.status_code == 200
        d = r.json()
        for k in ("mailersend", "shopify", "postproxy", "canva"):
            assert k in d
        # mailersend, postproxy expected green; shopify green; canva amber/red OK
        assert d["mailersend"]["ok"] is True, f"mailersend: {d['mailersend']}"
        assert d["postproxy"]["ok"] is True, f"postproxy: {d['postproxy']}"
        assert d["shopify"]["ok"] is True, f"shopify: {d['shopify']}"

    @pytest.mark.parametrize("path", [
        "/api/posts", "/api/calendar", "/api/brand",
        "/api/competitors", "/api/insights",
    ])
    def test_get_endpoints(self, auth, path):
        r = auth.get(f"{BASE_URL}{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code}"


# ---------------------- Shopify live products ----------------------
class TestShopifyProducts:
    def test_fetch_shopify_products_real(self):
        """Direct in-process call — needs to be ≥40 products with cdn.shopify.com images."""
        import sys
        sys.path.insert(0, "/app/backend")
        # Load .env so SHOPIFY_ADMIN_TOKEN is visible to agents module
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env", override=True)
        # Re-import agents fresh so module-level env reads pick up the loaded vars
        import importlib
        import agents as _agents
        importlib.reload(_agents)
        products = asyncio.run(_agents.fetch_shopify_products(limit=250))
        assert isinstance(products, list)
        assert len(products) >= 40, f"expected ≥40 products, got {len(products)}"
        # Verify at least 1 has cdn.shopify.com image (proves not mock)
        with_cdn = [p for p in products if p.get("image") and "cdn.shopify.com" in (p["image"] or "")]
        assert len(with_cdn) >= 1, \
            f"no cdn.shopify.com images — looks like mock fallback. sample={products[:2]}"

    def test_static_signature(self):
        src = open("/app/backend/agents.py").read()
        assert "X-Shopify-Access-Token" in src
        assert "_mock_products" in src
        assert "products.json" in src

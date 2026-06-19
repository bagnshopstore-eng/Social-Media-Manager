"""BagnShop backend integration tests - uses localhost to avoid CF 100s gateway timeout."""
import os, time, requests, pytest

BASE = "http://localhost:8001"
EMAIL = "bagnshopstore@gmail.com"
PASSWORD = "BagnShop@2026"

@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["token"]

@pytest.fixture(scope="session")
def H(token):
    return {"Authorization": f"Bearer {token}"}

def test_login_bad():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": "wrong"}, timeout=10)
    assert r.status_code == 401

def test_me(H):
    r = requests.get(f"{BASE}/api/auth/me", headers=H, timeout=10)
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL

def test_brand(H):
    r = requests.get(f"{BASE}/api/brand", headers=H, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["brand_name"] == "BagnShop"
    assert "linkedin_angle" in d

def test_competitors(H):
    r = requests.get(f"{BASE}/api/competitors", headers=H, timeout=10)
    assert r.status_code == 200
    docs = r.json()
    names = {d["name"] for d in docs}
    expected = {"IGP", "FNP", "Giftana", "OffiStore", "Across Corporate",
                "Saffron India", "Pinnacle Gifting", "Consortium Gifts",
                "Giftcart", "PrintStop"}
    assert expected.issubset(names), f"missing: {expected - names}"
    assert len(docs) >= 10

def test_audit(H):
    r = requests.post(f"{BASE}/api/agents/audit/run", headers=H, timeout=60)
    assert r.status_code == 200, r.text

def test_strategist_days2(H):
    r = requests.post(f"{BASE}/api/agents/strategist/run?days=2", headers=H, timeout=240)
    assert r.status_code == 200, r.text[:500]

def test_calendar_and_linkedin_b2b(H):
    r = requests.get(f"{BASE}/api/calendar", headers=H, timeout=15)
    assert r.status_code == 200
    slots = r.json()
    assert len(slots) > 0, "no calendar slots"
    for s in slots:
        for k in ("platform", "pillar", "hook", "scheduled_datetime"):
            assert k in s, f"missing {k}"
    li = [s for s in slots if s["platform"] == "linkedin"]
    assert len(li) > 0, "no linkedin slots"
    # b2b/founder check - look for keywords across hook+caption_angle+pillar
    b2b_kw = ["b2b", "corporate", "founder", "gifting", "building", "brand", "team", "leader", "business", "lessons", "story"]
    matched = 0
    for s in li:
        blob = (s.get("hook","") + " " + s.get("caption_angle","") + " " + s.get("pillar","") + " " + s.get("topic","")).lower()
        if any(k in blob for k in b2b_kw):
            matched += 1
    assert matched >= max(1, len(li)//2), f"LinkedIn slots not B2B/founder-led: {matched}/{len(li)}"

def test_creative_run(H):
    r = requests.post(f"{BASE}/api/agents/creative/run", headers=H, json={"limit": 1}, timeout=240)
    assert r.status_code == 200, r.text[:500]
    d = r.json()
    assert d.get("generated", 0) >= 1, d

def test_posts_pending(H):
    r = requests.get(f"{BASE}/api/posts", headers=H, timeout=15)
    assert r.status_code == 200
    posts = r.json()
    assert len(posts) >= 1
    pending = [p for p in posts if p["status"] == "pending_approval"]
    assert len(pending) >= 1, "no pending_approval posts"
    p = pending[0]
    assert p.get("caption"), "caption missing"
    # image_urls present
    assert isinstance(p.get("image_urls"), list)

def test_approve_and_publisher_only_publishes_approved(H):
    posts = requests.get(f"{BASE}/api/posts", headers=H, timeout=15).json()
    pending = [p for p in posts if p["status"] == "pending_approval"]
    assert len(pending) >= 1
    # Approve ONE, leave others pending
    approve_id = pending[0]["id"]
    pending_id = pending[1]["id"] if len(pending) > 1 else None

    r = requests.post(f"{BASE}/api/posts/{approve_id}/status",
                      headers=H, json={"status": "approved"}, timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    # If we have another pending, explicitly keep it pending_approval (it already is)
    # Run publisher
    r = requests.post(f"{BASE}/api/agents/publisher/run", headers=H, timeout=60)
    assert r.status_code == 200, r.text

    # Verify approved post is now published
    p = requests.get(f"{BASE}/api/posts/{approve_id}", headers=H, timeout=10).json()
    # Only published if scheduled_datetime <= now; check status either published or still approved
    if p["status"] == "published":
        assert p.get("published_id", "").startswith("mock_"), f"published_id not mock_: {p.get('published_id')}"
    else:
        # acceptable if scheduled in future - still approved
        assert p["status"] == "approved", f"unexpected status {p['status']}"

    # CRITICAL: pending post must NOT be published
    if pending_id:
        p2 = requests.get(f"{BASE}/api/posts/{pending_id}", headers=H, timeout=10).json()
        assert p2["status"] != "published", "Publisher published a non-approved post!"
        assert not p2.get("published_id"), f"Non-approved post got published_id: {p2.get('published_id')}"

def test_bulk_approve(H):
    r = requests.post(f"{BASE}/api/posts/bulk-approve", headers=H, json={}, timeout=15)
    assert r.status_code == 200
    assert "approved_count" in r.json()

def test_insights(H):
    r = requests.get(f"{BASE}/api/insights", headers=H, timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ("analytics", "learning", "recent_published"):
        assert k in d

def test_hook_patterns(H):
    r = requests.get(f"{BASE}/api/hook-patterns", headers=H, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "hook_patterns" in d and "content_gaps" in d

def test_shopify(H):
    r = requests.get(f"{BASE}/api/shopify/products", headers=H, timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_audit_log(H):
    r = requests.get(f"{BASE}/api/audit-log", headers=H, timeout=15)
    assert r.status_code == 200
    logs = r.json()
    # there was at least one approve action
    assert any("status_change" in (l.get("action") or "") for l in logs), "no status_change in audit log"

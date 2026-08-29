import os, sys, json, time, requests, pytest
from dotenv import load_dotenv
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

BASE_URL = (os.environ.get("BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_EMAIL = os.environ.get("FORGE_SUPER_ADMIN_EMAIL", "nicolas.ms13@gmail.com")
SUPER_PASS = os.environ.get("FORGE_SUPER_ADMIN_PASSWORD", "forge-admin-2026")
TEST_ATHLETE_EMAIL = "joao.silva@example.com"
TEST_ATHLETE_PASS = "joaopass123"

def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ===================== AUTH & INVITE =====================

def test_auth_login_super_admin():
    r = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    assert r.status_code == 200, f"login failed: {r.text}"
    data = r.json()
    assert data["token"]
    assert data["user"]["role"] == "SUPER_ADMIN"
    assert data["user"]["email"].lower() == SUPER_EMAIL.lower()


def test_auth_login_athlete():
    r = requests.post(f"{API}/auth/login", json={"email": TEST_ATHLETE_EMAIL, "password": TEST_ATHLETE_PASS})
    assert r.status_code == 200, f"athlete login failed: {r.text}"
    data = r.json()
    assert data["token"]
    assert data["user"]["role"] == "ATHLETE"


def test_auth_me_super_admin():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    r = requests.get(f"{API}/auth/me", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "SUPER_ADMIN"


def test_auth_me_athlete():
    login = requests.post(f"{API}/auth/login", json={"email": TEST_ATHLETE_EMAIL, "password": TEST_ATHLETE_PASS})
    token = login.json()["token"]
    r = requests.get(f"{API}/auth/me", headers=auth_header(token))
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "ATHLETE"


def test_auth_rejects_invalid_token():
    r = requests.get(f"{API}/auth/me", headers=auth_header("invalid.token.here"))
    assert r.status_code == 401


def test_auth_rejects_wrong_password():
    r = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": "wrongpassword"})
    assert r.status_code == 401


def test_auth_no_token():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code in (401, 403)


# ===================== SUPER_ADMIN INVITE FLOW =====================

def test_admin_create_and_accept_invite():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    admin_token = login.json()["token"]
    headers = auth_header(admin_token)

    # create athlete
    test_email = f"testinvite{int(time.time())}@example.com"
    # confirm_courtesy e courtesy_reason passaram a ser obrigatorios quando o convite
    # ganhou os dois modos: conceder acesso de graca exige dizer por que, e fica em
    # auditoria. Este teste cobre o modo cortesia, que e o comportamento anterior.
    create = requests.post(f"{API}/admin/athletes", json={
        "email": test_email, "name": "Test Invite User",
        "plan": "FORGE_ACCESS", "validity": "30", "admin_note": "core test",
        "access_mode": "courtesy", "confirm_courtesy": True,
        "courtesy_reason": "conta de teste automatizado"
    }, headers=headers)
    assert create.status_code == 200, f"create failed: {create.text}"
    invite_url = create.json()["invite_url"]
    invite_token = invite_url.split("/")[-1]

    # lookup invite
    lookup = requests.get(f"{API}/auth/invite/{invite_token}")
    assert lookup.status_code == 200
    assert lookup.json()["email"] == test_email

    # accept invite
    accept = requests.post(f"{API}/auth/accept-invite", json={
        "token": invite_token, "password": "testpass1234", "name": "Test Athlete"
    })
    assert accept.status_code == 200, f"accept failed: {accept.text}"
    ath_data = accept.json()
    assert ath_data["token"]
    assert ath_data["user"]["status"] == "ACTIVE"

    # verify login works
    login2 = requests.post(f"{API}/auth/login", json={"email": test_email, "password": "testpass1234"})
    assert login2.status_code == 200

    # verify cannot reuse invite
    reuse = requests.get(f"{API}/auth/invite/{invite_token}")
    assert reuse.status_code in (404, 410)  # token nulled after use


# ===================== SUSPENSION / REACTIVATION =====================

def test_admin_suspend_and_reactivate():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    admin_token = login.json()["token"]
    headers = auth_header(admin_token)

    # create then suspend
    test_email = f"testsusp{int(time.time())}@example.com"
    r = requests.post(f"{API}/admin/athletes", json={
        "email": test_email, "name": "Suspend Test", "plan": "FORGE_ACCESS", "validity": "30",
        "access_mode": "courtesy", "confirm_courtesy": True,
        "courtesy_reason": "conta de teste automatizado"
    }, headers=headers)
    assert r.status_code == 200, f"create failed: {r.text}"
    athlete_id = r.json()["athlete"]["id"]

    # get athlete list and find the user
    list_r = requests.get(f"{API}/admin/athletes", headers=headers)
    athletes = list_r.json()["athletes"]
    target = next(a for a in athletes if a["id"] == athlete_id)
    assert target["status"] == "PENDING"

    # suspend
    susp = requests.post(f"{API}/admin/athletes/{athlete_id}/suspend", headers=headers)
    assert susp.status_code == 200

    # verify suspended
    detail = requests.get(f"{API}/admin/athletes/{athlete_id}", headers=headers)
    assert detail.json()["athlete"]["status"] == "SUSPENDED"

    # reactivate
    react = requests.post(f"{API}/admin/athletes/{athlete_id}/reactivate", headers=headers)
    assert react.status_code == 200
    assert react.json()["status"] in ("ACTIVE", "PENDING")


# ===================== ATHLETE ISOLATION =====================

def test_athlete_cannot_access_admin():
    login = requests.post(f"{API}/auth/login", json={"email": TEST_ATHLETE_EMAIL, "password": TEST_ATHLETE_PASS})
    token = login.json()["token"]
    h = auth_header(token)
    r = requests.get(f"{API}/admin/athletes", headers=h)
    assert r.status_code == 403


def test_athlete_data_isolated_to_own_id():
    login = requests.post(f"{API}/auth/login", json={"email": TEST_ATHLETE_EMAIL, "password": TEST_ATHLETE_PASS})
    token = login.json()["token"]
    h = auth_header(token)
    # athlete bootstrap should return their own profile, not demo
    r = requests.get(f"{API}/bootstrap", headers=h)
    assert r.status_code == 200
    data = r.json()
    pid = data["profile"]["id"]
    # athlete cannot specify a different profile_id
    r2 = requests.get(f"{API}/bootstrap?profile_id=demo", headers=h)
    assert r2.status_code == 200
    assert r2.json()["profile"]["id"] == pid  # still returns own profile


def test_super_admin_can_view_any_profile():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)
    r = requests.get(f"{API}/bootstrap?profile_id=demo", headers=h)
    assert r.status_code == 200
    assert r.json()["profile"]["id"] == "demo"


# ===================== PROGRAM BUILDER CUSTOM PROGRAM =====================

def test_custom_program_full_flow():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    pid = "TEST_custom_core_test"
    # clean start
    requests.delete(f"{API}/custom-program/{pid}", headers=h)

    payload = {
        "profile_id": pid,
        "name": "Core Test Program",
        "week": "Test Week",
        "session_minutes": 50,
        "sessions": [
            {"day": 1, "label": "Push Test", "demand": "HIGH", "focus": ["Peitoral superior"],
             "exercises": [{"exercise_id": "incline-smith", "sets": 4, "reps": "6-8", "rir": "1", "rest": "3 min", "load": 85, "technique": "Rest-Pause", "technique_id": "rest-pause", "note": ""},
                           {"exercise_id": "lateral-raise", "sets": 3, "reps": "12", "rir": "1-2", "rest": "90 s", "load": 14, "technique": "Drop Set", "technique_id": "drop-set", "note": ""}]},
            {"day": 2, "label": "Pull Test", "demand": "MODERATE", "focus": ["Dorsais / largura"],
             "exercises": [{"exercise_id": "row", "sets": 3, "reps": "8", "rir": "2", "rest": "2 min", "load": 70, "technique": "Straight Sets", "technique_id": "straight", "note": ""}]},
        ]
    }
    r = requests.post(f"{API}/custom-program", json=payload, headers=h)
    assert r.status_code == 200, f"save failed: {r.text}"
    prog = r.json()["program"]
    assert prog["logic"]["manual"] is True
    assert prog["logic"]["mode"] == "FORGE_PRO"
    assert len(prog["sessions"]) == 2
    # verify technique preservation
    first = prog["sessions"][0]["exercises"][0]
    assert first["technique_id"] == "rest-pause"

    # verify persistence via bootstrap
    b = requests.get(f"{API}/bootstrap?profile_id={pid}", headers=h)
    assert b.status_code == 200
    bprog = b.json()["program"]
    assert bprog["logic"]["manual"] is True

    # delete and verify engine fallback
    d = requests.delete(f"{API}/custom-program/{pid}", headers=h)
    assert d.status_code == 200
    assert d.json()["cleared"] is True

    b2 = requests.get(f"{API}/bootstrap?profile_id={pid}", headers=h)
    assert not b2.json()["program"]["logic"].get("manual")


# ===================== WORKOUT SET LOGGING =====================

def test_sets_persist_actual_values():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    pid = "TEST_sets_core"
    payload = {
        "profile_id": pid,
        "exercise_id": "incline-smith",
        "set_number": 1,
        "weight": 92.5,
        "reps": 7,
        "rir": 1,
        "technique": "Top Set + Back-off",
        "note": "felt strong"
    }
    r = requests.post(f"{API}/sets", json=payload, headers=h)
    assert r.status_code == 200, f"set log failed: {r.text}"
    data = r.json()
    assert data["weight"] == 92.5
    assert data["reps"] == 7
    assert data["technique"] == "Top Set + Back-off"
    assert data["rir"] == 1
    assert data["id"]

    # verify via bootstrap
    b = requests.get(f"{API}/bootstrap?profile_id={pid}", headers=h)
    recent = b.json()["recent_sets"]
    found = any(s["weight"] == 92.5 and s["reps"] == 7 for s in recent)
    assert found, "logged set not found in recent_sets"


# ===================== EXERCISE HISTORY =====================

@pytest.mark.skip(reason="Needs deployment of new /api/exercise-history endpoint")
def test_exercise_history():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    pid = "TEST_history_core"
    # log multiple sets
    for i in range(3):
        requests.post(f"{API}/sets", json={
            "profile_id": pid, "exercise_id": "lateral-raise",
            "set_number": i+1, "weight": 10 + i*2, "reps": 12, "rir": 2
        }, headers=h)

    r = requests.get(f"{API}/exercise-history/lateral-raise?profile_id={pid}", headers=h)
    assert r.status_code == 200, f"history failed: {r.text}"
    data = r.json()
    assert data["exercise"] is not None
    assert data["count"] >= 3
    assert len(data["history"]) >= 3
    assert data["history"][0]["exercise_id"] == "lateral-raise"


# ===================== ANALYTICS (REAL DATA) =====================

def test_analytics_real_data():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.get(f"{API}/analytics", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "volume" in data
    assert "trend" in data
    assert "prs" in data
    assert len(data["trend"]) == 4
    for t in data["trend"]:
        assert "week" in t
        assert "load" in t
        assert "volume" in t


def test_analytics_with_profile():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.get(f"{API}/analytics?profile_id=demo", headers=h)
    assert r.status_code == 200
    assert len(r.json()["trend"]) == 4


# ===================== WEEKLY REPORT (REAL DATA) =====================

def test_weekly_report_real_data():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.get(f"{API}/weekly-report?profile_id=demo", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "completed" in data
    assert "planned" in data
    assert "adherence" in data
    assert "headline" in data
    assert "signals" in data
    assert "recommendation" in data


# ===================== TRAINING ENGINE / PROGRAM PREVIEW =====================

@pytest.mark.skip(reason="Needs deployment of new /api/program/preview endpoint")
def test_program_preview():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    profile = {
        "days": 4,
        "priorities": ["Peitoral superior", "Deltóide lateral"],
        "experience": "Avançado",
        "assessment": {"Peitoral superior": {"development": "fraco", "priority": "alta"}},
        "session_minutes": 70
    }
    r = requests.post(f"{API}/program/preview", json=profile, headers=h)
    assert r.status_code == 200, f"preview failed: {r.text}"
    data = r.json()
    assert data["preview"] is True
    assert data["program"]["logic"]["days"] == 4
    assert len(data["program"]["sessions"]) == 4
    assert "priority_scores" in data["program"]["logic"]


@pytest.mark.skip(reason="Needs deployment of new /api/program/preview endpoint")
def test_build_program_days_match():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    for days in [1, 2, 3, 4, 5, 6, 7]:
        r = requests.post(f"{API}/program/preview", json={"days": days}, headers=h)
        assert r.status_code == 200
        prog = r.json()["program"]
        assert prog["logic"]["days"] == days
        assert len(prog["sessions"]) == days


def test_assessment_save_returns_program():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    pid = f"TEST_assess_engine_{int(time.time())}"
    r = requests.post(f"{API}/assessment", json={
        "profile_id": pid, "days": 5, "experience": "Intermediário",
        "goal": "Hipertrofia", "priorities": ["Quadríceps", "Posteriores"],
        "assessment": {"Quadríceps": {"development": "fraco", "priority": "alta"}}
    }, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["assessment_version"] == 2
    assert data["program"]["logic"]["days"] == 5
    assert len(data["program"]["sessions"]) == 5


# ===================== COACH SSE =====================

def test_coach_sse_endpoint():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    body = {"question": "Como está meu treino?", "context": {
        "profile_id": "demo",
        "profile": {"name": "Rafael", "experience": "Avançado", "goal": "Hipertrofia"},
        "assessment": {"Peitoral superior": {"development": "fraco", "priority": "alta"}},
        "priorities": ["Peitoral superior"],
        "program": {"name": "Upper/Lower", "sessions": []},
        "recent_sets": [],
        "weekly_volume": {},
        "recovery": {"sleep_hours": 7, "stress": 2},
        "baseline": [],
    }}
    with requests.post(f"{API}/coach", json=body, headers=h, stream=True, timeout=45) as r:
        assert r.status_code == 200, f"coach failed: {r.text}"
        content_type = r.headers.get("content-type", "")
        assert "text/event-stream" in content_type
        got_text = False
        got_done = False
        for raw in r.iter_lines(decode_unicode=True):
            if not raw: continue
            if not raw.startswith("data:"): continue
            payload = raw[len("data:"):].strip()
            if payload == "[DONE]":
                got_done = True
                break
            try:
                obj = json.loads(payload)
                if "text" in obj or "error" in obj:
                    got_text = True
            except: pass
        assert got_done, "SSE stream did not emit [DONE]"
        assert got_text, "SSE stream did not emit text/error"


# ===================== EXERCISE ALTERNATIVES =====================

def test_exercise_alternatives():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)
    r = requests.get(f"{API}/exercises/incline-smith/alternatives", headers=h)
    assert r.status_code == 200
    assert r.json()["source"]["id"] == "incline-smith"
    assert len(r.json()["alternatives"]) >= 1


# ===================== MUSCLE MAP =====================

def test_muscle_map_18_regions():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.get(f"{API}/muscle-map/demo", headers=h)
    assert r.status_code == 200
    assert len(r.json()["rows"]) == 18


# ===================== ADMIN STATS =====================

def test_admin_stats():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.get(f"{API}/admin/stats", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "active" in data


def test_admin_audit_log():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.get(f"{API}/admin/audit-log?limit=10", headers=h)
    assert r.status_code == 200
    assert "log" in r.json()


# ===================== TECHNIQUES =====================

def test_techniques_catalog_core():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    r = requests.get(f"{API}/techniques", headers=auth_header(token))
    assert r.status_code == 200
    assert len(r.json()["techniques"]) == 10


# ===================== VISUAL ASSESSMENT =====================

def test_visual_assessment_no_photo():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.post(f"{API}/visual-assessment", data={"profile_id": "demo", "consent": "true", "views": "[]"}, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("unavailable", "completed", "error")
    assert "message" in data or "observations" in data


def test_visual_assessment_with_dummy_photo():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    import io
    dummy = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    dummy.name = "test.png"
    r = requests.post(f"{API}/visual-assessment",
                      data={"profile_id": "demo", "consent": "true", "views": '["frente"]'},
                      files={"photos": ("test.png", dummy, "image/png")}, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert "status" in data
    if data["status"] == "unavailable":
        assert any(kw in (data.get("message", "") + data.get("status", "")) for kw in ["GEMINI", "Vision", "indispon", "unavailable"])
    elif data["status"] == "completed":
        assert "observations" in data
        assert len(data.get("observations", {})) == 18
        assert "symmetry_notes" in data
        assert "suggested_priorities" in data


@pytest.mark.skip(reason="Needs deployment of new Visual Assessment endpoints")
def test_get_visual_assessment():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.get(f"{API}/visual-assessment/demo", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "manual_assessment" in data
    assert "vision_assessment" in data


@pytest.mark.skip(reason="Needs deployment of new Visual Assessment endpoints")
def test_visual_comparison():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.get(f"{API}/visual-comparison/demo", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "comparison" in data
    assert len(data["comparison"]) == 18
    for c in data["comparison"]:
        assert "muscle" in c
        assert "manual" in c
        assert "vision" in c
        assert "agreement" in c


@pytest.mark.skip(reason="Needs deployment of new Visual Assessment endpoints")
def test_visual_assessment_preserves_manual():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    # bootstrap before visual assessment
    before = requests.get(f"{API}/bootstrap?profile_id=demo", headers=h)
    assert before.status_code == 200
    before_assessment = before.json()["profile"].get("assessment", {})
    before_priorities = before.json()["profile"].get("priorities", [])

    # upload visual assessment
    requests.post(f"{API}/visual-assessment",
                  data={"profile_id": "demo", "consent": "true", "views": '["frente"]'},
                  headers=h)

    # bootstrap after - manual assessment must be intact
    after = requests.get(f"{API}/bootstrap?profile_id=demo", headers=h)
    assert after.status_code == 200
    after_assessment = after.json()["profile"].get("assessment", {})
    after_priorities = after.json()["profile"].get("priorities", [])

    # manual assessment should be preserved, vision is in visual_assessment field
    assert len(after_assessment) >= len(before_assessment)
    # priorities unchanged by vision
    assert after_priorities == before_priorities


# ===================== RECOVERY LOG =====================

def test_recovery_log():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.post(f"{API}/recovery", json={
        "profile_id": "TEST_recovery_core", "sleep": 4, "energy": 4,
        "motivation": 3, "soreness": 2, "stress": 2
    }, headers=h)
    assert r.status_code == 200
    assert r.json()["sleep"] == 4


# ===================== WEEKLY REVIEW =====================

def test_weekly_review():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.post(f"{API}/weekly-review", json={
        "profile_id": "TEST_review_core", "performance": 4, "recovery": 3,
        "soreness": 1, "improved_exercises": ["incline-smith"]
    }, headers=h)
    assert r.status_code == 200
    assert r.json()["recommendations"]


# ===================== PROGRAM ANALYSIS =====================

def test_program_analysis():
    login = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS})
    token = login.json()["token"]
    h = auth_header(token)

    r = requests.post(f"{API}/program/analyze", json={
        "profile_id": "TEST_analysis_core",
        "days": [{"exercises": [{"exercise_id": "incline-smith", "sets": 3}, {"exercise_id": "hack-squat", "sets": 4}]}]
    }, headers=h)
    assert r.status_code == 200
    assert r.json()["sessions"] == 1
    assert "volume_direct" in r.json()

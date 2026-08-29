import os, sys
import json
import requests
from dotenv import load_dotenv
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

BASE_URL = (os.environ.get("BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8000").rstrip("/")

# Estas rotas exigem login desde que a autenticacao foi aplicada a elas; test_seguranca
# verifica que nenhuma responde a anonimo. A sessao carrega o Authorization.
from sessao import sessao_admin

S = sessao_admin()

TECHNIQUE_IDS = {"straight","drop-set","mechanical-drop-set","rest-pause","myo-reps","cluster","top-set-backoff","pyramid","lengthened-partials","superset"}


# --- Techniques catalog ---
def test_techniques_catalog():
    r = S.get(f"{BASE_URL}/api/techniques")
    assert r.status_code == 200
    data = r.json()
    assert "techniques" in data
    assert len(data["techniques"]) == 10
    for t in data["techniques"]:
        for key in ("id","name","short","fatigue","description","protocol","when"):
            assert key in t, f"missing {key} in {t}"
    ids = {t["id"] for t in data["techniques"]}
    assert ids == TECHNIQUE_IDS


def test_bootstrap_includes_techniques():
    r = S.get(f"{BASE_URL}/api/bootstrap?profile_id=demo")
    assert r.status_code == 200
    body = r.json()
    assert "techniques" in body
    assert len(body["techniques"]) == 10


# --- Custom program flow ---
CUSTOM_PROFILE_ID = "TEST_custom_prog_v4"

def _custom_program_payload():
    return {
        "profile_id": CUSTOM_PROFILE_ID,
        "name": "Meu Programa Pro",
        "week": "Microciclo manual",
        "session_minutes": 65,
        "sessions": [
            {
                "day": 1, "label": "Push Pro", "demand": "HIGH", "focus": ["Peitoral superior"],
                "exercises": [
                    {"exercise_id": "incline-smith", "sets": 4, "reps": "5", "rir": "1", "rest": "3 min", "load": 80,
                     "technique": "Top Set + Back-off", "technique_id": "top-set-backoff", "note": "pico + volume"},
                    {"exercise_id": "lateral-raise", "sets": 3, "reps": "12", "rir": "0-1", "rest": "60 s", "load": 12,
                     "technique": "Myo-Reps", "technique_id": "myo-reps"},
                ],
            },
            {
                "day": 2, "label": "Pull Pro", "demand": "MODERATE", "focus": ["Dorsais / largura"],
                "exercises": [
                    {"exercise_id": "row", "sets": 3, "reps": "8", "rir": "1-2", "rest": "2 min", "load": 70,
                     "technique": "Rest-Pause", "technique_id": "rest-pause"},
                    {"exercise_id": "lat-pulldown", "sets": 3, "reps": "10", "rir": "2", "rest": "2 min", "load": 60,
                     "technique": "Straight Sets", "technique_id": "straight"},
                ],
            },
        ],
    }


def test_custom_program_post_and_persistence():
    # Ensure clean starting state
    S.delete(f"{BASE_URL}/api/custom-program/{CUSTOM_PROFILE_ID}")
    payload = _custom_program_payload()
    r = S.post(f"{BASE_URL}/api/custom-program", json=payload)
    assert r.status_code == 200, r.text
    prog = r.json()["program"]
    assert prog["logic"]["manual"] is True
    assert prog["logic"]["mode"] == "FORGE_PRO"
    assert prog["name"] == "Meu Programa Pro"
    # Techniques preserved on first exercise
    first_ex = prog["sessions"][0]["exercises"][0]
    assert first_ex["technique_id"] == "top-set-backoff"
    assert first_ex["technique"] == "Top Set + Back-off"

    # Persistence via bootstrap
    b = S.get(f"{BASE_URL}/api/bootstrap?profile_id={CUSTOM_PROFILE_ID}")
    assert b.status_code == 200
    bprog = b.json()["program"]
    assert bprog["logic"].get("manual") is True
    assert bprog["name"] == "Meu Programa Pro"
    # Verify profile has base fields merged (name populated)
    prof = b.json()["profile"]
    assert prof.get("name")


def test_custom_program_delete_reverts_to_engine():
    # Precondition: program exists
    S.post(f"{BASE_URL}/api/custom-program", json=_custom_program_payload())
    d = S.delete(f"{BASE_URL}/api/custom-program/{CUSTOM_PROFILE_ID}")
    assert d.status_code == 200
    assert d.json().get("cleared") is True
    b = S.get(f"{BASE_URL}/api/bootstrap?profile_id={CUSTOM_PROFILE_ID}")
    assert b.status_code == 200
    prog = b.json()["program"]
    assert not prog["logic"].get("manual"), "should revert to engine program"


# --- Sets with technique field ---
def test_sets_stores_technique_field():
    profile_id = "TEST_sets_tech_v4"
    payload = {"profile_id": profile_id, "exercise_id": "incline-smith", "set_number": 1,
               "weight": 90, "reps": 6, "rir": 1, "technique": "Rest-Pause"}
    r = S.post(f"{BASE_URL}/api/sets", json=payload)
    assert r.status_code == 200
    assert r.json()["technique"] == "Rest-Pause"
    b = S.get(f"{BASE_URL}/api/bootstrap?profile_id={profile_id}")
    assert b.status_code == 200
    recent = b.json()["recent_sets"]
    assert any(s.get("technique") == "Rest-Pause" and s.get("weight") == 90 for s in recent)


# --- Coach SSE endpoint ---
def test_coach_sse_streaming():
    context = {
        "profile_id": "demo",
        "profile": {"name": "Rafael", "experience": "Avançado", "goal": "Hipertrofia"},
        "assessment": {"Peitoral superior": {"development": "fraco", "priority": "alta"}},
        "priorities": ["Peitoral superior", "Deltóide lateral"],
        "program": {"name": "Upper/Lower", "sessions": []},
        "recent_sets": [],
        "weekly_volume": {"Peitoral superior": 8},
        "recovery": {"sleep_hours": 7, "stress": 2},
        "baseline": [{"exercise_id": "incline-smith", "weight": 80}],
    }
    body = {"question": "Como priorizar peitoral superior nesta semana?", "context": context}
    with S.post(f"{BASE_URL}/api/coach", json=body, stream=True, timeout=60) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        chunks = []
        got_done = False
        got_text_or_error = False
        for raw in r.iter_lines(decode_unicode=True):
            if not raw:
                continue
            assert raw.startswith("data:"), f"bad SSE line: {raw}"
            payload = raw[len("data:"):].strip()
            if payload == "[DONE]":
                got_done = True
                break
            # Should be valid JSON per line
            obj = json.loads(payload)
            assert ("text" in obj) or ("error" in obj)
            got_text_or_error = True
            chunks.append(obj)
        assert got_done, "SSE stream did not emit [DONE]"
        assert got_text_or_error, "SSE stream did not emit any text/error chunk"

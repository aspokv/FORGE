import os, sys
import requests
from dotenv import load_dotenv
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

BASE_URL = (os.environ.get("BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8000").rstrip("/")


def test_demo_legacy_compatibility_and_muscle_map():
    session = requests.Session()
    bootstrap = session.get(f"{BASE_URL}/api/bootstrap?profile_id=demo")
    assert bootstrap.status_code == 200
    assert bootstrap.json()["profile"]["id"] == "demo"
    muscle_map = session.get(f"{BASE_URL}/api/muscle-map/demo")
    assert muscle_map.status_code == 200
    assert len(muscle_map.json()["rows"]) == 18


def test_assessment_generates_requested_session_counts():
    session = requests.Session()
    for days in range(1, 8):
        payload = {"profile_id": f"TEST_regression_{days}", "days": days}
        response = session.post(f"{BASE_URL}/api/assessment", json=payload)
        assert response.status_code == 200
        program = response.json()["program"]
        assert program["logic"]["days"] == days
        assert len(program["sessions"]) == days


def test_v2_supporting_endpoints():
    session = requests.Session()
    alternatives = session.get(f"{BASE_URL}/api/exercises/incline-smith/alternatives")
    assert alternatives.status_code == 200 and alternatives.json()["alternatives"]
    review = session.post(f"{BASE_URL}/api/weekly-review", json={"profile_id": "TEST_review", "performance": 4})
    assert review.status_code == 200 and review.json()["recommendations"]
    analysis = session.post(f"{BASE_URL}/api/program/analyze", json={"profile_id": "TEST_analysis", "days": [{"exercises": [{"exercise_id": "incline-smith", "sets": 3}]}]})
    assert analysis.status_code == 200 and analysis.json()["sessions"] == 1

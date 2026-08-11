import os, sys
import requests
from dotenv import load_dotenv
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

BASE_URL = (os.environ.get("BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8000").rstrip("/")


def test_critical_api_flow():
    session = requests.Session()
    root = session.get(f"{BASE_URL}/api/")
    assert root.status_code == 200 and root.json()["message"] == "FORGE API online"
    bootstrap = session.get(f"{BASE_URL}/api/bootstrap")
    assert bootstrap.status_code == 200
    data = bootstrap.json()
    assert data["profile"]["id"] == "demo"
    assert len(data["program"]["sessions"]) == data["program"]["logic"]["days"]
    item = {"profile_id": "TEST_forge", "exercise_id": "incline-smith", "set_number": 1, "weight": 85, "reps": 8, "rir": 2}
    logged = session.post(f"{BASE_URL}/api/sets", json=item)
    assert logged.status_code == 200 and logged.json()["weight"] == 85 and "_id" not in logged.json()
    recovery = session.post(f"{BASE_URL}/api/recovery", json={"profile_id": "TEST_forge", "sleep": 4, "energy": 4, "motivation": 4, "soreness": 2, "stress": 2})
    assert recovery.status_code == 200 and recovery.json()["profile_id"] == "TEST_forge"
    analytics = session.get(f"{BASE_URL}/api/analytics")
    report = session.get(f"{BASE_URL}/api/weekly-report")
    assert analytics.status_code == 200 and analytics.json()["prs"]
    assert report.status_code == 200 and report.json()["adherence"] == 75
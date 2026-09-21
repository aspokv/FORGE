"""Imported diet targets: preview -> activation -> reload, with isolated storage."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user
import nutrition_routes as routes
import nutrition_import_routes as imports
from nutrition_import import (build_matcher, parse_diet_text, restore_import_targets,
                              targets_from_import_totals)

OLD = {"goal_calories": 2870, "protein_g": 136, "carbs_g": 428.5, "fat_g": 68}
TOTALS = {"kcal": 2398, "protein_g": 244, "carbs_g": 200, "fat_g": 67}
ASSESSMENT = {"weight_kg": 70, "height_cm": 175, "age": 30, "sex": "male",
              "training_days": 4, "goal": "maintenance"}


class Plans:
    def __init__(self, doc=None):
        self.doc = deepcopy(doc)
        self.writes = 0

    async def find_one(self, *_args, **_kwargs):
        return deepcopy(self.doc)

    async def replace_one(self, _filter, doc, **_kwargs):
        self.doc = deepcopy(doc)
        self.writes += 1

    async def update_one(self, query, update, **_kwargs):
        if not self.doc or ("plan" in query and query["plan"] != self.doc["plan"]):
            return SimpleNamespace(matched_count=0)
        for key, value in update["$set"].items():
            self.doc["plan"][key.removeprefix("plan.")] = deepcopy(value)
        self.writes += 1
        return SimpleNamespace(matched_count=1)


@pytest.fixture
def client(monkeypatch):
    db = SimpleNamespace(
        nutrition_plans=Plans(),
        profiles=SimpleNamespace(find_one=AsyncMock(return_value={"nutrition_assessment": ASSESSMENT}),
                                 update_one=AsyncMock()),
        nutrition_plan_versions=SimpleNamespace(insert_one=AsyncMock()),
        nutrition_import_drafts=SimpleNamespace(update_one=AsyncMock()),
    )
    monkeypatch.setattr(imports, "_matcher_for", AsyncMock(return_value=build_matcher()))
    monkeypatch.setattr(routes, "exigir_capacidade", AsyncMock())
    app = FastAPI()
    app.state.db = db
    app.dependency_overrides[get_current_user] = lambda: {"id": "test-import-user"}
    app.include_router(imports.router)
    app.include_router(routes.router)
    with TestClient(app) as c:
        yield c, db


def legacy():
    return {"profile_id": "test-import-user", "plan": {
        "source": "manual_import", "targets": deepcopy(OLD),
        "daily_totals": deepcopy(TOTALS), "meals": [{"name": "Saved", "foods": []}],
    }}


def test_reported_values_survive_reload_and_repair_only_once(client):
    c, db = client
    db.nutrition_plans.doc = legacy()
    before = deepcopy(db.nutrition_plans.doc["plan"]["meals"])
    for _ in range(2):
        response = c.get("/api/nutrition/plan")
        assert response.status_code == 200
        assert response.json()["targets"] == targets_from_import_totals(TOTALS)
    assert db.nutrition_plans.writes == 1
    assert db.nutrition_plans.doc["plan"]["meals"] == before
    assert db.nutrition_plans.doc["plan"]["daily_totals"] == TOTALS


def test_confirmed_preview_activation_and_reload_have_same_targets(client):
    c, db = client
    draft = parse_diet_text("Almoco\n150g de arroz branco\n120g de peito de frango")
    preview = deepcopy(draft["daily_totals"])
    # Extra totals from the browser must never override server/catalog calculations.
    draft["daily_totals"] = {"kcal": 99999}
    response = c.post("/api/nutrition/import/activate", json={
        "activation_token": "test-diet-activation", "draft": draft})
    assert response.status_code == 200, response.text
    plan = response.json()["plan"]
    assert plan["daily_totals"] == preview
    assert plan["targets"] == targets_from_import_totals(preview)
    assert plan["assessment_targets"] != plan["targets"]
    assert c.get("/api/nutrition/plan").json()["targets"] == plan["targets"]


def test_unresolved_draft_cannot_replace_existing_plan(client):
    c, db = client
    db.nutrition_plans.doc = legacy()
    draft = parse_diet_text("Almoco\n150g de arroz branco\n100g de xyzzydesconhecido")
    r = c.post("/api/nutrition/import/activate", json={
        "activation_token": "test-unresolved", "draft": draft})
    assert r.status_code == 422
    assert db.nutrition_plans.writes == 0


def test_questionnaire_does_not_replace_imported_targets(client):
    _c, db = client
    db.nutrition_plans.doc = legacy()
    assert asyncio.run(routes._atualizar_meta_do_plano(db, "test-import-user", ASSESSMENT)) is False
    assert db.nutrition_plans.writes == 0


def test_automatic_cycle_cannot_override_imported_plan(client):
    c, db = client
    db.nutrition_plans.doc = legacy()
    response = c.get("/api/nutrition/carb-cycle")
    assert response.status_code == 200
    assert response.json()["ativo"] is False


@pytest.mark.parametrize("change", ["generated", "already_repaired", "missing_totals"])
def test_repair_does_not_touch_other_plans(client, change):
    c, db = client
    original = legacy()
    if change == "generated":
        original["plan"]["source"] = "generated"
    elif change == "already_repaired":
        original["plan"]["targets_source"] = "manual_import"
    else:
        del original["plan"]["daily_totals"]
    db.nutrition_plans.doc = deepcopy(original)
    assert c.get("/api/nutrition/plan").json()["targets"] == OLD
    assert db.nutrition_plans.writes == 0


def test_concurrent_new_plan_is_not_overwritten(client):
    _c, db = client
    stale = legacy()
    db.nutrition_plans.doc = {"profile_id": "test-import-user", "plan": {
        "source": "generated", "targets": {"goal_calories": 3000}}}
    fresh = deepcopy(db.nutrition_plans.doc)
    result = asyncio.run(restore_import_targets(db, "test-import-user", stale))
    assert result == fresh
    assert db.nutrition_plans.doc == fresh
    assert db.nutrition_plans.writes == 0

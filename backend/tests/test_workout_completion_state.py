"""Exercise real endpoint bodies with an isolated database double."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock
import uuid

def endpoints():
    source = ast.parse((Path(__file__).parents[1] / "server.py").read_text())
    names = {"complete_workout", "latest_workout_completion"}
    nodes = [n for n in source.body if isinstance(n, ast.AsyncFunctionDef) and n.name in names]
    for node in nodes:
        node.decorator_list = []
    ns = dict(Depends=lambda f: None, get_current_user=lambda: None,
              Optional=Optional, WorkoutCompleteIn=object,
              datetime=datetime, timezone=timezone, uuid=uuid,
              HTTPException=lambda *a: RuntimeError(a))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "server.py", "exec"), ns)
    return ns

class Profiles:
    def __init__(self):
        self.doc = {"id": "athlete", "current_session_day": 1}
    async def update_one(self, query, update, **kwargs):
        matches = self.doc.get("last_workout_operation") != query.get("last_workout_operation", {}).get("$ne")
        if "$or" in query:
            matches = matches and (self.doc["current_session_day"] == query["$or"][0]["current_session_day"] or self.doc["current_session_day"] not in query["$or"][1]["current_session_day"]["$nin"])
        if matches:
            self.doc.update(update["$set"])
        return SimpleNamespace(matched_count=int(matches))
    async def find_one(self, *args, **kwargs):
        return self.doc

def test_latest_completion_is_scoped_to_authenticated_owner():
    ns = endpoints()
    find = AsyncMock(return_value={"day": 1})
    ns.update(db=SimpleNamespace(workout_completions=SimpleNamespace(find_one=find)),
              owned_profile_id=lambda user, requested: user["id"])
    assert asyncio.run(ns["latest_workout_completion"]({"id":"athlete"}, "someone-else")) == {"completion":{"day":1}}
    assert find.call_args.args[0] == {"profile_id":"athlete"}

def test_retry_does_not_duplicate_even_when_program_has_one_session():
    ns = endpoints()
    profiles = Profiles()
    insert = AsyncMock()
    ns.update(db=SimpleNamespace(profiles=profiles, workout_completions=SimpleNamespace(insert_one=insert)),
              owned_profile_id=lambda user, requested: user["id"],
              load_profile=AsyncMock(side_effect=lambda _: dict(profiles.doc)),
              build_program=AsyncMock(return_value={"active_day":1,"sessions":[{"day":1,"label":"Full Body"}]}))
    payload=SimpleNamespace(profile_id=None,day=1,completed_sets=3,total_sets=3,
         duration_seconds=1200,started_at="2026-09-10T10:00:00Z",partial_reason="",discomfort="none")
    async def run():
        return await asyncio.gather(ns["complete_workout"](payload,{"id":"athlete"}),ns["complete_workout"](payload,{"id":"athlete"}))
    results=asyncio.run(run())
    assert insert.await_count == 1
    assert sorted(r["already_completed"] for r in results) == [False,True]
    assert profiles.doc["current_session_day"] == 1

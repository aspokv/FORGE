"""Exercise real endpoint bodies with an isolated database double."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock
import uuid
from workout_calendar import calendar_selection

def endpoints():
    source = ast.parse((Path(__file__).parents[1] / "server.py").read_text())
    names = {"complete_workout", "latest_workout_completion"}
    nodes = [n for n in source.body if isinstance(n, ast.AsyncFunctionDef) and n.name in names]
    for node in nodes:
        node.decorator_list = []
    ns = dict(Depends=lambda f: None, get_current_user=lambda: None,
              Optional=Optional, WorkoutCompleteIn=object,
              datetime=datetime, timezone=timezone, uuid=uuid, calendar_selection=calendar_selection,
              HTTPException=lambda *a: RuntimeError(a))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "server.py", "exec"), ns)
    return ns

class Profiles:
    def __init__(self):
        self.doc = {"id": "athlete", "current_session_day": 1}
    async def update_one(self, query, update, **kwargs):
        matches = self.doc.get("last_workout_operation") != query.get("last_workout_operation", {}).get("$ne")
        matches = matches and self.doc.get("last_workout_completion_day") != query.get("last_workout_completion_day", {}).get("$ne")
        if "$or" in query:
            matches = matches and (self.doc["current_session_day"] == query["$or"][0]["current_session_day"] or self.doc["current_session_day"] not in query["$or"][1]["current_session_day"]["$nin"])
        if matches:
            self.doc.update(update["$set"])
        return SimpleNamespace(matched_count=int(matches))
    async def find_one(self, *args, **kwargs):
        return self.doc

def test_latest_completion_is_scoped_to_authenticated_owner():
    ns = endpoints()
    find = AsyncMock(return_value=None)
    ns.update(db=SimpleNamespace(workout_completions=SimpleNamespace(find_one=find)),
              owned_profile_id=lambda user, requested: user["id"])
    assert asyncio.run(ns["latest_workout_completion"]({"id":"athlete"}, "someone-else")) == {"completion":None}
    assert find.call_args.args[0] == {"profile_id":"athlete"}

def test_retry_does_not_duplicate_even_when_program_has_one_session():
    ns = endpoints()
    profiles = Profiles()
    insert = AsyncMock()
    ns.update(db=SimpleNamespace(profiles=profiles, workout_completions=SimpleNamespace(insert_one=insert,find_one=AsyncMock(return_value=None))),
              owned_profile_id=lambda user, requested: user["id"],
              load_profile=AsyncMock(side_effect=lambda _: dict(profiles.doc)),
              build_program=AsyncMock(return_value={"active_day":1,"sessions":[{"day":1,"label":"Full Body"}]}))
    payload=SimpleNamespace(profile_id=None,day=1,local_date="2026-09-10",completed_sets=3,total_sets=3,
         duration_seconds=1200,started_at="2026-09-10T10:00:00Z",partial_reason="",discomfort="none")
    async def run():
        return await asyncio.gather(ns["complete_workout"](payload,{"id":"athlete"}),ns["complete_workout"](payload,{"id":"athlete"}))
    results=asyncio.run(run())
    assert insert.await_count == 1
    assert sorted(r["already_completed"] for r in results) == [False,True]
    assert profiles.doc["current_session_day"] == 1

def test_different_operations_on_the_same_day_do_not_advance_twice():
    ns = endpoints()
    profiles = Profiles()
    insert = AsyncMock()
    ns.update(db=SimpleNamespace(profiles=profiles, workout_completions=SimpleNamespace(insert_one=insert,find_one=AsyncMock(return_value=None))),
              owned_profile_id=lambda user, requested: user["id"],
              load_profile=AsyncMock(side_effect=lambda _: dict(profiles.doc)),
              build_program=AsyncMock(return_value={"active_day":1,"sessions":[{"day":1,"label":"Push"},{"day":2,"label":"Pull"}]}))
    def payload(day, start, date="2026-09-10"):
        return SimpleNamespace(profile_id=None,day=day,local_date=date,completed_sets=3,total_sets=3,
          duration_seconds=1200,started_at=start,partial_reason="",discomfort="none")
    async def run():
        first=await ns["complete_workout"](payload(1,"2026-09-10T10:00:00Z"),{"id":"athlete"})
        second=await ns["complete_workout"](payload(2,"2026-09-10T11:00:00Z"),{"id":"athlete"})
        assert first["already_completed"] is False
        assert second["already_completed"] is True
        assert insert.await_count == 1
        third=await ns["complete_workout"](payload(2,"2026-09-11T10:00:00Z","2026-09-11"),{"id":"athlete"})
        assert third["already_completed"] is False
        assert insert.await_count == 2
    asyncio.run(run())

def test_next_session_uses_server_pointer_without_second_rotation():
    ns=endpoints()
    sessions=[{"day":1,"label":"Push 1"},{"day":2,"label":"Pull 1"},{"day":3,"label":"Legs"}]
    ns.update(db=SimpleNamespace(workout_completions=SimpleNamespace(find_one=AsyncMock(return_value={"day":1,"label":"Push 1"}))),
      owned_profile_id=lambda user, requested:user["id"],load_profile=AsyncMock(return_value={}),
      build_program=AsyncMock(return_value={"active_day":2,"sessions":sessions}))
    result=asyncio.run(ns["latest_workout_completion"]({"id":"athlete"}))["completion"]
    assert result["next_session"] == sessions[1]
    assert result["next_session_status"] == "confirmed"

def test_old_push_label_with_reused_day_does_not_preview_another_push():
    ns=endpoints()
    ns.update(db=SimpleNamespace(workout_completions=SimpleNamespace(find_one=AsyncMock(return_value={"day":3,"label":"Push Ombros"}))),
      owned_profile_id=lambda user, requested:user["id"],load_profile=AsyncMock(return_value={}),
      build_program=AsyncMock(return_value={"active_day":1,"sessions":[{"day":1,"label":"Push 1"},{"day":2,"label":"Pull 1"},{"day":3,"label":"Legs"}]}))
    result=asyncio.run(ns["latest_workout_completion"]({"id":"athlete"}))["completion"]
    assert result["next_session"] is None
    assert result["next_session_status"] == "program_changed"

def test_sequence_snapshot_detects_reordering_even_if_completed_label_matches():
    ns=endpoints()
    old=[{"day":1,"label":"Push"},{"day":2,"label":"Pull"},{"day":3,"label":"Legs"}]
    ns.update(db=SimpleNamespace(workout_completions=SimpleNamespace(find_one=AsyncMock(return_value={"day":1,"label":"Push","session_sequence":old}))),
      owned_profile_id=lambda user, requested:user["id"],load_profile=AsyncMock(return_value={}),
      build_program=AsyncMock(return_value={"active_day":2,"sessions":[old[0],{"day":2,"label":"Legs"},{"day":3,"label":"Pull"}]}))
    result=asyncio.run(ns["latest_workout_completion"]({"id":"athlete"}))["completion"]
    assert result["next_session"] is None

def test_calendar_friday_completes_even_if_pointer_is_monday_and_retry_is_atomic():
    ns = endpoints()
    profiles = Profiles()
    insert = AsyncMock()
    sessions = [{"day": 1, "label": "Segunda · Upper A"},
                {"day": 4, "label": "Sexta · Upper C"},
                {"day": 5, "label": "Sábado · Full Body B"}]
    ns.update(db=SimpleNamespace(profiles=profiles, workout_completions=SimpleNamespace(insert_one=insert,find_one=AsyncMock(return_value=None))),
              owned_profile_id=lambda user, requested: user["id"],
              load_profile=AsyncMock(side_effect=lambda _: dict(profiles.doc)),
              build_program=AsyncMock(return_value={"active_day":4,"sessions":sessions}))
    payload=SimpleNamespace(profile_id=None,day=4,local_date="2026-09-11",completed_sets=3,total_sets=3,
         duration_seconds=1200,started_at="2026-09-11T10:00:00Z",partial_reason="",discomfort="none")
    async def run():
        first=await ns["complete_workout"](payload,{"id":"athlete"})
        assert first["completed_day"] == 4
        assert first["next_day"] == 5
        second=await ns["complete_workout"](payload,{"id":"athlete"})
        assert second["already_completed"] is True
    asyncio.run(run())
    assert insert.await_count == 1
    assert insert.call_args.args[0]["label"] == "Sexta · Upper C"

def test_calendar_rejects_monday_session_on_friday_and_rest_day():
    import pytest
    ns=endpoints()
    profiles=Profiles()
    insert=AsyncMock()
    ns.update(db=SimpleNamespace(profiles=profiles,workout_completions=SimpleNamespace(insert_one=insert)),
              owned_profile_id=lambda user, requested:user["id"],
              load_profile=AsyncMock(return_value=profiles.doc),
              build_program=AsyncMock(return_value={"active_day":1,"sessions":[{"day":1,"label":"Segunda · Upper A"},{"day":4,"label":"Sexta · Upper C"}]}))
    for date in ("2026-09-11","2026-09-10"):
        payload=SimpleNamespace(profile_id=None,day=1,local_date=date)
        with pytest.raises(RuntimeError,match="409"):
            asyncio.run(ns["complete_workout"](payload,{"id":"athlete"}))
    assert insert.await_count == 0

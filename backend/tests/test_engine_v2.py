"""Tests for FORGE Training Engine v2.1 — bugs fixed."""
import sys, os, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import (
    EXERCISES, EXERCISE_INDEX, FRONTEND_EXERCISE_LIST, EXERCISE_BY_MUSCLE,
    determine_split, get_day_targets, calculate_session_capacity,
    select_exercises_for_day, build_exercise_prescription,
    calculate_weekly_volume, build_all_sessions,
    validate_sessions, count_weekly_sets_per_muscle,
    SPLIT_FULL_BODY, SPLIT_UPPER_LOWER, SPLIT_PUSH_PULL_LEGS,
    SPLIT_UL_PPL, SPLIT_UPPER_LOWER_PPL,
    UPPER_TARGETS, LOWER_TARGETS, PUSH_TARGETS, PULL_TARGETS, LEGS_TARGETS,
    _equipment_ok, _filter_candidates, _pick_best,
)
from muscles import to_internal, to_frontend, get_profile_priorities_internal

def test_exercise_count():
    assert len(EXERCISES) >= 80

def test_original_ids_preserved():
    for eid in ("incline-smith", "lat-pulldown", "lateral-raise", "hack-squat", "leg-curl", "row"):
        assert eid in EXERCISE_INDEX

def test_frontend_exercise_list_shape():
    for key in ("id", "name", "muscle", "secondary", "equipment", "pattern", "fatigue", "alternatives"):
        for ex in FRONTEND_EXERCISE_LIST:
            assert key in ex

def test_splits():
    assert determine_split(1, "Intermediário") == SPLIT_FULL_BODY
    assert determine_split(3, "Avançado") == SPLIT_PUSH_PULL_LEGS
    assert determine_split(4, "Intermediário") == SPLIT_UPPER_LOWER
    assert determine_split(5, "Bodybuilder") == SPLIT_UL_PPL
    assert determine_split(6, "Avançado") == SPLIT_PUSH_PULL_LEGS
    assert determine_split(7, "Avançado") == SPLIT_PUSH_PULL_LEGS

def test_equipment_hard_filter_rejects_incompatible():
    ex = EXERCISE_INDEX["bb-squat"]
    assert _equipment_ok(ex, {"equipment": ["Academia completa"]}) == True
    assert _equipment_ok(ex, {"equipment": []}) == True
    assert _equipment_ok(ex, {"equipment": ["dumbbell", "bench"]}) == False
    assert _equipment_ok(EXERCISE_INDEX["db-lateral-raise"], {"equipment": ["dumbbell"]}) == True

def test_filter_candidates_removes_incompatible():
    candidates = EXERCISE_BY_MUSCLE.get("quads", [])
    profile = {"equipment": ["dumbbell", "bench"]}
    filtered = _filter_candidates(candidates, profile, set())
    for eid in filtered:
        ex = EXERCISE_INDEX[eid]
        ok = _equipment_ok(ex, profile)
        assert ok, f"{eid} should not be in filtered results"

def test_no_avoid_exercise_selected():
    profile = {"equipment": ["Academia completa"], "avoid_exercises": ["bb-squat", "conventional-deadlift"]}
    exercises = select_exercises_for_day(["quads", "hamstrings", "glutes"], profile, 4)
    ids = [e["id"] for e in exercises]
    assert "bb-squat" not in ids
    assert "conventional-deadlift" not in ids

def test_arms_included_in_upper_day():
    profile = {"experience": "Avançado", "session_minutes": 90, "equipment": ["Academia completa"],
               "priorities": [], "assessment": {}}
    targets = UPPER_TARGETS
    exercises = select_exercises_for_day(targets, profile, 7, "MODERATE", 0)
    muscles = [e["primary_muscle"] for e in exercises]
    assert "biceps" in muscles or "triceps" in muscles, f"No arm exercise in Upper day: {muscles}"

def test_side_delts_included_in_upper():
    profile = {"experience": "Intermediário", "session_minutes": 75, "equipment": ["Academia completa"],
               "priorities": [], "assessment": {}}
    exercises = select_exercises_for_day(
        ["mid_chest","upper_chest","lats","upper_back","front_delts","side_delts","rear_delts","biceps","triceps"],
        profile, 6, "MODERATE", 0)
    muscles = [e["primary_muscle"] for e in exercises]
    assert "side_delts" in muscles, f"No side delt in Upper day: {muscles}"

def test_rear_delts_included_in_pull():
    profile = {"experience": "Intermediário", "session_minutes": 75, "equipment": ["Academia completa"],
               "priorities": [], "assessment": {}}
    exercises = select_exercises_for_day(["lats","upper_back","rear_delts","biceps"], profile, 4, "MODERATE", 0)
    muscles = [e["primary_muscle"] for e in exercises]
    assert "rear_delts" in muscles, f"No rear delt in Pull day: {muscles}"

def test_priority_gets_more_sets():
    profile = {"experience": "Avançado", "session_minutes": 90, "equipment": ["Academia completa"],
               "priorities": ["Peitoral superior"], "assessment": {"Peitoral superior": {"development": "fraco", "priority": "maxima"}}}
    sessions = build_all_sessions(profile, SPLIT_UPPER_LOWER, 4, 90)
    chest_sets = 0
    for s in sessions:
        for e in s["exercises"]:
            if EXERCISE_INDEX.get(e["exercise_id"], {}).get("primary_muscle") == to_internal("Peitoral superior"):
                chest_sets += e["sets"]
    assert chest_sets >= 8, f"Priority chest only got {chest_sets} weekly sets"

def test_equipment_limited_only_dumbbell():
    profile = {"id": "test-2", "experience": "Intermediário", "days": 4, "session_minutes": 60,
               "priorities": [], "assessment": {},
               "equipment": ["dumbbell", "bench"], "avoid_exercises": ["bb-bench-press"]}
    sessions = build_all_sessions(profile, SPLIT_UPPER_LOWER, 4, 60)
    for s in sessions:
        for e in s["exercises"]:
            ex = EXERCISE_INDEX[e["exercise_id"]]
            ok = _equipment_ok(ex, profile)
            assert ok, f"Equipment mismatch: {e['exercise_id']} requires {ex.get('equipment', [])}"

def test_full_validation_all_profiles():
    profiles = {
        "A": {"id":"a","experience":"Iniciante","days":3,"session_minutes":60,"priorities":[],"assessment":{},"equipment":["Academia completa"]},
        "B": {"id":"b","experience":"Intermediário","days":4,"session_minutes":75,"priorities":["Deltóide lateral","Dorsais / largura"],
              "assessment":{"Deltóide lateral":{"development":"fraco","priority":"alta"},"Dorsais / largura":{"development":"fraco","priority":"alta"}},"equipment":["Academia completa"]},
        "C": {"id":"c","experience":"Bodybuilder","days":5,"session_minutes":90,"priorities":["Deltóide lateral","Posteriores","Costas / espessura"],
              "assessment":{"Deltóide lateral":{"development":"muito fraco","priority":"maxima"},"Posteriores":{"development":"fraco","priority":"alta"},"Costas / espessura":{"development":"fraco","priority":"alta"}},"equipment":["Academia completa"]},
        "D": {"id":"d","experience":"Avançado","days":6,"session_minutes":90,"priorities":["Peitoral superior","Deltóide lateral"],
              "assessment":{"Peitoral superior":{"development":"muito fraco","priority":"maxima"},"Deltóide lateral":{"development":"fraco","priority":"alta"}},"equipment":["Academia completa"]},
        "E": {"id":"e","experience":"Intermediário","days":4,"session_minutes":60,"priorities":[],"assessment":{},
              "equipment":["dumbbell","bench"],"avoid_exercises":["bb-bench-press","bb-squat"]},
    }
    for label, p in profiles.items():
        st = determine_split(p["days"], p["experience"])
        sessions = build_all_sessions(p, st, p["days"], p["session_minutes"])
        warnings = validate_sessions(sessions, p, st, p["days"], p["session_minutes"])
        errors = [w for w in warnings if "[ERROR]" in w]
        assert not errors, f"Profile {label} has ERROR warnings: {errors}"
        for s in sessions:
            assert len(s["exercises"]) >= 3, f"Profile {label} session {s['label']} too short"
            ids = [e["exercise_id"] for e in s["exercises"]]
            assert len(ids) == len(set(ids)), f"Profile {label} duplicate exercises in {s['label']}"
            for e in s["exercises"]:
                ex = EXERCISE_INDEX[e["exercise_id"]]
                assert _equipment_ok(ex, p), f"Profile {label} {e['exercise_id']} equipment mismatch"

def test_custom_program_preserved():
    async def _t():
        p = {"id":"x","custom_program":{"name":"My","sessions":[{"day":1,"label":"Custom","exercises":[{"exercise_id":"incline-smith","sets":4}]}]}}
        r = await __import__("engine").build_program_v2(p, None)
        assert r["logic"]["manual"] is True
        assert r["sessions"][0]["label"] == "Custom"
    asyncio.run(_t())

def test_capacity_pull_day_increased():
    cap = calculate_session_capacity("Avançado", 90, "HIGH", ["lats","upper_back","rear_delts","biceps"], SPLIT_PUSH_PULL_LEGS)
    assert cap >= 4, f"Pull day capacity {cap} too low"

def test_all_8_schema_fields_present():
    p = {"id":"schema","experience":"Intermediário","days":4,"session_minutes":75,"priorities":[],"assessment":{},"equipment":["Academia completa"]}
    sessions = build_all_sessions(p, SPLIT_UPPER_LOWER, 4, 75)
    for s in sessions:
        for e in s["exercises"]:
            for key in ("exercise_id","sets","reps","rir","rest","load","technique","technique_id"):
                assert key in e, f"Missing field {key}"

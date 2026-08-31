"""Tests for FORGE Training Engine v3.0 — progression + periodization + deload + readiness."""
import sys, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import (
    EXERCISES, EXERCISE_INDEX, EXERCISE_BY_MUSCLE, FRONTEND_EXERCISE_LIST,
    determine_split, get_day_targets, calculate_session_capacity,
    select_exercises_for_day, build_exercise_prescription,
    calculate_weekly_volume, build_all_sessions, validate_sessions,
    count_weekly_sets_per_muscle, count_effective_sets_per_muscle,
    count_training_frequency, build_program_quality_report,
    performance_volume_factor, summarize_training_memory,
    SPLIT_FULL_BODY, SPLIT_UPPER_LOWER, SPLIT_PUSH_PULL_LEGS,
    UPPER_TARGETS, PULL_TARGETS, LEGS_TARGETS,
    _equipment_ok, _filter_candidates, advance_periodization,
    _compute_block_modifier, build_program_v2,
)
from progression import (
    decide_load_action, compute_today_exercise_adjustment,
    get_last_performance, get_recent_sets,
)
from muscles import to_internal, to_frontend, get_profile_priorities_internal

# ─── Basic library + split tests ───────────────────────────────────────

def test_exercise_count():
    assert len(EXERCISES) >= 86

def test_original_ids_preserved():
    for eid in ("incline-smith","lat-pulldown","lateral-raise","hack-squat","leg-curl","row"):
        assert eid in EXERCISE_INDEX

def test_equipment_hard_filter():
    assert _equipment_ok(EXERCISE_INDEX["bb-squat"], {"equipment": ["dumbbell","bench"]}) == False
    assert _equipment_ok(EXERCISE_INDEX["db-bench-press"], {"equipment": ["dumbbell","bench"]}) == True

def test_db_calf_exists():
    assert "db-calf-raise" in EXERCISE_INDEX, "Need dumbbell calf exercise"
    assert "dumbbell" in EXERCISE_INDEX["db-calf-raise"]["equipment"]

def test_db_adductor_exists():
    assert "db-adductor-lunge" in EXERCISE_INDEX or "side-lying-adduction" in EXERCISE_INDEX

# ─── Progression tests ─────────────────────────────────────────────────

def test_decide_load_first_time():
    action, weight, reason = decide_load_action("8-12", None, 3, "2")
    assert action == "FIRST_TIME"

def test_decide_load_top_of_range():
    perf = {"avg_weight": 40, "min_reps": 12, "sets_completed": 3, "avg_rir": 2.0, "date": "2026-01-01"}
    action, weight, reason = decide_load_action("8-12", perf, 3, "2")
    assert action == "LOAD_UP"

def test_decide_load_above_range():
    perf = {"avg_weight": 32, "min_reps": 14, "sets_completed": 3, "avg_rir": 1.5, "date": "2026-01-01"}
    action, weight, reason = decide_load_action("8-12", perf, 3, "2")
    assert action == "LOAD_UP"

def test_decide_load_in_range():
    perf = {"avg_weight": 50, "min_reps": 10, "sets_completed": 3, "avg_rir": 2, "date": "2026-01-01"}
    action, weight, reason = decide_load_action("8-12", perf, 3, "2")
    assert action in ("ADD_REPS", "KEEP_LOAD")

def test_decide_load_below_range():
    perf = {"avg_weight": 60, "min_reps": 5, "sets_completed": 3, "avg_rir": 2, "date": "2026-01-01"}
    action, weight, reason = decide_load_action("8-12", perf, 3, "2")
    assert action in ("REDUCE_LOAD", "KEEP_LOAD")

def test_today_adjustment_deload():
    perf = {"avg_weight": 50, "min_reps": 10, "sets_completed": 3, "avg_rir": 2, "date": "2026-01-01"}
    adj = compute_today_exercise_adjustment("db-bench-press", "compound", 3, "8-12", "2", perf, "NORMAL", "deload")
    assert adj["adjusted_sets"] < 3
    assert adj["block"] == "deload"

def test_today_adjustment_low_readiness():
    perf = {"avg_weight": 50, "min_reps": 10, "sets_completed": 3, "avg_rir": 2, "date": "2026-01-01"}
    adj = compute_today_exercise_adjustment("bb-squat", "compound", 4, "4-8", "1", perf, "LOW", "accumulation")
    assert adj["adjusted_sets"] < 4 or int(adj["adjusted_rir"][0]) >= 2

def test_today_adjustment_high_readiness():
    perf = {"avg_weight": 50, "min_reps": 10, "sets_completed": 3, "avg_rir": 2, "date": "2026-01-01"}
    adj = compute_today_exercise_adjustment("db-lateral-raise", "isolation", 3, "12-20", "2", perf, "HIGH", "progression")
    assert adj["adjusted_sets"] == 3

# ─── Periodization tests ───────────────────────────────────────────────

def test_perio_initial_state():
    profile = {"id": "p1"}
    state = advance_periodization(profile, [], [])
    assert state["block_type"] == "accumulation"
    assert state["block_week"] == 2

def test_perio_block_modifiers():
    vol, rir, override = _compute_block_modifier("accumulation")
    assert vol == 1.0
    assert rir == 2.0
    vol, rir, override = _compute_block_modifier("deload")
    assert vol < 0.6
    assert override == "3+"

def test_deload_sessions_reduced():
    profile = {"id": "p2", "experience": "Intermediario", "days": 4, "session_minutes": 75,
               "equipment": ["Academia completa"], "priorities": [], "assessment": {}}
    normal = build_all_sessions(profile, SPLIT_UPPER_LOWER, 4, 75, block_type="accumulation")
    deload = build_all_sessions(profile, SPLIT_UPPER_LOWER, 4, 75, block_type="deload")
    normal_total = sum(e["sets"] for s in normal for e in s["exercises"])
    deload_total = sum(e["sets"] for s in deload for e in s["exercises"])
    assert deload_total < normal_total * 0.8, f"Deload {deload_total} not reduced vs normal {normal_total}"

def test_recovery_low_sessions_reduced():
    profile = {"id": "p3", "experience": "Intermediario", "days": 4, "session_minutes": 75,
               "equipment": ["Academia completa"], "priorities": [], "assessment": {}}
    normal = build_all_sessions(profile, SPLIT_UPPER_LOWER, 4, 75, block_type="accumulation", recovery_data={"level": "NORMAL"})
    low = build_all_sessions(profile, SPLIT_UPPER_LOWER, 4, 75, block_type="accumulation", recovery_data={"level": "LOW"})
    normal_total = sum(e["sets"] for s in normal for e in s["exercises"])
    low_total = sum(e["sets"] for s in low for e in s["exercises"])
    assert low_total <= normal_total, f"Low recovery {low_total} > normal {normal_total}"

# ─── Full validation regression ────────────────────────────────────────

def test_all_profiles_no_errors():
    import asyncio
    async def _t():
        profiles = {
            "A":{"id":"a","experience":"Iniciante","days":3,"session_minutes":60,"priorities":[],"assessment":{},"equipment":["Academia completa"]},
            "B":{"id":"b","experience":"Intermediario","days":4,"session_minutes":75,"priorities":["Deltóide lateral","Dorsais / largura"],
                  "assessment":{"Deltóide lateral":{"development":"fraco","priority":"alta"}},"equipment":["Academia completa"]},
            "C":{"id":"c","experience":"Bodybuilder","days":5,"session_minutes":90,"priorities":["Deltóide lateral","Posteriores","Costas / espessura"],
                  "assessment":{"Deltóide lateral":{"development":"muito fraco","priority":"maxima"}},"equipment":["Academia completa"]},
            "E":{"id":"e","experience":"Intermediario","days":4,"session_minutes":60,"priorities":[],"assessment":{},
                  "equipment":["dumbbell","bench"],"avoid_exercises":["bb-bench-press","bb-squat"]},
        }
        for label, p in profiles.items():
            st = determine_split(p["days"], p["experience"])
            sessions = build_all_sessions(p, st, p["days"], p["session_minutes"])
            warnings = validate_sessions(sessions, p, st, p["days"], p["session_minutes"])
            errors = [w for w in warnings if "[ERROR]" in w]
            assert not errors, f"Profile {label}: {errors}"
            for s in sessions:
                assert len(s["exercises"]) >= 3, f"Profile {label} {s['label']} short"
                for e in s["exercises"]:
                    assert _equipment_ok(EXERCISE_INDEX[e["exercise_id"]], p), f"{e['exercise_id']} equip mismatch"
    asyncio.run(_t())

def test_arms_delts_still_fixed():
    profile = {"experience": "Intermediario", "session_minutes": 75, "equipment": ["Academia completa"],
               "priorities": [], "assessment": {}}
    exercises = select_exercises_for_day(UPPER_TARGETS, profile, 9, "MODERATE", 0)
    muscles = [e["primary_muscle"] for e in exercises]
    assert "biceps" in muscles or "triceps" in muscles
    assert "side_delts" in muscles

def test_avoid_exercises_still_work():
    profile = {"equipment": ["Academia completa"], "avoid_exercises": ["bb-squat"]}
    exercises = select_exercises_for_day(["quads"], profile, 2, "MODERATE")
    assert "bb-squat" not in [e["id"] for e in exercises]

def test_build_program_has_perio_fields():
    async def _t():
        p = {"id":"x","experience":"Intermediario","days":4,"session_minutes":75,"equipment":["Academia completa"],
             "priorities":[],"assessment":{}}
        r = await build_program_v2(p, None)
        assert "block_type" in r["logic"]
        assert "block_week" in r["logic"]
        assert "periodization" in r["logic"]
        assert r["logic"]["block_type"] == "accumulation"
    asyncio.run(_t())

def test_old_profiles_still_work_no_state_fields():
    """Profile without periodization key should default to accumulation."""
    async def _t():
        p = {"id":"old","experience":"Intermediario","days":4,"session_minutes":75,"equipment":["Academia completa"],
             "priorities":["Peitoral superior"],"assessment":{"Peitoral superior":{"development":"fraco","priority":"alta"}}}
        r = await build_program_v2(p, None)
        assert r["logic"]["block_type"] == "accumulation"
        assert r["sessions"]
    asyncio.run(_t())

def test_custom_program_preserved():
    async def _t():
        p = {"id":"cp","custom_program":{"name":"My","sessions":[{"day":1,"label":"C","exercises":[{"exercise_id":"incline-smith","sets":4}]}]}}
        r = await build_program_v2(p, None)
        assert r["logic"]["manual"] == True
    asyncio.run(_t())

def test_schema_fields_still_present():
    """All 8 frontend-required fields still exist."""
    profile = {"id":"s","experience":"Intermediario","days":4,"session_minutes":75,"equipment":["Academia completa"],
               "priorities":[],"assessment":{}}
    sessions = build_all_sessions(profile, SPLIT_UPPER_LOWER, 4, 75)
    for s in sessions:
        for e in s["exercises"]:
            for key in ("exercise_id","sets","reps","rir","rest","load","technique","technique_id"):
                assert key in e, f"Missing {key}"


def test_quality_gate_counts_indirect_work_without_inflating_direct_volume():
    sessions = [{"day": 1, "label": "Push", "exercises": [
        {"exercise_id": "bb-bench-press", "sets": 4},
    ]}]
    direct = count_weekly_sets_per_muscle(sessions)
    effective = count_effective_sets_per_muscle(sessions)
    assert direct["mid_chest"] == 4
    assert effective["mid_chest"] == 4
    assert any(v == 2 for k, v in effective.items() if k != "mid_chest")


def test_algorithmic_program_exposes_professional_quality_gate():
    profile = {"id": "quality", "experience": "Avançado", "days": 4,
               "session_minutes": 75, "equipment": ["Academia completa"],
               "priorities": ["Peitoral superior"], "assessment": {}}
    split = determine_split(profile["days"], profile["experience"])
    sessions = build_all_sessions(profile, split, 4, 75)
    report = build_program_quality_report(sessions, profile, split, 4, 75)
    assert 0 <= report["score"] <= 100
    assert report["authority"] == "FORGE deterministic training engine"
    assert report["method_profile"]["id"] == "specialization"
    assert report["weekly_effective_sets"]
    assert report["frequency"]


def test_training_memory_is_factual_and_does_not_invent_history():
    assert summarize_training_memory([])["signal"] == "insufficient_history"
    rows = [{"exercise_id": "bb-squat", "rir": 1, "weight": 100,
             "reps": 8, "created_at": "2026-08-30T10:00:00+00:00"}]
    memory = summarize_training_memory(rows)
    assert memory["logged_sets"] == 1
    assert memory["exercises"] == 1
    assert memory["average_rir"] == 1.0


def test_volume_factor_compares_each_exercise_only_with_itself():
    rows = []
    for i in range(6):
        rows.append({"exercise_id": "bb-squat", "weight": 100, "reps": 8,
                     "created_at": "2026-08-30T10:00:00+00:00"})
        rows.append({"exercise_id": "lateral-raise", "weight": 10, "reps": 15,
                     "created_at": "2026-08-20T10:00:00+00:00"})
    assert performance_volume_factor(rows) == 1.0

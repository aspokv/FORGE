"""Regression coverage for FORGE Training Engine V5."""
import engine
from training_engine_v4 import install as install_v4
from training_engine_v5 import install as install_v5

install_v4(engine)
install_v5(engine)


def profile(**extra):
    base = {
        "experience": "Avançado",
        "age": 25,
        "equipment": ["Academia completa"],
        "priorities": [],
        "avoid_exercises": [],
        "advanced_mode": True,
        "session_minutes": 60,
    }
    return {**base, **extra}


def build(split, days, **extra):
    return engine.build_all_sessions(
        profile(**extra), split, days, 60,
        recovery_data={"level": "NORMAL"},
    )


def assert_structured(sessions):
    assert sessions
    for session in sessions:
        assert len(session["exercises"]) >= 4
        assert session.get("archetype")
        ids = [item["exercise_id"] for item in session["exercises"]]
        assert len(ids) == len(set(ids))
        assert all(item.get("role") for item in session["exercises"])
        assert all(item.get("stimulus") for item in session["exercises"])
        assert all(item.get("technique_id") for item in session["exercises"])


def test_full_body_is_structured():
    assert_structured(build(engine.SPLIT_FULL_BODY, 3))


def test_upper_lower_is_structured():
    sessions = build(engine.SPLIT_UPPER_LOWER, 4)
    assert_structured(sessions)
    assert [s["archetype"] for s in sessions] == ["upper", "lower", "upper", "lower"]


def test_ppl_is_structured():
    sessions = build(engine.SPLIT_PUSH_PULL_LEGS, 6)
    assert_structured(sessions)
    assert [s["archetype"] for s in sessions[:3]] == ["push", "pull", "legs"]


def test_ul_ppl_is_structured():
    assert_structured(build(engine.SPLIT_UL_PPL, 5))


def test_upper_lower_ppl_is_structured():
    assert_structured(build(engine.SPLIT_UPPER_LOWER_PPL, 5))


def test_abc_is_structured():
    assert_structured(build(engine.SPLIT_ABC, 3))


def test_abcd_has_distinct_specialized_days():
    sessions = build(engine.SPLIT_ABCD, 4)
    assert_structured(sessions)
    assert [s["archetype"] for s in sessions] == [
        "chest_triceps", "back_biceps", "legs", "shoulders_arms"
    ]


def test_abcde_has_distinct_specialized_days():
    sessions = build(engine.SPLIT_ABCDE, 5)
    assert_structured(sessions)
    assert [s["archetype"] for s in sessions] == [
        "chest", "back", "legs", "shoulders", "arms"
    ]


def test_pull_finishes_back_before_direct_biceps():
    pull = build(engine.SPLIT_PUSH_PULL_LEGS, 3)[1]
    muscles = [engine.EXERCISE_INDEX[i["exercise_id"]]["primary_muscle"] for i in pull["exercises"]]
    back = [i for i, m in enumerate(muscles) if m in {"lats", "upper_back"}]
    biceps = [i for i, m in enumerate(muscles) if m == "biceps"]
    assert len(back) >= 3
    assert biceps
    assert min(biceps) > max(back)


def test_explicit_lower_body_priority_changes_order_without_sex_assumption():
    neutral = build(engine.SPLIT_UPPER_LOWER, 2, sex="Feminino")[1]
    prioritized = build(
        engine.SPLIT_UPPER_LOWER, 2,
        sex="Feminino", priorities=["Glúteos", "Posteriores"],
    )[1]
    neutral_first = engine.EXERCISE_INDEX[neutral["exercises"][0]["exercise_id"]]["primary_muscle"]
    prioritized_first = engine.EXERCISE_INDEX[prioritized["exercises"][0]["exercise_id"]]["primary_muscle"]
    assert prioritized_first in {"glutes", "hamstrings"}
    assert neutral_first != prioritized_first or neutral_first == "quads"


def test_advanced_techniques_are_real_engine_output():
    sessions = build(
        engine.SPLIT_ABCD, 4,
        priorities=["Deltóide lateral", "Bíceps"],
    )
    technique_ids = {
        item["technique_id"]
        for session in sessions
        for item in session["exercises"]
    }
    assert technique_ids - {"straight"}
    assert technique_ids <= {
        "straight", "top-set-backoff", "superset", "drop-set",
        "mechanical-drop-set", "rest-pause", "myo-reps", "cluster",
        "lengthened-partials",
    }


def test_low_recovery_disables_advanced_techniques():
    sessions = engine.build_all_sessions(
        profile(priorities=["Bíceps"]),
        engine.SPLIT_PUSH_PULL_LEGS, 3, 60,
        recovery_data={"level": "LOW"},
    )
    assert all(
        item["technique_id"] == "straight"
        for session in sessions for item in session["exercises"]
    )


def test_minor_profile_never_gets_intensification_automatically():
    sessions = engine.build_all_sessions(
        profile(age=16, priorities=["Bíceps"]),
        engine.SPLIT_ABCD, 4, 60,
        recovery_data={"level": "NORMAL"},
    )
    assert all(
        item["technique_id"] == "straight"
        for session in sessions for item in session["exercises"]
    )

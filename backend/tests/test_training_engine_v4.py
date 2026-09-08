"""Regression tests for FORGE structural workout programming."""
import engine
from training_engine_v4 import install


install(engine)


def _profile():
    return {
        "experience": "Avançado",
        "equipment": ["Academia completa"],
        "priorities": [],
        "avoid_exercises": [],
    }


def test_pull_uses_real_session_capacity_and_finishes_back_before_biceps():
    exercises = engine.select_exercises_for_day(
        engine.PULL_TARGETS,
        _profile(),
        count=6,
        demand="MODERATE",
        day_index=1,
    )

    assert len(exercises) >= 5
    assert len({exercise["id"] for exercise in exercises}) == len(exercises)

    back_positions = [
        index for index, exercise in enumerate(exercises)
        if exercise["primary_muscle"] in {"lats", "upper_back"}
    ]
    biceps_positions = [
        index for index, exercise in enumerate(exercises)
        if exercise["primary_muscle"] == "biceps"
    ]

    assert len(back_positions) >= 3
    assert biceps_positions
    assert min(biceps_positions) > max(back_positions)


def test_low_recovery_changes_dose_not_exercise_count():
    normal = engine.build_all_sessions(
        _profile(), engine.SPLIT_PUSH_PULL_LEGS, 3, 60,
        recovery_data={"level": "NORMAL"},
    )
    low = engine.build_all_sessions(
        _profile(), engine.SPLIT_PUSH_PULL_LEGS, 3, 60,
        recovery_data={"level": "LOW"},
    )

    assert [len(session["exercises"]) for session in normal] == [
        len(session["exercises"]) for session in low
    ]
    assert all(len(session["exercises"]) >= 5 for session in low)


def test_pull_validator_rejects_direct_biceps_before_unfinished_back_work():
    # PPL identifies the session by its position in the complete cycle, not its label.
    # A single entry at index zero is Push, even if its label says Pull.
    sessions = engine.build_all_sessions(
        _profile(), engine.SPLIT_PUSH_PULL_LEGS, 3, 60
    )
    sessions[1] = {
        "day": 2,
        "label": "Pull",
        "demand": "MODERATE",
        "focus": [],
        "exercises": [
            {"exercise_id": "row", "sets": 3},
            {"exercise_id": "bb-curl", "sets": 3},
            {"exercise_id": "lat-pulldown", "sets": 3},
            {"exercise_id": "cable-row", "sets": 3},
            {"exercise_id": "machine-rear-fly", "sets": 2},
        ],
    }

    warnings = engine.validate_sessions(
        sessions, _profile(), engine.SPLIT_PUSH_PULL_LEGS, 3, 60
    )

    assert any("biceps work appears before primary back work" in warning for warning in warnings)

    exercises = sessions[1]["exercises"]
    exercises.append(exercises.pop(1))
    corrected = engine.validate_sessions(
        sessions, _profile(), engine.SPLIT_PUSH_PULL_LEGS, 3, 60
    )
    assert not any("biceps work appears before primary back work" in warning for warning in corrected)

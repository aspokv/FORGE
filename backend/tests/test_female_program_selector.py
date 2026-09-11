"""Unit tests for deterministic female library selection."""
from female_program_selector import (
    FEMALE_AUTO_TEMPLATE_IDS,
    build_female_library_program,
    is_female_profile,
)


def test_is_female_profile_accepts_existing_variants():
    for value in ("Feminino", "female", " F ", "mulher"):
        assert is_female_profile({"sex": value})


def test_non_female_profile_is_not_auto_selected():
    assert build_female_library_program({"sex": "Masculino", "days": 3}) is None
    assert build_female_library_program({"days": 3}) is None


def test_library_snapshot_is_deterministic_and_moderate():
    profile = {
        "sex": "feminino",
        "days": 4,
        "training_method": "resistencia",
        "priorities": ["Posteriores"],
    }
    first = build_female_library_program(profile)
    second = build_female_library_program(profile)

    assert first == second
    assert first["source"] == "female_library_auto"
    assert len(first["sessions"]) == 4
    assert first["sessions"][0]["template_id"] == "full-body-female-athlete"
    assert all(item["template_id"] in FEMALE_AUTO_TEMPLATE_IDS for item in first["sessions"])
    assert all(item["demand"] == "MODERATE" for item in first["sessions"])
    assert "Resistência" in first["focus"]
    assert "Corpo inteiro" in first["focus"]


def test_invalid_days_fall_back_to_three_sessions():
    program = build_female_library_program({"sex": "F", "days": "not-a-number"})
    assert len(program["sessions"]) == 3

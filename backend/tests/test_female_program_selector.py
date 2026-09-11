"""Unit tests for exact female library-program selection."""
from copy import deepcopy

from female_program_selector import (
    FEMALE_LIBRARY_AUTO_SOURCES,
    FEMALE_LIBRARY_PROGRAM_IDS,
    build_female_library_program,
    is_female_library_source,
    is_female_profile,
)
from training_programs import TRAINING_PROGRAMS


def _female_catalog():
    return {
        item["id"]: item
        for item in TRAINING_PROGRAMS
        if item.get("audience_type") == "female"
    }


def test_is_female_profile_accepts_existing_variants():
    for value in ("Feminino", "female", " F ", "mulher"):
        assert is_female_profile({"sex": value})


def test_non_female_profile_is_not_auto_selected():
    assert build_female_library_program({"sex": "Masculino", "days": 3}) is None
    assert build_female_library_program({"days": 3}) is None


def test_selection_uses_only_complete_female_catalog_programs():
    catalog = _female_catalog()
    assert set(FEMALE_LIBRARY_PROGRAM_IDS) == set(catalog)
    for value in ("Recreativo", "Intermediário", "Avançado"):
        selected = build_female_library_program({
            "sex": "feminino",
            "experience": value,
            "days": 3,
            "goal": "resistência",
        })
        assert selected["source"] in FEMALE_LIBRARY_AUTO_SOURCES
        assert selected["program_id"] in catalog
        assert selected["program_id"] in FEMALE_LIBRARY_PROGRAM_IDS
        assert selected["sessions"]


def test_snapshot_preserves_the_selected_phase_without_new_sessions():
    catalog = _female_catalog()
    selected = build_female_library_program({
        "sex": "F",
        "experience": "Avançado",
        "days": 6,
        "goal": "Ganhar massa muscular",
        "priorities": ["Glúteos"],
    })
    source_phase = next(
        phase for phase in catalog[selected["program_id"]]["phases"]
        if phase.get("sessions")
    )
    expected = []
    for day, workout in enumerate(source_phase["sessions"], start=1):
        item = deepcopy(workout)
        item["day"] = day
        expected.append(item)
    assert selected["phase_id"] == source_phase["id"]
    assert selected["sessions"] == expected
    assert selected["selection_method"] == "female_library_catalog"
    assert "nenhuma sessão" in selected["selection_reason"].lower()


def test_explicit_library_reference_wins_without_synthesizing_content():
    selected = build_female_library_program({
        "sex": "feminino",
        "days": 5,
        "training_method": "Shape de Cavala",
    })
    assert selected["program_id"] == "female-shape-de-cavala"
    assert all("template_id" not in workout for workout in selected["sessions"])


def test_legacy_template_source_is_detected_for_migration():
    assert is_female_library_source("female_library_auto")
    assert is_female_library_source("female_library_program_auto")
    assert not is_female_library_source("manual")

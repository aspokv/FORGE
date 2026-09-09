from copy import deepcopy
import json
from pathlib import Path

import training_programs
from custom_training_programs import install


def _installed_catalog():
    old_categories = deepcopy(training_programs.PROGRAM_CATEGORIES)
    old_programs = deepcopy(training_programs.TRAINING_PROGRAMS)
    try:
        install(training_programs)
        install(training_programs)
        return deepcopy(training_programs.PROGRAM_CATEGORIES), deepcopy(training_programs.TRAINING_PROGRAMS)
    finally:
        training_programs.PROGRAM_CATEGORIES[:] = old_categories
        training_programs.TRAINING_PROGRAMS[:] = old_programs


def test_custom_category_and_program_are_installed_once():
    categories, programs = _installed_catalog()
    assert sum(item["id"] == "custom" for item in categories) == 1
    assert sum(item["id"] == "custom-upper-full-body-hybrid-6x" for item in programs) == 1


def test_custom_upper_full_body_preserves_submitted_week_structure():
    _, programs = _installed_catalog()
    plan = next(item for item in programs if item["id"] == "custom-upper-full-body-hybrid-6x")
    workout_phase = plan["phases"][0]

    assert plan["category"] == "custom"
    assert plan["name"] == "Upper + Full Body Híbrido"
    assert workout_phase["weeks"] == "4–6 semanas"
    assert "Qui descanso" in workout_phase["note"]
    assert [item["label"] for item in workout_phase["sessions"]] == [
        "Segunda · Upper A",
        "Terça · Full Body A",
        "Quarta · Upper B",
        "Sexta · Upper C",
        "Sábado · Full Body B",
        "Domingo · Upper D",
    ]

    monday = workout_phase["sessions"][0]["exercises"]
    assert [(item["exercise_id"], item["sets"], item["reps"]) for item in monday[:4]] == [
        ("incline-smith", 3, "5–8"),
        ("machine-chest-press", 3, "6–10"),
        ("row", 3, "6–10"),
        ("cable-pulldown", 3, "8–12"),
    ]


def test_custom_program_only_uses_known_exercise_ids():
    _, programs = _installed_catalog()
    plan = next(item for item in programs if item["id"] == "custom-upper-full-body-hybrid-6x")
    exercise_file = Path(__file__).resolve().parents[1] / "exercises.json"
    known = {item["id"] for item in json.loads(exercise_file.read_text(encoding="utf-8"))}
    used = {
        exercise["exercise_id"]
        for workout_phase in plan["phases"]
        for workout in workout_phase["sessions"]
        for exercise in workout["exercises"]
    }
    assert used <= known

import json
from pathlib import Path

from workout_templates import CATEGORIES, WORKOUT_TEMPLATES, public_catalog


EXERCISE_IDS = {
    item["id"]
    for item in json.loads((Path(__file__).parents[1] / "exercises.json").read_text(encoding="utf-8"))
}


def test_library_has_three_professional_variants_per_category():
    assert [item["id"] for item in CATEGORIES] == ["push", "pull", "legs", "upper", "lower", "full_body"]
    for category in CATEGORIES:
        variants = [item for item in WORKOUT_TEMPLATES if item["category"] == category["id"]]
        assert len(variants) == 3


def test_every_template_uses_real_catalog_exercises_and_complete_prescriptions():
    template_ids = set()
    for template in WORKOUT_TEMPLATES:
        assert template["id"] not in template_ids
        template_ids.add(template["id"])
        assert 4 <= len(template["exercises"]) <= 8
        assert template["duration"] >= 40
        exercise_ids = [item["exercise_id"] for item in template["exercises"]]
        assert len(exercise_ids) == len(set(exercise_ids))
        assert set(exercise_ids) <= EXERCISE_IDS
        for exercise in template["exercises"]:
            assert 1 <= exercise["sets"] <= 8
            assert exercise["reps"]
            assert exercise["rir"]
            assert exercise["rest"]


def test_public_catalog_calculates_counts_without_mutating_source():
    catalog = public_catalog()
    assert len(catalog["templates"]) == 18
    first = catalog["templates"][0]
    assert first["exercise_count"] == len(first["exercises"])
    assert first["total_sets"] == sum(item["sets"] for item in first["exercises"])
    first["exercises"].clear()
    assert WORKOUT_TEMPLATES[0]["exercises"]


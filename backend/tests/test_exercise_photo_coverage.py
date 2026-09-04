"""Every exercise used by shipped plans must have an exact photo identity."""
import json
from pathlib import Path
from workout_templates import public_catalog

ROOT = Path(__file__).resolve().parents[2]


def test_all_catalog_and_plan_exercises_have_photos():
    catalog = json.loads((ROOT / 'backend/exercises.json').read_text(encoding='utf-8'))
    photos = json.loads((ROOT / 'frontend/src/features/exercisePhotoCatalog.json').read_text(encoding='utf-8'))
    ids = {item['id'] for item in catalog}
    photo_ids = {item['id'] for item in photos}
    assert ids == photo_ids
    assert len(photo_ids) == len(photos)

    def inspect(value):
        if isinstance(value, dict):
            if 'exercise_id' in value:
                assert value['exercise_id'] in photo_ids, value['exercise_id']
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    inspect(public_catalog())
    for item in photos:
        file = ROOT / 'frontend/public' / item['src'].lstrip('/')
        assert file.is_file(), item['id']

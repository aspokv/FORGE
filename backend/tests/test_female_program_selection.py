"""Female assessments receive a complete program from the female library."""
import asyncio
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import engine
from training_programs import TRAINING_PROGRAMS


FEMALE_LIBRARY_IDS = {
    item["id"] for item in TRAINING_PROGRAMS
    if item.get("audience_type") == "female"
}


@pytest.mark.parametrize("sex", ["Feminino", "female", " F ", "mulher"])
@pytest.mark.parametrize("level", ["Recreativo", "Intermediário", "Avançado"])
def test_female_profile_gets_complete_library_program(sex, level):
    profile = {
        "sex": sex,
        "experience": level,
        "days": 6,
        "split_preference": "ppl",
        "onboarding_required": False,
    }
    result = asyncio.run(engine.build_program_v2(profile))

    assert not result.get("program_selection_required")
    assert result["program_source"] == "female_library_program"
    assert result["library_program_id"] in FEMALE_LIBRARY_IDS
    assert result["library_phase_id"]
    assert result["sessions"]
    assert result["logic"]["manual"] is False
    assert all(item["template_id"] is None for item in result["sessions"])


def test_resistance_focus_uses_one_existing_female_program():
    profile = {
        "sex": "feminino",
        "days": 5,
        "training_method": "resistência",
        "priorities": ["Quadríceps"],
        "onboarding_required": False,
    }
    result = asyncio.run(engine.build_program_v2(profile))

    assert result["program_source"] == "female_library_program"
    assert result["library_program_id"] in FEMALE_LIBRARY_IDS
    assert result["sessions"]
    assert result["logic"]["split"] == result["name"]
    assert "Resistência" not in result["focus"]


def test_saved_custom_program_survives_refresh_for_female_profile():
    profile = {
        "sex": "Feminino",
        "custom_program": {
            "name": "Programa escolhido",
            "sessions": [
                {"day": 1, "label": "Sessão revisada", "focus": ["Glúteos"], "exercises": []}
            ],
        },
    }
    result = asyncio.run(engine.build_program_v2(profile))

    assert not result.get("program_selection_required")
    assert result["name"] == "Programa escolhido"
    assert result["sessions"][0]["label"] == "Sessão revisada"
    assert result["program_source"] == "custom"


def test_legacy_automatic_snapshot_is_migrated_to_catalog():
    profile = {
        "sex": "Feminino",
        "custom_program": {
            "source": "female_library_auto",
            "sessions": [{"day": 1, "label": "Full Body criado", "exercises": []}],
        },
    }
    result = asyncio.run(engine.build_program_v2(profile))
    assert result["program_source"] == "female_library_program"
    assert result["library_program_id"] in FEMALE_LIBRARY_IDS
    assert result["sessions"][0]["label"] != "Full Body criado"


def test_male_and_unspecified_profiles_keep_generation():
    for sex in ("Masculino", None):
        result = asyncio.run(engine.build_program_v2({
            "sex": sex,
            "days": 3,
            "experience": "Intermediário",
            "onboarding_required": False,
        }))
        assert not result.get("program_selection_required")
        assert result["sessions"]


def test_reassessment_persists_catalog_female_program_and_preserves_guards():
    source = ast.parse((Path(__file__).parents[1] / "server.py").read_text())
    node = next(
        item for item in source.body
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "save_assessment"
    )
    node.decorator_list = []
    ns = {
        "DeepAssessment": object,
        "Depends": lambda value: None,
        "get_current_user": lambda: None,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), "server.py", "exec"), ns)

    previous = {
        "sex": "Masculino",
        "assessment": {"Bíceps": {"development": "forte"}},
        "last_workout_operation": "old-op",
        "last_workout_completion_day": "2026-09-11",
    }
    profiles = SimpleNamespace(
        find_one=AsyncMock(return_value=previous),
        replace_one=AsyncMock(),
    )
    library_program = {
        "source": "female_library_program_auto",
        "program_id": "abcd-wellness-advanced",
        "phase_id": "base",
        "sessions": [{"day": 1, "label": "A · Quadríceps", "exercises": []}],
    }
    ns.update(
        db=SimpleNamespace(
            profiles=profiles,
            assessments=SimpleNamespace(insert_one=AsyncMock()),
        ),
        BODY_GOALS=(),
        _intensity_key=lambda _: None,
        _is_fat_loss_goal=lambda _: False,
        is_female_profile=lambda profile: str(profile.get("sex") or "").strip().casefold()
        in {"feminino", "female", "f", "mulher"},
        is_female_library_source=lambda source: source in {
            "female_library_auto", "female_library_program_auto"
        },
        build_female_library_program=lambda _: library_program,
        build_program=AsyncMock(return_value={"program_source": "female_library_program"}),
    )

    assessment = SimpleNamespace(
        model_dump=lambda: {"sex": "Feminino", "assessment": {}},
        created_at="now",
    )
    result = asyncio.run(ns["save_assessment"](assessment, {"id": "athlete", "role": "ATHLETE"}))
    saved = profiles.replace_one.call_args.args[1]

    assert saved["custom_program"]["source"] == "female_library_program_auto"
    assert saved["custom_program"]["program_id"] == "abcd-wellness-advanced"
    assert saved["last_workout_operation"] == "old-op"
    assert saved["last_workout_completion_day"] == "2026-09-11"
    assert saved["assessment"] == {}
    assert result["program"]["program_source"] == "female_library_program"

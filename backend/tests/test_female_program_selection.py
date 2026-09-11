"""Female assessments receive a curated library sequence without a generic PPL fallback."""
import asyncio
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import engine


FEMALE_AUTO_TEMPLATE_IDS = {
    "full-body-female-athlete",
    "push-female-performance",
    "pull-female-posture",
}


@pytest.mark.parametrize("sex", ["Feminino", "female", " F ", "mulher"])
@pytest.mark.parametrize("level", ["Recreativo", "Intermediário", "Avançado"])
def test_female_profile_gets_curated_library_program(sex, level):
    profile = {
        "sex": sex,
        "experience": level,
        "days": 6,
        "split_preference": "ppl",
        "onboarding_required": False,
    }
    result = asyncio.run(engine.build_program_v2(profile))

    assert not result.get("program_selection_required")
    assert result["program_source"] == "female_library_auto"
    assert result["sessions"]
    assert result["sessions"][0]["template_id"] == "full-body-female-athlete"
    assert all(item["template_id"] in FEMALE_AUTO_TEMPLATE_IDS for item in result["sessions"])
    assert all(item["demand"] == "MODERATE" for item in result["sessions"])
    assert result["logic"]["manual"] is False


def test_resistance_focus_keeps_lower_body_coverage_and_uses_moderate_sessions():
    profile = {
        "sex": "feminino",
        "days": 5,
        "training_method": "resistência",
        "priorities": ["Quadríceps"],
        "onboarding_required": False,
    }
    result = asyncio.run(engine.build_program_v2(profile))

    ids = [item["template_id"] for item in result["sessions"]]
    assert ids == [
        "full-body-female-athlete",
        "push-female-performance",
        "full-body-female-athlete",
        "pull-female-posture",
    ]
    assert result["week"].startswith("4 sessões")
    assert "Resistência" in result["focus"]
    assert "Corpo inteiro" in result["focus"]
    assert all(item["demand"] == "MODERATE" for item in result["sessions"])


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


def test_reassessment_persists_auto_female_program_and_preserves_guards():
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
    auto_program = {
        "source": "female_library_auto",
        "sessions": [{"day": 1, "label": "Corpo inteiro", "exercises": []}],
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
        build_female_library_program=lambda _: auto_program,
        build_program=AsyncMock(return_value={"program_source": "female_library_auto"}),
    )

    assessment = SimpleNamespace(
        model_dump=lambda: {"sex": "Feminino", "assessment": {}},
        created_at="now",
    )
    result = asyncio.run(ns["save_assessment"](assessment, {"id": "athlete", "role": "ATHLETE"}))
    saved = profiles.replace_one.call_args.args[1]

    assert saved["custom_program"]["source"] == "female_library_auto"
    assert saved["last_workout_operation"] == "old-op"
    assert saved["last_workout_completion_day"] == "2026-09-11"
    assert saved["assessment"] == {}
    assert result["program"]["program_source"] == "female_library_auto"

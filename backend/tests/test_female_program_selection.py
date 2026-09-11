"""Female onboarding routes to authored programs without prescribing expert plans."""
import asyncio
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
import engine

@pytest.mark.parametrize("sex", ["Feminino", "female", " F ", "mulher"])
@pytest.mark.parametrize("level", ["Recreativo", "Intermediário", "Avançado"])
def test_female_profile_chooses_catalog_instead_of_silent_ppl(sex,level):
    p={"sex":sex,"experience":level,"days":6,"split_preference":"ppl","onboarding_required":False}
    result=asyncio.run(engine.build_program_v2(p))
    assert result["program_selection_required"] is True
    assert result["selection_audience"] == "female"
    assert result["sessions"] == []
    assert result["active_day"] is None

def test_saved_custom_program_survives_refresh_for_female_profile():
    p={"sex":"Feminino","custom_program":{"name":"Programa escolhido","sessions":[
        {"day":1,"label":"Sessão revisada","focus":["Glúteos"],"exercises":[]}
    ]}}
    result=asyncio.run(engine.build_program_v2(p))
    assert not result.get("program_selection_required")
    assert result["name"] == "Programa escolhido"
    assert result["sessions"][0]["label"] == "Sessão revisada"

def test_male_and_unspecified_profiles_keep_generation():
    for sex in ("Masculino",None):
        result=asyncio.run(engine.build_program_v2({"sex":sex,"days":3,"experience":"Intermediário","onboarding_required":False}))
        assert not result.get("program_selection_required")
        assert result["sessions"]

def test_reassessment_preserves_completion_guards_and_does_not_copy_other_profile_assessment():
    source=ast.parse((Path(__file__).parents[1]/"server.py").read_text())
    node=next(n for n in source.body if isinstance(n,ast.AsyncFunctionDef) and n.name=="save_assessment")
    node.decorator_list=[]
    ns={"DeepAssessment":object,"Depends":lambda x:None,"get_current_user":lambda:None}
    exec(compile(ast.Module(body=[node],type_ignores=[]),"server.py","exec"),ns)
    previous={"sex":"Masculino","assessment":{"Bíceps":{"development":"forte"}},"last_workout_operation":"old-op","last_workout_completion_day":"2026-09-11"}
    profiles=SimpleNamespace(find_one=AsyncMock(return_value=previous),replace_one=AsyncMock())
    ns.update(db=SimpleNamespace(profiles=profiles,assessments=SimpleNamespace(insert_one=AsyncMock())),
        BODY_GOALS=(),_intensity_key=lambda _:None,_is_fat_loss_goal=lambda _:False,
        build_program=AsyncMock(return_value={"program_selection_required":True}))
    assessment=SimpleNamespace(model_dump=lambda:{"sex":"Feminino","assessment":{}},created_at="now")
    result=asyncio.run(ns["save_assessment"](assessment,{"id":"athlete","role":"ATHLETE"}))
    saved=profiles.replace_one.call_args.args[1]
    assert saved["last_workout_operation"]=="old-op"
    assert saved["last_workout_completion_day"]=="2026-09-11"
    assert saved["assessment"]=={}
    assert result["program"]["program_selection_required"] is True

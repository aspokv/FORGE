"""FORGE — periodização calórica semanal.

O que estes testes defendem, em ordem de importância: proteína não cai, gordura não fura
o piso de segurança, e uma meta impossível é declarada impossível em vez de "resolvida"
cortando o que não devia.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import FORGE_COACH_METHODOLOGY  # noqa: E402
from nutrition_periodization import (  # noqa: E402
    KCAL_CARB, KCAL_FAT, KCAL_PROTEIN, MIN_WEEKLY_KCAL, build_periodization,
    fat_floor_g, resolve_target_kcal, sanitize_edited_table,
)

BASE = {"kcal": 2800, "protein_g": 180, "fat_g": 78, "carbs_g": 330}
PESO = 80.0


def periodizar(**kwargs):
    args = {"base": BASE, "weight_kg": PESO, "weeks": 6, "target_kcal": 2200,
            "goal": "fat_loss"}
    args.update(kwargs)
    return build_periodization(**args)


# --- piso de gordura ------------------------------------------------------------------

def test_fat_floor_comes_from_the_app_methodology_not_a_second_rule():
    esperado = PESO * FORGE_COACH_METHODOLOGY["fat_range_g_per_kg"]["fat_loss"][0]
    assert fat_floor_g(PESO, "fat_loss") == round(esperado, 1)
    assert fat_floor_g(80, "fat_loss") == 64.0   # 0,8 g/kg


def test_fat_never_goes_below_the_floor_in_any_week():
    p = periodizar(target_kcal=1800, weeks=8)
    piso = p["fat_floor_g"]
    assert all(w["fat_g"] >= piso for w in p["table"])


def test_when_fat_hits_the_floor_the_difference_goes_to_carbs():
    p = periodizar(target_kcal=2200, weeks=6)
    travadas = [w for w in p["table"] if w["fat_floor_applied"] and w["feasible"]]
    assert travadas, "esperava pelo menos uma semana com o piso aplicado"
    for w in travadas:
        assert w["fat_g"] == p["fat_floor_g"]
        # a kcal da semana continua fechando com os macros informados
        total = w["protein_g"] * KCAL_PROTEIN + w["carbs_g"] * KCAL_CARB + w["fat_g"] * KCAL_FAT
        assert total == pytest.approx(w["kcal"], abs=2)


# --- proteína fixa --------------------------------------------------------------------

def test_protein_is_identical_in_every_week():
    for p in [periodizar(), periodizar(pct=-20, target_kcal=None),
              periodizar(target_kcal=3400, goal="muscle_gain")]:
        assert {w["protein_g"] for w in p["table"]} == {round(BASE["protein_g"], 1)}


# --- progressão -----------------------------------------------------------------------

def test_progression_is_linear_and_lands_exactly_on_the_target():
    p = periodizar(target_kcal=2200, weeks=6)
    kcals = [w["kcal"] for w in p["table"]]
    assert kcals[-1] == 2200
    passos = {round(kcals[i] - kcals[i + 1]) for i in range(len(kcals) - 1)}
    assert len(passos) == 1, f"degraus desiguais: {kcals}"


def test_deficit_and_surplus_directions():
    assert periodizar(target_kcal=2200)["direction"] == "deficit"
    assert periodizar(target_kcal=3200, goal="muscle_gain")["direction"] == "surplus"


def test_percentage_target_is_equivalent_to_the_absolute_one():
    por_pct = periodizar(target_kcal=None, pct=-20)
    assert por_pct["target_kcal"] == round(BASE["kcal"] * 0.8)
    assert por_pct["table"][-1]["kcal"] == round(BASE["kcal"] * 0.8)


def test_surplus_keeps_protein_and_raises_carbs():
    p = periodizar(target_kcal=3200, weeks=4, goal="muscle_gain")
    assert p["table"][-1]["carbs_g"] > BASE["carbs_g"]
    assert p["table"][-1]["protein_g"] == BASE["protein_g"]


# --- metas impossíveis ----------------------------------------------------------------

def test_impossible_week_is_declared_not_silently_solved():
    p = periodizar(target_kcal=1000, weeks=3)
    assert p["infeasible_weeks"], "meta impossivel deveria ser sinalizada"
    inviavel = [w for w in p["table"] if not w["feasible"]][0]
    assert inviavel["fat_g"] == p["fat_floor_g"]      # nao furou o piso
    assert inviavel["protein_g"] == BASE["protein_g"]  # nao cortou proteina
    assert "minimo seguro" in inviavel["warnings"][0]


def test_carbs_never_go_negative():
    p = periodizar(target_kcal=1400, weeks=2)
    assert all(w["carbs_g"] >= 0 for w in p["table"])


@pytest.mark.parametrize("weeks", [0, -3, 53])
def test_invalid_duration_is_rejected(weeks):
    with pytest.raises(ValueError):
        periodizar(weeks=weeks)


def test_target_below_the_hard_minimum_is_rejected():
    with pytest.raises(ValueError):
        periodizar(target_kcal=MIN_WEEKLY_KCAL - 1)


def test_missing_target_and_pct_is_rejected():
    with pytest.raises(ValueError):
        resolve_target_kcal(2800, None, None)


def test_base_without_protein_is_rejected():
    with pytest.raises(ValueError):
        build_periodization({"kcal": 2000, "protein_g": 0}, PESO, 4, target_kcal=1800)


# --- edição manual --------------------------------------------------------------------

def test_manual_edit_recomputes_kcal_from_the_macros():
    tabela = sanitize_edited_table(
        [{"protein_g": 180, "carbs_g": 200, "fat_g": 70, "kcal": 99999}], PESO)
    esperado = 180 * KCAL_PROTEIN + 200 * KCAL_CARB + 70 * KCAL_FAT
    assert tabela[0]["kcal"] == esperado  # a kcal enviada pelo cliente é ignorada


def test_manual_edit_cannot_break_the_fat_floor():
    tabela = sanitize_edited_table(
        [{"protein_g": 180, "carbs_g": 300, "fat_g": 20}], PESO, "fat_loss")
    assert tabela[0]["fat_g"] == fat_floor_g(PESO, "fat_loss")
    assert tabela[0]["fat_floor_applied"] is True


def test_manual_edit_flags_a_week_below_the_minimum():
    tabela = sanitize_edited_table([{"protein_g": 40, "carbs_g": 10, "fat_g": 10}], PESO)
    assert tabela[0]["feasible"] is False


def test_manual_edit_rejects_negative_macros():
    tabela = sanitize_edited_table([{"protein_g": -50, "carbs_g": -10, "fat_g": 70}], PESO)
    assert tabela[0]["protein_g"] == 0 and tabela[0]["carbs_g"] == 0

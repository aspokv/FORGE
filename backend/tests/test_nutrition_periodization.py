"""FORGE — o piso de gordura que o Conselho respeita ao aplicar um ajuste.

A tabela de periodizacao antiga saiu (ver `nutrition_periodization.py`); o piso ficou,
e e ele que impede um ajuste automatico de levar a gordura abaixo do seguro.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import FORGE_COACH_METHODOLOGY  # noqa: E402
from nutrition_periodization import KCAL_CARB, KCAL_FAT, KCAL_PROTEIN, fat_floor_g  # noqa: E402

PESO = 80.0


def test_fat_floor_comes_from_the_app_methodology_not_a_second_rule():
    esperado = PESO * FORGE_COACH_METHODOLOGY["fat_range_g_per_kg"]["fat_loss"][0]
    assert fat_floor_g(PESO, "fat_loss") == round(esperado, 1)
    assert fat_floor_g(80, "fat_loss") == 64.0   # 0,8 g/kg


def test_unknown_goal_falls_back_to_maintenance():
    assert fat_floor_g(PESO, "objetivo-que-nao-existe") == fat_floor_g(PESO, "maintenance")


def test_calories_per_gram():
    assert (KCAL_PROTEIN, KCAL_CARB, KCAL_FAT) == (4, 4, 9)

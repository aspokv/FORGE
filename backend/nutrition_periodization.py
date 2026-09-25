"""FORGE — piso de gordura e calorias por grama, usados pelo Conselho.

Este arquivo ja foi a "periodizacao calorica semanal": uma tabela linear do plano base
ate uma meta, que a tela gravava e nenhuma parte do aplicativo lia depois. Foi substituida
pela periodizacao automatica (`periodizacao_automatica.py`), que aplica cada semana na
meta e no prato. Ficou aqui o que continua em uso: o piso de gordura e as calorias por
grama, que o Conselho usa ao aplicar um ajuste.
"""
from nutrition_engine import FORGE_COACH_METHODOLOGY

KCAL_PROTEIN = 4
KCAL_CARB = 4
KCAL_FAT = 9


def fat_floor_g(weight_kg: float, goal: str = "fat_loss") -> float:
    """Piso de gordura em gramas/dia. Vem da metodologia do proprio FORGE, para nao
    existirem duas regras diferentes de gordura minima no mesmo app."""
    faixa = FORGE_COACH_METHODOLOGY["fat_range_g_per_kg"].get(
        goal, FORGE_COACH_METHODOLOGY["fat_range_g_per_kg"]["maintenance"])
    return round(float(weight_kg) * float(faixa[0]), 1)

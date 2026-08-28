"""Ritmos de ganho de massa: controlado / moderado / agressivo.

Mesma estrutura das intensidades de emagrecimento, e deliberadamente o MESMO motor: o
carboidrato continua sendo o macro residual e as regras de proteina/gordura sao as que
ja existiam. Nenhum segundo motor de calculo foi criado.

Testes puros: nao precisam de banco nem de servidor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from nutrition_engine import (
    FORGE_COACH_METHODOLOGY, compute_macro_targets, default_intensity_for,
    resolve_intensity_protocol,
)

W, H, AGE, DAYS = 85, 178, 30, 4


def alvos(intensity, goal="muscle_gain", w=W, sex="male"):
    return compute_macro_targets(w, H, AGE, sex, DAYS, goal, "moderate", intensity)


def superavit_pct(t):
    return (t["goal_calories"] / t["tdee"] - 1) * 100


# --- faixas pedidas -----------------------------------------------------------------

def test_controlado_fica_entre_5_e_8_por_cento():
    assert 5 <= superavit_pct(alvos("controlado")) <= 8


def test_moderado_fica_entre_10_e_15_por_cento():
    assert 10 <= superavit_pct(alvos("moderado")) <= 15


def test_agressivo_fica_entre_15_e_20_por_cento():
    assert 15 <= superavit_pct(alvos("agressivo")) <= 20


@pytest.mark.parametrize("w,sex", [(52, "female"), (60, "female"), (85, "male"), (110, "male")])
def test_as_faixas_valem_para_qualquer_perfil(w, sex):
    assert 5 <= superavit_pct(alvos("controlado", w=w, sex=sex)) <= 8
    assert 10 <= superavit_pct(alvos("moderado", w=w, sex=sex)) <= 15
    assert 15 <= superavit_pct(alvos("agressivo", w=w, sex=sex)) <= 20


def test_caloria_cresce_do_controlado_ao_agressivo():
    c, m, a = (alvos(i)["goal_calories"] for i in ("controlado", "moderado", "agressivo"))
    assert c < m < a


def test_mais_energia_significa_mais_carboidrato():
    c, a = alvos("controlado"), alvos("agressivo")
    assert a["carbs_g"] > c["carbs_g"]


def test_proteina_sobe_de_forma_coerente_sem_salto_arbitrario():
    p = [alvos(i)["protein_g"] for i in ("controlado", "moderado", "agressivo")]
    assert p[0] < p[1] < p[2]
    # nenhum degrau maior que 0,3 g/kg entre ritmos vizinhos
    assert all((b - a) / W <= 0.3 for a, b in zip(p, p[1:]))


def test_macros_fecham_a_caloria():
    for i in ("controlado", "moderado", "agressivo"):
        t = alvos(i)
        soma = t["protein_g"] * 4 + t["carbs_g"] * 4 + t["fat_g"] * 9
        assert abs(soma - t["goal_calories"]) <= 5


def test_ganho_nao_tem_teto_de_carboidrato():
    for i in ("controlado", "moderado", "agressivo"):
        assert alvos(i)["carb_ceiling_g"] is None


# --- padroes e selecao consciente ---------------------------------------------------

def test_controlado_e_o_recomendado_e_o_padrao():
    cfg = FORGE_COACH_METHODOLOGY["bulking_intensity"]
    assert FORGE_COACH_METHODOLOGY["bulking_intensity_default"] == "controlado"
    assert [k for k, v in cfg.items() if v.get("recommended")] == ["controlado"]
    assert default_intensity_for("muscle_gain") == "controlado"


def test_agressivo_nunca_e_padrao():
    for goal in ("muscle_gain", "fat_loss", "maintenance"):
        assert default_intensity_for(goal) != "agressivo"


def test_agressivo_e_marcado_como_avancado_e_tem_aviso():
    cfg = FORGE_COACH_METHODOLOGY["bulking_intensity"]["agressivo"]
    assert cfg["advanced"] is True
    assert "gordura" in cfg["warning"].lower()


# --- o ritmo nao atravessa entre objetivos ------------------------------------------

def test_ritmo_de_emagrecimento_nao_vale_no_ganho():
    assert resolve_intensity_protocol("muscle_gain", "leve") is None
    assert alvos("leve") == alvos(None)


def test_ritmo_de_ganho_nao_vale_no_emagrecimento():
    assert resolve_intensity_protocol("fat_loss", "controlado") is None


def test_manutencao_nao_tem_ritmo():
    assert default_intensity_for("maintenance") is None
    for i in ("controlado", "moderado", "agressivo", "leve"):
        assert resolve_intensity_protocol("maintenance", i) is None


# --- compatibilidade ----------------------------------------------------------------

def test_perfil_legado_sem_ritmo_mantem_o_superavit_antigo():
    """Quem ja tem plano de ganho nao pode ver o alvo calorico mudar."""
    antes = compute_macro_targets(W, H, AGE, "male", DAYS, "muscle_gain", "moderate")
    assert antes["goal_calories"] == round(antes["tdee"] * FORGE_COACH_METHODOLOGY["surplus_pct"], 0)
    assert "cut_protocol" not in antes


def test_o_guardrail_de_ganho_comporta_o_ritmo_agressivo():
    """evaluate_goal_directional_substitution exige goal_calories dentro de
    [min,max]*tdee — o teto foi ampliado justamente para o agressivo caber."""
    guard = FORGE_COACH_METHODOLOGY["daily_guardrails"]["muscle_gain"]
    for i in ("controlado", "moderado", "agressivo"):
        t = alvos(i)
        assert guard["min_total_kcal_pct"] * t["tdee"] <= t["goal_calories"] <= guard["max_total_kcal_pct"] * t["tdee"]
    # e o legado tambem continua dentro
    legado = compute_macro_targets(W, H, AGE, "male", DAYS, "muscle_gain", "moderate")
    assert legado["goal_calories"] <= guard["max_total_kcal_pct"] * legado["tdee"]


def test_protocolo_de_ganho_viaja_nos_targets_para_persistir():
    t = alvos("moderado")
    assert t["cut_protocol"]["intensity"] == "moderado"
    assert t["cut_protocol"]["goal_key"] == "muscle_gain"

"""Intensidades de emagrecimento: leve / moderado / agressivo.

As opcoes nao podem ser so visuais — cada uma tem que mudar de fato os parametros e o
resultado da geracao. O modo agressivo em especial nao e "tirar 30 g de carboidrato": e
um protocolo low-carb com teto de 20 a 50 g/dia.

Testes puros: nao precisam de banco nem de servidor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from nutrition_engine import (
    FORGE_COACH_METHODOLOGY, check_plan_hard_limits, compute_macro_targets,
    food_carb_density, generate_daily_plan, resolve_cut_protocol, FOOD_INDEX,
)

W, H, AGE, DAYS = 85, 178, 30, 4

BASE = {"weight_kg": W, "height_cm": H, "age": AGE, "sex": "male", "goal": "fat_loss",
        "activity_level": "moderate", "training_days": DAYS, "meal_count": 4,
        "preferred_foods": [], "disliked_foods": [], "avoid_foods": [],
        "allergies": [], "dietary_restrictions": []}


def targets_for(intensity, goal="fat_loss", w=W, sex="male"):
    return compute_macro_targets(w, H, AGE, sex, DAYS, goal, "moderate", intensity)


def deficit_pct(t):
    return (1 - t["goal_calories"] / t["tdee"]) * 100


# ── parametros por intensidade ───────────────────────────────────────────────────────

def test_leve_fica_na_faixa_de_10_a_15_por_cento():
    assert 10 <= deficit_pct(targets_for("leve")) <= 15


def test_moderado_fica_na_faixa_de_15_a_20_por_cento():
    assert 15 <= deficit_pct(targets_for("moderado")) <= 20


def test_leve_preserva_mais_carboidrato_que_moderado():
    assert targets_for("leve")["carbs_g"] > targets_for("moderado")["carbs_g"]


def test_proteina_sobe_conforme_a_intensidade():
    leve, mod, agr = (targets_for(i)["protein_g"] for i in ("leve", "moderado", "agressivo"))
    assert leve < mod < agr


def test_moderado_e_a_opcao_recomendada():
    cfg = FORGE_COACH_METHODOLOGY["cutting_intensity"]
    assert FORGE_COACH_METHODOLOGY["cutting_intensity_default"] == "moderado"
    assert [k for k, v in cfg.items() if v.get("recommended")] == ["moderado"]


# ── agressivo: protocolo low-carb de verdade ─────────────────────────────────────────

@pytest.mark.parametrize("w,sex", [(52, "female"), (60, "female"), (85, "male"), (110, "male")])
def test_agressivo_fica_entre_20_e_50g_de_carboidrato(w, sex):
    t = targets_for("agressivo", w=w, sex=sex)
    assert 20 <= t["carbs_g"] <= 50
    assert t["carb_ceiling_g"] == 50


def test_agressivo_tem_deficit_mais_forte_que_moderado():
    assert deficit_pct(targets_for("agressivo")) > deficit_pct(targets_for("moderado"))


def test_agressivo_usa_gordura_para_fechar_a_caloria():
    """Com o carboidrato virando teto, a gordura passa a ser o macro residual."""
    agr, mod = targets_for("agressivo"), targets_for("moderado")
    assert agr["fat_g"] > mod["fat_g"]
    soma = agr["protein_g"] * 4 + agr["carbs_g"] * 4 + agr["fat_g"] * 9
    assert abs(soma - agr["goal_calories"]) <= 5


@pytest.mark.parametrize("seed", range(6))
def test_plano_agressivo_gerado_respeita_o_teto(seed):
    t = targets_for("agressivo")
    plano = generate_daily_plan(t, BASE, 4, "fat_loss", seed)
    assert plano["daily_totals"]["carbs_g"] <= t["carb_ceiling_g"]
    assert check_plan_hard_limits(plano, t) == []


@pytest.mark.parametrize("seed", range(4))
def test_plano_agressivo_nao_traz_arroz_pao_massa_ou_aveia(seed):
    proibidos = {"rice-white", "rice-brown", "pasta", "pasta-whole", "oats",
                 "bread-white", "bread-whole", "tapioca", "cassava", "sweet-potato"}
    t = targets_for("agressivo")
    plano = generate_daily_plan(t, BASE, 4, "fat_loss", seed)
    usados = {f["food_id"] for m in plano["meals"] for f in m["foods"]}
    assert not (usados & proibidos)
    teto = FORGE_COACH_METHODOLOGY["cutting_intensity"]["agressivo"]["max_food_carb_g_per_100g"]
    for fid in usados:
        assert food_carb_density(FOOD_INDEX[fid]) <= teto


def test_plano_fora_do_teto_e_reprovado_pela_validacao():
    """A validacao determinística tem que barrar, nao apenas avisar."""
    t = targets_for("agressivo")
    estourado = {"daily_totals": {"carbs_g": t["carb_ceiling_g"] + 12, "kcal": t["goal_calories"]}}
    erros = check_plan_hard_limits(estourado, t)
    assert erros and "carboidrato" in erros[0].lower()


def test_leve_e_moderado_nao_tem_teto_de_carboidrato():
    for i in ("leve", "moderado"):
        t = targets_for(i)
        assert t["carb_ceiling_g"] is None
        assert check_plan_hard_limits({"daily_totals": {"carbs_g": 400}}, t) == []


# ── compatibilidade ──────────────────────────────────────────────────────────────────

def test_perfil_legado_sem_intensidade_mantem_o_calculo_antigo():
    """Quem ja tem plano nao pode ver o alvo calorico mudar por causa desta feature."""
    antes = compute_macro_targets(W, H, AGE, "male", DAYS, "fat_loss", "moderate")
    depois = compute_macro_targets(W, H, AGE, "male", DAYS, "fat_loss", "moderate", None)
    assert antes == depois
    assert "cut_protocol" not in antes


def test_intensidade_e_ignorada_na_manutencao():
    """Manter e recompor e um caminho so: nao tem leve/moderado/agressivo."""
    assert resolve_cut_protocol("maintenance", "agressivo") is None
    com = compute_macro_targets(W, H, AGE, "male", DAYS, "maintenance", "moderate", "agressivo")
    sem = compute_macro_targets(W, H, AGE, "male", DAYS, "maintenance", "moderate")
    assert com == sem


def test_protocolo_de_cutting_nao_atravessa_para_o_ganho():
    """resolve_cut_protocol so responde por emagrecimento — o ganho tem o proprio ritmo,
    resolvido por resolve_intensity_protocol."""
    assert resolve_cut_protocol("muscle_gain", "agressivo") is None


def test_intensidade_desconhecida_cai_no_legado_em_vez_de_quebrar():
    assert resolve_cut_protocol("fat_loss", "turbo") is None


def test_protocolo_viaja_nos_targets_para_persistir_com_o_plano():
    t = targets_for("agressivo")
    assert t["cut_protocol"]["intensity"] == "agressivo"
    assert t["cut_protocol"]["protocol_version"] == FORGE_COACH_METHODOLOGY["cut_protocol_version"]
    plano = generate_daily_plan(t, BASE, 4, "fat_loss", 1)
    assert plano["targets"]["cut_protocol"]["intensity"] == "agressivo"

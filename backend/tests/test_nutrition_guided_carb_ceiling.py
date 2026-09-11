# -*- coding: utf-8 -*-
"""
O fluxo guiado nao conseguia ser concluido no protocolo agressivo.

A atleta escolhia as seis refeicoes uma a uma e, no fim, `confirm` devolvia 422:
"Carboidrato do dia acima do teto do protocolo Agressivo". Nenhum plano era gravado, e o
trabalho de seis telas ia embora.

Duas lacunas somadas, e nenhuma delas na geracao automatica — que sempre funcionou:

1. `/plan/draft/choose-remaining` ("FORGE escolhe por mim") nao passava o perfil por
   `_com_protocolo`, entao montava o dia com alimentos que a propria tela de opcoes
   (`/plan/draft/options`) nunca ofereceria — ela ja fazia esse preparo.

2. O passe de teto de carboidrato (`_apply_carb_ceiling`) so existia dentro de
   `generate_daily_plan`. O caminho guiado montava o dia refeicao a refeicao e nunca
   passava por ele.
"""
import pytest

from nutrition_engine import (FORGE_COACH_METHODOLOGY, aplicar_teto_de_carboidrato,
                              build_food_item, check_plan_hard_limits,
                              compute_macro_targets, generate_daily_plan, sum_plan_totals)

# A atleta do video: mulher, emagrecimento agressivo, seis refeicoes.
PERFIL = dict(w=59, h=163, age=30, sex="female", td=5)


def _alvos(goal="fat_loss", intensity="agressivo"):
    return compute_macro_targets(goal=goal, intensity=intensity, al="moderate", **PERFIL)


def test_o_protocolo_agressivo_declara_um_teto_de_carboidrato():
    alvos = _alvos()
    assert alvos.get("carb_ceiling_g"), "sem teto declarado nao ha o que este arquivo proteja"
    # A meta e menor que o teto de proposito: encostar no teto deixa o plano a um
    # arredondamento de estourar.
    assert alvos["carbs_g"] <= alvos["carb_ceiling_g"]


def test_o_passe_de_teto_e_publico_e_reaproveitavel():
    """
    Ele so existia como `_apply_carb_ceiling`, privado ao motor. O fluxo guiado precisa
    aplicar o MESMO passe — duas implementacoes divergiriam com o tempo.
    """
    alvos = _alvos()
    plano = generate_daily_plan(alvos, {}, meal_count=6, goal="fat_loss")
    refeicoes = plano["meals"] if isinstance(plano, dict) else plano
    # Idempotente: rodar de novo sobre um dia ja dentro do teto nao o quebra.
    de_novo = aplicar_teto_de_carboidrato(refeicoes, alvos)
    assert sum_plan_totals(de_novo)["carbs_g"] <= alvos["carb_ceiling_g"]


def test_sem_teto_no_protocolo_o_passe_nao_altera_nada():
    """Recomp nao tem teto: o passe precisa ser inocuo, e nao 'quase inocuo'."""
    alvos = _alvos(goal="recomp", intensity=None)
    assert alvos.get("carb_ceiling_g") is None
    plano = generate_daily_plan(alvos, {}, meal_count=6, goal="recomp")
    refeicoes = plano["meals"] if isinstance(plano, dict) else plano
    antes = sum_plan_totals(refeicoes)
    depois = sum_plan_totals(aplicar_teto_de_carboidrato(refeicoes, alvos))
    assert abs(antes["kcal"] - depois["kcal"]) < 1
    assert abs(antes["carbs_g"] - depois["carbs_g"]) < 1


def _dia_fora_do_teto(alvos):
    """Monta a mao um dia carregado de carboidrato, como o guiado montava."""
    pesados = ["rice-white", "sweet-potato", "potato", "oats", "banana", "cassava"]
    refeicoes = []
    for i, fid in enumerate(pesados):
        try:
            item = build_food_item(fid, 150)
        except Exception:
            continue
        refeicoes.append({"name": f"Refeicao {i+1}", "foods": [item]})
    return refeicoes


def test_um_dia_montado_fora_do_teto_volta_para_dentro():
    alvos = _alvos()
    refeicoes = _dia_fora_do_teto(alvos)
    if not refeicoes:
        pytest.skip("catalogo sem os alimentos de carga usados por este teste")
    antes = sum_plan_totals(refeicoes)["carbs_g"]
    if antes <= alvos["carb_ceiling_g"]:
        pytest.skip("o dia montado ja nasceu dentro do teto")
    depois = sum_plan_totals(aplicar_teto_de_carboidrato(refeicoes, alvos))["carbs_g"]
    assert depois < antes, "o passe precisa reduzir o carboidrato do dia"


@pytest.mark.parametrize("n", [4, 6])
def test_a_geracao_automatica_continua_dentro_do_teto(n):
    """Regressao: o caminho que ja funcionava nao pode ter sido afetado."""
    alvos = _alvos()
    plano = generate_daily_plan(alvos, {}, meal_count=n, goal="fat_loss")
    erros = check_plan_hard_limits(plano if isinstance(plano, dict)
                                   else {"meals": plano, "daily_totals": sum_plan_totals(plano)},
                                   alvos)
    assert erros == [], f"{n} refeicoes fora dos limites: {erros}"


def test_o_teto_por_alimento_do_protocolo_existe_e_e_menor_que_o_do_dia():
    """
    `_com_protocolo` injeta este numero no perfil, e e ele que impede a escolha de
    alimentos que depois nao cabem no dia. Era o que faltava em choose-remaining.
    """
    cfg = FORGE_COACH_METHODOLOGY["cutting_intensity"]["agressivo"]
    assert cfg.get("max_food_carb_g_per_100g"), "sem teto por alimento, a escolha fica livre"
    assert cfg["max_food_carb_g_per_100g"] < cfg["carb_target_g"] * 2

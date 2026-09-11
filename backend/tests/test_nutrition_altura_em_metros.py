# -*- coding: utf-8 -*-
"""
Altura digitada em metros produzia um plano inteiro errado, sem nenhum erro aparecer.

Caso real de producao, reproduzido numero por numero: mulher de 65 kg, emagrecimento
moderado, com a altura gravada como "1,6" em vez de 163.

    altura em metros  ->   427 kcal   P143  C 0   G52     <- o que o usuario viu
    altura em cm      ->  1624 kcal   P143  C146  G52     <- o correto

A TMB calculada ficava em 348 kcal. O campo pede centimetros, mas `Field(gt=0, le=280)`
aceitava 1.63 — e o numero atravessava BMR, TDEE, meta e as seis refeicoes sem disparar
nada. O carboidrato ia a zero porque proteina e gordura sozinhas ja estouravam o total.

O defeito nao se manifestava como erro: se manifestava como um plano plausivel e errado,
que e a forma mais cara de errar.
"""
import pytest

from nutrition_engine import (calculate_bmr, compute_macro_targets, normalizar_altura_cm)


# ── A conversao ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("metros,cm", [
    (1.63, 163), (1.5, 150), (1.85, 185), (1.0, 100), (2.0, 200),
])
def test_altura_em_metros_vira_centimetros(metros, cm):
    assert normalizar_altura_cm(metros) == pytest.approx(cm)


@pytest.mark.parametrize("altura", [150, 163, 178, 200, 3.0, 280])
def test_altura_ja_em_centimetros_nao_e_mexida(altura):
    # 3 e o limite: ninguem tem 3 cm, e ninguem tem 3 metros. Acima disso e cm por definicao.
    assert normalizar_altura_cm(altura) == pytest.approx(altura)


def test_valor_impossivel_de_converter_passa_intacto():
    """Normalizar nao pode virar um lugar onde dado torto some em silencio."""
    assert normalizar_altura_cm(None) is None
    assert normalizar_altura_cm("abc") == "abc"


# ── O caso do usuario ─────────────────────────────────────────────────────────

PERFIL = dict(w=65, age=28, sex="female", td=5, goal="fat_loss", intensity="moderado")


def _alvos(h):
    return compute_macro_targets(PERFIL["w"], h, PERFIL["age"], PERFIL["sex"],
                                 PERFIL["td"], PERFIL["goal"], "moderate",
                                 PERFIL["intensity"])


def test_o_plano_de_427_kcal_nao_acontece_mais():
    """A asserção central: a altura em metros deixa de produzir meta de tres digitos."""
    alvos = _alvos(1.63)
    assert alvos["goal_calories"] > 1000, (
        f"altura em metros ainda produz {alvos['goal_calories']:.0f} kcal")


def test_metros_e_centimetros_dao_o_mesmo_resultado():
    """1,63 e 163 sao a mesma pessoa — e agora o motor concorda."""
    em_metros, em_cm = _alvos(1.63), _alvos(163)
    for campo in ("bmr", "tdee", "goal_calories", "protein_g", "carbs_g", "fat_g"):
        assert em_metros[campo] == pytest.approx(em_cm[campo], rel=0.01), f"{campo} diverge"


def test_a_tmb_volta_a_ser_fisiologicamente_possivel():
    # Ficava em 348 kcal, metade do minimo de qualquer adulto.
    assert _alvos(1.63)["bmr"] > 1000


def test_o_carboidrato_para_de_ir_a_zero_por_conta_da_altura():
    """
    Carboidrato zerado era CONSEQUENCIA, e nao causa: com a meta em 427, proteina e
    gordura sozinhas ja passavam do total, e o residual era cortado em zero.
    """
    assert _alvos(1.63)["carbs_g"] > 0


def test_calculate_bmr_sozinho_nao_normaliza():
    """
    A normalizacao mora em `compute_macro_targets`, que e o portao unico das metas.
    `calculate_bmr` continua sendo uma formula pura — se um dia alguem a chamar direto,
    este teste documenta que a responsabilidade nao e dela.
    """
    assert calculate_bmr(65, 1.63, 28, "female") < calculate_bmr(65, 163, 28, "female")


@pytest.mark.parametrize("goal,intensity", [
    ("fat_loss", "leve"), ("fat_loss", "moderado"), ("fat_loss", "agressivo"),
    ("recomp", None), ("maintenance", None), ("muscle_gain", "moderado"),
])
def test_nenhum_protocolo_produz_meta_absurda_com_altura_em_metros(goal, intensity):
    alvos = compute_macro_targets(65, 1.63, 28, "female", 5, goal, "moderate", intensity)
    assert alvos["goal_calories"] > 1000, f"{goal}/{intensity} -> {alvos['goal_calories']:.0f}"

# -*- coding: utf-8 -*-
"""
Dois defeitos vistos em producao numa dieta feminina de seis refeicoes.

1. O cafe da manha virava um prato de peixe. O layout de seis chama a primeira refeicao de
   "Cafe da manha / Pre-treino", e `_infer_meal_type` perguntava por pre-treino ANTES de
   perguntar por cafe da manha. A refeicao caia no template `pre_workout`, onde a proteina
   e opcional e vem da familia pre/pos — que aceita tilapia. Saia batata-doce, mamao,
   tilapia e azeite: sem ovo, sem laticinio.

2. A META do dia ficava em algumas centenas de kcal. Nao era erro de conta: numa dieta
   colada, `draft_to_plan` transforma o que foi LIDO na meta do dia, e linhas como
   "arroz a vontade" valem zero. O plano fica coerente consigo mesmo e absurdo para quem
   vai comer.
"""
import pytest

from nutrition_engine import (FORGE_COACH_METHODOLOGY, MEAL_TEMPLATES, _infer_meal_type,
                              calculate_bmr, compute_macro_targets, generate_daily_plan,
                              _meal_totals)
from nutrition_import import (draft_to_plan, parse_diet_text, recompute, validate_draft)


# ── 1. Classificacao da refeicao ──────────────────────────────────────────────

def test_cafe_da_manha_que_tambem_e_pre_treino_continua_cafe_da_manha():
    # O nome exato que o layout de seis refeicoes usa.
    assert _infer_meal_type("Cafe da manha / Pre-treino") == "breakfast"


def test_pre_treino_sozinho_continua_pre_treino():
    # A correcao nao pode sequestrar a refeicao que e so pre-treino.
    assert _infer_meal_type("Pre-treino") == "pre_workout"
    assert _infer_meal_type("Lanche pre-treino") == "pre_workout"


def test_os_demais_nomes_nao_mudaram():
    assert _infer_meal_type("Pos-treino") == "post_workout"
    assert _infer_meal_type("Almoco") == "lunch"
    assert _infer_meal_type("Jantar") == "dinner"
    assert _infer_meal_type("Ceia") == "snack"
    assert _infer_meal_type("Lanche da tarde") == "snack"


def test_todo_nome_do_layout_de_seis_cai_num_template_existente():
    for nome in FORGE_COACH_METHODOLOGY["meal_names"][6]:
        assert _infer_meal_type(nome) in MEAL_TEMPLATES


@pytest.mark.parametrize("objetivo", ["fat_loss", "recomp", "maintenance"])
def test_cafe_da_manha_de_seis_refeicoes_tem_proteina_de_cafe_da_manha(objetivo):
    """
    O defeito que a atleta viu: cafe da manha sem nada que se coma de manha.

    A asserção e sobre a FAMILIA da proteina ancora, e nao sobre um alimento especifico —
    o motor faz rodizio, e travar um id transformaria variedade em quebra de teste.
    """
    alvos = compute_macro_targets(w=62, h=165, age=28, sex="female", td=5, goal=objetivo)
    plano = generate_daily_plan(alvos, {}, meal_count=6, goal=objetivo)
    refeicoes = plano["meals"] if isinstance(plano, dict) else plano
    primeira = refeicoes[0]

    assert "cafe da manha" in primeira["name"].lower()
    familia = set(FORGE_COACH_METHODOLOGY.get("food_families", {}).get("BREAKFAST_PROTEIN", [])) \
        or set(__import__("nutrition_engine").FOOD_FAMILIES["BREAKFAST_PROTEIN"])
    ids = {f["food_id"] for f in primeira["foods"]}
    assert ids & familia, f"cafe da manha sem proteina de cafe da manha: {sorted(ids)}"


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_o_plano_entrega_a_meta_em_qualquer_quantidade_de_refeicoes(n):
    """Guarda contra o sintoma que originou o chamado: um dia somando muito menos que a
    meta. A folga e larga de proposito — o alvo aqui e o absurdo, nao o arredondamento."""
    alvos = compute_macro_targets(w=62, h=165, age=28, sex="female", td=5, goal="recomp")
    plano = generate_daily_plan(alvos, {}, meal_count=n, goal="recomp")
    refeicoes = plano["meals"] if isinstance(plano, dict) else plano
    total = sum(_meal_totals(m)[0] for m in refeicoes)
    proporcao = total / alvos["goal_calories"]
    assert 0.85 <= proporcao <= 1.15, (
        f"{n} refeicoes entregaram {total:.0f} kcal de {alvos['goal_calories']:.0f}")


# ── 2. A dieta importada nao redefine a meta ─────────────────────────────────

DIETA_COM_LINHAS_SOLTAS = """Cafe da manha
2 fatias de pao integral
mamao a vontade

Almoco
1 file de frango
arroz a vontade
salada verde a vontade

Jantar
legumes refogados
"""

ATLETA = {"weight_kg": 62, "height_cm": 165, "age": 28, "sex": "female",
          "training_days": 5, "goal": "recomp"}


def _alvos_do_atleta():
    return {k: v for k, v in compute_macro_targets(
        ATLETA["weight_kg"], ATLETA["height_cm"], ATLETA["age"], ATLETA["sex"],
        ATLETA["training_days"], ATLETA["goal"]).items()
        if k in ("goal_calories", "protein_g", "carbs_g", "fat_g")}


def test_a_meta_vem_do_questionario_e_nao_da_dieta_colada():
    """
    O defeito relatado: uma dieta lida pela metade virava META de poucas centenas de kcal.

    O plano importado passa a carregar DOIS numeros — o que a pessoa precisa (`targets`) e
    o que a dieta entrega (`daily_totals`). A diferenca fica visivel em vez de sumir.
    """
    rascunho = recompute(parse_diet_text(DIETA_COM_LINHAS_SOLTAS))
    plano = draft_to_plan(rascunho, _alvos_do_atleta())

    entregue = plano["daily_totals"]["kcal"]
    meta = plano["targets"]["goal_calories"]

    assert meta == _alvos_do_atleta()["goal_calories"]
    assert meta > 1500, "a meta de uma mulher de 62kg nao pode ser de centenas de kcal"
    # A entrega segue sendo o que foi lido — e agora da para ver o buraco.
    assert entregue < meta


def test_sem_questionario_o_comportamento_antigo_e_preservado():
    """Sem peso, altura e idade nao ha necessidade calculada; a unica referencia possivel
    continua sendo o que a dieta entrega."""
    rascunho = recompute(parse_diet_text(DIETA_COM_LINHAS_SOLTAS))
    plano = draft_to_plan(rascunho, None)
    assert plano["targets"]["goal_calories"] == round(plano["daily_totals"]["kcal"])


def test_dieta_parcial_legitima_continua_ativavel():
    """
    Uma importacao curta — poucas refeicoes, todos os itens resolvidos — e valida: a pessoa
    pode completar depois. A correcao nao pode transformar isso em bloqueio.
    """
    curta = """Cafe da manha
2 ovos inteiros
50g de aveia em flocos
200ml de leite desnatado

Almoco
150g de arroz branco cozido
120g de peito de frango grelhado
"""
    rascunho = recompute(parse_diet_text(curta))
    assert validate_draft(rascunho) == [], "uma dieta curta e completa nao pode ser barrada"
    plano = draft_to_plan(rascunho, _alvos_do_atleta())
    assert len(plano["meals"]) == 2
    assert plano["daily_totals"]["kcal"] > 0


def test_o_que_a_dieta_entrega_continua_fiel_ao_lido():
    """A entrega nao pode ser 'corrigida' para parecer com a meta: ela e o que foi lido."""
    rascunho = recompute(parse_diet_text(DIETA_COM_LINHAS_SOLTAS))
    plano = draft_to_plan(rascunho, _alvos_do_atleta())
    soma_refeicoes = sum(m["target_cal"] for m in plano["meals"])
    assert abs(soma_refeicoes - plano["daily_totals"]["kcal"]) <= len(plano["meals"])

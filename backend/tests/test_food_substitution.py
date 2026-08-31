"""Substituicao de alimentos: pool de candidatos, equivalencia e protecoes.

O relato era "Nenhuma substituicao disponivel" para alimentos comuns. Tres causas:

  1. um pool nao-vazio da DNA IMPEDIA as demais fontes, entao no cafe da manha uma
     proteina so podia virar ovo, omelete ou whey — nunca frango, peixe ou carne;
  2. a simulacao redimensionava a refeicao para o alvo NOMINAL, desfazendo o ajuste que
     _reconcile_daily faz de proposito para o DIA fechar; o dia entao saia da faixa e o
     guardrail reprovava um dano criado pela propria simulacao;
  3. o guardrail testava limites ABSOLUTOS, entao um dia que ja pousava no piso (cutting
     agressivo) reprovava toda e qualquer troca.

Testes puros: nao precisam de banco nem de servidor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from nutrition_engine import (
    FOOD_INDEX, FOODS_BY_ROLE, _allergy_key, _daily_kcal_ok, _food_macros, _infer_meal_type,
    _role_of_food, _substitution_candidates, calculate_meal_portions, compute_macro_targets,
    build_food_item, find_substitutes, generate_daily_plan, portion_for_equivalence, sum_plan_totals,
)

BASE = {"weight_kg": 85, "height_cm": 178, "age": 30, "sex": "male", "goal": "fat_loss",
        "activity_level": "moderate", "training_days": 4, "meal_count": 4,
        "preferred_foods": [], "disliked_foods": [], "avoid_foods": [], "allergies": [],
        "dietary_restrictions": []}

CARNES_E_PEIXES = {"chicken-breast", "chicken-thigh", "beef-grill", "beef-ground",
                   "pork-loin", "tilapia", "salmon", "tuna-can"}
LATICINIOS = {"whey-protein", "rice-cream-whey", "milk-whole", "milk-skim",
              "yogurt-natural", "yogurt-greek", "cheese-mozzarella", "cheese-cottage"}
OVOS = {"eggs-whole", "egg-whites", "chicken-egg-omelet"}


def plano(na=None, intensidade=None, goal="fat_loss", seed=3):
    na = na or BASE
    t = compute_macro_targets(na["weight_kg"], na["height_cm"], na["age"], na["sex"],
                              na["training_days"], goal, "moderate", intensidade)
    return t, generate_daily_plan(t, na, 4, goal, seed)


def opcoes_de(fid_procurado, na=None, intensidade=None, goal="fat_loss", seed=3, maximo=6):
    """Opcoes para o primeiro item com este id, no plano gerado."""
    na = na or BASE
    t, p = plano(na, intensidade, goal, seed)
    for meal in p["meals"]:
        for item in meal["foods"]:
            if item["food_id"] != fid_procurado:
                continue
            return find_substitutes(
                fid_procurado, na, [x["food_id"] for x in meal["foods"]], maximo,
                item["grams"], goal, meal=meal["foods"], daily_totals=p["daily_totals"],
                targets=t, meal_type=_infer_meal_type(meal["name"]),
                meal_target_cal=meal.get("target_cal"),
                meal_target_protein=meal.get("target_protein"),
                meal_target_fat=meal.get("target_fat"))
    return None


def todas_as_proteinas(na=None, intensidade=None, goal="fat_loss", seed=3):
    na = na or BASE
    t, p = plano(na, intensidade, goal, seed)
    saida = {}
    for meal in p["meals"]:
        ids = [x["food_id"] for x in meal["foods"]]
        for item in meal["foods"]:
            if _role_of_food(FOOD_INDEX[item["food_id"]]) != "primary_protein":
                continue
            saida[(meal["name"], item["food_id"])] = find_substitutes(
                item["food_id"], na, ids, 6, item["grams"], goal, meal=meal["foods"],
                daily_totals=p["daily_totals"], targets=t,
                meal_type=_infer_meal_type(meal["name"]),
                meal_target_cal=meal.get("target_cal"),
                meal_target_protein=meal.get("target_protein"),
                meal_target_fat=meal.get("target_fat"))
    return saida


# --- normalizacao de alergias -------------------------------------------------------

@pytest.mark.parametrize("digitado,esperado", [
    ("ovo", "egg"), ("Ovos", "egg"), ("OVO ", "egg"), ("clara de ovo", "egg"),
    ("leite", "lactose"), ("Lactose", "lactose"), ("laticinio", "lactose"),
    ("peixe", "fish"), ("peixes", "fish"),
    ("amendoim", "peanut"), ("castanhas", "nuts"), ("soja", "soy"),
    ("gluten", "gluten"), ("trigo", "gluten"),
    ("egg", "egg"), ("fish", "fish"),          # ingles continua valendo
    ("", None), ("nada disso", None),
])
def test_alergia_digitada_em_portugues_e_reconhecida(digitado, esperado):
    assert _allergy_key(digitado) == esperado


# --- pool de candidatos -------------------------------------------------------------

@pytest.mark.parametrize("fid", ["tilapia", "chicken-breast", "tuna-can", "eggs-whole",
                                 "egg-whites", "beef-grill", "salmon", "whey-protein"])
def test_toda_proteina_comum_tem_candidatos(fid):
    cands = _substitution_candidates(fid, "lunch")
    assert len(cands) >= 6, f"{fid} so ofereceu {cands}"
    assert fid not in cands


def test_o_pool_soma_as_fontes_em_vez_de_uma_bloquear_a_outra():
    """Antes, um pool nao-vazio da DNA impedia SUB_TIER, SUB_GROUPS e o catalogo."""
    cafe = set(_substitution_candidates("egg-whites", "breakfast"))
    assert cafe & CARNES_E_PEIXES, "cafe da manha ficou sem carne/peixe no pool"
    assert "whey-protein" in cafe


def test_alimento_fora_das_tabelas_ainda_recebe_candidatos_pelo_papel():
    """Rede de seguranca: o catalogo por papel e a ultima camada."""
    for fid in FOODS_BY_ROLE["primary_protein"]:
        assert _substitution_candidates(fid, None), f"{fid} ficou sem candidato"


# --- proteinas: nunca vazio ---------------------------------------------------------

@pytest.mark.parametrize("intensidade", [None, "leve", "moderado", "agressivo"])
def test_nenhuma_proteina_fica_sem_opcao_no_emagrecimento(intensidade):
    for (refeicao, fid), opts in todas_as_proteinas(intensidade=intensidade).items():
        assert opts, f"{fid} em {refeicao} (intensidade={intensidade}) ficou sem opcao"


@pytest.mark.parametrize("goal,intensidade", [("muscle_gain", "controlado"),
                                              ("muscle_gain", "agressivo"),
                                              ("maintenance", None)])
def test_nenhuma_proteina_fica_sem_opcao_nos_demais_objetivos(goal, intensidade):
    for (refeicao, fid), opts in todas_as_proteinas(goal=goal, intensidade=intensidade).items():
        assert opts, f"{fid} em {refeicao} ({goal}) ficou sem opcao"


def test_tilapia_oferece_alternativas_reais_de_proteina():
    opts = opcoes_de("tilapia")
    assert opts, "tilapia ficou sem opcao — era exatamente o relato"
    ids = {o[0] for o in opts}
    assert ids & CARNES_E_PEIXES, f"nenhuma carne/peixe entre {ids}"


def test_tilapia_onivoro_nunca_oferece_tofu_e_prioriza_frango_e_carne():
    opts = opcoes_de("tilapia", maximo=12)
    ids = {o[0] for o in opts}
    assert "tofu" not in ids
    assert "soy-protein" not in ids
    assert "chicken-breast" in ids
    assert ids & {"beef-grill", "beef-ground"}


def test_azeite_e_sempre_fracionado_em_cinco_gramas():
    assert build_food_item("olive-oil", 7)["grams"] == 5
    assert build_food_item("olive-oil", 13)["grams"] == 15


def test_plano_expoe_acompanhamento_e_hidratacao_personalizada():
    _targets, generated = plano()
    guidance = generated["coach_guidance"]
    assert 2.0 <= guidance["hydration_target_l"] <= 5.0
    assert "jejum" in guidance["weekly_weigh_in"].lower()
    assert "fotos" in guidance["progress_photos"].lower()
    assert generated["quality_gate"]["authority"] == "FORGE deterministic nutrition engine"


def test_carne_vermelha_compensa_azeite_em_vez_de_duplicar_gordura():
    portions = calculate_meal_portions(
        ["beef-grill", "potato", "pumpkin", "olive-oil", "broccoli"],
        target_cal=514, target_protein=56, target_fat=21, goal="fat_loss")
    assert portions["beef-grill"] >= 150
    assert portions["olive-oil"] <= 10


def test_seis_refeicoes_incluem_lanche_jantar_e_ceia_reais():
    t = compute_macro_targets(BASE["weight_kg"], BASE["height_cm"], BASE["age"],
                              BASE["sex"], BASE["training_days"], BASE["goal"])
    generated = generate_daily_plan(t, {**BASE, "meal_count": 6}, 6, BASE["goal"], 4)
    names = [meal["name"] for meal in generated["meals"]]
    assert "Lanche da tarde" in names
    assert "Jantar" in names
    assert "Ceia" in names


def test_whey_aparece_quando_permitido():
    oferecidos = {o[0] for v in todas_as_proteinas().values() for o in v}
    assert "whey-protein" in oferecidos


# --- protecoes ----------------------------------------------------------------------

def test_vegetariano_nao_recebe_carne_nem_peixe():
    na = {**BASE, "dietary_restrictions": ["vegetarian"]}
    oferecidos = {o[0] for v in todas_as_proteinas(na).values() for o in v}
    assert oferecidos, "vegetariano ficou sem nenhuma opcao"
    assert not (oferecidos & CARNES_E_PEIXES)


def test_sem_lactose_nao_recebe_whey():
    na = {**BASE, "dietary_restrictions": ["lactose_free"]}
    oferecidos = {o[0] for v in todas_as_proteinas(na).values() for o in v}
    assert oferecidos
    assert not (oferecidos & LATICINIOS)


def test_alergia_a_ovo_em_portugues_bloqueia_ovos():
    na = {**BASE, "allergies": ["ovo"]}
    oferecidos = {o[0] for v in todas_as_proteinas(na).values() for o in v}
    assert oferecidos
    assert not (oferecidos & OVOS)


def test_alimento_que_o_atleta_nao_gosta_nao_e_oferecido():
    na = {**BASE, "disliked_foods": ["chicken-breast"]}
    oferecidos = {o[0] for v in todas_as_proteinas(na).values() for o in v}
    assert "chicken-breast" not in oferecidos


# --- equivalencia -------------------------------------------------------------------

def test_a_porcao_e_recalculada_e_nao_copiada():
    opts = opcoes_de("tilapia")
    origem = FOOD_INDEX["tilapia"]
    for cid, gramas, *_ in opts:
        densidade_igual = abs(
            (FOOD_INDEX[cid]["kcal"] / (FOOD_INDEX[cid]["grams"] or 100))
            - (origem["kcal"] / (origem["grams"] or 100))) < 0.05
        if not densidade_igual:
            assert gramas > 0


def test_equivalencia_de_proteina_iguala_a_proteina():
    """Prioridade 1 do protocolo para proteinas."""
    gramas, motivo = portion_for_equivalence("chicken-breast", "tilapia", 200)
    assert "proteina equivalente" in motivo.lower()
    _, p_novo, _, _ = _food_macros("chicken-breast", gramas)
    _, p_orig, _, _ = _food_macros("tilapia", 200)
    assert abs(p_novo - p_orig) <= max(4.0, p_orig * 0.12)


def test_equivalencia_de_carboidrato_iguala_o_carboidrato():
    gramas, motivo = portion_for_equivalence("rice-white", "potato", 200)
    assert "carboidrato equivalente" in motivo.lower()
    _, _, c_novo, _ = _food_macros("rice-white", gramas)
    _, _, c_orig, _ = _food_macros("potato", 200)
    assert abs(c_novo - c_orig) <= max(5.0, c_orig * 0.15)


def test_equivalencia_de_gordura_iguala_a_gordura():
    gramas, motivo = portion_for_equivalence("avocado", "olive-oil", 20)
    assert "gordura equivalente" in motivo.lower()


# --- guardrail diario ---------------------------------------------------------------

def test_dia_dentro_da_faixa_exige_continuar_dentro():
    assert _daily_kcal_ok(1900, 1950, 1800, 2000) is True
    assert _daily_kcal_ok(1900, 2100, 1800, 2000) is False


def test_dia_ja_fora_da_faixa_so_reprova_se_piorar():
    """Um plano de cutting agressivo pousa no piso e o arredondamento o deixa alguns kcal
    abaixo; testar limites absolutos ali reprovava TODAS as substituicoes."""
    assert _daily_kcal_ok(1795, 1798, 1800, 2000) is True   # aproximou
    assert _daily_kcal_ok(1795, 1795, 1800, 2000) is True   # empatou
    assert _daily_kcal_ok(1795, 1700, 1800, 2000) is False  # piorou


# --- cutting agressivo --------------------------------------------------------------

def _dia_apos_aplicar(plano_completo, mi, meal, fid_original, cid, gramas, evald, goal):
    """Reproduz o que o endpoint GRAVA, conforme o modo de dimensionamento que o motor
    aprovou. Um delta 1:1 ingenuo da numero errado no modo meal_sim, que redimensiona a
    refeicao inteira e ajusta tambem o carboidrato dos outros itens."""
    ids = [x["food_id"] for x in meal["foods"]]
    if evald.get("sizing") == "meal_sim":
        novos_ids = [cid if x == fid_original else x for x in ids]
        porcoes = calculate_meal_portions(novos_ids, evald["sim_cal"], evald["sim_protein"],
                                          evald.get("sim_fat") or 0, goal)
        novas = [{"food_id": f, "grams": porcoes.get(f, 0)} for f in novos_ids]
    else:
        novas = [{"food_id": (cid if x["food_id"] == fid_original else x["food_id"]),
                  "grams": (gramas if x["food_id"] == fid_original else x["grams"])}
                 for x in meal["foods"]]
    refeicoes = list(plano_completo["meals"])
    refeicoes[mi] = {**meal, "foods": novas}
    return sum_plan_totals(refeicoes)


def test_nenhuma_opcao_no_agressivo_estoura_o_teto_de_carboidrato():
    na = BASE
    t, p = plano(na, "agressivo")
    teto = t["carb_ceiling_g"]
    assert teto == 50
    testadas = 0
    for mi, meal in enumerate(p["meals"]):
        ids = [x["food_id"] for x in meal["foods"]]
        for item in meal["foods"]:
            opts = find_substitutes(
                item["food_id"], na, ids, 6, item["grams"], "fat_loss", meal=meal["foods"],
                daily_totals=p["daily_totals"], targets=t,
                meal_type=_infer_meal_type(meal["name"]),
                meal_target_cal=meal.get("target_cal"),
                meal_target_protein=meal.get("target_protein"),
                meal_target_fat=meal.get("target_fat"))
            for cid, gramas, _motivo, evald in opts:
                dia = _dia_apos_aplicar(p, mi, meal, item["food_id"], cid, gramas,
                                        evald, "fat_loss")
                testadas += 1
                assert dia["carbs_g"] <= teto + 0.5, \
                    f"{item['food_id']} -> {cid} deixaria o dia em {dia['carbs_g']:.1f} g"
    assert testadas > 0, "nenhuma opcao foi testada"


# --- demais categorias --------------------------------------------------------------

@pytest.mark.parametrize("papel", ["primary_carb", "vegetable", "fat_source", "fruit"])
def test_outras_categorias_tambem_tem_opcoes(papel):
    t, p = plano(goal="maintenance")
    encontrou = False
    for meal in p["meals"]:
        ids = [x["food_id"] for x in meal["foods"]]
        for item in meal["foods"]:
            if _role_of_food(FOOD_INDEX[item["food_id"]]) != papel:
                continue
            encontrou = True
            opts = find_substitutes(
                item["food_id"], BASE, ids, 6, item["grams"], "maintenance",
                meal=meal["foods"], daily_totals=p["daily_totals"], targets=t,
                meal_type=_infer_meal_type(meal["name"]),
                meal_target_cal=meal.get("target_cal"),
                meal_target_protein=meal.get("target_protein"),
                meal_target_fat=meal.get("target_fat"))
            assert opts, f"{item['food_id']} ({papel}) ficou sem opcao"
    assert encontrou, f"nenhum alimento com papel {papel} no plano de teste"

"""FORGE — importador de dieta em texto: parser, matching e macros.

Funções puras: sem servidor, sem Mongo, sem rede. É o portão que garante que nenhuma
caloria é inventada — quantidade ausente fica ausente, alimento fora do catálogo fica
sem alimento, e medida caseira nasce marcada como estimativa.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import FOOD_INDEX  # noqa: E402
from nutrition_import import (  # noqa: E402
    MAX_IMPORT_CHARS, REVIEW_ESTIMATED_PORTION, REVIEW_FOOD_UNMATCHED,
    REVIEW_QUANTITY_MISSING, apply_resolution, build_matcher, draft_to_plan,
    item_macros, parse_diet_text, parse_quantity, to_grams, unmatched_names,
    validate_draft,
)

DIETA = """CAFÉ DA MANHÃ
2 ovos inteiros
50g de aveia
200ml de leite desnatado

ALMOÇO
150g de arroz branco
120g de peito de frango
1 concha de feijão preto

LANCHE
1 scoop de whey
1 banana"""


def itens(draft):
    return [i for m in draft["meals"] for i in m["items"]]


# --- estrutura ------------------------------------------------------------------------

def test_meals_and_items_are_recognized():
    d = parse_diet_text(DIETA)
    assert d["stats"]["meals"] == 3
    assert d["stats"]["items"] == 8
    assert [m["name"] for m in d["meals"]] == ["CAFÉ DA MANHÃ", "ALMOÇO", "LANCHE"]


def test_foods_resolve_against_the_existing_catalog():
    d = parse_diet_text(DIETA)
    assert [i["food_id"] for i in itens(d)] == [
        "eggs-whole", "oats", "milk-skim", "rice-white", "chicken-breast",
        "beans-black", "whey-protein", "banana"]


def test_one_line_with_two_foods_becomes_two_items():
    d = parse_diet_text("ALMOÇO\n100g de arroz\nsalada de alface e tomate")
    ids = [i["food_id"] for i in itens(d)]
    assert "lettuce" in ids and "tomato" in ids


@pytest.mark.parametrize("bad", ["", "   ", "\n\n"])
def test_empty_text_is_rejected(bad):
    with pytest.raises(ValueError):
        parse_diet_text(bad)


def test_text_without_food_is_rejected():
    with pytest.raises(ValueError):
        parse_diet_text("bom dia, quanto custa a consultoria?")


def test_oversized_text_is_rejected():
    with pytest.raises(ValueError):
        parse_diet_text("100g de arroz\n" * (MAX_IMPORT_CHARS // 10))


# --- quantidades ----------------------------------------------------------------------

@pytest.mark.parametrize("linha,gramas", [
    ("150g de arroz branco", 150),
    ("150 g de arroz branco", 150),
    ("1,5 kg de arroz branco", 1500),
    ("200ml de leite desnatado", 200),
    ("50 gramas de aveia", 50),
])
def test_mass_and_volume_are_exact(linha, gramas):
    item = itens(parse_diet_text("ALMOÇO\n" + linha))[0]
    assert item["grams"] == gramas
    assert item["estimated"] is False
    assert REVIEW_ESTIMATED_PORTION not in item["review_reasons"]


@pytest.mark.parametrize("linha,gramas", [
    ("1 concha de feijão preto", 80),
    ("2 colheres de sopa de aveia", 30),
    ("1 scoop de whey", 30),
    ("2 ovos", 100),
    ("1 banana", 100),
    ("1 fatia de pão integral", 25),
])
def test_household_measures_are_converted_but_flagged_as_estimates(linha, gramas):
    item = itens(parse_diet_text("LANCHE\n" + linha))[0]
    assert item["grams"] == gramas
    assert item["estimated"] is True
    assert REVIEW_ESTIMATED_PORTION in item["review_reasons"]


def test_olive_oil_spoon_is_not_fifteen_grams():
    item = itens(parse_diet_text("ALMOÇO\n1 colher de sopa de azeite"))[0]
    assert item["food_id"] == "olive-oil"
    assert item["grams"] == 8


def test_missing_quantity_is_flagged_never_invented():
    item = itens(parse_diet_text("JANTAR\nbrócolis"))[0]
    assert item["food_id"] == "broccoli"
    assert item["grams"] is None
    assert REVIEW_QUANTITY_MISSING in item["review_reasons"]
    assert item["macros"] == {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}


def test_parse_quantity_pieces():
    assert parse_quantity("150g de arroz") == (150.0, "g", "arroz")
    assert parse_quantity("arroz")[0] is None


def test_unit_without_known_weight_stays_unresolved():
    assert to_grams(1, "unidade", "broccoli") == (None, False)


# --- matching -------------------------------------------------------------------------

def test_alias_resolves_common_brazilian_writing():
    m = build_matcher()
    for texto, fid in [("frango", "chicken-breast"), ("arroz", "rice-white"),
                       ("feijão", "beans-black"), ("batata doce", "sweet-potato"),
                       ("whey", "whey-protein"), ("pasta de amendoim", "peanut-butter")]:
        assert m.match(texto)[0] == fid, texto


def test_word_order_variation_matches():
    assert build_matcher().match("frango grelhado peito")[0] == "chicken-breast"


def test_food_outside_the_catalog_is_never_invented():
    d = parse_diet_text("JANTAR\n100g de bacalhau à lagareiro")
    item = itens(d)[0]
    assert item["food_id"] is None
    assert REVIEW_FOOD_UNMATCHED in item["review_reasons"]
    assert unmatched_names(d) == ["bacalhau à lagareiro"]
    assert validate_draft(d)  # bloqueia a ativação


def test_resolution_fills_the_food_and_recomputes_grams_for_units():
    d = parse_diet_text("LANCHE\n2 unidades de bacalhau à lagareiro")
    d = apply_resolution(d, {"bacalhau à lagareiro": "eggs-whole"}, "ai", "ai_suggested")
    item = itens(d)[0]
    assert item["food_id"] == "eggs-whole"
    assert item["grams"] == 100          # 2 x 50 g, agora que o alimento é conhecido
    assert item["needs_review"] is True  # veio da IA: pede confirmação


def test_resolution_ignores_food_outside_the_catalog():
    d = parse_diet_text("JANTAR\n100g de bacalhau à lagareiro")
    d = apply_resolution(d, {"bacalhau à lagareiro": "nao-existe"}, "ai", "ai_suggested")
    assert itens(d)[0]["food_id"] is None


# --- macros ---------------------------------------------------------------------------

def test_item_macros_come_from_the_catalog_table():
    d = parse_diet_text("ALMOÇO\n100g de peito de frango")
    macros = itens(d)[0]["macros"]
    frango = FOOD_INDEX["chicken-breast"]
    assert macros["kcal"] == pytest.approx(frango["kcal"], abs=1)
    assert macros["protein_g"] == pytest.approx(frango["protein_g"], abs=0.5)


def test_double_the_grams_doubles_the_macros():
    um = itens(parse_diet_text("ALMOÇO\n100g de arroz branco"))[0]["macros"]
    dois = itens(parse_diet_text("ALMOÇO\n200g de arroz branco"))[0]["macros"]
    assert dois["kcal"] == pytest.approx(um["kcal"] * 2, abs=2)


def test_meal_and_daily_totals_are_the_sum_of_the_items():
    d = parse_diet_text(DIETA)
    soma_kcal = sum(i["macros"]["kcal"] for i in itens(d))
    assert d["daily_totals"]["kcal"] == pytest.approx(soma_kcal, abs=1)
    for meal in d["meals"]:
        assert meal["totals"]["kcal"] == pytest.approx(
            sum(i["macros"]["kcal"] for i in meal["items"]), abs=1)


def test_daily_totals_are_realistic_for_a_real_diet():
    d = parse_diet_text(DIETA)
    assert 800 < d["daily_totals"]["kcal"] < 3500
    assert d["daily_totals"]["protein_g"] > 50


# --- conversão para o formato do plano existente ---------------------------------------

def test_draft_converts_to_the_shape_generate_daily_plan_produces():
    d = parse_diet_text("ALMOÇO\n150g de arroz branco\n120g de peito de frango")
    plan = draft_to_plan(d)
    assert set(plan) >= {"meals", "daily_totals", "targets", "source"}
    meal = plan["meals"][0]
    assert set(meal) >= {"name", "target_cal", "target_protein", "target_fat", "foods"}
    food = meal["foods"][0]
    # mesmas chaves que build_food_item entrega no plano gerado
    assert set(food) >= {"food_id", "grams", "food"}


def test_foods_with_a_unit_carry_the_display_fields_like_the_generated_plan():
    """Ovo tem unit_grams no catálogo, então o item sai com "2 ovos" para exibição —
    exatamente como no plano gerado pelo motor."""
    d = parse_diet_text("CAFÉ DA MANHÃ\n2 ovos")
    food = draft_to_plan(d)["meals"][0]["foods"][0]
    assert food["display_quantity"] == 2
    assert "ovo" in food["display_unit"]


def test_unresolved_items_never_reach_the_activated_plan():
    d = parse_diet_text("ALMOÇO\n150g de arroz branco\nbrócolis")
    plan = draft_to_plan(d)
    assert [f["food_id"] for f in plan["meals"][0]["foods"]] == ["rice-white"]

"""FORGE Nutrition Engine v1.2 — Final calibration.
Goal-directional substitution, daily impact, protein distribution."""
import json, random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set, Union

ROOT = Path(__file__).parent
with open(ROOT / "foods.json", encoding="utf-8") as f:
    FOODS = json.load(f)
FOOD_INDEX = {f["id"]: f for f in FOODS}
FOODS_BY_CAT = {}
FOODS_BY_ROLE = {}
for f in FOODS:
    FOODS_BY_CAT.setdefault(f["category"], []).append(f["id"])
    for r in f.get("roles", []):
        FOODS_BY_ROLE.setdefault(r, []).append(f["id"])
R = random.Random()

FORGE_COACH_METHODOLOGY = {
    "engine_version": "1.2", "coach_version": "v1.2-forge-brazilian",
    "bmr_formula": "mifflin_st_jeor",
    "protein_range_g_per_kg": {"fat_loss": [2.0, 2.4], "maintenance": [1.6, 2.0], "muscle_gain": [1.8, 2.2]},
    "fat_range_g_per_kg": {"fat_loss": [0.8, 1.0], "maintenance": [0.8, 1.2], "muscle_gain": [0.8, 1.2]},
    "fat_min_pct": 0.15,
    "deficit_pct": 0.80, "surplus_pct": 1.12, "calorie_tolerance_pct": 0.05,
    # Safety floor for the more-aggressive-deficit check in calculate_goal_calories: a
    # profile only gets pushed to daily_guardrails.fat_loss's min_total_kcal_pct floor
    # when the residual carb after protein+fat still clears this per-kg minimum — a
    # widely-used floor for avoiding a crash-diet-level carb residual, not a fixed gram
    # number applied to every athlete (it still scales with bodyweight).
    "min_carb_g_per_kg_aggressive_deficit": 1.5,
    # -- Intensidades de emagrecimento -------------------------------------------------
    # Escolha explicita do usuario. Antes disso, calculate_goal_calories decidia sozinha
    # entre 20% e 30% de deficit pelo residuo de carboidrato, sem o atleta saber. Perfis
    # sem "intensity" continuam no caminho legado (ver resolve_cut_protocol) para nao
    # mudar o alvo calorico de quem ja tem plano gerado.
    #
    # leve/moderado: deficit percentual; carboidrato segue sendo o macro residual.
    # agressivo: protocolo low-carb de verdade — o carboidrato vira TETO (nao residuo) e
    # a gordura passa a fechar a conta calorica. Sem isso "agressivo" seria so tirar
    # algumas gramas de carbo, que e exatamente o que este produto nao quer.
    "cutting_intensity": {
        "leve": {
            "label": "Leve", "kcal_pct": 0.875, "protein_g_per_kg": 2.0,
            "carb_mode": "residual",
            "description": "Emagrecimento gradual, com maior flexibilidade alimentar e melhor preservacao do desempenho.",
        },
        "moderado": {
            "label": "Moderado", "kcal_pct": 0.825, "protein_g_per_kg": 2.2,
            "carb_mode": "residual", "recommended": True,
            "description": "Reducao mais acelerada, equilibrando resultado, desempenho e aderencia.",
        },
        "agressivo": {
            "label": "Agressivo/Atleta", "kcal_pct": 0.70, "protein_g_per_kg": 2.4,
            "carb_mode": "capped",
            "carb_target_g": 35, "carb_min_g": 20, "carb_max_g": 50,
            # Teto por densidade: 12 g de carbo por 100 g exclui arroz, pao, massa, aveia,
            # tapioca, mandioca, feijoes e frutas densas, e mantem vegetais folhosos,
            # proteinas magras e gorduras. O carbo residual dos alimentos permitidos
            # continua sendo contabilizado no total do dia.
            "max_food_carb_g_per_100g": 12.0,
            "advanced": True,
            "description": "Protocolo avancado de cutting com carboidratos extremamente reduzidos, proteina elevada e estrategia alimentar rigorosa.",
            "warning": "Protocolo extremo e temporario. Pode reduzir energia, desempenho no treino, recuperacao e hidratacao.",
        },
    },
    "cutting_intensity_default": "moderado",
    "cut_protocol_version": "cut-v1",
    "macro_tolerance_g": {"protein": 5, "carbs": 10, "fat": 5},
    "goal_directional_tolerance": {
        # allow_overshoot_pct for fat_loss matches the same 12% calorie-equivalence
        # tolerance recalculate_substitution_portion already uses elsewhere in this
        # engine — a same-role substitution (tilapia <-> frango, resized to the same
        # protein target) isn't the athlete deliberately eating more, it's a real,
        # unavoidable density difference between foods; the whole-day guardrail
        # (daily_guardrails.fat_loss) is what actually protects the deficit.
        "fat_loss": {"allow_undershoot_pct": 0.25, "allow_overshoot_pct": 0.12},
        "maintenance": {"allow_undershoot_pct": 0.08, "allow_overshoot_pct": 0.08},
        "muscle_gain": {"allow_undershoot_pct": 0.05, "allow_overshoot_pct": 0.25},
    },
    "daily_guardrails": {
        "fat_loss": {"min_total_kcal_pct": 0.70, "max_total_kcal_pct": 0.90, "min_protein_g_per_kg": 1.8, "min_fat_g_per_kg": 0.6},
        "maintenance": {"min_total_kcal_pct": 0.90, "max_total_kcal_pct": 1.05, "min_protein_g_per_kg": 1.4, "min_fat_g_per_kg": 0.7},
        "muscle_gain": {"min_total_kcal_pct": 1.02, "max_total_kcal_pct": 1.15, "min_protein_g_per_kg": 1.6, "min_fat_g_per_kg": 0.7},
    },
    "meal_distribution": {
        3: [0.30, 0.35, 0.35], 4: [0.25, 0.30, 0.20, 0.25],
        5: [0.25, 0.18, 0.22, 0.12, 0.23], 6: [0.20, 0.18, 0.18, 0.10, 0.14, 0.20],
    },
    "meal_names": {
        3: ["Cafe da manha", "Almoco", "Jantar"],
        4: ["Cafe da manha", "Almoco", "Lanche", "Jantar"],
        5: ["Cafe da manha", "Lanche manha", "Almoco", "Lanche tarde", "Jantar"],
        6: ["Cafe da manha", "Lanche", "Almoco", "Pre-treino", "Pos-treino", "Jantar"],
    },
    "portion_limits": {"PROTEIN": [50, 300], "CARBOHYDRATE": [50, 350], "FAT": [5, 40],
                       "FRUIT": [80, 350], "VEGETABLE": [80, 400], "DAIRY": [100, 300], "LEGUME": [50, 250], "MIXED": [50, 300]},
    "min_protein_per_meal_g": 10, "min_fat_per_meal_g": 3,
    "meal_role_kcal_share_cap": {"primary_protein": 0.65, "fat_source": 0.30},
    # Coach anchor floor (not a ceiling): primary_protein claims at least this fraction
    # of the meal's OWN calorie budget too, not just the bare grams its protein macro
    # target implies — a lean, low-density protein (peixe/frango) still gets a natural,
    # substantial portion instead of shrinking to a bare-minimum "protein math" figure
    # while carb/vegetal fill the rest of the meal.
    "primary_protein_anchor_kcal_share": 0.325,
    # Daily protein distribution (not a single-meal solve): a solid meat/fish primary_
    # protein should stay within a real single-plate reference (150-250g) rather than
    # concentrate a whole day's protein deficit into one oversized portion — the day's
    # protein need should spread across meals/sources instead. Applies only to
    # MEAT_FISH_MAIN_IDS; eggs/whey/plant proteins are unaffected.
    "meat_fish_single_meal_max_g": 250,
    "carb_hierarchy": {"tier_1": ["potato","sweet-potato"], "tier_2": ["cassava","rice-white","rice-brown"], "tier_3_contextual": ["rice-flour"]},
    "carb_meal_context": {
        "breakfast": ["oats","tapioca","rice-flour","corn-flour","sweet-potato"],
        "lunch": ["potato","sweet-potato","cassava","rice-white","rice-brown"],
        "dinner": ["potato","sweet-potato","cassava","rice-white","rice-brown"],
        "snack": ["oats","tapioca","rice-flour","banana","papaya","sweet-potato"],
        "pre_workout": ["banana","oats","tapioca","rice-white","sweet-potato"],
        "post_workout": ["rice-white","potato","sweet-potato","tapioca","banana"],
    },
    "methodology_exclude_default": ["bread-whole","bread-white","pasta","pasta-whole"],
    "satiety_weight_by_goal": {"fat_loss": 3.0, "maintenance": 1.0, "muscle_gain": 0.3},
    "satiety_bonus": {"HIGH": 20, "MEDIUM": 10, "LOW": 0},
    "meal_role_scores": {"primary_protein": 50, "primary_carb": 40, "vegetable": 20,
                         "fruit": 15, "dairy": 15, "fat_source": 12, "legume": 10,
                         "secondary_protein": 8, "recipe_component": 0},
    "max_same_protein_per_day": 2,
    # A food's own comfortable/hard_max (foods.json) always wins when present; these are
    # only the fallback for a food that somehow lacks per-food values.
    "portion_fallback_multiplier": {"comfortable": 1.0, "hard_max": 1.3},
    # A real food item rarely lands below this many kcal (a 50g floor portion of almost
    # anything already clears it). Used to cap how many *optional* template roles a small
    # meal can afford before each one's minimum floor starts summing past the meal's own
    # target_cal — the mechanism that produced 4-item 137kcal pre-workout snacks.
    "min_kcal_per_meal_item": 90,
    # Guided flow (item: MEAL_ARCHETYPES): an archetype option is never offered to the
    # athlete below this coherence bar — same bar the real_meal_composition test suite
    # already holds every generated meal to.
    "min_archetype_coherence": 55,
    # Preference bonus (USER_PREFERENCES) is ranking-only and deliberately small next to
    # methodology-driven score components (30-150+) — it can reorder within the already-
    # guardrail-filtered set, never resurrect an excluded food or bury a required one.
    "preference_bonus_cap": 15,
    "redistribution_cap_multiplier": 1.8,
}

# FORGE NUTRITION DNA — food_families.py-equivalent: named groups of concrete food IDs
# that reflect the coach's real method, not raw nutrient category. "food availability !=
# meal suitability" — e.g. tuna-can is a real protein but never belongs to the LEAN_
# PROTEIN_SOLID family a lunch/dinner combo draws from; it lives in QUICK_PROTEIN instead
# (snack-appropriate, matching its own 'snack'/'quick' tags in foods.json). Every family
# is additive over the existing SUB_GROUPS/SUB_TIER substitution tiers below — this is a
# separate, meal-composition-time concept, not a replacement for the substitution logic.
FOOD_FAMILIES = {
    "LEAN_PROTEIN_SOLID": ["chicken-breast", "beef-grill", "tilapia", "pork-loin", "salmon",
                           "chicken-thigh", "beef-ground", "tofu", "soy-protein"],
    "QUICK_PROTEIN": ["tuna-can", "whey-protein", "cheese-cottage", "yogurt-greek"],
    "EGG_FAMILY": ["eggs-whole", "egg-whites"],
    "OMELET_FAMILY": ["chicken-egg-omelet"],
    "FAST_PROTEIN": ["whey-protein"],
    "BREAKFAST_PROTEIN": ["eggs-whole", "egg-whites", "whey-protein", "chicken-egg-omelet"],
    "POST_PRE_PROTEIN": ["chicken-breast", "beef-grill", "tilapia", "pork-loin", "salmon",
                         "chicken-thigh", "beef-ground", "whey-protein"],
    "MAIN_CARB": ["rice-white", "potato", "sweet-potato", "cassava", "rice-brown"],
    "PORRIDGE_CARB": ["oats", "rice-flour"],
    "RICE_FLOUR_FAMILY": ["rice-flour"],
    "BREAD_FAMILY": ["bread-whole", "bread-white"],
    "FRUIT_FAMILY": ["banana", "apple", "papaya", "orange", "watermelon", "strawberry", "grapes", "mango"],
    "VEGETABLE_FAMILY": ["broccoli", "spinach", "lettuce", "tomato", "carrot", "zucchini",
                         "green-beans", "eggplant", "pumpkin", "beetroot"],
    "FAT_FAMILY": ["olive-oil", "avocado", "peanuts", "brazil-nuts", "peanut-butter"],
}

# Solid meat/fish primary_protein sources (item: daily protein distribution) — the
# animal-protein subset of LEAN_PROTEIN_SOLID/POST_PRE_PROTEIN, excluding plant proteins
# (tofu/soy-protein) which don't carry the "carne/peixe numa unica refeicao" concern.
MEAT_FISH_MAIN_IDS = {"chicken-breast", "beef-grill", "tilapia", "pork-loin", "salmon",
                      "chicken-thigh", "beef-ground"}

# REAL_MEAL_COMPOSITION — explicit roles per meal, so a meal is built from a small set of
# culinarily coherent slots instead of a solver free to inflate whichever single food
# closes the macro fastest. "required" roles must be filled when candidates exist;
# optional roles fill in only when they earn their place (variety, protein-compound need,
# or leftover calorie budget) — see generate_meal() / _needs_secondary_protein(). This is
# the always-available FALLBACK used by the legacy one-shot /generate endpoint and
# whenever no MEAL_COMBOS entry survives the feasibility guardrail for an athlete — so it
# carries the same DNA-approved families as the combos below (item 20: no silent fallback
# reintroducing "atum at lunch" or a floating optional legume with no combo identity).
MEAL_TEMPLATES = {
    "breakfast": [
        {"role": "primary_protein", "category": "PROTEIN", "required": True, "family": "BREAKFAST_PROTEIN"},
        {"role": "secondary_protein", "category": "PROTEIN", "required": False},
        {"role": "primary_carb", "category": "CARBOHYDRATE", "required": True},
        {"role": "fruit", "category": "FRUIT", "required": False, "family": "FRUIT_FAMILY"},
        {"role": "fat_source", "category": "FAT", "required": False, "family": "FAT_FAMILY"},
    ],
    "lunch": [
        {"role": "primary_protein", "category": "PROTEIN", "required": True, "family": "LEAN_PROTEIN_SOLID"},
        {"role": "primary_carb", "category": "CARBOHYDRATE", "required": True, "family": "MAIN_CARB"},
        {"role": "vegetable", "category": "VEGETABLE", "required": True, "family": "VEGETABLE_FAMILY"},
        {"role": "fat_source", "category": "FAT", "required": False, "family": "FAT_FAMILY"},
    ],
    "dinner": [
        {"role": "primary_protein", "category": "PROTEIN", "required": True, "family": "LEAN_PROTEIN_SOLID"},
        {"role": "primary_carb", "category": "CARBOHYDRATE", "required": True, "family": "MAIN_CARB"},
        {"role": "vegetable", "category": "VEGETABLE", "required": True, "family": "VEGETABLE_FAMILY"},
        {"role": "fat_source", "category": "FAT", "required": False, "family": "FAT_FAMILY"},
    ],
    "snack": [
        {"role": "primary_protein", "category": "PROTEIN", "required": True, "family": "QUICK_PROTEIN"},
        {"role": "primary_carb", "category": "CARBOHYDRATE", "required": False, "family": "PORRIDGE_CARB"},
        {"role": "fruit", "category": "FRUIT", "required": False, "family": "FRUIT_FAMILY"},
    ],
    "pre_workout": [
        {"role": "primary_carb", "category": "CARBOHYDRATE", "required": True},
        {"role": "fruit", "category": "FRUIT", "required": False, "family": "FRUIT_FAMILY"},
        {"role": "primary_protein", "category": "PROTEIN", "required": False, "family": "POST_PRE_PROTEIN"},
    ],
    "post_workout": [
        {"role": "primary_protein", "category": "PROTEIN", "required": True, "family": "POST_PRE_PROTEIN"},
        {"role": "primary_carb", "category": "CARBOHYDRATE", "required": True},
        {"role": "fruit", "category": "FRUIT", "required": False, "family": "FRUIT_FAMILY"},
    ],
}

# FORGE NUTRITION DNA — MEAL_COMBOS: the real unit of meal composition. A meal is never
# assembled by picking independent role-slots from a wide category — it's built from one
# of these named, whole combinations (MACROS AJUSTAM A REFEIÇÃO, MACROS NÃO INVENTAM A
# REFEIÇÃO). Deliberately small: a handful of strong, real combos observed in the coach's
# actual method, not dozens of synthetic ones — quality over quantity, and the model below
# (meal_types + components) leaves room to grow the library later without touching engine
# code. Every component still flows through the unchanged generate_meal() /
# calculate_meal_portions() / calculate_meal_coherence_score() pipeline; get_meal_
# archetype_options() is what turns a combo into 2-5 real, sized, guardrail-checked
# options for one meal slot — MEAL_TEMPLATES remains the always-viable fallback whenever
# no combo below survives an athlete's restrictions for that slot.
MEAL_COMBOS = [
    {"id": "forge_oats_whey_banana", "label": "Mingau FORGE", "meal_types": ["breakfast", "snack"],
     "components": [
         {"role": "primary_carb", "category": "CARBOHYDRATE", "family": "PORRIDGE_CARB", "required": True},
         {"role": "primary_protein", "category": "PROTEIN", "family": "FAST_PROTEIN", "required": True},
         {"role": "fruit", "category": "FRUIT", "family": "FRUIT_FAMILY", "required": False},
     ]},
    {"id": "forge_eggs_classic", "label": "Clássico FORGE", "meal_types": ["breakfast"],
     "components": [
         {"role": "primary_protein", "category": "PROTEIN", "family": "EGG_FAMILY", "required": True},
         {"role": "secondary_protein", "category": "PROTEIN", "required": False},
         {"role": "primary_carb", "category": "CARBOHYDRATE", "family": "PORRIDGE_CARB", "required": False},
         {"role": "fruit", "category": "FRUIT", "family": "FRUIT_FAMILY", "required": False},
     ]},
    {"id": "forge_bread_eggs_whey", "label": "Pão e ovos", "meal_types": ["breakfast"],
     "components": [
         {"role": "primary_carb", "category": "CARBOHYDRATE", "family": "BREAD_FAMILY", "required": True},
         {"role": "primary_protein", "category": "PROTEIN", "family": "EGG_FAMILY", "required": True},
         {"role": "primary_protein", "category": "PROTEIN", "family": "FAST_PROTEIN", "required": True},
     ]},
    {"id": "forge_omelete", "label": "Omelete FORGE", "meal_types": ["breakfast", "snack"],
     "components": [
         {"role": "primary_protein", "category": "PROTEIN", "family": "OMELET_FAMILY", "required": True},
         {"role": "primary_carb", "category": "CARBOHYDRATE", "family": "MAIN_CARB", "required": False},
     ]},
    {"id": "forge_solid_meal", "label": "Refeição sólida", "meal_types": ["lunch", "dinner", "post_workout"],
     "components": [
         {"role": "primary_protein", "category": "PROTEIN", "family": "LEAN_PROTEIN_SOLID", "required": True},
         {"role": "primary_carb", "category": "CARBOHYDRATE", "family": "MAIN_CARB", "required": True},
         {"role": "vegetable", "category": "VEGETABLE", "family": "VEGETABLE_FAMILY", "required": True},
         {"role": "fat_source", "category": "FAT", "family": "FAT_FAMILY", "required": False},
     ]},
    {"id": "forge_postwork_fruit", "label": "Pós-treino com fruta", "meal_types": ["post_workout"],
     "components": [
         {"role": "primary_protein", "category": "PROTEIN", "family": "LEAN_PROTEIN_SOLID", "required": True},
         {"role": "primary_carb", "category": "CARBOHYDRATE", "family": "MAIN_CARB", "required": True},
         {"role": "fruit", "category": "FRUIT", "family": "FRUIT_FAMILY", "required": False},
     ]},
    {"id": "forge_prework_meat_carb_fruit", "label": "Pré-treino completo", "meal_types": ["pre_workout"],
     "components": [
         {"role": "primary_protein", "category": "PROTEIN", "family": "LEAN_PROTEIN_SOLID", "required": True},
         {"role": "primary_carb", "category": "CARBOHYDRATE", "family": "MAIN_CARB", "required": True},
         {"role": "fruit", "category": "FRUIT", "family": "FRUIT_FAMILY", "required": False},
     ]},
    {"id": "forge_prework_riceflour_whey", "label": "Pré-treino rápido", "meal_types": ["pre_workout"],
     "components": [
         {"role": "primary_carb", "category": "CARBOHYDRATE", "family": "RICE_FLOUR_FAMILY", "required": True},
         {"role": "primary_protein", "category": "PROTEIN", "family": "FAST_PROTEIN", "required": True},
     ]},
]

SUB_GROUPS = {
    "CARB": ["potato","sweet-potato","cassava","rice-white","rice-brown","tapioca","oats","corn-flour"],
    "LEAN_PROTEIN": ["chicken-breast","tilapia","tuna-can","egg-whites","pork-loin","beef-grill","tofu","soy-protein"],
    "FATTIER_PROTEIN": ["chicken-thigh","beef-ground","salmon","eggs-whole"],
    "FAT": ["olive-oil","peanuts","brazil-nuts","peanut-butter","avocado"],
    "DAIRY": ["milk-whole","milk-skim","yogurt-natural","yogurt-greek","cheese-mozzarella","cheese-cottage"],
    "FRUIT": ["banana","apple","papaya","orange","watermelon","strawberry","grapes","mango"],
    "LEGUME": ["beans-black","beans-carioca","lentils","chickpeas"],
    "VEGETABLE": ["broccoli","spinach","lettuce","tomato","carrot","zucchini","green-beans","eggplant","pumpkin","beetroot"],
}
SUB_TIER = {
    "potato": ["sweet-potato","cassava","rice-white","rice-brown"],
    "sweet-potato": ["potato","cassava","rice-white","rice-brown"],
    "cassava": ["potato","sweet-potato","rice-white","rice-brown"],
    "rice-white": ["potato","sweet-potato","cassava","rice-brown"],
    "rice-brown": ["potato","sweet-potato","cassava","rice-white"],
    "chicken-breast": ["beef-grill","tilapia","pork-loin","chicken-thigh"],
    "beef-grill": ["chicken-breast","tilapia","pork-loin","chicken-thigh"],
    "tilapia": ["chicken-breast","beef-grill","pork-loin"],
    "eggs-whole": ["egg-whites","chicken-breast","beef-grill"],
    "egg-whites": ["eggs-whole","chicken-breast","beef-grill"],
    "chicken-thigh": ["chicken-breast","beef-ground","salmon"],
    "beef-ground": ["chicken-breast","chicken-thigh","salmon"],
}

VEG_ROTATION = ["broccoli","spinach","green-beans","zucchini","tomato","carrot","pumpkin","beetroot"]
LEGUME_ROTATION = ["lentils","beans-black","beans-carioca","chickpeas"]
FRUIT_ROTATION = ["banana","papaya","apple","orange","strawberry","mango"]

_DAIRY_IDS = {f["id"] for f in FOODS if f.get("category") == "DAIRY"} | {"whey-protein", "rice-cream-whey"}
_GLUTEN_IDS = {f["id"] for f in FOODS
               if f.get("category") in ("CARBOHYDRATE", "MIXED") and "gluten_free" not in f.get("tags", [])}
ALLERGY_EXCLUDE_IDS = {
    "lactose": _DAIRY_IDS, "dairy": _DAIRY_IDS, "milk": _DAIRY_IDS,
    "gluten": _GLUTEN_IDS, "wheat": _GLUTEN_IDS,
    "peanut": {"peanuts", "peanut-butter"},
    "nuts": {"peanuts", "peanut-butter", "brazil-nuts"},
    "tree_nuts": {"brazil-nuts"},
    "soy": {"tofu", "soy-protein"},
    "egg": {"eggs-whole", "egg-whites", "chicken-egg-omelet"},
    "eggs": {"eggs-whole", "egg-whites", "chicken-egg-omelet"},
    "fish": {"tilapia", "salmon", "tuna-can"},
    "shellfish": set(),
}

# A primary protein this dense of a partner works with, when the meal's protein target
# outgrows what the primary can comfortably deliver alone (item 4 — protein composta).
SECONDARY_PROTEIN_PAIRS = {
    "eggs-whole": ["egg-whites"], "egg-whites": ["eggs-whole"],
    "chicken-breast": ["whey-protein", "cheese-cottage"],
    "tilapia": ["whey-protein"], "salmon": ["whey-protein"],
    "beef-grill": ["whey-protein"], "beef-ground": ["whey-protein"],
    "pork-loin": ["whey-protein"], "chicken-thigh": ["whey-protein"],
    "tuna-can": ["whey-protein", "cheese-cottage"],
    "tofu": ["whey-protein", "soy-protein"], "oats": ["whey-protein", "yogurt-greek"],
    "tapioca": ["whey-protein"], "rice-white": ["whey-protein"],
    "sweet-potato": ["whey-protein"], "potato": ["whey-protein"],
    "banana": ["whey-protein", "yogurt-greek"],
}


def _portion_limit(food, kind):
    """Per-food comfortable/hard_max (real serving ceilings, item 3) with a category-based
    fallback only for a food that somehow lacks its own values — no duplicated magic
    numbers, the fallback multiplier itself lives in FORGE_COACH_METHODOLOGY."""
    key = "comfortable_portion_g" if kind == "comfortable" else "hard_max_portion_g"
    val = food.get(key)
    if val:
        return val
    lo, hi = FORGE_COACH_METHODOLOGY["portion_limits"].get(food.get("category", "PROTEIN"), [50, 250])
    mult = FORGE_COACH_METHODOLOGY["portion_fallback_multiplier"][kind]
    return hi * mult if kind == "hard_max" else hi * FORGE_COACH_METHODOLOGY["portion_fallback_multiplier"]["comfortable"]


def _protein_hard_max(fid, food):
    """hard_max for a primary_protein item, capped further for solid meat/fish (item:
    daily protein distribution) so a single meal never concentrates 280g+ of carne/peixe
    — the reference stays a real single-plate amount, with any extra daily protein need
    meant to spread across other meals/sources instead."""
    hard_max = _portion_limit(food, "hard_max")
    if fid in MEAT_FISH_MAIN_IDS:
        return min(hard_max, FORGE_COACH_METHODOLOGY["meat_fish_single_meal_max_g"])
    return hard_max


def _snap_to_unit(fid, grams, lo, hi):
    """Portion humanization (item 3): a food with a natural unit (an egg, a clara) is
    never shown — or even calculated — as an arbitrary gram figure like "180g"; it's
    rounded to the nearest whole, human count first (bounded by this slot's own [lo, hi],
    so it never crosses comfortable/hard_max), and that snapped weight is what the rest
    of the meal reconciles against — not a cosmetic label slapped on top of the raw
    number. Foods without a unit_grams pass through unchanged."""
    f = FOOD_INDEX.get(fid, {})
    unit_g = f.get("unit_grams")
    if not unit_g or unit_g <= 0:
        return grams
    qty = max(1, round(grams / unit_g))
    snapped = qty * unit_g
    while snapped > hi and qty > 1:
        qty -= 1
        snapped = qty * unit_g
    while snapped < lo and qty < 50:
        qty += 1
        snapped = qty * unit_g
    return snapped


def _display_fields(fid, grams):
    """Presentation layer for a unit-based food (item 3): "3 ovos" instead of "150g" —
    the engine still calculates and persists in grams throughout; this only adds the
    display_quantity/display_unit the frontend renders instead of the raw gram figure.
    Returns {} for any food without a defined natural unit (the vast majority — grams
    stay the primary display for a carb, a vegetable, a spoon of oil, etc.)."""
    f = FOOD_INDEX.get(fid, {})
    unit_g = f.get("unit_grams")
    if not unit_g or unit_g <= 0:
        return {}
    qty = round(grams / unit_g)
    if qty <= 0:
        return {}
    label = f.get("unit_label_singular") if qty == 1 else f.get("unit_label_plural")
    if not label:
        return {}
    return {"display_quantity": qty, "display_unit": label}


def build_food_item(fid, grams):
    """Single place every meal-food entry is built, so display_quantity/display_unit
    (item 3) show up consistently everywhere a food item is returned — generation,
    guided-flow options, swap-food, choose, confirm — never just some of them."""
    item = {"food_id": fid, "grams": grams, "food": FOOD_INDEX.get(fid, {})}
    item.update(_display_fields(fid, grams))
    return item


def _needs_secondary_protein(primary_fid, target_protein, meal_type=None):
    """True when the primary alone would have to blow past its own ceiling to hit the
    meal's protein target — the exact condition that produced 300g+ egg-white
    breakfasts. A small 5% slack avoids recruiting a helper for a marginal shortfall.

    Breakfast/snack use hard_max (not comfortable) as that ceiling: a single food
    naturally sized up to "3 ovos" or "6 claras" is still simple and human, so a second
    protein food should only be recruited when even that isn't enough — not on every
    moderate target, which was silently pairing eggs-whole+egg-whites (or +whey) far
    more often than a coach actually would ("empilhamento artificial so para fechar
    macros"). Lunch/dinner keep the tighter comfortable-based gate."""
    f = FOOD_INDEX.get(primary_fid)
    if not f or target_protein <= 0:
        return False
    ppg = f.get("protein_g", 0) / max(1, f.get("grams", 100))
    if ppg <= 0:
        return False
    limit_kind = "hard_max" if meal_type in ("breakfast", "snack") else "comfortable"
    max_protein_alone = _portion_limit(f, limit_kind) * ppg
    return target_protein > max_protein_alone * 1.05


def _goal_key(goal):
    gl = (goal or "").lower()
    if "fat" in gl or "perda" in gl: return "fat_loss"
    if "muscle" in gl or "ganho" in gl or "massa" in gl: return "muscle_gain"
    return "maintenance"

def calculate_bmr(w, h, age, sex="male"):
    return 10*w + 6.25*h - 5*age + 5 if str(sex).lower() not in ("f","female","feminino") else 10*w + 6.25*h - 5*age - 161

def calculate_activity_factor(td, al="moderate"):
    lv = {"sedentary":1.1,"light":1.25,"moderate":1.35,"active":1.45,"very_active":1.55}
    return round(lv.get(str(al).lower(),1.35) + min(0.15, td*0.02), 2)

def calculate_tdee(bmr, af): return round(bmr*af, 0)

def calculate_goal_calories(tdee, goal, w=0, protein_g=0, fat_g=0):
    gl = (goal or "").lower()
    if "fat" in gl or "perda" in gl:
        m = FORGE_COACH_METHODOLOGY
        moderate = tdee * m["deficit_pct"]
        if not w:
            return round(moderate, 0)
        # A more aggressive deficit (down to daily_guardrails.fat_loss's own
        # min_total_kcal_pct floor — never below it) is used automatically whenever THIS
        # profile's protein/fat needs leave enough headroom for a real, non-crash carb
        # residual — never a fixed number applied to every user. protein_g/fat_g are
        # already fixed by the methodology's own per-kg minimums (never reduced here),
        # so the extra reduction lands on carbs, which are already the residual macro —
        # fat is deliberately left untouched since it's already at its own range floor.
        guard = m["daily_guardrails"]["fat_loss"]
        aggressive = tdee * guard["min_total_kcal_pct"]
        min_carb_kcal = m["min_carb_g_per_kg_aggressive_deficit"] * w * 4
        residual_at_aggressive = aggressive - protein_g*4 - fat_g*9
        if residual_at_aggressive >= min_carb_kcal:
            return round(aggressive, 0)
        return round(moderate, 0)
    if "maintenance" in gl or "manut" in gl: return round(tdee, 0)
    return round(tdee*1.12, 0)

def calculate_protein_target(w, goal):
    gk = _goal_key(goal)
    return round(w*FORGE_COACH_METHODOLOGY["protein_range_g_per_kg"][gk][0], 1)

def calculate_fat_target(w, goal):
    gk = _goal_key(goal)
    return round(w*FORGE_COACH_METHODOLOGY["fat_range_g_per_kg"][gk][0], 1)

def calculate_carb_target(gc, pg, fg):
    return round(max(0, (gc - pg*4 - fg*9)/4), 1)

def _intensity_key(intensity):
    """Normaliza a intensidade escolhida. Devolve None para perfil legado (sem escolha),
    que segue no caminho automatico antigo de calculate_goal_calories."""
    v = str(intensity or "").strip().lower()
    if not v:
        return None
    if v.startswith("lev") or v == "light":
        return "leve"
    if v.startswith("mod"):
        return "moderado"
    if v.startswith("agr") or v.startswith("atl") or v in ("aggressive", "athlete", "extreme"):
        return "agressivo"
    return None


def resolve_cut_protocol(goal, intensity):
    """Protocolo de emagrecimento efetivo, ou None.

    So existe para fat_loss: 'emagrecimento leve' num bulk nao significa nada, entao a
    intensidade e deliberadamente ignorada nos outros objetivos."""
    if _goal_key(goal) != "fat_loss":
        return None
    key = _intensity_key(intensity)
    if key is None:
        return None
    cfg = FORGE_COACH_METHODOLOGY["cutting_intensity"][key]
    return {"intensity": key,
            "protocol_version": FORGE_COACH_METHODOLOGY["cut_protocol_version"], **cfg}


def carb_ceiling_for(protocol):
    """Teto diario de carboidrato em gramas, ou None quando o carbo e residual."""
    if not protocol or protocol.get("carb_mode") != "capped":
        return None
    return float(protocol["carb_max_g"])


def _targets_for_cut_protocol(bmr, af, tdee, w, protocol):
    m = FORGE_COACH_METHODOLOGY
    guard = m["daily_guardrails"]["fat_loss"]
    pg = round(w * protocol["protein_g_per_kg"], 1)
    kcal = tdee * protocol["kcal_pct"]

    if protocol["carb_mode"] == "capped":
        # Low-carb: o carboidrato e um TETO fixo e a gordura passa a ser o macro residual
        # que fecha a caloria — o inverso do calculo normal.
        cg = float(protocol["carb_target_g"])
        fg = (kcal - pg * 4 - cg * 4) / 9.0
        fat_floor = max(m["fat_min_pct"] * kcal / 9.0, guard["min_fat_g_per_kg"] * w)
        if fg < fat_floor:
            # Preferir subir a caloria a entregar gordura abaixo do piso de seguranca. O
            # teto de carbo e a caracteristica que define o protocolo: nao e ele que cede.
            fg = fat_floor
            kcal = pg * 4 + cg * 4 + fg * 9
    else:
        fg = calculate_fat_target(w, "fat_loss")
        cg = max(0.0, (kcal - pg * 4 - fg * 9) / 4.0)

    pg, fg, cg, kcal = round(pg, 1), round(fg, 1), round(cg, 1), round(kcal, 0)
    return {"bmr": bmr, "tdee": tdee, "activity_factor": af, "goal_calories": kcal,
            "protein_g": pg, "fat_g": fg, "carbs_g": cg,
            "protein_kcal": round(pg * 4), "fat_kcal": round(fg * 9), "carbs_kcal": round(cg * 4),
            # Vai junto no plano persistido (generate_daily_plan devolve targets), entao a
            # intensidade e os parametros do protocolo sobrevivem a refresh e a troca de
            # aparelho sem precisar de colecao nova.
            "cut_protocol": {k: protocol[k] for k in
                             ("intensity", "protocol_version", "label", "kcal_pct",
                              "protein_g_per_kg", "carb_mode")
                             if k in protocol},
            "carb_ceiling_g": carb_ceiling_for(protocol)}


def compute_macro_targets(w, h, age, sex, td, goal, al="moderate", intensity=None):
    bmr = calculate_bmr(w,h,age,sex)
    af = calculate_activity_factor(td,al)
    tdee = calculate_tdee(bmr,af)
    protocol = resolve_cut_protocol(goal, intensity)
    if protocol:
        return _targets_for_cut_protocol(bmr, af, tdee, w, protocol)
    # Caminho legado (perfil sem intensidade escolhida): preservado byte a byte para nao
    # mexer no alvo calorico de quem ja tem plano gerado.
    # protein/fat are computed first — they're driven purely by bodyweight/goal, never by
    # goal_calories — so calculate_goal_calories can check whether THIS profile's own
    # protein+fat minimums leave room for a more aggressive deficit (see above).
    pg = calculate_protein_target(w,goal)
    fg = calculate_fat_target(w,goal)
    gc = calculate_goal_calories(tdee,goal,w,pg,fg)
    cg = calculate_carb_target(gc,pg,fg)
    return {"bmr":bmr,"tdee":tdee,"activity_factor":af,"goal_calories":gc,
            "protein_g":pg,"fat_g":fg,"carbs_g":cg,
            "protein_kcal":round(pg*4),"fat_kcal":round(fg*9),"carbs_kcal":round(cg*4)}

def food_carb_density(food):
    """Gramas de carboidrato por 100 g do alimento."""
    grams = food.get("grams") or 100
    return food.get("carbs_g", 0) * 100.0 / max(1, grams)


def _food_compatible(food, pn, used_ids):
    if food["id"] in set(pn.get("avoid_foods") or []): return False
    # Protocolo low-carb (intensidade agressiva): exclui a fonte densa de carboidrato na
    # origem, em vez de gerar arroz/pao/massa/aveia e tentar consertar na porcao depois.
    # Injetado por generate_daily_plan a partir do protocolo resolvido.
    ceiling = pn.get("_max_food_carb_g_per_100g")
    if ceiling is not None and food_carb_density(food) > ceiling: return False
    for a in (pn.get("allergies") or []):
        if food["id"] in ALLERGY_EXCLUDE_IDS.get(str(a).lower().strip(), set()): return False
    rt = set(pn.get("dietary_restrictions") or [])
    vegetarian_ok_ids = {"eggs-whole","egg-whites","whey-protein","tofu","soy-protein",
        "beans-black","beans-carioca","lentils","chickpeas",
        "yogurt-greek","cheese-cottage","cheese-mozzarella","milk-whole","milk-skim","yogurt-natural"}
    if "vegetarian" in rt and food.get("category")=="PROTEIN" and food["id"] not in vegetarian_ok_ids:
        return False
    # Reuses the same _DAIRY_IDS set the "lactose"/"dairy"/"milk" ALLERGY exclusion
    # already relies on (item: whey-protein/rice-cream-whey were already treated as
    # lactose-containing there but not here — a real inconsistency, now fixed at its one
    # source of truth instead of a second hand-maintained list drifting out of sync).
    if "lactose_free" in rt and food["id"] in _DAIRY_IDS:
        return False
    return True

def _score_food(food, meal_type, pn, goal="maintenance"):
    score = 30; fid = food["id"]; m = FORGE_COACH_METHODOLOGY
    if fid in m.get("methodology_exclude_default",[]): score -= 80
    if fid in set(pn.get("preferred_foods") or []): score += 35
    if fid in set(pn.get("disliked_foods") or []): score -= 80
    if fid in m.get("carb_hierarchy",{}).get("tier_1",[]): score += 25
    if fid in m.get("carb_hierarchy",{}).get("tier_2",[]): score += 15
    ctx = m.get("carb_meal_context",{}).get(meal_type,[])
    if fid in ctx: score += 10
    t3 = m.get("carb_hierarchy",{}).get("tier_3_contextual",[])
    if fid in t3 and meal_type not in ("breakfast","snack"): score -= 30
    gk = _goal_key(goal)
    # Satiety here reflects a whole-food serving's fill factor; a fat_source is used in
    # small, macro-driven amounts (a drizzle of oil, a few slices of avocado), so its
    # satiety tag doesn't represent meal fullness and must not outweigh fat-density
    # (below), or a low-density source like avocado gets picked, caps out on portion
    # limits before reaching the fat target, and reconciliation has to bolt on more fat.
    if "fat_source" not in food.get("roles",[]):
        sat_w = m.get("satiety_weight_by_goal",{}).get(gk, 1.0)
        sat = food.get("satiety","MEDIUM")
        sb = m.get("satiety_bonus",{}).get(sat, 0)
        score += int(sb * sat_w)
    rs = 0
    for r in food.get("roles",[]):
        rs += m.get("meal_role_scores",{}).get(r, 0)
    score += min(rs, 40)
    mt = {"breakfast":["breakfast"],"lunch":["lunch"],"dinner":["dinner"],"snack":["snack","quick"]}
    if any(t in food.get("tags",[]) for t in mt.get(meal_type,[])): score += 12
    if "high_protein" in food.get("tags",[]): score += 10
    if "primary_protein" in food.get("roles",[]) and food.get("kcal",0) > 0:
        score += round((food.get("protein_g",0) / food["kcal"]) * 100)
    if "fat_source" in food.get("roles",[]) and food.get("grams",0) > 0:
        # denser fat sources (oil) can hit a meal's fat target within realistic portion
        # limits; low-density ones (avocado) hit their portion cap before reaching target.
        score += round((food.get("fat_g",0) / food["grams"]) * 20)
    return score

def select_food_for_slot(candidates, role, meal_type, pn, used_ids, goal="maintenance"):
    scored = []
    for fid in candidates:
        f = FOOD_INDEX.get(fid)
        if not f or not _food_compatible(f, pn, used_ids): continue
        scored.append((_score_food(f, meal_type, pn, goal), fid))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored and scored[0][0] > 0 else None

def calculate_meal_portions(food_ids, target_cal, target_protein, target_fat=0, goal="maintenance"):
    """Size the primary_protein and fat_source foods directly from their macro targets
    first (so the meal actually converges on target_protein/target_fat), then split the
    remaining calorie budget across the rest. REAL_MEAL_COMPOSITION (item 3): every food
    is capped at its own comfortable_portion_g first; only if the meal's macro math still
    needs more does a food get pushed toward hard_max_portion_g — which it may never
    cross. A primary_protein short of its target after comfortable prefers handing the
    remainder to a secondary_protein (item 4) over inflating itself past comfortable."""
    portions = {}
    if not food_ids: return portions
    remaining_cal = target_cal
    sized = set()

    kcal_cap = FORGE_COACH_METHODOLOGY["meal_role_kcal_share_cap"]

    protein_fid = next((fid for fid in food_ids
                         if "primary_protein" in FOOD_INDEX.get(fid, {}).get("roles", [])), None)
    secondary_fid = next((fid for fid in food_ids
                           if fid != protein_fid and "secondary_protein" in FOOD_INDEX.get(fid, {}).get("roles", [])), None)
    if protein_fid and target_protein > 0:
        f = FOOD_INDEX.get(protein_fid, {})
        ppg = f.get("protein_g", 0) / max(1, f.get("grams", 100))
        if ppg > 0:
            comfortable = _portion_limit(f, "comfortable")
            hard_max = _protein_hard_max(protein_fid, f)
            lo, _ = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category", "PROTEIN"), [50, 250])
            # without a secondary to hand the remainder to, the primary is allowed up to
            # hard_max (capped further for solid meat/fish — item: daily protein
            # distribution, never one meal absorbing a 280g+ plate) so the protein target
            # isn't silently abandoned; with a secondary present, the primary stops at
            # comfortable and the secondary covers the rest.
            cap = hard_max if not secondary_fid else comfortable
            cpg = f.get("kcal", 100) / max(1, f.get("grams", 100))
            protein_driven = round(target_protein / ppg, -1)
            # Coach anchor: a real, dimensioned priority claim on the meal's OWN calorie
            # budget, not just the bare grams the protein macro alone implies — this is
            # what keeps a lean, low-density protein (peixe/frango) from shrinking to a
            # thin "protein math" portion while carb/vegetal fill the rest of the plate.
            # Still fully target/profile-driven (scales with target_cal, never a fixed
            # number): only ever raises grams above what target_protein itself needed.
            anchor_kcal = target_cal * FORGE_COACH_METHODOLOGY["primary_protein_anchor_kcal_share"]
            anchor_driven = round(anchor_kcal / cpg, -1) if cpg > 0 else 0
            grams = max(lo, min(cap, max(protein_driven, anchor_driven)))
            max_kcal = target_cal * kcal_cap["primary_protein"]
            if cpg > 0 and grams * cpg > max_kcal:
                grams = max(lo, round(max_kcal / cpg, -1))
            grams = _snap_to_unit(protein_fid, grams, lo, cap)
            portions[protein_fid] = grams
            sized.add(protein_fid)
            remaining_cal -= grams * cpg

            if secondary_fid:
                delivered = grams * ppg
                protein_gap = max(0, target_protein - delivered)
                sf = FOOD_INDEX.get(secondary_fid, {})
                spg = sf.get("protein_g", 0) / max(1, sf.get("grams", 100))
                if spg > 0 and protein_gap > 0:
                    s_lo, _ = FORGE_COACH_METHODOLOGY["portion_limits"].get(sf.get("category", "PROTEIN"), [20, 100])
                    s_comfortable = _portion_limit(sf, "comfortable")
                    s_hard_max = _portion_limit(sf, "hard_max")
                    s_grams = max(s_lo, min(s_hard_max, round(protein_gap / spg, -1)))
                    if s_grams > s_comfortable:
                        s_grams = s_comfortable  # never blow the helper's own comfortable either
                    s_grams = _snap_to_unit(secondary_fid, s_grams, s_lo, s_comfortable)
                    s_cpg = sf.get("kcal", 100) / max(1, sf.get("grams", 100))
                    portions[secondary_fid] = s_grams
                    sized.add(secondary_fid)
                    remaining_cal -= s_grams * s_cpg
                else:
                    portions[secondary_fid] = s_lo if spg <= 0 else 0
                    sized.add(secondary_fid)

    fat_fid = next((fid for fid in food_ids
                     if fid not in sized and "fat_source" in FOOD_INDEX.get(fid, {}).get("roles", [])), None)
    if fat_fid and target_fat > 0:
        f = FOOD_INDEX.get(fat_fid, {})
        fpg = f.get("fat_g", 0) / max(1, f.get("grams", 100))
        if fpg > 0:
            hard_max = _portion_limit(f, "hard_max")
            lo, _ = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category", "FAT"), [5, 40])
            grams = max(lo, min(hard_max, round(target_fat / fpg, -1)))
            cpg = f.get("kcal", 100) / max(1, f.get("grams", 100))
            max_kcal = target_cal * kcal_cap["fat_source"]
            if cpg > 0 and grams * cpg > max_kcal:
                grams = max(lo, round(max_kcal / cpg, -1))
            portions[fat_fid] = grams
            sized.add(fat_fid)
            remaining_cal -= grams * cpg

    # Cutting: give vegetables a bigger weighted share of the remaining calorie budget
    # instead of an even split with calorie-dense carbs. Because they're low-density,
    # the same kcal share buys far more mass — bulk/satiety without spending extra
    # calories, and it stays proportionate to whatever budget this profile actually has
    # (no fixed-gram override that could blow a tight cutting budget).
    # Bulking (item 12: "aumentar principalmente capacidade energética dos combos: mais
    # arroz/batata/aveia") — the inverse bias: a big muscle_gain meal's extra calorie
    # share leans into the carb, which comfortably absorbs a large dense portion, rather
    # than pushing a vegetable toward an oversized pile just to hit the same target —
    # aveia+whey+banana stays that combo with more of each, not a random 5th ingredient.
    # Maintenance gets the same carb-first bias as bulking (item 6): with no explicit
    # satiety-first philosophy of its own, letting a dense carb absorb the overflow is
    # the more natural default than pushing carb AND vegetable both toward hard_max
    # together (e.g. "batata 400g + abobrinha 400g" in one plate).
    remaining_ids = [fid for fid in food_ids if fid not in sized]
    gk = _goal_key(goal)

    def _cap_grams(fid, cal_share, cap_kind):
        f = FOOD_INDEX.get(fid, {})
        cpg = f.get("kcal", 100) / max(1, f.get("grams", 100))
        lo, _ = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category", "PROTEIN"), [50, 250])
        cap = _portion_limit(f, cap_kind)
        grams = cal_share / max(0.1, cpg) if cpg > 0 else 100
        return max(lo, min(cap, round(grams, -1)))

    def _kcal_of(fid, grams):
        f = FOOD_INDEX.get(fid, {})
        return grams * (f.get("kcal", 100) / max(1, f.get("grams", 100)))

    comfortable_grams = {}
    if gk == "fat_loss":
        # Cutting: give vegetables a bigger weighted share of the remaining calorie
        # budget instead of an even split with calorie-dense carbs — low-density foods
        # buy far more mass/satiety per kcal, proportionate to whatever budget this
        # profile actually has (no fixed-gram override that could blow a tight budget).
        weights = {fid: (3.0 if FOOD_INDEX.get(fid, {}).get("category") == "VEGETABLE" else 1.0)
                   for fid in remaining_ids}
        total_w = sum(weights.values()) or 1
        for fid in remaining_ids:
            comfortable_grams[fid] = _cap_grams(fid, remaining_cal * (weights[fid] / total_w), "comfortable")
    else:
        # primary_protein -> primary_carb -> vegetables/fruit/legume -> fats (coach
        # hierarchy): primary_carb gets a real, sequential first claim on what's left of
        # the calorie budget — up to its own comfortable portion — before vegetable/
        # fruit/legume see any of it, instead of racing it proportionally (which let
        # both balloon toward comfortable together, e.g. "400g batata + 350g abobrinha"
        # just to close calories). Bulking/maintenance: a big meal's extra calorie share
        # leans into the carb, which comfortably absorbs a large dense portion, rather
        # than pushing a vegetable toward an oversized pile for the same target.
        carb_ids = [fid for fid in remaining_ids if FOOD_INDEX.get(fid, {}).get("category") in ("CARBOHYDRATE", "MIXED")]
        other_ids = [fid for fid in remaining_ids if fid not in carb_ids]
        cal_left = remaining_cal
        for fid in carb_ids:
            comfortable_grams[fid] = _cap_grams(fid, cal_left, "comfortable")
            cal_left -= _kcal_of(fid, comfortable_grams[fid])
        other_w = len(other_ids) or 1
        for fid in other_ids:
            comfortable_grams[fid] = _cap_grams(fid, max(0, cal_left) / other_w, "comfortable")

    # Pass 2: if the comfortable-capped set can't absorb the remaining calorie budget,
    # grow items that still have room up to their hard_max_portion_g — never beyond it.
    # This is what replaces blindly inflating a single food.
    absorbed = sum(_kcal_of(fid, comfortable_grams[fid]) for fid in remaining_ids)
    shortfall = remaining_cal - absorbed
    if shortfall > 20 and remaining_ids:
        if gk == "fat_loss":
            # Deliberately equal weights here (not the veg-boosted Pass 1 weights): the
            # satiety objective (more volume within a comfortable, human portion) was
            # already served in Pass 1. Continuing to funnel the *overflow past
            # comfortable* preferentially into vegetables produces exactly "vegetais
            # utilizados como filler calorico" — two vegetables both pushed toward
            # hard_max for one big cutting meal. Past comfortable, the leftover spreads
            # evenly instead.
            room_ids = [fid for fid in remaining_ids
                        if comfortable_grams[fid] < _portion_limit(FOOD_INDEX.get(fid, {}), "hard_max")]
            room_w = len(room_ids) or 1
            for fid in room_ids:
                extra_grams = (shortfall / room_w) / max(0.1, FOOD_INDEX.get(fid, {}).get("kcal", 100) / max(1, FOOD_INDEX.get(fid, {}).get("grams", 100)))
                hard_max = _portion_limit(FOOD_INDEX.get(fid, {}), "hard_max")
                comfortable_grams[fid] = min(hard_max, round(comfortable_grams[fid] + extra_grams, -1))
        else:
            # Same sequential hierarchy for the overflow: primary_carb claims the whole
            # shortfall (up to ITS hard_max) before vegetable/fruit/legume are pushed
            # past their own comfortable portion at all.
            carb_ids = [fid for fid in remaining_ids if FOOD_INDEX.get(fid, {}).get("category") in ("CARBOHYDRATE", "MIXED")]
            other_ids = [fid for fid in remaining_ids if fid not in carb_ids]
            carb_room = [fid for fid in carb_ids
                         if comfortable_grams[fid] < _portion_limit(FOOD_INDEX.get(fid, {}), "hard_max")]
            room_w = len(carb_room) or 1
            for fid in carb_room:
                extra_grams = (shortfall / room_w) / max(0.1, FOOD_INDEX.get(fid, {}).get("kcal", 100) / max(1, FOOD_INDEX.get(fid, {}).get("grams", 100)))
                hard_max = _portion_limit(FOOD_INDEX.get(fid, {}), "hard_max")
                comfortable_grams[fid] = min(hard_max, round(comfortable_grams[fid] + extra_grams, -1))
            absorbed_after_carb = sum(_kcal_of(fid, comfortable_grams[fid]) for fid in remaining_ids)
            remaining_shortfall = remaining_cal - absorbed_after_carb
            if remaining_shortfall > 20:
                other_room = [fid for fid in other_ids
                              if comfortable_grams[fid] < _portion_limit(FOOD_INDEX.get(fid, {}), "hard_max")]
                other_room_w = len(other_room) or 1
                for fid in other_room:
                    extra_grams = (remaining_shortfall / other_room_w) / max(0.1, FOOD_INDEX.get(fid, {}).get("kcal", 100) / max(1, FOOD_INDEX.get(fid, {}).get("grams", 100)))
                    hard_max = _portion_limit(FOOD_INDEX.get(fid, {}), "hard_max")
                    comfortable_grams[fid] = min(hard_max, round(comfortable_grams[fid] + extra_grams, -1))

    for fid in remaining_ids:
        portions[fid] = comfortable_grams[fid]
    return portions

def _food_macros(fid, grams):
    f = FOOD_INDEX.get(fid, {})
    fac = grams/max(1, f.get("grams",100))
    return round(f.get("kcal",0)*fac), round(f.get("protein_g",0)*fac,1), round(f.get("carbs_g",0)*fac,1), round(f.get("fat_g",0)*fac,1)

def _meal_totals(meal):
    k,p,c,f = 0,0,0,0
    for item in meal.get("foods",[]):
        mk,mp,mc,mf = _food_macros(item["food_id"], item.get("grams",100))
        k+=mk; p+=mp; c+=mc; f+=mf
    return k,p,c,f

def _infer_meal_type(meal_name):
    tn = meal_name.lower()
    if "pre" in tn and "trein" in tn: return "pre_workout"
    if "pos" in tn and "trein" in tn: return "post_workout"
    if "cafe" in tn or "manha" in tn: return "breakfast"
    if "lanche" in tn or "tarde" in tn or "snack" in tn: return "snack"
    if "jantar" in tn: return "dinner"
    return "lunch"


def generate_meal(meal_name, meal_type, target_cal, target_protein, target_fat,
                  pn, used_food_ids, goal="maintenance", daily_used_proteins=None,
                  day_index=0, is_later_meal=False, template_override=None):
    mt = _infer_meal_type(meal_name)

    # FORGE NUTRITION DNA: build from the named combo for this meal type instead of an
    # ad-hoc role list, so every meal stays a small, culinarily coherent identity. A
    # caller building alternative MEAL_COMBOS options for the same meal slot passes its
    # own component list here instead of the single default template — everything
    # downstream (selection, sizing, coherence scoring) is unchanged.
    template = template_override if template_override is not None else MEAL_TEMPLATES.get(mt, MEAL_TEMPLATES["lunch"])
    total_roles = [(r["role"], r["category"], r.get("required", False), r.get("family")) for r in template]
    # Cutting: a second vegetable (like a real plate — main veg + salad) adds
    # near-free volume/satiety without meaningfully spending the calorie budget.
    # Only applies to the default template — a custom combo defines its own components.
    if template_override is None and mt in ("lunch", "dinner") and _goal_key(goal) == "fat_loss":
        total_roles.append(("vegetable", "VEGETABLE", True, "VEGETABLE_FAMILY"))

    # Optional roles only earn their place when the meal's own budget can actually
    # afford another item — a required role is always attempted regardless of count.
    n_required = sum(1 for _, _, req, _ in total_roles if req)
    min_item_kcal = FORGE_COACH_METHODOLOGY.get("min_kcal_per_meal_item", 90)
    max_items = max(n_required, int(target_cal // min_item_kcal)) if target_cal > 0 else n_required

    ctx = FORGE_COACH_METHODOLOGY.get("carb_meal_context",{}).get(mt,[])
    exclude = set(FORGE_COACH_METHODOLOGY.get("methodology_exclude_default",[]))
    dislike = set(pn.get("disliked_foods") or [])

    # Deterministic variety: rotate protein/veg/legume/fruit per day_index
    if daily_used_proteins is None: daily_used_proteins = {}
    prot_count = daily_used_proteins.copy()
    max_same = FORGE_COACH_METHODOLOGY.get("max_same_protein_per_day", 2)

    selected = []; mu = set(used_food_ids)
    for role, cat, required, family in total_roles:
        if role == "fat_source" and target_fat < 5:
            continue
        # Optional roles (item 3/6: fewer, more human items on a tight per-meal budget)
        # only get filled while the meal can still afford another ~min_kcal_per_meal_item
        # item — secondary_protein is exempt since it's gated by real protein need, not
        # by "nice to have" (see its own _needs_secondary_protein check below).
        if not required and role != "secondary_protein" and len(selected) >= max_items:
            continue
        if role == "secondary_protein":
            # Only recruit a protein-compound partner (item 4) when the primary really
            # can't cover the target within its comfortable portion — never unconditionally.
            primary_fid = next((s for s in selected if "primary_protein" in FOOD_INDEX.get(s, {}).get("roles", [])), None)
            if not primary_fid or not _needs_secondary_protein(primary_fid, target_protein, mt):
                continue
            pair_ids = set(SECONDARY_PROTEIN_PAIRS.get(primary_fid, []))
            cands = [c for c in FOODS_BY_ROLE.get(role, []) if c in pair_ids]
            cands = [c for c in cands if c not in exclude and c not in dislike and c not in mu]
            fid = select_food_for_slot(cands, role, mt, pn, mu, goal)
            if fid:
                selected.append(fid); mu.add(fid)
            continue

        # FORGE NUTRITION DNA: a family IS the candidate pool (food availability != meal
        # suitability) — a food only reaches this slot because it genuinely belongs to
        # the combo's identity, not merely because it shares a nutrient category. Only a
        # role with no family declared (a rare legacy/safety-net case) falls back to the
        # old wide role/category pool.
        if family:
            cands = list(FOOD_FAMILIES.get(family, []))
            # methodology_exclude_default ("breads/flours not a generic solution") exists
            # to keep bread out of the WIDE, undifferentiated pool — it was never meant to
            # veto a food that's the deliberate, named anchor of a real combo (e.g. "pão +
            # ovos + whey"). A curated family is itself the "belongs to a valid combo"
            # check item 4 asks for, so it isn't re-filtered through the blanket list.
            cands = [c for c in cands if c not in dislike]
        else:
            cands = list(FOODS_BY_ROLE.get(role, FOODS_BY_CAT.get(cat, [])))
            cands = [c for c in cands if c not in exclude and c not in dislike]

        if role == "primary_carb" and not family and ctx:
            ctxc = [c for c in cands if c in ctx]
            if ctxc: cands = ctxc

        # Daily variety (item 10): every role prefers a food not already used elsewhere
        # today — soft preference, not a hard ban, so "frango duas vezes" or "aveia no
        # café e na ceia" stays perfectly valid whenever no fresh alternative exists.
        remaining = [c for c in cands if c not in mu]
        if remaining: cands = remaining

        if role == "primary_protein":
            varied = [c for c in cands if prot_count.get(c, 0) < max_same]
            if varied: cands = varied

        if role == "legume":
            idx = (day_index + len(selected)) % len(LEGUME_ROTATION)
            preferred = LEGUME_ROTATION[idx]
            if preferred in cands: cands = [preferred] + [c for c in cands if c != preferred]

        if role == "vegetable":
            idx = (day_index + len(selected)) % len(VEG_ROTATION)
            preferred = VEG_ROTATION[idx]
            if preferred in cands: cands = [preferred] + [c for c in cands if c != preferred]

        if role == "fruit":
            idx = (day_index + len(selected)) % len(FRUIT_ROTATION)
            preferred = FRUIT_ROTATION[idx]
            if preferred in cands: cands = [preferred] + [c for c in cands if c != preferred]

        fid = select_food_for_slot(cands, role, mt, pn, mu, goal)
        if fid:
            if role == "primary_protein":
                prot_count[fid] = prot_count.get(fid, 0) + 1
            selected.append(fid); mu.add(fid)

    portions = calculate_meal_portions(selected, target_cal, target_protein, target_fat, goal)
    foods = [build_food_item(fid, portions.get(fid, 100)) for fid in selected]
    return {"name": meal_name, "target_cal": round(target_cal), "target_protein": round(target_protein),
            "target_fat": round(target_fat, 1), "foods": foods}

def _preference_bonus(foods, preferences):
    """USER_PREFERENCES: ranking-only nudge for the guided flow. `preferences` is
    {food_id: {"signal": "liked"|"avoided"|"neutral", "chosen_count": int}}. This never
    runs before the guardrail filter in get_meal_archetype_options — it only reorders
    among options that already passed it, so a "prefiro evitar" food can lower an
    archetype's rank but can never make an otherwise-invalid archetype appear, and an
    explicit "avoided" is still just a preference, never treated as an allergy."""
    if not preferences:
        return 0
    cap = FORGE_COACH_METHODOLOGY.get("preference_bonus_cap", 15)
    total = 0
    for it in foods:
        p = preferences.get(it["food_id"])
        if not p:
            continue
        total += min(10, p.get("chosen_count", 0) * 2)
        if p.get("signal") == "liked":
            total += 8
        elif p.get("signal") == "avoided":
            total -= 8
    return max(-cap, min(cap, total))

def get_meal_archetype_options(meal_name, target_cal, target_protein, target_fat, pn, used_food_ids,
                                goal="maintenance", daily_used_proteins=None, day_index=0,
                                preferences=None, max_options=5, variety_seed=0):
    """FORGE NUTRITION DNA entry point (item 7 — combo first, portion after): 2-5 real,
    complete, coach-plausible meal combinations for one meal slot, drawn from MEAL_COMBOS
    — never a raw ingredient list assembled from independent role slots. Reuses
    generate_meal/calculate_meal_portions/calculate_meal_coherence_score exactly as-is;
    the logic here is COACH_GUARDRAILS (a combo that would need to cross hard_max_portion_g,
    that scores below the coherence bar, or that can't fill one of its own required
    components is simply never offered) plus preference-based ranking among survivors."""
    mt = _infer_meal_type(meal_name)
    combos = [c for c in MEAL_COMBOS if mt in c["meal_types"]]
    min_score = FORGE_COACH_METHODOLOGY.get("min_archetype_coherence", 55)
    options = []
    seen_signatures = set()
    for combo in combos:
        meal = generate_meal(meal_name, mt, target_cal, target_protein, target_fat, pn, used_food_ids,
                              goal, daily_used_proteins, day_index + variety_seed,
                              template_override=combo["components"])
        if not meal["foods"]:
            continue  # infeasible for this athlete's restrictions — never offered
        # generate_meal silently skips a role it can't fill (e.g. an allergy wipes out
        # every candidate in that combo's family) rather than failing outright — correct
        # there for the legacy single-template flow, but here a required component left
        # empty means this WHOLE combo is infeasible for this athlete and must never be
        # offered as a real combination missing its own protein/carb/etc identity.
        chosen_ids = {it["food_id"] for it in meal["foods"]}
        required_unmet = False
        for req in combo["components"]:
            if not req.get("required"):
                continue
            allowed = set(FOOD_FAMILIES.get(req["family"], [])) if req.get("family") else None
            matched = any(
                (req["role"] in FOOD_INDEX.get(fid, {}).get("roles", []) or FOOD_INDEX.get(fid, {}).get("category") == req["category"])
                and (allowed is None or fid in allowed)
                for fid in chosen_ids)
            if not matched:
                required_unmet = True
                break
        if required_unmet:
            continue
        signature = tuple(sorted(it["food_id"] for it in meal["foods"]))
        if signature in seen_signatures:
            continue  # two combos resolved to the same concrete foods — not a real choice
        hard_max_ok = all(
            it["grams"] <= _portion_limit(FOOD_INDEX.get(it["food_id"], {}), "hard_max") + 0.5
            for it in meal["foods"])
        meal["composition_source"] = "dna"
        score = calculate_meal_coherence_score(meal, mt, goal, used_elsewhere=used_food_ids)
        if not hard_max_ok or score < min_score:
            continue
        seen_signatures.add(signature)
        options.append({
            "archetype_id": combo["id"], "label": combo["label"], "meal": meal,
            "coherence_score": score,
            "rank_score": score + _preference_bonus(meal["foods"], preferences),
        })
    if not options:
        # Guaranteed fallback (COACH_GUARDRAILS never leaves the athlete with zero
        # options, item 20): the always-viable default template, exactly as the legacy
        # flow uses — still runs through the same coherence validator, and is tagged
        # composition_source="fallback" so a silent low-quality result is never invisible.
        fallback = generate_meal(meal_name, mt, target_cal, target_protein, target_fat, pn, used_food_ids,
                                  goal, daily_used_proteins, day_index + variety_seed)
        fallback["composition_source"] = "fallback"
        score = calculate_meal_coherence_score(fallback, mt, goal, used_elsewhere=used_food_ids)
        options = [{"archetype_id": "default", "label": "Padrão", "meal": fallback,
                    "coherence_score": score, "rank_score": score}]
    options.sort(key=lambda o: -o["rank_score"])
    return options[:max_options]

def redistribute_remaining_targets(meals, locked, targets, goal="maintenance"):
    """After some meal slots are locked in by the athlete's choice, the not-yet-chosen
    meals must aim at what's actually left of the day's budget — not the original static
    meal_distribution share — or an early rich choice would silently blow the daily
    guardrail while later meals starve. Reuses the same meal_distribution weights already
    used by generate_daily_plan as the reference for splitting *what's left*, and the same
    _meal_totals helper _reconcile_daily already relies on."""
    dist = FORGE_COACH_METHODOLOGY["meal_distribution"].get(len(meals), FORGE_COACH_METHODOLOGY["meal_distribution"][4])
    locked_kcal = locked_protein = locked_fat = 0.0
    unlocked_idx = []
    for i, m in enumerate(meals):
        if locked[i]:
            mk, mp, mc, mf = _meal_totals(m)
            locked_kcal += mk; locked_protein += mp; locked_fat += mf
        else:
            unlocked_idx.append(i)
    remaining_kcal = max(0.0, targets["goal_calories"] - locked_kcal)
    remaining_protein = max(0.0, targets["protein_g"] - locked_protein)
    remaining_fat = max(0.0, targets["fat_g"] - locked_fat)
    weight_sum = sum(dist[i] for i in unlocked_idx) or 1
    # Cap how much of the day's shortfall a single remaining meal can be asked to absorb.
    # Without this, an earlier meal's small under-delivery (a low-capacity archetype like
    # a 2-item "leve" snack structurally can't hit a big target) cascades entirely onto
    # whatever meal is chosen last, asking a light snack to somehow deliver 1300kcal — no
    # archetype could ever satisfy that. A meal's target never exceeds ~1.8x its own
    # original static share of the day; any residual shortfall stays unabsorbed rather
    # than being dumped on one meal, exactly the "don't force artificial precision on a
    # single meal — the daily total is the solver's goal" rule already governs elsewhere.
    cap_mult = FORGE_COACH_METHODOLOGY.get("redistribution_cap_multiplier", 1.8)
    for i in unlocked_idx:
        share = dist[i] / weight_sum
        cap_cal = dist[i] * targets["goal_calories"] * cap_mult
        cap_protein = dist[i] * targets["protein_g"] * cap_mult
        cap_fat = dist[i] * targets["fat_g"] * cap_mult
        meals[i]["target_cal"] = round(min(remaining_kcal * share, cap_cal))
        meals[i]["target_protein"] = round(min(remaining_protein * share, cap_protein))
        meals[i]["target_fat"] = round(min(remaining_fat * share, cap_fat), 1)
    return meals

def _reconcile_daily(meals, targets, pn, goal, max_iterations=8):
    gk = _goal_key(goal)
    guard = FORGE_COACH_METHODOLOGY["daily_guardrails"][gk]
    weight = pn.get("weight_kg")
    # +1.5g safety margin absorbs the per-item rounding sum_plan_totals applies (1 decimal
    # place per food), so the post-rounding daily total never lands fractionally under guard.
    min_daily_protein = (guard["min_protein_g_per_kg"] * weight if weight else targets.get("protein_g", 0) * 0.85) + 1.5
    # fat_loss preserves/grows low-density volume foods (satiety) instead of letting
    # reconciliation shrink them like carbs — see FORGE.md "priorizar saciedade e maior
    # volume alimentar por caloria" for cutting.
    satiety_priority = gk == "fat_loss"
    # Bulking and maintenance (item 6/12): grow carb capacity first ("mais arroz/
    # batata/aveia"), not vegetables — otherwise a big meal pushes both its carb AND
    # its vegetable toward hard_max together (two oversized items instead of one dense
    # carb portion, which is completely normal for a non-cutting plate).
    carb_priority = gk != "fat_loss"
    SATIETY_CATS = {"VEGETABLE", "FRUIT", "LEGUME"}
    CARB_CATS = {"CARBOHYDRATE", "MIXED"}

    for _ in range(max_iterations):
        totals = sum_plan_totals(meals)
        cal_gap = targets["goal_calories"] - totals["kcal"]
        fat_gap = targets["fat_g"] - totals["fat_g"]
        if abs(cal_gap) < targets["goal_calories"] * 0.03 and abs(fat_gap) < 5:
            break
        protein_room = totals["protein_g"] - min_daily_protein
        # Shared across every meal this iteration: the fixed per-item step sizes below
        # are a per-item *ceiling*, but with fewer, larger items per meal (REAL_MEAL_
        # COMPOSITION's smaller templates) that ceiling summed across every eligible item
        # in every meal could move far more kcal in one pass than cal_gap actually calls
        # for, overshooting past the target and oscillating. This budget caps the total
        # kcal moved this iteration to what's actually needed, converging instead of
        # bouncing past the guardrail.
        kcal_budget = abs(cal_gap)
        for m in meals:
            mk, mp, mc, mf = _meal_totals(m)
            if cal_gap < -30:
                for item in m.get("foods",[]):
                    if kcal_budget <= 0: break
                    f = FOOD_INDEX.get(item["food_id"],{})
                    if "fat_source" in f.get("roles",[]): continue  # fat has its own dedicated correction below
                    cpg = f.get("kcal", 100) / max(1, f.get("grams", 100))
                    is_protein = "primary_protein" in f.get("roles",[])
                    is_satiety = f.get("category") in SATIETY_CATS
                    if is_protein:
                        if protein_room <= 0: continue  # never cut protein below the daily guardrail
                        ppg = f.get("protein_g", 0) / max(1, f.get("grams", 100))
                        max_room_grams = (protein_room / ppg) if ppg > 0 else 0
                        step = min(8, item["grams"] - 60, max_room_grams)
                    elif is_satiety and satiety_priority:
                        continue  # preserve satiety/volume foods in cutting; shrink dense carbs instead
                    else:
                        step = item["grams"] - max(50, item["grams"] - 20)
                    step = round(min(step, kcal_budget / max(0.1, cpg)))
                    if step <= 0: continue
                    item["grams"] -= step
                    kcal_budget -= step * cpg
                    if is_protein: protein_room -= step * ppg
            elif cal_gap > 20:
                # REAL_MEAL_COMPOSITION (item 3): hard_max_portion_g is the true ceiling —
                # no *1.2 fudge. Grow whichever eligible items are still under their own
                # comfortable_portion_g first; only once none remain does the pool widen
                # to items already at/above comfortable (still capped at hard_max).
                eligible = []
                for item in m.get("foods",[]):
                    f = FOOD_INDEX.get(item["food_id"],{})
                    if "fat_source" in f.get("roles",[]): continue  # fat has its own dedicated correction below
                    is_protein = "primary_protein" in f.get("roles",[])
                    is_satiety = f.get("category") in SATIETY_CATS
                    if satiety_priority and not is_satiety and not is_protein:
                        continue  # in cutting, close the remaining gap with volume foods, not dense carbs
                    eligible.append(item)
                under_comfortable = [it for it in eligible
                                      if it["grams"] < _portion_limit(FOOD_INDEX.get(it["food_id"],{}), "comfortable")]
                growth_pool = under_comfortable or eligible
                if carb_priority:
                    carb_pool = [it for it in growth_pool if FOOD_INDEX.get(it["food_id"], {}).get("category") in CARB_CATS]
                    if carb_pool: growth_pool = carb_pool
                elif satiety_priority and not under_comfortable:
                    # Every satiety item already reached comfortable — protein still has
                    # real room up to its own hard_max and is a more natural place for
                    # the rest than pushing a SECOND vegetable past comfortable too
                    # ("vegetais como filler calórico", item 18). Only once protein is
                    # also maxed does growth widen back to every satiety item.
                    protein_pool = [it for it in eligible
                                     if "primary_protein" in FOOD_INDEX.get(it["food_id"], {}).get("roles", [])
                                     and it["grams"] < _protein_hard_max(it["food_id"], FOOD_INDEX.get(it["food_id"], {}))]
                    if protein_pool: growth_pool = protein_pool
                for item in growth_pool:
                    if kcal_budget <= 0: break
                    f = FOOD_INDEX.get(item["food_id"],{})
                    cpg = f.get("kcal", 100) / max(1, f.get("grams", 100))
                    is_protein = "primary_protein" in f.get("roles", [])
                    hard_max = _protein_hard_max(item["food_id"], f) if is_protein else _portion_limit(f, "hard_max")
                    step = round(min(15, kcal_budget / max(0.1, cpg)))
                    if step <= 0: continue
                    item["grams"] = min(hard_max, item["grams"] + step)
                    kcal_budget -= step * cpg

            # Fat correction runs independently of the overall calorie gap: a meal
            # already close to its calorie target would otherwise leave fat permanently
            # stuck (neither cal_gap branch above ever fires to nudge it).
            fat_items = [it for it in m.get("foods",[]) if "fat_source" in FOOD_INDEX.get(it["food_id"],{}).get("roles",[])]
            if fat_gap > 5:
                bumped = False
                for item in fat_items:
                    f = FOOD_INDEX.get(item["food_id"],{})
                    hard_max = _portion_limit(f, "hard_max")
                    if item["grams"] < hard_max:
                        item["grams"] = min(hard_max, item["grams"] + min(8, max(1, round(abs(fat_gap)/6))))
                        bumped = True
                if not bumped:
                    used_ids = [it["food_id"] for it in m.get("foods",[])]
                    fat_cands = sorted(
                        [fid for fid in FOODS_BY_ROLE.get("fat_source",[])
                         if _food_compatible(FOOD_INDEX.get(fid,{}), pn, set()) and fid not in used_ids],
                        key=lambda fid: -(FOOD_INDEX.get(fid,{}).get("fat_g",0) / max(1, FOOD_INDEX.get(fid,{}).get("grams",100))))
                    if fat_cands:
                        fid = fat_cands[0]
                        f = FOOD_INDEX.get(fid, {})
                        fpg = f.get("fat_g",0) / max(1, f.get("grams",100))
                        lo,_ = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category","FAT"),[5,40])
                        hard_max = _portion_limit(f, "hard_max")
                        grams = round(min(abs(fat_gap), 15) / max(0.01, fpg))
                        m["foods"].append(build_food_item(fid, max(lo, min(hard_max, grams))))
            elif fat_gap < -5:
                for item in fat_items:
                    item["grams"] = max(3, item["grams"] - 5)

            # Daily protein distribution (item: "a distribuicao diaria e mais importante
            # do que fazer uma unica refeicao absorver todo o deficit"): if the day is
            # still under the protein guardrail after the passes above, top up
            # protein-bearing items a modest step per meal per iteration — spreading
            # across MULTIPLE meals/sources over the iterations rather than dumping the
            # whole shortfall into one plate. Respects each food's own comfortable/
            # hard_max and the meat/fish single-meal reference cap.
            if protein_room < 0:
                protein_items = [it for it in m.get("foods", [])
                                  if "primary_protein" in FOOD_INDEX.get(it["food_id"], {}).get("roles", [])
                                  or "secondary_protein" in FOOD_INDEX.get(it["food_id"], {}).get("roles", [])]
                for item in protein_items:
                    if protein_room >= 0: break
                    f = FOOD_INDEX.get(item["food_id"], {})
                    ppg = f.get("protein_g", 0) / max(1, f.get("grams", 100))
                    if ppg <= 0: continue
                    is_protein = "primary_protein" in f.get("roles", [])
                    hard_max = _protein_hard_max(item["food_id"], f) if is_protein else _portion_limit(f, "hard_max")
                    if item["grams"] >= hard_max: continue
                    step_grams = min(20, hard_max - item["grams"])
                    if step_grams <= 0: continue
                    item["grams"] += step_grams
                    protein_room += step_grams * ppg
    return meals

def generate_daily_plan(targets, pn, meal_count=4, goal="maintenance", variety_seed=0):
    m = FORGE_COACH_METHODOLOGY
    # O protocolo viaja dentro de targets (compute_macro_targets ja o resolveu). Copia
    # rasa: o dict do chamador nao e mutado.
    protocol = (targets or {}).get("cut_protocol") or {}
    if protocol.get("carb_mode") == "capped":
        cfg = m["cutting_intensity"][protocol["intensity"]]
        pn = {**pn, "_max_food_carb_g_per_100g": cfg["max_food_carb_g_per_100g"]}
    dist = m["meal_distribution"].get(meal_count, m["meal_distribution"][4])
    names = m["meal_names"].get(meal_count, m["meal_names"][4])
    gc, gp, gf = targets["goal_calories"], targets["protein_g"], targets["fat_g"]
    meals = []; ug = set(); dp = {}
    for i in range(meal_count):
        mc = gc * dist[i]; mp = gp * dist[i]; mf = gf * dist[i]
        # variety_seed shifts the existing vegetable/legume/fruit rotation (day_index)
        # without touching primary_protein/primary_carb selection or any scoring — so
        # "Regenerar plano" can produce a genuinely different, still-methodology-correct
        # plan instead of the same deterministic pick every time, while every directional/
        # coherence guarantee that assumes the top-scored protein/carb stays intact.
        meals.append(generate_meal(names[i], names[i], mc, mp, mf, pn, ug, goal, dp, i + variety_seed))
        for f2 in meals[-1]["foods"]:
            ug.add(f2["food_id"])
            probe = FOOD_INDEX.get(f2["food_id"],{}).get("primary_muscle","")
            for r in FOOD_INDEX.get(f2["food_id"],{}).get("roles",[]):
                if r == "primary_protein": dp[f2["food_id"]] = dp.get(f2["food_id"], 0) + 1
    pre_reconciliation_totals = sum_plan_totals(meals)
    meals = _reconcile_daily(meals, targets, pn, goal)
    # Protocolo com teto de carbo: o passe abaixo roda DEPOIS da reconciliacao normal,
    # porque e ela que infla alimento de volume por saciedade e estoura o teto.
    meals = _apply_carb_ceiling(meals, targets)
    totals = sum_plan_totals(meals)
    for meal in meals:
        meal["coherence_score"] = calculate_meal_coherence_score(meal, _infer_meal_type(meal["name"]), goal)
    return {"meals": meals, "daily_totals": totals, "pre_reconciliation_totals": pre_reconciliation_totals,
            "targets": targets, "engine_version": m["engine_version"], "methodology_version": m["coach_version"]}

def _item_macros(item):
    """kcal/carbo/gordura de um item do plano, escalados da base do alimento."""
    f = item.get("food") or FOOD_INDEX.get(item.get("food_id"), {})
    base = f.get("grams") or 100
    k = item.get("grams", 0) / max(1, base)
    return f.get("kcal", 0) * k, f.get("carbs_g", 0) * k, f.get("fat_g", 0) * k


def _roles_of(item):
    f = item.get("food") or FOOD_INDEX.get(item.get("food_id"), {})
    return set(f.get("roles") or [])


def _apply_carb_ceiling(meals, targets):
    """Fecha o dia dentro do teto de carboidrato do protocolo low-carb.

    O pipeline normal otimiza saciedade em fat_loss inflando alimento de volume
    (satiety_priority). Sob um teto de carbo isso e justamente o que estoura a meta: 400 g
    de melancia sozinhos valem 30 g de carboidrato, e nenhum filtro de densidade pega isso
    porque a densidade dela e baixa — o problema e a porcao.

    Ordem: fruta sai (o protocolo nao comporta porcao relevante de fruta); vegetais
    encolhem proporcionalmente ate o dia caber no teto, com piso por item para o prato
    continuar real; e a caloria perdida volta como GORDURA, que e o macro residual deste
    protocolo — nunca como carboidrato."""
    ceiling = (targets or {}).get("carb_ceiling_g")
    if ceiling is None:
        return meals
    goal_kcal = (targets or {}).get("goal_calories") or 0
    # Mira a META do protocolo (35 g), nao o TETO (50 g): encostar no teto deixa o plano
    # a um arredondamento de estourar, e o teto e limite duro, nao alvo.
    aim = min(float((targets or {}).get("carbs_g") or ceiling), ceiling)
    VEG_FLOOR_G = 40
    FAT_ITEM_MAX_G = FORGE_COACH_METHODOLOGY["portion_limits"]["FAT"][1]

    for m in meals:
        m["foods"] = [it for it in m.get("foods", []) if "fruit" not in _roles_of(it)]

    def day_carbs():
        return sum(_item_macros(it)[1] for m in meals for it in m.get("foods", []))

    # Encolhe quem carrega carboidrato sem ser a ancora proteica nem a fonte de gordura:
    # vegetal primeiro (mais volume, menos valor no protocolo), laticinio/resto depois.
    for roles in ({"vegetable"}, None):
        over = day_carbs() - aim
        if over <= 0:
            break
        alvo = [it for m in meals for it in m.get("foods", [])
                if not ({"primary_protein", "fat_source"} & _roles_of(it))
                and (roles is None or (roles & _roles_of(it)))]
        carbs_alvo = sum(_item_macros(it)[1] for it in alvo)
        if carbs_alvo <= 0:
            continue
        keep = max(0.0, (carbs_alvo - over) / carbs_alvo)
        for it in alvo:
            it["grams"] = max(VEG_FLOOR_G, round(it["grams"] * keep))
            it.update(build_food_item(it["food_id"], it["grams"]))

    # Recompoe a caloria com gordura, respeitando o limite de porcao por item.
    if goal_kcal:
        falta = goal_kcal - sum(_item_macros(it)[0] for m in meals for it in m.get("foods", []))
        fat_items = [it for m in meals for it in m.get("foods", []) if "fat_source" in _roles_of(it)]
        for it in fat_items:
            if falta <= 0:
                break
            f = it.get("food") or FOOD_INDEX.get(it["food_id"], {})
            base = f.get("grams") or 100
            kcal_per_g = f.get("kcal", 0) / max(1, base)
            if kcal_per_g <= 0:
                continue
            room = FAT_ITEM_MAX_G - it["grams"]
            if room <= 0:
                continue
            add = min(room, falta / kcal_per_g)
            it["grams"] = round(it["grams"] + add)
            it.update(build_food_item(it["food_id"], it["grams"]))
            falta -= add * kcal_per_g

    for m in meals:
        mk, mp, mc, mf = _meal_totals(m)
        m["totals"] = {"kcal": round(mk), "protein_g": round(mp, 1),
                       "carbs_g": round(mc, 1), "fat_g": round(mf, 1)}
    return meals


def sum_plan_totals(meals):
    t = {"kcal":0,"protein_g":0,"carbs_g":0,"fat_g":0,"fiber_g":0}
    for m in meals:
        mk,mp,mc,mf = _meal_totals(m)
        t["kcal"]+=mk; t["protein_g"]+=mp; t["carbs_g"]+=mc; t["fat_g"]+=mf
    for k in t: t[k] = round(t[k], 1)
    return t

def calculate_meal_coherence_score(meal, meal_type, goal="maintenance", used_elsewhere=None):
    """0-100 human-plausibility score for a generated meal (item 6, expanded for FORGE
    NUTRITION DNA item 18). Rewards a normal item count (2-4 is the sweet spot, item 19),
    human portions, and goal-appropriate satiety; penalizes hard the exact failure modes
    reported in production — an oversized single food, one food resolving nearly an
    entire macro alone, or a food repeated from elsewhere in the same day's plan when a
    fresh alternative existed. `used_elsewhere` is optional (backward compatible with
    every existing caller) — food_ids already used in other meals today, for the
    adjacent/daily repetition penalty (item 10)."""
    foods = meal.get("foods", [])
    if not foods:
        return 0.0
    score = 100.0
    n = len(foods)

    # item 19: 2-4 components is the real-world sweet spot — a lone item is too sparse,
    # 5 is acceptable but not ideal, 6+ starts looking like ingredients thrown at a target
    # rather than a plate a coach would prescribe.
    if n == 1:
        score -= 25
    elif n == 5:
        score -= 8
    elif n >= 6:
        score -= 10 * (n - 5)

    if meal.get("composition_source") == "fallback":
        # item 20: never let a silent fallback look identical to a real DNA combo —
        # still fully valid and offerable, just naturally ranked behind a real combo
        # whenever one exists, and visibly flagged for diagnosis either way.
        score -= 10

    if used_elsewhere:
        repeated = sum(1 for it in foods if it["food_id"] in used_elsewhere)
        if repeated:
            score -= min(15, 8 * repeated)  # soft penalty, item 10 — never a hard ban

    macros = [( _food_macros(it["food_id"], it.get("grams", 0)), it) for it in foods]
    total_protein = sum(mm[1] for mm, _ in macros)
    total_carbs = sum(mm[2] for mm, _ in macros)
    gk = _goal_key(goal)

    for (mk, mp, mc, mf), it in macros:
        f = FOOD_INDEX.get(it["food_id"], {})
        g = it.get("grams", 0)
        comfortable = _portion_limit(f, "comfortable")
        hard_max = _portion_limit(f, "hard_max")
        if g > hard_max:
            score -= 40  # should be structurally unreachable now; scored hard if it ever occurs
        elif g > comfortable:
            over_pct = (g - comfortable) / max(1, comfortable)
            # A generous vegetable portion in a cutting meal is the methodology's own
            # intentional choice (satiety/volume priority, item 12) — not the same red
            # flag as an oversized protein or carb, so it's penalized more gently here
            # instead of being scored as if it were "vegetais como filler calórico".
            # Same reasoning for the protein source specifically under fat_loss: cutting
            # carries the HIGHEST protein target of all three goals (2.0-2.4g/kg, to
            # preserve muscle in a deficit) — a cutting athlete's single protein source
            # sitting between comfortable and hard_max (never beyond) is the expected
            # case that range exists for, not a coherence failure.
            veg_softened = gk == "fat_loss" and f.get("category") == "VEGETABLE"
            protein_softened = gk == "fat_loss" and "primary_protein" in f.get("roles", [])
            softened = veg_softened or protein_softened
            penalty_cap = 8 if veg_softened else 12 if protein_softened else 20
            score -= min(penalty_cap, over_pct * (20 if softened else 40))

        # one food resolving almost the entire protein/carb macro alone, while
        # MEANINGFULLY past its comfortable size — exactly "resolver todo um macro com
        # um único alimento" (the original 300g+ egg-white bug was 65%+ over comfortable).
        # A DNA combo's whole design is one main protein source per meal, so ">comfortable"
        # alone is the ordinary case, not the failure mode — that's already counted once
        # by the per-item penalty above; this catches the genuinely extreme case instead
        # of double-penalizing an athlete who simply needs a bit more than "comfortable".
        if total_protein > 0 and "primary_protein" in f.get("roles", []) and g > comfortable * 1.3:
            if mp / total_protein > 0.85:
                score -= 15
        if total_carbs > 0 and "primary_carb" in f.get("roles", []) and g > comfortable * 1.3:
            if mc / total_carbs > 0.9:
                score -= 10

    ids = [it["food_id"] for it in foods]
    if len(set(ids)) < len(ids):
        score -= 20  # repeated food within the same meal

    if gk == "fat_loss":
        sat_score = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        avg_sat = sum(sat_score.get(FOOD_INDEX.get(it["food_id"], {}).get("satiety", "MEDIUM"), 2) for it in foods) / n
        if avg_sat < 2:
            score -= 10  # cutting meal leaning on low-satiety foods

    return max(0.0, round(score, 1))

def validate_meal(meal, pn, idx):
    w = []; name = meal.get("name",f"M{idx+1}"); foods = meal.get("foods",[])
    if not foods: w.append(f"[{name}] Empty meal"); return w
    av = set(pn.get("avoid_foods") or [])
    pt = sum(f.get("protein_g",0)*item.get("grams",100)/max(1,f.get("grams",100))
             for item in foods if (f:=FOOD_INDEX.get(item["food_id"],{})))
    ft = sum(f.get("fat_g",0)*item.get("grams",100)/max(1,f.get("grams",100))
             for item in foods if (f:=FOOD_INDEX.get(item["food_id"],{})))
    for item in foods:
        fid = item["food_id"]
        if fid in av: w.append(f"[ERROR] [{name}] Avoid: {fid}")
        g = item.get("grams",0); f = FOOD_INDEX.get(fid,{})
        lo,hi = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category","PROTEIN"),[50,250])
        if g < lo*0.3: w.append(f"[{name}] Very low: {fid} {g}g")
        if g > hi*2.5: w.append(f"[{name}] Very high: {fid} {g}g")
    if pt < FORGE_COACH_METHODOLOGY["min_protein_per_meal_g"]*0.3:
        w.append(f"[{name}] Low protein: {round(pt,1)}g")
    return w

def check_plan_hard_limits(plan, targets):
    """Violacoes que IMPEDEM persistir o plano.

    Diferente de validate_daily_plan, que devolve avisos informativos e nao bloqueia
    nada. Aqui so entra o que o protocolo trata como limite duro — hoje, o teto de
    carboidrato do modo agressivo. Um plano "agressivo" com carboidrato moderado nao e
    um plano agressivo, entao ele nao pode ser salvo e apresentado como tal.

    Deliberadamente NAO transforma a tolerancia calorica de validate_daily_plan em erro:
    ela ja existia como aviso e promove-la a bloqueio faria a geracao falhar para
    objetivos que hoje funcionam."""
    errors = []
    totals = plan.get("daily_totals") or {}
    ceiling = (targets or {}).get("carb_ceiling_g")
    if ceiling is not None:
        carbs = totals.get("carbs_g", 0)
        if carbs > ceiling:
            label = ((targets.get("cut_protocol") or {}).get("label") or "").strip()
            errors.append(
                f"Carboidrato do dia ({round(carbs, 1)} g) acima do teto de {round(ceiling)} g"
                + (f" do protocolo {label}" if label else ""))
    return errors


def validate_daily_plan(plan, targets, pn):
    w = []
    for i, m in enumerate(plan.get("meals",[])): w.extend(validate_meal(m, pn, i))
    t = plan.get("daily_totals",{})
    tp = FORGE_COACH_METHODOLOGY["calorie_tolerance_pct"]
    gc = targets["goal_calories"]
    if abs(t.get("kcal",0)-gc) > gc*tp:
        w.append(f"[daily] Cal mismatch: {round(t['kcal'])} vs {round(gc)}")
    if abs(t.get("fat_g",0)-targets["fat_g"]) > targets["fat_g"]*0.3:
        w.append(f"[daily] Fat mismatch: {t['fat_g']}g vs {targets['fat_g']}g")
    return w

def evaluate_goal_directional_substitution(orig_fid, new_fid, orig_grams, new_grams, goal,
                                            meal_before, day_before, targets, pn):
    """LEVEL 1 (local) + LEVEL 2 (daily impact) validation for a food substitution,
    respecting GOAL_DIRECTIONAL_TOLERANCE. See FORGE_COACH_METHODOLOGY['goal_directional_tolerance']
    and ['daily_guardrails'] — no thresholds are hardcoded here."""
    m = FORGE_COACH_METHODOLOGY
    gk = _goal_key(goal)
    tol = m["goal_directional_tolerance"][gk]
    guard = m["daily_guardrails"][gk]
    dead_band = m["calorie_tolerance_pct"]

    ok, op, oc, of = _food_macros(orig_fid, orig_grams)
    nk, np_, nc, nf = _food_macros(new_fid, new_grams)
    local_delta_kcal = nk - ok
    local_pct = (local_delta_kcal / ok) if ok else 0.0

    if abs(local_pct) <= dead_band:
        direction = "equivalent"
    elif local_delta_kcal < 0:
        direction = "undershoot"
    else:
        direction = "overshoot"

    favorable = {"fat_loss": "undershoot", "muscle_gain": "overshoot", "maintenance": None}[gk]
    unfavorable = {"fat_loss": "overshoot", "muscle_gain": "undershoot", "maintenance": None}[gk]

    goal_compatible = True
    reasons = []
    if gk == "maintenance":
        if direction == "undershoot" and abs(local_pct) > tol["allow_undershoot_pct"]:
            goal_compatible = False
            reasons.append("Reducao calorica maior que a tolerancia de manutencao")
        elif direction == "overshoot" and local_pct > tol["allow_overshoot_pct"]:
            goal_compatible = False
            reasons.append("Aumento calorico maior que a tolerancia de manutencao")
    elif direction == unfavorable:
        limit = tol["allow_overshoot_pct"] if unfavorable == "overshoot" else tol["allow_undershoot_pct"]
        if abs(local_pct) > limit:
            goal_compatible = False
            reasons.append(f"Direcao contraria ao objetivo {gk} alem do limite permitido")

    day_after_kcal = day_before.get("kcal", 0) + local_delta_kcal
    day_after_protein = day_before.get("protein_g", 0) + (np_ - op)
    day_after_fat = day_before.get("fat_g", 0) + (nf - of)
    daily_delta_kcal = local_delta_kcal

    # daily_guardrails pcts are calibrated against TDEE (the neutral reference point),
    # matching how goal_calories itself is derived (deficit_pct/surplus_pct * tdee) —
    # goal_calories always sits inside [min_total_kcal_pct, max_total_kcal_pct] * tdee.
    tdee = targets.get("tdee") or targets.get("goal_calories", day_before.get("kcal", 0)) or 0
    min_k = guard["min_total_kcal_pct"] * tdee
    max_k = guard["max_total_kcal_pct"] * tdee
    daily_kcal_ok = min_k <= day_after_kcal <= max_k
    if not daily_kcal_ok:
        reasons.append("Impacto diario excede os limites seguros de calorias")

    weight = pn.get("weight_kg")
    min_protein_g = guard["min_protein_g_per_kg"] * weight if weight else targets.get("protein_g", 0) * 0.85
    min_fat_g = guard["min_fat_g_per_kg"] * weight if weight else targets.get("fat_g", 0) * 0.7
    protein_ok = day_after_protein >= min_protein_g
    fat_ok = day_after_fat >= min_fat_g
    if not protein_ok: reasons.append("Proteina diaria abaixo do minimo")
    if not fat_ok: reasons.append("Gordura diaria abaixo do minimo")

    meal_protein_before = meal_before.get("protein_g", 0)
    meal_fat_before = meal_before.get("fat_g", 0)
    meal_protein_after = meal_protein_before + (np_ - op)
    meal_fat_after = meal_fat_before + (nf - of)
    meal_min_p = m["min_protein_per_meal_g"]
    meal_min_f = m["min_fat_per_meal_g"]
    meal_floor_ok = True
    if meal_protein_before >= meal_min_p and meal_protein_after < meal_min_p * 0.6:
        meal_floor_ok = False
        reasons.append("Substituicao reduz proteina da refeicao abaixo do minimo")
    if meal_fat_before >= meal_min_f and meal_fat_after < meal_min_f * 0.5:
        meal_floor_ok = False
        reasons.append("Substituicao reduz gordura da refeicao abaixo do minimo")

    portion_ok = True
    if orig_grams > 0 and (new_grams < orig_grams * 0.25 or new_grams > orig_grams * 4):
        portion_ok = False
        reasons.append("Porcao resultante impraticavel")

    valid = goal_compatible and daily_kcal_ok and protein_ok and fat_ok and meal_floor_ok and portion_ok
    reason = "; ".join(reasons) if reasons else "Aceito: compativel com a direcao do objetivo e o impacto diario"
    return {
        "valid": valid, "direction": direction, "goal_compatible": goal_compatible,
        "local_delta_kcal": round(local_delta_kcal, 1), "daily_delta_kcal": round(daily_delta_kcal, 1),
        "reason": reason,
    }


def evaluate_goal_directional_substitution_meal_level(meal_before, meal_after, goal, day_before, targets, pn,
                                                        meal_target_cal=None):
    """Same LEVEL 1 (local) + LEVEL 2 (daily impact) validation as
    evaluate_goal_directional_substitution, but comparing the whole MEAL's totals
    before/after instead of a single food's before/after. The single-food version
    assumes every other item in the meal stays exactly as it was, which is true for the
    naive calorie-equivalence fallback — but false for role-aware equivalence, where
    calculate_meal_portions resizes every item in the meal to hit the same meal target
    (item 2: 'reconcilie os demais componentes da refeicao'). Comparing just the swapped
    food's isolated before/after there produces a large, misleading delta and rejects
    substitutions that the reconciled meal is actually fine with.

    LEVEL 1 direction/goal_compatible is measured against the meal's own target_cal, not
    its pre-swap actual total: target_cal already bakes in the deficit/surplus (via
    deficit_pct/surplus_pct in compute_macro_targets), so "does the new meal still land
    near what this meal was always supposed to deliver" IS the goal-directional check.
    Comparing to the pre-swap total instead rejected almost every real cross-species
    protein swap during a deficit (e.g. tilapia -> frango), since a leaner fish naturally
    costs fewer calories per gram of protein than a fattier meat even when both correctly
    hit the same protein target — a real, unavoidable difference between foods, not a
    goal violation. day_before/daily_delta_kcal below still use the real before/after
    delta, so the whole-day guardrail keeps tracking the swap's actual calorie impact."""
    m = FORGE_COACH_METHODOLOGY
    gk = _goal_key(goal)
    tol = m["goal_directional_tolerance"][gk]
    guard = m["daily_guardrails"][gk]
    dead_band = m["calorie_tolerance_pct"]

    ok, op, oc, of = meal_before["kcal"], meal_before["protein_g"], meal_before["carbs_g"], meal_before["fat_g"]
    nk, np_, nc, nf = meal_after["kcal"], meal_after["protein_g"], meal_after["carbs_g"], meal_after["fat_g"]
    local_delta_kcal = nk - ok

    target_ref = meal_target_cal if meal_target_cal else ok
    target_delta_kcal = nk - target_ref
    target_pct = (target_delta_kcal / target_ref) if target_ref else 0.0

    if abs(target_pct) <= dead_band:
        direction = "equivalent"
    elif target_delta_kcal < 0:
        direction = "undershoot"
    else:
        direction = "overshoot"

    unfavorable = {"fat_loss": "overshoot", "muscle_gain": "undershoot", "maintenance": None}[gk]

    goal_compatible = True
    reasons = []
    if gk == "maintenance":
        if direction == "undershoot" and abs(target_pct) > tol["allow_undershoot_pct"]:
            goal_compatible = False
            reasons.append("Reducao calorica maior que a tolerancia de manutencao")
        elif direction == "overshoot" and target_pct > tol["allow_overshoot_pct"]:
            goal_compatible = False
            reasons.append("Aumento calorico maior que a tolerancia de manutencao")
    elif direction == unfavorable:
        limit = tol["allow_overshoot_pct"] if unfavorable == "overshoot" else tol["allow_undershoot_pct"]
        if abs(target_pct) > limit:
            goal_compatible = False
            reasons.append(f"Direcao contraria ao objetivo {gk} alem do limite permitido")

    day_after_kcal = day_before.get("kcal", 0) + local_delta_kcal
    day_after_protein = day_before.get("protein_g", 0) + (np_ - op)
    day_after_fat = day_before.get("fat_g", 0) + (nf - of)
    daily_delta_kcal = local_delta_kcal

    tdee = targets.get("tdee") or targets.get("goal_calories", day_before.get("kcal", 0)) or 0
    min_k = guard["min_total_kcal_pct"] * tdee
    max_k = guard["max_total_kcal_pct"] * tdee
    daily_kcal_ok = min_k <= day_after_kcal <= max_k
    if not daily_kcal_ok:
        reasons.append("Impacto diario excede os limites seguros de calorias")

    weight = pn.get("weight_kg")
    min_protein_g = guard["min_protein_g_per_kg"] * weight if weight else targets.get("protein_g", 0) * 0.85
    min_fat_g = guard["min_fat_g_per_kg"] * weight if weight else targets.get("fat_g", 0) * 0.7
    protein_ok = day_after_protein >= min_protein_g
    fat_ok = day_after_fat >= min_fat_g
    if not protein_ok: reasons.append("Proteina diaria abaixo do minimo")
    if not fat_ok: reasons.append("Gordura diaria abaixo do minimo")

    meal_min_p = m["min_protein_per_meal_g"]
    meal_min_f = m["min_fat_per_meal_g"]
    meal_floor_ok = True
    if op >= meal_min_p and np_ < meal_min_p * 0.6:
        meal_floor_ok = False
        reasons.append("Substituicao reduz proteina da refeicao abaixo do minimo")
    if of >= meal_min_f and nf < meal_min_f * 0.5:
        meal_floor_ok = False
        reasons.append("Substituicao reduz gordura da refeicao abaixo do minimo")

    valid = goal_compatible and daily_kcal_ok and protein_ok and fat_ok and meal_floor_ok
    reason = "; ".join(reasons) if reasons else "Aceito: compativel com a direcao do objetivo e o impacto diario"
    return {
        "valid": valid, "direction": direction, "goal_compatible": goal_compatible,
        "local_delta_kcal": round(local_delta_kcal, 1), "daily_delta_kcal": round(daily_delta_kcal, 1),
        "reason": reason,
    }

def _role_of_food(food):
    """Which role a food represents for substitution purposes (item 1) — the main
    structural roles (protein/carb/vegetable/fat) take priority over secondary/recipe
    roles, since those are the "componente principal" an athlete actually swaps."""
    roles = food.get("roles", [])
    for r in ("primary_protein", "primary_carb", "vegetable", "fat_source"):
        if r in roles:
            return r
    return roles[0] if roles else None


def _dna_candidates_for_role(role, meal_type, exclude_food_id=None):
    """FORGE NUTRITION DNA candidate pool (item 1/5): the union of every family a real
    MEAL_COMBOS entry — or the MEAL_TEMPLATES fallback — uses for this exact role at this
    exact meal type. Never the wide role/category pool: this is what makes "tilápia ↔
    frango ↔ patinho" possible at lunch while never offering "tilápia ↔ tofu" there just
    because both happen to be PROTEIN category."""
    families = set()
    for combo in MEAL_COMBOS:
        if meal_type not in combo["meal_types"]:
            continue
        for comp in combo["components"]:
            if comp["role"] == role and comp.get("family"):
                families.add(comp["family"])
    for comp in MEAL_TEMPLATES.get(meal_type, []):
        if comp["role"] == role and comp.get("family"):
            families.add(comp["family"])
    candidates = set()
    for fam in families:
        candidates.update(FOOD_FAMILIES.get(fam, []))
    candidates.discard(exclude_food_id)
    return candidates


def find_substitutes(food_id, pn, current_meal_foods, max_results=3, orig_grams=100, goal="maintenance",
                      meal=None, daily_totals=None, targets=None, meal_type=None,
                      meal_target_cal=None, meal_target_protein=None, meal_target_fat=None,
                      validate_daily=True):
    """FORGE NUTRITION DNA substitution (item 1/2/5): every real component — protein or
    carb especially — gets real, role-appropriate alternatives from the same families a
    coach would actually use there, sized by simulating the WHOLE meal through the
    unchanged calculate_meal_portions — the number shown is exactly what applying
    produces, never a naive calorie-for-calorie guess ("200g batata" doesn't become
    "200g arroz"; the engine recomputes what arroz needs to be to fill that same role).

    `validate_daily=False` is the guided-flow draft, where the day isn't complete yet —
    evaluating a still-in-progress day against the full daily guardrail would reject
    every substitution (a partial day is always far below the minimum), so this instead
    validates against the MEAL's own target and hard_max, exactly as item 2 specifies
    ("verificar calorias/macros totais DA REFEIÇÃO"). The confirmed-plan path keeps the
    full whole-day goal-directional validation unchanged."""
    src = FOOD_INDEX.get(food_id)
    if not src: return []
    av = set(pn.get("avoid_foods") or [])
    dislike = set(pn.get("disliked_foods") or [])
    used = set(current_meal_foods)

    role = _role_of_food(src)
    dna_cands = _dna_candidates_for_role(role, meal_type, exclude_food_id=food_id) if (role and meal_type) else set()
    if dna_cands:
        all_cands = list(dna_cands)
    else:
        # Safety-net fallback: no MEAL_COMBOS/MEAL_TEMPLATES entry declares this exact
        # role+meal_type — fall back to the older substitution tier rather than zero
        # results (item 20's "never a silent dead end", applied to substitution too).
        tier = SUB_TIER.get(food_id, [])
        group = None
        for g, ids in SUB_GROUPS.items():
            if food_id in ids: group = g; break
        all_cands = list(tier) + ([i for i in SUB_GROUPS.get(group, []) if i != food_id and i not in tier] if group else [])

    full_context = meal is not None and daily_totals is not None and targets is not None
    meal_before = _meal_totals({"foods": meal}) if full_context else None
    if full_context:
        mk, mp, mc, mf = meal_before
        meal_before = {"kcal": mk, "protein_g": mp, "carbs_g": mc, "fat_g": mf}

    has_meal_target = meal_target_cal is not None and meal_target_protein is not None
    current_ids = [it.get("food_id") for it in meal] if meal else list(current_meal_foods)

    results = []
    for cid in all_cands:
        if len(results) >= max_results: break
        if cid in av or cid in dislike or cid in used: continue
        f = FOOD_INDEX.get(cid)
        if not f or not _food_compatible(f, pn, used): continue

        sim_portions = None
        if has_meal_target:
            # Role-aware equivalence (item 2): simulate the whole meal with cid swapped
            # in, sized by the exact same target-driven Portion Engine every meal uses.
            new_ids = [cid if fid == food_id else fid for fid in current_ids]
            sim_portions = calculate_meal_portions(new_ids, meal_target_cal, meal_target_protein,
                                                     meal_target_fat or 0, goal)
            ng = sim_portions.get(cid)
            if not ng or ng <= 0:
                continue
            reason = "Porcao recalculada para o papel deste alimento na refeicao"
        else:
            ng, reason = recalculate_substitution_portion(cid, food_id, orig_grams)

        if full_context and validate_daily and sim_portions is not None:
            # The whole meal was reconciled around the swap (every item may have shifted,
            # not just cid), so validation must compare the MEAL's before/after totals —
            # not just this one food in isolation (that would misreport a large "delta"
            # for items that merely freed up room for the rest of the meal to compensate).
            new_ids = [cid if fid == food_id else fid for fid in current_ids]
            nk, np_, nc, nf = 0.0, 0.0, 0.0, 0.0
            for fid in new_ids:
                fk, fp, fc, ff = _food_macros(fid, sim_portions.get(fid, 0))
                nk += fk; np_ += fp; nc += fc; nf += ff
            meal_after = {"kcal": nk, "protein_g": np_, "carbs_g": nc, "fat_g": nf}
            evald = evaluate_goal_directional_substitution_meal_level(
                meal_before, meal_after, goal, daily_totals, targets, pn, meal_target_cal=meal_target_cal)
            if not evald["valid"]: continue
            results.append((cid, ng, reason, evald))
        elif full_context and validate_daily:
            evald = evaluate_goal_directional_substitution(
                food_id, cid, orig_grams, ng, goal, meal_before, daily_totals, targets, pn)
            if not evald["valid"]: continue
            results.append((cid, ng, reason, evald))
        elif full_context:
            # Draft context (day incomplete): validate against this meal's own bounds —
            # hard_max is the one rule that's never negotiable regardless of context.
            hard_max = _portion_limit(f, "hard_max")
            if ng > hard_max + 0.5:
                continue
            results.append((cid, ng, reason, {
                "valid": True, "direction": "equivalent", "goal_compatible": True,
                "local_delta_kcal": 0, "daily_delta_kcal": 0,
                "reason": "Aceito: dentro do alvo da refeicao",
            }))
        else:
            results.append((cid, ng, reason))
    return results

def recalculate_substitution_portion(new_fid, orig_fid, orig_grams):
    src = FOOD_INDEX.get(orig_fid,{})
    dst = FOOD_INDEX.get(new_fid,{})
    if not src or not dst: return orig_grams, "Mantendo porcao"
    oc = src.get("kcal",100)*orig_grams/max(1,src.get("grams",100))
    dcpg = dst.get("kcal",100)/max(1,dst.get("grams",100))
    ng = round(oc/max(0.01,dcpg), 0) if dcpg>0 else orig_grams
    lo,hi = FORGE_COACH_METHODOLOGY["portion_limits"].get(dst.get("category","PROTEIN"),[50,250])
    ng = max(lo*0.5, min(hi*1.5, ng))
    check_kcal = dst.get("kcal",100)*ng/max(1,dst.get("grams",100))
    if oc > 0 and abs(check_kcal-oc)/oc > 0.12:
        ng = round(oc/dcpg, 0)
        ng = max(lo*0.5, min(hi*1.5, ng))
    return ng, "Porcao ajustada para equivalencia calorica"

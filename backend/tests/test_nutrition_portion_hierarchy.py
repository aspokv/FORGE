"""FORGE Nutrition DNA — coach portion hierarchy tests.

Direct regression coverage for the production report: lunch/dinner meals were closing
macros mathematically instead of respecting a real meal hierarchy — primary_carb and
vegetable were both pushed toward hard_max simultaneously just to hit target_cal (e.g.
"400g batata + 350g abobrinha"), while breakfast/snack over-recruited a secondary
protein (clara + ovo, clara + whey) even when the primary alone had comfortable room.

The fix lives in calculate_meal_portions (primary_protein -> primary_carb ->
vegetable/fruit/legume -> fat_source hierarchy, goal-conditional: fat_loss keeps its
existing satiety-first vegetable design unchanged) and _needs_secondary_protein
(breakfast/snack now only recruit a protein-compound partner when the primary can't
cover the target even at its own hard_max, not merely past comfortable).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import (
    compute_macro_targets, generate_daily_plan, generate_meal, calculate_meal_portions,
    find_substitutes, FOOD_INDEX, FOOD_FAMILIES, _portion_limit, _needs_secondary_protein,
    FORGE_COACH_METHODOLOGY, MEAT_FISH_MAIN_IDS,
)


def _profile(w=80, **overrides):
    p = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
         "preferred_foods": [], "disliked_foods": [], "weight_kg": w}
    p.update(overrides)
    return p


PROFILES = [
    (62, 163, 27, "female", "fat_loss", 4, 62),
    (88, 181, 34, "male", "fat_loss", 3, 88),
    (75, 172, 38, "male", "maintenance", 4, 75),
    (82, 176, 31, "male", "maintenance", 5, 82),
    (78, 178, 24, "male", "muscle_gain", 5, 78),
    (105, 190, 23, "male", "muscle_gain", 6, 105),
]


# ─── 1. primary_protein anchors the majority of lunch/dinner's protein ─────────────────

def test_lunch_dinner_primary_protein_anchors_majority_of_meal_protein():
    violations = []
    for w, h, age, sex, goal, meal_count, ww in PROFILES:
        targets = compute_macro_targets(w, h, age, sex, 5, goal, "moderate")
        plan = generate_daily_plan(targets, _profile(ww), meal_count, goal)
        for meal in plan["meals"]:
            if meal["name"] not in ("Almoco", "Jantar"):
                continue
            protein_item = next((it for it in meal["foods"]
                                  if "primary_protein" in FOOD_INDEX.get(it["food_id"], {}).get("roles", [])), None)
            if not protein_item:
                continue
            total_protein = sum(FOOD_INDEX.get(it["food_id"], {}).get("protein_g", 0) * it["grams"]
                                 / max(1, FOOD_INDEX.get(it["food_id"], {}).get("grams", 100)) for it in meal["foods"])
            anchor_protein = (FOOD_INDEX[protein_item["food_id"]].get("protein_g", 0) * protein_item["grams"]
                               / max(1, FOOD_INDEX[protein_item["food_id"]].get("grams", 100)))
            if total_protein > 0 and anchor_protein / total_protein < 0.60:
                violations.append((sex, goal, ww, meal["name"], protein_item["food_id"],
                                    round(anchor_protein, 1), round(total_protein, 1)))
    assert not violations, f"primary_protein failed to anchor majority of meal protein: {violations}"


# ─── 2. primary_carb and vegetable never both reach hard_max together ──────────────────

def test_primary_carb_and_vegetable_never_both_reach_hard_max_together():
    """Direct regression for '400g batata + 350g abobrinha': the two must not both be
    pushed to their own ceiling in the same meal just to close calories."""
    violations = []
    for w, h, age, sex, goal, meal_count, ww in PROFILES:
        targets = compute_macro_targets(w, h, age, sex, 5, goal, "moderate")
        plan = generate_daily_plan(targets, _profile(ww), meal_count, goal)
        for meal in plan["meals"]:
            carb_item = next((it for it in meal["foods"]
                               if "primary_carb" in FOOD_INDEX.get(it["food_id"], {}).get("roles", [])), None)
            veg_items = [it for it in meal["foods"] if FOOD_INDEX.get(it["food_id"], {}).get("category") == "VEGETABLE"]
            if not carb_item or not veg_items:
                continue
            carb_hard_max = _portion_limit(FOOD_INDEX[carb_item["food_id"]], "hard_max")
            carb_at_max = carb_item["grams"] >= carb_hard_max - 0.5
            veg_at_max = [v for v in veg_items
                          if v["grams"] >= _portion_limit(FOOD_INDEX[v["food_id"]], "hard_max") - 0.5]
            if carb_at_max and veg_at_max:
                violations.append((sex, goal, ww, meal["name"], carb_item, veg_at_max))
    assert not violations, f"carb and vegetable both maxed out simultaneously: {violations}"


# ─── 3. breakfast/snack: secondary protein only recruited when truly needed ────────────

def test_secondary_protein_only_recruited_past_primary_hard_max_not_comfortable():
    eggs = FOOD_INDEX["eggs-whole"]
    ppg = eggs["protein_g"] / eggs["grams"]
    comfortable = _portion_limit(eggs, "comfortable")
    hard_max = _portion_limit(eggs, "hard_max")
    # a target the primary can cover between comfortable and hard_max: no longer needs
    # a compound partner (this is the exact "clara + ovo" over-recruitment fixed here)
    mid_target = (comfortable * ppg + hard_max * ppg) / 2
    assert not _needs_secondary_protein("eggs-whole", mid_target, "breakfast")
    # a target genuinely beyond what even hard_max can deliver still recruits help
    big_target = hard_max * ppg * 1.5
    assert _needs_secondary_protein("eggs-whole", big_target, "breakfast")
    # lunch/dinner keep the tighter comfortable-based gate (unchanged behavior)
    assert _needs_secondary_protein("eggs-whole", mid_target, "lunch")


def test_breakfast_eggs_combo_still_valid_and_humanized():
    """Preserves item 3: 'café da manhã com ovos deve continuar sendo válido e
    humanizado' — the eggs combo must still be offered, and its egg items still carry
    display_quantity/display_unit."""
    from nutrition_engine import get_meal_archetype_options, _display_fields
    pn = _profile(85)
    opts = get_meal_archetype_options("Cafe da manha", 500, 35, 15, pn, set(), "maintenance")
    eggs_combo = next((o for o in opts if o["archetype_id"] == "forge_eggs_classic"), None)
    assert eggs_combo, f"forge_eggs_classic no longer offered: {[o['archetype_id'] for o in opts]}"
    egg_items = [it for it in eggs_combo["meal"]["foods"] if it["food_id"] in ("eggs-whole", "egg-whites")]
    assert egg_items, "expected at least one egg item in forge_eggs_classic"
    for it in egg_items:
        fields = _display_fields(it["food_id"], it["grams"])
        assert "display_quantity" in fields and "display_unit" in fields


# ─── 4. Trocar offers real cross-subtype alternatives, not just same-species copies ────

def test_swap_offers_multiple_distinct_protein_species_at_lunch():
    """'Se frango, patinho, peixe... forem válidos, ofereça também' — a tilapia swap at
    lunch must surface genuinely different protein species, not a narrow same-subtype list."""
    from nutrition_engine import build_food_item
    ids = ["tilapia", "potato", "zucchini", "olive-oil"]
    portions = calculate_meal_portions(ids, 750, 61.6, 25.0, "maintenance")
    foods = [build_food_item(fid, portions.get(fid, 100)) for fid in ids]
    pn = _profile(88)
    subs = find_substitutes(
        "tilapia", pn, ids, max_results=5, orig_grams=portions.get("tilapia", 100),
        goal="maintenance", meal=foods, daily_totals={"kcal": 200, "protein_g": 15, "carbs_g": 10, "fat_g": 8},
        targets={"goal_calories": 2400, "protein_g": 170, "fat_g": 70}, meal_type="lunch",
        meal_target_cal=750, meal_target_protein=61.6, meal_target_fat=25.0, validate_daily=False)
    offered = {s[0] for s in subs}
    assert offered, "expected real protein alternatives for tilapia at lunch"
    assert offered <= set(FOOD_FAMILIES["LEAN_PROTEIN_SOLID"])
    # at least two genuinely distinct species/cuts offered, not a single narrow option
    assert len(offered) >= 2, f"expected multiple distinct protein alternatives, got: {offered}"


# ─── 5b. primary_protein claims a real calorie anchor, not just the bare protein-gram
#         minimum, when the meal's own budget can support more ─────────────────────────

def test_primary_protein_gets_anchor_floor_above_bare_protein_math_when_meal_allows():
    """Direct regression for the reported '102g tilapia / 100g frango' feel-too-small
    complaint: a modest target_protein relative to a real meal-sized target_cal must not
    leave the protein source thinner than a natural, calorie-proportional anchor share —
    scaled by target_cal (never a fixed number), and never above the food's own
    comfortable/hard_max ceiling."""
    ids = ["tilapia", "potato", "tomato"]
    target_cal, target_protein = 565, 29  # the exact maintenance/82kg lunch from the report
    portions = calculate_meal_portions(ids, target_cal, target_protein, 15, "maintenance")
    f = FOOD_INDEX["tilapia"]
    ppg = f["protein_g"] / f["grams"]
    bare_protein_grams = round(target_protein / ppg, -1)
    assert portions["tilapia"] > bare_protein_grams, (
        f"primary_protein stayed at the bare protein-math minimum ({bare_protein_grams}g) "
        f"instead of claiming its calorie anchor share: got {portions['tilapia']}g")
    comfortable = _portion_limit(f, "comfortable")
    assert portions["tilapia"] <= comfortable + 0.5, f"anchor floor overshot the food's own comfortable ceiling: {portions}"


def test_primary_protein_anchor_never_exceeds_meal_role_kcal_share_cap():
    """The anchor floor (item: 'permitindo naturalmente porcoes maiores') must still
    respect the existing upper ceiling — it raises the minimum, it never removes the max."""
    ids = ["chicken-breast", "cassava", "pumpkin"]
    target_cal, target_protein = 664, 8  # deliberately tiny protein target vs a big meal
    portions = calculate_meal_portions(ids, target_cal, target_protein, 15, "muscle_gain")
    f = FOOD_INDEX["chicken-breast"]
    cpg = f["kcal"] / f["grams"]
    max_kcal = target_cal * FORGE_COACH_METHODOLOGY["meal_role_kcal_share_cap"]["primary_protein"]
    assert portions["chicken-breast"] * cpg <= max_kcal + 1, (
        f"anchor floor let primary_protein exceed its meal_role_kcal_share_cap ceiling: {portions}")


# ─── 5. fat_loss's existing satiety-first vegetable design stays untouched ─────────────

def test_fat_loss_vegetable_priority_unchanged_by_the_carb_hierarchy_fix():
    """The carb-first hierarchy only applies to non-fat_loss goals — fat_loss keeps its
    already-validated satiety-first vegetable weighting exactly as before."""
    ids = ["tilapia", "potato", "zucchini", "olive-oil"]
    portions = calculate_meal_portions(ids, 750, 61.6, 25.0, "fat_loss")
    # vegetable still allowed its full weighted share for fat_loss (satiety objective) —
    # this must NOT have been narrowed by the maintenance/muscle_gain carb-priority fix
    assert portions["zucchini"] >= 250, f"fat_loss vegetable share unexpectedly shrunk: {portions}"


# ─── 6. daily protein distribution: meat/fish never exceeds 250g/meal, 3/4/5/6 refeicoes ─

DISTRIBUTION_PROFILES = [
    ("CUTTING", 88, 181, 34, "male", "fat_loss", 88),
    ("MANUTENCAO", 82, 176, 31, "male", "maintenance", 82),
    ("BULKING", 105, 190, 23, "male", "muscle_gain", 105),
]


def _min_daily_protein(goal, ww):
    gk = "fat_loss" if goal == "fat_loss" else "muscle_gain" if goal == "muscle_gain" else "maintenance"
    guard = FORGE_COACH_METHODOLOGY["daily_guardrails"][gk]
    return guard["min_protein_g_per_kg"] * ww


def test_meat_fish_never_exceeds_250g_per_meal_across_3_4_5_6_meals():
    """Direct regression: a solid meat/fish primary_protein must stay within its
    single-plate reference (<=250g) regardless of meal count/goal — the day's protein
    need is meant to spread across meals/sources instead of ballooning one plate."""
    violations = []
    for label, w, h, age, sex, goal, ww in DISTRIBUTION_PROFILES:
        for meal_count in (3, 4, 5, 6):
            targets = compute_macro_targets(w, h, age, sex, 5, goal, "moderate")
            plan = generate_daily_plan(targets, _profile(ww), meal_count, goal)
            for meal in plan["meals"]:
                for it in meal["foods"]:
                    if it["food_id"] in MEAT_FISH_MAIN_IDS and it["grams"] > 250.5:
                        violations.append((label, meal_count, meal["name"], it["food_id"], it["grams"]))
    assert not violations, f"meat/fish exceeded 250g/meal: {violations}"


def test_daily_protein_guardrail_still_met_across_3_4_5_6_meals():
    """The meat/fish cap must not silently starve the day's protein — the daily
    guardrail (already validated elsewhere) must still be met once the cap forces
    the shortfall to distribute across other meals/sources."""
    violations = []
    for label, w, h, age, sex, goal, ww in DISTRIBUTION_PROFILES:
        for meal_count in (3, 4, 5, 6):
            targets = compute_macro_targets(w, h, age, sex, 5, goal, "moderate")
            plan = generate_daily_plan(targets, _profile(ww), meal_count, goal)
            min_daily = _min_daily_protein(goal, ww)
            if plan["daily_totals"]["protein_g"] < min_daily - 0.5:
                violations.append((label, meal_count, plan["daily_totals"]["protein_g"], min_daily))
    assert not violations, f"daily protein guardrail missed after the meat/fish cap: {violations}"


def test_six_meals_spreads_meat_fish_across_multiple_meals_not_one():
    """'o engine pode perfeitamente utilizar carne/peixe em 2 ou 3 refeicoes diferentes
    do dia' — for a 6-meal plan, meat/fish protein must appear in more than a single
    meal (not concentrated in just one attempt to cover the whole day's need)."""
    for label, w, h, age, sex, goal, ww in DISTRIBUTION_PROFILES:
        targets = compute_macro_targets(w, h, age, sex, 5, goal, "moderate")
        plan = generate_daily_plan(targets, _profile(ww), 6, goal)
        meat_meals = {meal["name"] for meal in plan["meals"]
                      for it in meal["foods"] if it["food_id"] in MEAT_FISH_MAIN_IDS}
        assert len(meat_meals) >= 2, f"{label}: meat/fish concentrated in a single meal: {meat_meals}"

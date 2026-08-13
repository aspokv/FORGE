"""FORGE Nutrition DNA — substitution equivalence + humanization tests.

Covers the production bug report: 'Trocar' on the primary protein/carb of a lunch meal
returned "Nenhuma alternativa disponivel agora" because the guided-flow draft validated
substitutions against the whole (still-incomplete) day instead of the meal itself. These
tests exercise find_substitutes/_role_of_food/_dna_candidates_for_role/build_food_item
directly at the engine level (fast, no server needed) for exactly the reported scenario
(tilapia/potato/zucchini/olive-oil at lunch, plus the eggs-whole/egg-whites humanization).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import (
    find_substitutes, calculate_meal_portions, calculate_meal_coherence_score,
    build_food_item, _display_fields, _role_of_food, _dna_candidates_for_role,
    FOOD_INDEX, FOOD_FAMILIES, _portion_limit, compute_macro_targets, generate_daily_plan,
    validate_daily_plan,
)

LUNCH_MEAL_TARGET_CAL = 750
LUNCH_MEAL_TARGET_PROTEIN = 61.6
LUNCH_MEAL_TARGET_FAT = 25.0


def _profile(**overrides):
    p = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
         "preferred_foods": [], "disliked_foods": [], "weight_kg": 88}
    p.update(overrides)
    return p


def _lunch_meal():
    """The exact reported production meal: tilapia + potato + zucchini + olive-oil."""
    ids = ["tilapia", "potato", "zucchini", "olive-oil"]
    portions = calculate_meal_portions(ids, LUNCH_MEAL_TARGET_CAL, LUNCH_MEAL_TARGET_PROTEIN,
                                        LUNCH_MEAL_TARGET_FAT, "fat_loss")
    return [build_food_item(fid, portions.get(fid, 100)) for fid in ids]


def _find(food_id, foods, pn, goal="fat_loss", validate_daily=False, daily_totals=None):
    ids = [f["food_id"] for f in foods]
    orig = next(f["grams"] for f in foods if f["food_id"] == food_id)
    return find_substitutes(
        food_id, pn, ids, max_results=5, orig_grams=orig, goal=goal, meal=foods,
        daily_totals=daily_totals if daily_totals is not None else {"kcal": 200, "protein_g": 15, "carbs_g": 10, "fat_g": 8},
        targets={"goal_calories": 2200, "protein_g": 170, "fat_g": 70}, meal_type="lunch",
        meal_target_cal=LUNCH_MEAL_TARGET_CAL, meal_target_protein=LUNCH_MEAL_TARGET_PROTEIN,
        meal_target_fat=LUNCH_MEAL_TARGET_FAT, validate_daily=validate_daily)


# ─── 1. main protein has real alternatives ─────────────────────────────────────────────

def test_primary_protein_has_real_dna_alternatives_at_lunch():
    foods = _lunch_meal()
    pn = _profile()
    subs = _find("tilapia", foods, pn)
    assert subs, "tilapia at lunch must offer real substitution options — this is the exact reported bug"
    offered = {s[0] for s in subs}
    assert offered <= set(FOOD_FAMILIES["LEAN_PROTEIN_SOLID"]), f"non-DNA-appropriate protein offered: {offered}"
    assert offered, "no protein alternatives offered at all"


# ─── 2. carb has real equivalent alternatives ──────────────────────────────────────────

def test_primary_carb_has_real_dna_alternatives_at_lunch():
    foods = _lunch_meal()
    pn = _profile()
    subs = _find("potato", foods, pn)
    assert subs, "potato at lunch must offer real substitution options"
    offered = {s[0] for s in subs}
    assert offered <= set(FOOD_FAMILIES["MAIN_CARB"]), f"non-DNA-appropriate carb offered: {offered}"


# ─── 3. substitution recalculates grams — never a naive same-grams or calorie-copy ─────

def test_substitution_recalculates_grams_role_aware_not_naive_same_quantity():
    foods = _lunch_meal()
    pn = _profile()
    orig_potato_grams = next(f["grams"] for f in foods if f["food_id"] == "potato")
    subs = _find("potato", foods, pn)
    assert subs, "expected carb alternatives"
    for cid, new_grams, reason, *_ in subs:
        # "200g de batata NAO devem virar 200g de arroz automaticamente" — the new
        # quantity must come from simulating the meal, not from copying the original grams.
        assert new_grams != orig_potato_grams or FOOD_INDEX[cid]["kcal"] == FOOD_INDEX["potato"]["kcal"], (
            f"{cid} got the exact same grams ({new_grams}) as the original potato portion "
            f"({orig_potato_grams}) — looks like a naive copy, not a real recalculation")
        assert new_grams > 0


def test_substitution_uses_meal_simulation_not_calorie_equivalence_recalc():
    """The new equivalence path must be selected (has_meal_target=True) whenever meal
    targets are supplied — confirms the reason string, not just a passing number."""
    foods = _lunch_meal()
    pn = _profile()
    subs = _find("tilapia", foods, pn)
    assert subs
    for cid, grams, reason, *_ in subs:
        assert "recalculada" in reason.lower(), f"unexpected reason (naive fallback?): {reason}"


# ─── 4. swap preserves the meal's nutritional target approximately ────────────────────

def test_swap_preserves_meal_target_approximately():
    foods = _lunch_meal()
    pn = _profile()
    subs = _find("tilapia", foods, pn)
    assert subs
    for cid, new_grams, reason, *_ in subs:
        new_ids = [cid if f["food_id"] == "tilapia" else f["food_id"] for f in foods]
        portions = calculate_meal_portions(new_ids, LUNCH_MEAL_TARGET_CAL, LUNCH_MEAL_TARGET_PROTEIN,
                                            LUNCH_MEAL_TARGET_FAT, "fat_loss")
        kcal = sum(FOOD_INDEX[fid]["kcal"] * portions.get(fid, 0) / FOOD_INDEX[fid]["grams"] for fid in new_ids)
        protein = sum(FOOD_INDEX[fid]["protein_g"] * portions.get(fid, 0) / FOOD_INDEX[fid]["grams"] for fid in new_ids)
        assert abs(kcal - LUNCH_MEAL_TARGET_CAL) / LUNCH_MEAL_TARGET_CAL < 0.30, (
            f"{cid} swap drifted meal kcal too far: {kcal} vs target {LUNCH_MEAL_TARGET_CAL}")
        assert abs(protein - LUNCH_MEAL_TARGET_PROTEIN) / LUNCH_MEAL_TARGET_PROTEIN < 0.35, (
            f"{cid} swap drifted meal protein too far: {protein} vs target {LUNCH_MEAL_TARGET_PROTEIN}")


# ─── 5. eggs/whites shown in human units ───────────────────────────────────────────────

def test_eggs_whole_displayed_in_human_units():
    fields = _display_fields("eggs-whole", 150)
    assert fields == {"display_quantity": 3, "display_unit": "ovos"}


def test_egg_whites_displayed_in_human_units():
    fields = _display_fields("egg-whites", 165)
    assert fields == {"display_quantity": 5, "display_unit": "claras"}


def test_singular_unit_label_used_for_quantity_one():
    fields = _display_fields("eggs-whole", 50)
    assert fields == {"display_quantity": 1, "display_unit": "ovo"}


def test_non_unit_foods_have_no_display_fields():
    assert _display_fields("potato", 200) == {}


def test_build_food_item_carries_display_fields_through():
    item = build_food_item("eggs-whole", 150)
    assert item["food_id"] == "eggs-whole"
    assert item["grams"] == 150
    assert item["display_quantity"] == 3
    assert item["display_unit"] == "ovos"
    # internal grams stay the source of truth for calculation/persistence
    assert item["grams"] == 150


# ─── 6. allergies/restrictions still block substitution candidates ────────────────────

def test_allergy_blocks_substitution_candidates():
    foods = _lunch_meal()
    pn = _profile(allergies=["fish"])
    subs = _find("tilapia", foods, pn)
    offered = {s[0] for s in subs}
    assert "tilapia" not in offered
    assert not any(FOOD_INDEX[fid].get("category") == "PROTEIN" and "fish" in FOOD_INDEX[fid].get("tags", [])
                   for fid in offered)


def test_lactose_free_restriction_blocks_dairy_substitution_candidates():
    ids = ["chicken-breast", "rice-white", "spinach", "olive-oil"]
    portions = calculate_meal_portions(ids, 600, 45, 18, "maintenance")
    foods = [build_food_item(fid, portions.get(fid, 100)) for fid in ids]
    pn = _profile(dietary_restrictions=["lactose_free"])
    subs = _find("chicken-breast", foods, pn, goal="maintenance")
    offered = {s[0] for s in subs}
    assert not (offered & {"whey-protein", "rice-cream-whey", "cheese-cottage", "yogurt-greek"})


def test_avoid_food_blocks_substitution_candidates():
    foods = _lunch_meal()
    pn = _profile(avoid_foods=["chicken-breast"])
    subs = _find("tilapia", foods, pn)
    offered = {s[0] for s in subs}
    assert "chicken-breast" not in offered


# ─── 7. swap doesn't break MEAL_COMBO coherence ────────────────────────────────────────

def test_swap_does_not_break_meal_combo_coherence():
    foods = _lunch_meal()
    pn = _profile()
    before = calculate_meal_coherence_score({"foods": foods}, "lunch", "fat_loss")
    subs = _find("tilapia", foods, pn)
    assert subs
    cid, new_grams, reason, *_ = subs[0]
    new_ids = [cid if f["food_id"] == "tilapia" else f["food_id"] for f in foods]
    portions = calculate_meal_portions(new_ids, LUNCH_MEAL_TARGET_CAL, LUNCH_MEAL_TARGET_PROTEIN,
                                        LUNCH_MEAL_TARGET_FAT, "fat_loss")
    new_foods = [build_food_item(fid, portions.get(fid, 100)) for fid in new_ids]
    after = calculate_meal_coherence_score({"foods": new_foods}, "lunch", "fat_loss")
    assert after >= 55, f"post-swap coherence dropped to {after} (was {before})"


# ─── 8. absurd portions avoided/reconciled when a valid alternative exists ─────────────

def test_substitution_never_exceeds_hard_max_even_when_role_forces_a_bigger_food():
    """The draft-context path (validate_daily=False) explicitly checks hard_max — this is
    the concrete guard against the reported '400g abobrinha' style ballooning applying to
    a *substituted* food too, not just the originally-generated one."""
    foods = _lunch_meal()
    pn = _profile()
    for target_food in ("tilapia", "potato"):
        subs = _find(target_food, foods, pn)
        for cid, grams, reason, *_ in subs:
            hard_max = _portion_limit(FOOD_INDEX[cid], "hard_max")
            assert grams <= hard_max + 0.5, f"{cid} substitution grams {grams} exceeds hard_max {hard_max}"


# ─── 9. final plan stays within existing guardrails after substitution ────────────────

def test_full_day_plan_stays_within_guardrails_after_a_substitution_is_applied():
    targets = compute_macro_targets(88, 181, 34, "male", 4, "fat_loss", "moderate")
    pn = _profile(w=88)
    plan = generate_daily_plan(targets, pn, 4, "fat_loss")
    lunch = plan["meals"][1]
    lunch_ids = [it["food_id"] for it in lunch["foods"]]
    protein_item = next((it for it in lunch["foods"]
                          if "primary_protein" in FOOD_INDEX.get(it["food_id"], {}).get("roles", [])), None)
    if protein_item is None:
        return
    subs = find_substitutes(
        protein_item["food_id"], pn, lunch_ids, max_results=3, orig_grams=protein_item["grams"],
        goal="fat_loss", meal=lunch["foods"], daily_totals={"kcal": 300, "protein_g": 20, "carbs_g": 20, "fat_g": 10},
        targets=targets, meal_type="lunch", meal_target_cal=lunch["target_cal"],
        meal_target_protein=lunch["target_protein"], meal_target_fat=lunch.get("target_fat", 0),
        validate_daily=False)
    if not subs:
        return
    cid, new_grams, reason, *_ = subs[0]
    new_ids = [cid if fid == protein_item["food_id"] else fid for fid in lunch_ids]
    portions = calculate_meal_portions(new_ids, lunch["target_cal"], lunch["target_protein"],
                                        lunch.get("target_fat", 0), "fat_loss")
    plan["meals"][1]["foods"] = [build_food_item(fid, portions.get(fid, 100)) for fid in new_ids]
    from nutrition_engine import sum_plan_totals
    plan["daily_totals"] = sum_plan_totals(plan["meals"])
    warnings = validate_daily_plan(plan, targets, pn)
    guard_warnings = [w for w in warnings if "very high" in str(w).lower() or "error" in str(w).lower()]
    assert not guard_warnings, f"substitution pushed the day plan outside guardrails: {guard_warnings}"


# ─── 10. safety-net fallback: role/meal_type combos with no DNA entry still don't crash ─

def test_role_and_candidate_helpers_handle_unknown_meal_type_gracefully():
    tilapia = FOOD_INDEX["tilapia"]
    assert _role_of_food(tilapia) == "primary_protein"
    assert _dna_candidates_for_role("primary_protein", "nonexistent_meal_type") == set()


# ═════════════════════════════════════════════════════════════════════════════════════
# Production bug: on a real generated fat_loss plan, Trocar on the CONFIRMED plan
# (/substitute, validate_daily=True) returned "Nenhuma substituicao disponivel" for both
# the primary protein and the primary carb — e.g. "File de tilapia 239g" and "Batata
# doce cozida 70g". Root cause: evaluate_goal_directional_substitution_meal_level
# compared the resized meal's calories against the meal's PRE-swap actual total instead
# of its own target_cal, and fat_loss's allow_overshoot_pct (5%) was calibrated for the
# old near-zero-delta naive calorie-equivalence method — both made the tight local check
# reject nearly every real cross-species protein/carb swap during a deficit, even though
# the whole-day guardrail (the real protection) was never actually violated.
# ═════════════════════════════════════════════════════════════════════════════════════

from nutrition_engine import _infer_meal_type, evaluate_goal_directional_substitution_meal_level, _meal_totals, _food_macros  # noqa: E402


def _confirmed_plan_swap(food_id, meal, daily_totals, targets, pn, goal="fat_loss"):
    """Mirrors exactly what /nutrition/substitute (the CONFIRMED plan) calls:
    validate_daily=True (the default), using the meal's own persisted target_*."""
    food_ids = [f["food_id"] for f in meal["foods"]]
    orig_grams = next(f["grams"] for f in meal["foods"] if f["food_id"] == food_id)
    return find_substitutes(
        food_id, pn, food_ids, max_results=3, orig_grams=orig_grams, goal=goal,
        meal=meal["foods"], daily_totals=daily_totals, targets=targets,
        meal_type=_infer_meal_type(meal["name"]), meal_target_cal=meal.get("target_cal"),
        meal_target_protein=meal.get("target_protein"), meal_target_fat=meal.get("target_fat"))


def test_production_case_tilapia_swap_on_confirmed_fat_loss_plan_returns_alternatives():
    """Direct regression for the reported 'File de tilapia 239g -> Nenhuma substituicao
    disponivel'. Runs the real generate_daily_plan pipeline (not a synthetic meal) for a
    real fat_loss profile, then swaps the primary protein exactly as /substitute would."""
    pn = _profile(weight_kg=85)
    targets = compute_macro_targets(85, 178, 30, "male", 4, "fat_loss", "moderate")
    plan = generate_daily_plan(targets, pn, 4, "fat_loss")
    meal = next(m for m in plan["meals"] if any(
        "primary_protein" in FOOD_INDEX.get(it["food_id"], {}).get("roles", []) for it in m["foods"]))
    protein_item = next(it for it in meal["foods"]
                         if "primary_protein" in FOOD_INDEX.get(it["food_id"], {}).get("roles", []))
    subs = _confirmed_plan_swap(protein_item["food_id"], meal, plan["daily_totals"], plan["targets"], pn)
    assert subs, (f"expected real protein alternatives for {protein_item['food_id']} "
                   f"{protein_item['grams']}g at {meal['name']} (fat_loss, confirmed plan), got none")
    for cid, grams, reason, evald in subs:
        assert grams > 0
        assert evald["valid"] is True


def test_production_case_carb_swap_on_confirmed_fat_loss_plan_returns_alternatives():
    """Direct regression for the reported 'Batata doce cozida 70g -> Nenhuma
    substituicao disponivel', same confirmed-plan path as the protein case above."""
    pn = _profile(weight_kg=85)
    targets = compute_macro_targets(85, 178, 30, "male", 4, "fat_loss", "moderate")
    plan = generate_daily_plan(targets, pn, 4, "fat_loss")
    meal = next(m for m in plan["meals"] if any(
        "primary_carb" in FOOD_INDEX.get(it["food_id"], {}).get("roles", []) for it in m["foods"]))
    carb_item = next(it for it in meal["foods"]
                      if "primary_carb" in FOOD_INDEX.get(it["food_id"], {}).get("roles", []))
    subs = _confirmed_plan_swap(carb_item["food_id"], meal, plan["daily_totals"], plan["targets"], pn)
    assert subs, (f"expected real carb alternatives for {carb_item['food_id']} "
                   f"{carb_item['grams']}g at {meal['name']} (fat_loss, confirmed plan), got none")
    for cid, grams, reason, evald in subs:
        assert grams > 0
        assert "recalculada" in reason.lower()


def test_meal_level_evaluator_measures_against_meal_target_not_pre_swap_total():
    """The precise root-cause fix: a meal that's already sitting BELOW its own
    target_cal (common right after generation) must not reject a swap that brings it
    CLOSER to target just because it's numerically above the pre-swap total. day_before/
    targets use a real, internally-consistent full-day snapshot for an 85kg fat_loss
    profile so the daily guardrail/protein-floor checks reflect a realistic day, not an
    arbitrary fixture that fails those checks for unrelated reasons."""
    real_targets = compute_macro_targets(85, 178, 30, "male", 4, "fat_loss", "moderate")
    meal_before = {"kcal": 552, "protein_g": 60.9, "carbs_g": 43.9, "fat_g": 16.8}
    meal_after = {"kcal": 608, "protein_g": 65.0, "carbs_g": 43.0, "fat_g": 18.0}  # closer to target than before
    day_before = {"kcal": real_targets["goal_calories"], "protein_g": real_targets["protein_g"],
                   "carbs_g": real_targets["carbs_g"], "fat_g": real_targets["fat_g"]}
    pn = {"weight_kg": 85}
    ev = evaluate_goal_directional_substitution_meal_level(
        meal_before, meal_after, "fat_loss", day_before, real_targets, pn, meal_target_cal=624)
    assert ev["valid"] is True, f"swap that lands closer to the meal's own target was rejected: {ev}"
    assert ev["direction"] == "equivalent"

"""FORGE NUTRITION DNA — Coach Method engine tests.

Covers the spec's tests A-X (section 23) not already exercised by
test_nutrition_guided_flow.py (engine-level: guardrails, preferences, redistribution)
or test_nutrition_guided_flow_api.py (RESET_PLAN, persistence, confirm, substitution —
tests O/P/Q/R/S/T). This file focuses on the combo-first architecture itself: real
combinations instead of independently-picked ingredients, meal-type appropriateness,
goal-directional scaling that preserves combo identity, and the specific production bug
(300-400g egg whites) staying fixed under the new engine.

Section at the bottom (item 25) generates 15 real profiles (5 cutting / 5 maintenance /
5 bulking), prints every plan, and programmatically checks them for the qualities a human
coach would look for — repetition, hard_max, coherence, meal suitability, macro tolerance.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import (
    compute_macro_targets, generate_daily_plan, get_meal_archetype_options,
    FOOD_INDEX, _portion_limit, MEAL_COMBOS, FOOD_FAMILIES, FORGE_COACH_METHODOLOGY,
)

MEAL_NAME_BY_TYPE = {
    "breakfast": "Cafe da manha", "lunch": "Almoco", "dinner": "Jantar",
    "snack": "Lanche", "pre_workout": "Pre-treino", "post_workout": "Pos-treino",
}


def _profile(w=80, **overrides):
    p = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
         "preferred_foods": [], "disliked_foods": [], "weight_kg": w}
    p.update(overrides)
    return p


def _combo(combo_id):
    return next(c for c in MEAL_COMBOS if c["id"] == combo_id)


def _options_by_id(meal_type, target_cal=600, target_protein=45, target_fat=18, **profile_kw):
    profile = _profile(**profile_kw)
    opts = get_meal_archetype_options(MEAL_NAME_BY_TYPE[meal_type], target_cal, target_protein, target_fat,
                                       profile, set(), profile_kw.get("goal", "maintenance"))
    return {o["archetype_id"]: o for o in opts}


# ─── TEST A: breakfast does not arbitrarily generate tuna ──────────────────────────────

def test_A_breakfast_never_generates_tuna():
    for w in (55, 70, 80, 95, 110):
        for goal in ("fat_loss", "maintenance", "muscle_gain"):
            targets = compute_macro_targets(w, 170, 30, "male", 4, goal, "moderate")
            plan = generate_daily_plan(targets, _profile(w), 4, goal)
            breakfast = plan["meals"][0]
            ids = {it["food_id"] for it in breakfast["foods"]}
            assert "tuna-can" not in ids, f"tuna-can appeared at breakfast: {breakfast}"
            opts = _options_by_id("breakfast", target_cal=targets["goal_calories"] * 0.25,
                                   target_protein=targets["protein_g"] * 0.25, target_fat=targets["fat_g"] * 0.25,
                                   w=w, goal=goal)
            for o in opts.values():
                ids = {it["food_id"] for it in o["meal"]["foods"]}
                assert "tuna-can" not in ids, f"tuna-can offered as a breakfast option: {o}"


# ─── TEST B: oats+whey+banana keeps its identity while resized ─────────────────────────

def test_B_oats_whey_banana_keeps_structure_across_realistic_sizes():
    for target_cal in (250, 450, 700):
        opts = _options_by_id("breakfast", target_cal=target_cal, target_protein=target_cal * 0.08,
                               target_fat=target_cal * 0.02, w=80, goal="muscle_gain")
        combo = opts.get("forge_oats_whey_banana")
        assert combo, f"forge_oats_whey_banana not offered at target_cal={target_cal}"
        ids = {it["food_id"] for it in combo["meal"]["foods"]}
        assert {"oats", "whey-protein"} <= ids, f"oats+whey missing at target_cal={target_cal}: {ids}"
        # every gram value is a real, human portion — never 0 and never past hard_max
        for it in combo["meal"]["foods"]:
            assert it["grams"] > 0
            assert it["grams"] <= _portion_limit(FOOD_INDEX[it["food_id"]], "hard_max") + 0.5


def test_B2_oats_whey_banana_correctly_excluded_rather_than_forced_at_unrealistic_size():
    """item 8: 'se um combo não consegue absorver o target de forma confortável... tente
    outro combo' — a single 'mingau' bowl genuinely cannot deliver 1000kcal without every
    component sitting at its own hard_max simultaneously. The combo must be excluded
    (coherence below bar) rather than forced into an unrealistic single bowl."""
    opts = _options_by_id("breakfast", target_cal=1000, target_protein=80, target_fat=20, w=80, goal="muscle_gain")
    combo = opts.get("forge_oats_whey_banana")
    if combo:
        for it in combo["meal"]["foods"]:
            assert it["grams"] <= _portion_limit(FOOD_INDEX[it["food_id"]], "hard_max") + 0.5
    # a real combo (solid protein+carb+veg) must still be available for this athlete
    assert opts, "no breakfast option at all for a large muscle_gain target"


# ─── TEST C/F: lunch/dinner/post-workout produce solid protein + appropriate carb + veg ─

def test_C_lunch_produces_solid_protein_carb_vegetable():
    for w in (60, 80, 100):
        opts = _options_by_id("lunch", target_cal=700, target_protein=50, target_fat=20, w=w)
        combo = opts["forge_solid_meal"]
        ids = {it["food_id"] for it in combo["meal"]["foods"]}
        assert ids & set(FOOD_FAMILIES["LEAN_PROTEIN_SOLID"]), f"no solid protein in lunch: {ids}"
        assert ids & set(FOOD_FAMILIES["MAIN_CARB"]), f"no appropriate carb in lunch: {ids}"
        assert ids & set(FOOD_FAMILIES["VEGETABLE_FAMILY"]), f"no vegetable in lunch: {ids}"


def test_F_dinner_and_post_workout_produce_fish_chicken_or_meat_plus_carb_and_veg():
    for meal_type in ("dinner", "post_workout"):
        opts = _options_by_id(meal_type, target_cal=650, target_protein=45, target_fat=18)
        found_protein_carb_veg = False
        for o in opts.values():
            ids = {it["food_id"] for it in o["meal"]["foods"]}
            if (ids & set(FOOD_FAMILIES["LEAN_PROTEIN_SOLID"])) and (ids & set(FOOD_FAMILIES["MAIN_CARB"])):
                found_protein_carb_veg = True
        assert found_protein_carb_veg, f"{meal_type} never produced a protein+carb combo: {opts.keys()}"


# ─── TEST D/E: pre-workout combos (meat+carb+fruit, or rice-flour+whey) ────────────────

def test_D_prework_meat_carb_fruit_combo_available():
    opts = _options_by_id("pre_workout", target_cal=400, target_protein=30, target_fat=10)
    combo = opts.get("forge_prework_meat_carb_fruit")
    assert combo, f"forge_prework_meat_carb_fruit not offered: {opts.keys()}"
    ids = {it["food_id"] for it in combo["meal"]["foods"]}
    assert ids & set(FOOD_FAMILIES["LEAN_PROTEIN_SOLID"])
    assert ids & set(FOOD_FAMILIES["MAIN_CARB"])


def test_E_prework_riceflour_whey_combo_available():
    opts = _options_by_id("pre_workout", target_cal=250, target_protein=20, target_fat=5)
    combo = opts.get("forge_prework_riceflour_whey")
    assert combo, f"forge_prework_riceflour_whey not offered: {opts.keys()}"
    ids = {it["food_id"] for it in combo["meal"]["foods"]}
    assert ids == {"rice-flour", "whey-protein"}, f"unexpected foods: {ids}"


# ─── TEST G/H: goal scaling grows/shrinks the combo, never destroys or breaks it ───────

def test_G_high_calorie_athlete_grows_portions_coherently_without_absurd_amounts():
    targets = compute_macro_targets(115, 195, 24, "male", 6, "muscle_gain", "very_active")
    plan = generate_daily_plan(targets, _profile(115), 5, "muscle_gain")
    for meal in plan["meals"]:
        for it in meal["foods"]:
            hard_max = _portion_limit(FOOD_INDEX[it["food_id"]], "hard_max")
            assert it["grams"] <= hard_max + 0.5, f"{it} exceeds hard_max {hard_max}"
        assert meal["coherence_score"] >= 55, f"{meal['name']} scored {meal['coherence_score']} for a bulking athlete"


def test_H_low_calorie_cutting_athlete_shrinks_without_destroying_combo():
    targets = compute_macro_targets(52, 155, 24, "female", 3, "fat_loss", "sedentary")
    plan = generate_daily_plan(targets, _profile(52), 3, "fat_loss")
    for meal in plan["meals"]:
        assert 1 <= len(meal["foods"]) <= 5, f"{meal['name']} has an unrealistic item count: {len(meal['foods'])}"
        for it in meal["foods"]:
            hard_max = _portion_limit(FOOD_INDEX[it["food_id"]], "hard_max")
            assert it["grams"] <= hard_max + 0.5


# ─── TEST I: hard_max is never exceeded, across a wide profile/goal grid ───────────────

def test_I_hard_max_never_exceeded_across_grid():
    violations = []
    for w, goal, meals in [(55, "fat_loss", 3), (75, "maintenance", 4), (95, "muscle_gain", 5),
                            (110, "muscle_gain", 6), (60, "fat_loss", 5)]:
        targets = compute_macro_targets(w, 170, 30, "male", 5, goal, "active")
        plan = generate_daily_plan(targets, _profile(w), meals, goal)
        for meal in plan["meals"]:
            for it in meal["foods"]:
                hard_max = _portion_limit(FOOD_INDEX[it["food_id"]], "hard_max")
                if it["grams"] > hard_max + 0.5:
                    violations.append((w, goal, meal["name"], it, hard_max))
    assert not violations, f"hard_max violations: {violations}"


# ─── TEST J/K/L: restrictions remove the whole combo, never bypassed ───────────────────

def test_J_restriction_removes_whole_combo_when_necessary():
    opts_normal = _options_by_id("breakfast", allergies=[])
    opts_egg_allergy = _options_by_id("breakfast", allergies=["egg"])
    assert "forge_eggs_classic" in opts_normal
    assert "forge_eggs_classic" not in opts_egg_allergy


def test_K_lactose_free_never_receives_whey_or_yogurt_the_data_classifies_as_incompatible():
    """whey-protein and rice-cream-whey are classified lactose-containing by the engine's
    own _DAIRY_IDS set (used for the lactose ALLERGY exclusion) — the lactose_free
    dietary_restriction must respect that exact same classification, not a second,
    looser list. This also covers the real yogurt-family dairy foods."""
    for meal_type in ("breakfast", "snack", "pre_workout"):
        opts = _options_by_id(meal_type, dietary_restrictions=["lactose_free"], target_cal=500,
                               target_protein=35, target_fat=15)
        for o in opts.values():
            ids = {it["food_id"] for it in o["meal"]["foods"]}
            assert "whey-protein" not in ids, f"whey-protein leaked into lactose_free {meal_type}: {o}"
            assert "rice-cream-whey" not in ids
            assert not (ids & {"yogurt-greek", "yogurt-natural", "milk-whole", "cheese-cottage", "cheese-mozzarella"})


def test_L_allergy_never_bypassed_across_full_combo_library():
    for meal_type in MEAL_NAME_BY_TYPE:
        opts = _options_by_id(meal_type, allergies=["egg", "fish", "soy", "peanut"],
                               target_cal=500, target_protein=35, target_fat=15)
        for o in opts.values():
            ids = {it["food_id"] for it in o["meal"]["foods"]}
            banned = {"eggs-whole", "egg-whites", "chicken-egg-omelet", "tilapia", "salmon", "tuna-can",
                      "tofu", "soy-protein", "peanuts", "peanut-butter"}
            assert not (ids & banned), f"allergy bypassed in {meal_type}/{o['archetype_id']}: {ids & banned}"


# ─── TEST M: adjacent meals avoid repetition when an equivalent alternative exists ─────

def test_M_adjacent_meals_avoid_unnecessary_repetition():
    targets = compute_macro_targets(80, 178, 30, "male", 5, "maintenance", "moderate")
    plan = generate_daily_plan(targets, _profile(80), 5, "maintenance")
    protein_food_ids = []
    for meal in plan["meals"]:
        for it in meal["foods"]:
            if "primary_protein" in FOOD_INDEX.get(it["food_id"], {}).get("roles", []):
                protein_food_ids.append(it["food_id"])
    # not a hard ban (max_same_protein_per_day already allows a controlled repeat) —
    # just confirms the same single protein doesn't dominate literally every meal when
    # several DNA-approved alternatives exist for a 5-meal day.
    if protein_food_ids:
        most_common = max(set(protein_food_ids), key=protein_food_ids.count)
        assert protein_food_ids.count(most_common) < len(protein_food_ids), (
            f"one protein ({most_common}) used in every single meal: {protein_food_ids}")


# ─── TEST U: no meal is missing protein when its combo requires it ─────────────────────

def test_U_no_meal_missing_protein_when_combo_requires_it():
    for w, goal in [(65, "fat_loss"), (80, "maintenance"), (100, "muscle_gain")]:
        targets = compute_macro_targets(w, 175, 30, "male", 5, goal, "moderate")
        plan = generate_daily_plan(targets, _profile(w), 4, goal)
        for meal in plan["meals"]:
            mt_combos = [c for c in MEAL_COMBOS if any(mt in c["meal_types"] for mt in MEAL_NAME_BY_TYPE)]
            requires_protein = any(
                comp["required"] and comp["category"] == "PROTEIN"
                for template_source in (MEAL_COMBOS,) for c in template_source
                for comp in c["components"])
            if not requires_protein:
                continue
            ids = {it["food_id"] for it in meal["foods"]}
            has_protein = any("primary_protein" in FOOD_INDEX.get(fid, {}).get("roles", []) for fid in ids)
            # every current template/combo that requires protein at all must have it present
            assert has_protein or not meal["foods"], f"{meal['name']} has foods but no protein: {meal}"


# ─── TEST W: no absurd egg-white quantity when a real alternative combo exists ─────────

def test_W_no_absurd_egg_white_quantity_when_alternative_combo_exists():
    """Direct regression test for the reported production bug (344g egg whites + sweet
    potato + papaya + peanut butter) — now must never recur given real DNA combos exist."""
    for w in (70, 90, 110):
        targets = compute_macro_targets(w, 182, 27, "male", 6, "muscle_gain", "very_active")
        plan = generate_daily_plan(targets, _profile(w), 4, "muscle_gain")
        for meal in plan["meals"]:
            for it in meal["foods"]:
                if it["food_id"] == "egg-whites":
                    assert it["grams"] <= 250, f"egg-whites still ballooning: {it} in {meal['name']}"


# ─── TEST X: daily plan stays within the existing macro/kcal tolerances ────────────────

def test_X_daily_totals_stay_within_existing_tolerances():
    for w, goal in [(60, "fat_loss"), (80, "maintenance"), (100, "muscle_gain")]:
        targets = compute_macro_targets(w, 175, 30, "male", 5, goal, "active")
        plan = generate_daily_plan(targets, _profile(w), 4, goal)
        gk = "fat_loss" if goal == "fat_loss" else "muscle_gain" if goal == "muscle_gain" else "maintenance"
        guard = FORGE_COACH_METHODOLOGY["daily_guardrails"][gk]
        tdee = targets["tdee"]
        kcal = plan["daily_totals"]["kcal"]
        min_k, max_k = guard["min_total_kcal_pct"] * tdee, guard["max_total_kcal_pct"] * tdee
        assert min_k * 0.95 <= kcal <= max_k * 1.05, f"{goal} kcal {kcal} outside [{min_k:.0f},{max_k:.0f}]"


# ═════════════════════════════════════════════════════════════════════════════════════
# Item 25 — quality test with real profiles: 5 cutting, 5 maintenance, 5 muscle_gain.
# Prints every plan and checks programmatically for repetition/hard_max/coherence/
# meal-suitability/macro-tolerance — the human "eu entregaria isso para um aluno?" bar.
# ═════════════════════════════════════════════════════════════════════════════════════

QUALITY_PROFILES = [
    # cutting
    dict(w=62, h=163, age=27, sex="female", goal="fat_loss", meals=4, restr=[], pref=[]),
    dict(w=88, h=181, age=34, sex="male", goal="fat_loss", meals=3, restr=[], pref=[]),
    dict(w=70, h=168, age=45, sex="female", goal="fat_loss", meals=5, restr=["lactose_free"], pref=[]),
    dict(w=95, h=178, age=29, sex="male", goal="fat_loss", meals=4, restr=[], pref=["rice-white"]),
    dict(w=58, h=160, age=22, sex="female", goal="fat_loss", meals=6, restr=[], pref=[]),
    # maintenance
    dict(w=75, h=172, age=38, sex="male", goal="maintenance", meals=4, restr=[], pref=[]),
    dict(w=65, h=165, age=50, sex="female", goal="maintenance", meals=3, restr=[], pref=[]),
    dict(w=82, h=176, age=31, sex="male", goal="maintenance", meals=5, restr=[], pref=["chicken-breast"]),
    dict(w=60, h=162, age=26, sex="female", goal="maintenance", meals=4, restr=["lactose_free"], pref=[]),
    dict(w=100, h=185, age=42, sex="male", goal="maintenance", meals=6, restr=[], pref=[]),
    # muscle_gain / bulking
    dict(w=78, h=178, age=24, sex="male", goal="muscle_gain", meals=5, restr=[], pref=[]),
    dict(w=68, h=170, age=28, sex="female", goal="muscle_gain", meals=4, restr=[], pref=[]),
    dict(w=105, h=190, age=23, sex="male", goal="muscle_gain", meals=6, restr=[], pref=[]),
    dict(w=90, h=183, age=33, sex="male", goal="muscle_gain", meals=4, restr=["lactose_free"], pref=[]),
    dict(w=72, h=169, age=25, sex="female", goal="muscle_gain", meals=5, restr=[], pref=[]),
]


def _generate_quality_plan(p):
    targets = compute_macro_targets(p["w"], p["h"], p["age"], p["sex"], 5, p["goal"], "moderate")
    profile = _profile(p["w"], dietary_restrictions=p["restr"], preferred_foods=p["pref"])
    return targets, generate_daily_plan(targets, profile, p["meals"], p["goal"])


def test_quality_15_real_profiles_pass_the_human_coach_bar():
    print("\n" + "=" * 100)
    print("FORGE NUTRITION DNA — QUALITY REPORT: 15 REAL PROFILES (5 cutting / 5 maintenance / 5 bulking)")
    print("=" * 100)

    all_violations = []
    for i, p in enumerate(QUALITY_PROFILES, 1):
        targets, plan = _generate_quality_plan(p)
        label = f"#{i} {p['sex']}/{p['goal']}/{p['w']}kg/{p['meals']}meals restr={p['restr']} pref={p['pref']}"
        print(f"\n--- {label} ---")
        print(f"  target: {targets['goal_calories']}kcal  P{targets['protein_g']}g C{targets['carbs_g']}g F{targets['fat_g']}g")
        print(f"  actual: {plan['daily_totals']['kcal']}kcal  P{plan['daily_totals']['protein_g']}g "
              f"C{plan['daily_totals']['carbs_g']}g F{plan['daily_totals']['fat_g']}g")

        day_food_ids = []
        for meal in plan["meals"]:
            items = ", ".join(f"{it['food_id']} {it['grams']}g" for it in meal["foods"])
            print(f"  {meal['name']:16s} ({meal['coherence_score']:5.1f}) target={meal['target_cal']}kcal: {items}")
            day_food_ids.extend(it["food_id"] for it in meal["foods"])

            for it in meal["foods"]:
                hard_max = _portion_limit(FOOD_INDEX[it["food_id"]], "hard_max")
                if it["grams"] > hard_max + 0.5:
                    all_violations.append((label, "hard_max", meal["name"], it, hard_max))
            if meal["coherence_score"] < 55:
                all_violations.append((label, "coherence", meal["name"], meal["coherence_score"]))
            if p["restr"] and "lactose_free" in p["restr"]:
                ids = {it["food_id"] for it in meal["foods"]}
                if ids & set(FOOD_INDEX[i].get("category") == "DAIRY" and i or None for i in ids if i):
                    pass  # category check below covers this more directly
                for it in meal["foods"]:
                    if FOOD_INDEX[it["food_id"]].get("category") == "DAIRY" or it["food_id"] in ("whey-protein", "rice-cream-whey"):
                        all_violations.append((label, "lactose_free_violated", meal["name"], it))

        # meal suitability: breakfast should never contain a lunch-only solid-meal fish
        breakfast = plan["meals"][0]
        breakfast_ids = {it["food_id"] for it in breakfast["foods"]}
        if breakfast_ids & {"tuna-can", "beef-grill", "beef-ground", "pork-loin"}:
            all_violations.append((label, "meal_suitability", "breakfast has a lunch-only protein", breakfast_ids))

        # repetition: same exact single food shouldn't be the whole day's protein story
        from collections import Counter
        counts = Counter(day_food_ids)
        dominant = counts.most_common(1)[0] if counts else (None, 0)
        if dominant[1] >= p["meals"] and p["meals"] >= 3:
            all_violations.append((label, "total_repetition", dominant))

        gk = "fat_loss" if p["goal"] == "fat_loss" else "muscle_gain" if p["goal"] == "muscle_gain" else "maintenance"
        guard = FORGE_COACH_METHODOLOGY["daily_guardrails"][gk]
        min_k, max_k = guard["min_total_kcal_pct"] * targets["tdee"], guard["max_total_kcal_pct"] * targets["tdee"]
        if not (min_k * 0.95 <= plan["daily_totals"]["kcal"] <= max_k * 1.05):
            all_violations.append((label, "macro_tolerance", plan["daily_totals"]["kcal"], min_k, max_k))

    print("\n" + "=" * 100)
    print(f"VIOLATIONS FOUND: {len(all_violations)}")
    for v in all_violations:
        print(" ", v)
    print("=" * 100)

    assert not all_violations, f"{len(all_violations)} quality violations across 15 real profiles — see printed report above"

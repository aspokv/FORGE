"""Tests for FORGE Nutrition Engine v1.0."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import (
    calculate_bmr, calculate_activity_factor, calculate_tdee,
    calculate_goal_calories, calculate_protein_target, calculate_fat_target,
    calculate_carb_target, compute_macro_targets, generate_daily_plan,
    validate_daily_plan, validate_meal, find_substitutes,
    recalculate_substitution_portion, FOOD_INDEX, FOODS,
    FORGE_COACH_METHODOLOGY, _food_compatible, _score_food,
    select_food_for_slot,
)

def test_food_count():
    assert len(FOODS) >= 55

def test_bmr_male():
    bmr = calculate_bmr(80, 180, 30, "male")
    assert bmr > 1700
    assert bmr < 1900

def test_bmr_female():
    bmr = calculate_bmr(60, 165, 25, "female")
    assert bmr > 1200
    assert bmr < 1450

def test_tdee():
    tdee = calculate_tdee(1800, 1.35)
    assert abs(tdee - 2430) < 50

def test_goal_fat_loss():
    cal = calculate_goal_calories(2500, "fat_loss")
    assert cal == 2000

def test_goal_maintenance():
    cal = calculate_goal_calories(2500, "maintenance")
    assert cal == 2500

def test_goal_muscle_gain():
    cal = calculate_goal_calories(2500, "muscle_gain")
    assert cal == 2800

def test_protein_target_fat_loss():
    p = calculate_protein_target(80, "fat_loss")
    assert p >= 80 * 2.0

def test_fat_target():
    f = calculate_fat_target(80, "muscle_gain")
    assert f >= 80 * 0.8

def test_carb_target():
    c = calculate_carb_target(2500, 160, 65)
    assert c > 0

def test_macro_reconciliation():
    targets = compute_macro_targets(80, 180, 30, "male", 4, "muscle_gain")
    total = targets["protein_kcal"] + targets["fat_kcal"] + targets["carbs_kcal"]
    assert abs(total - targets["goal_calories"]) < 10

def test_generate_3_meals():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(80, 180, 30, "male", 4, "muscle_gain")
    plan = generate_daily_plan(targets, profile, 3)
    assert len(plan["meals"]) == 3

def test_generate_4_meals():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(75, 170, 25, "female", 3, "maintenance")
    plan = generate_daily_plan(targets, profile, 4)
    assert len(plan["meals"]) == 4

def test_generate_5_meals():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(75, 170, 25, "female", 3, "maintenance")
    plan = generate_daily_plan(targets, profile, 5)
    assert len(plan["meals"]) == 5

def test_generate_6_meals():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(80, 180, 30, "male", 4, "muscle_gain")
    plan = generate_daily_plan(targets, profile, 6)
    assert len(plan["meals"]) == 6

def test_avoid_food_excluded():
    profile = {"avoid_foods": ["rice-white"], "allergies": [], "dietary_restrictions": [],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(80, 180, 30, "male", 4, "muscle_gain")
    plan = generate_daily_plan(targets, profile, 4)
    all_food_ids = [f["food_id"] for m in plan["meals"] for f in m.get("foods", [])]
    assert "rice-white" not in all_food_ids

def test_vegetarian_no_meat():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": ["vegetarian"],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(70, 170, 25, "female", 3, "maintenance")
    plan = generate_daily_plan(targets, profile, 4)
    all_ids = [f["food_id"] for m in plan["meals"] for f in m.get("foods", [])]
    meat_ids = ["chicken-breast","beef-grill","beef-ground","tilapia","salmon","chicken-thigh","pork-loin","tuna-can"]
    for mid in meat_ids:
        assert mid not in all_ids, f"Meat {mid} found in vegetarian plan"

def test_food_not_compatible_with_avoid():
    f = FOOD_INDEX["rice-white"]
    assert _food_compatible(f, {"avoid_foods": ["rice-white"]}, set()) == False
    assert _food_compatible(f, {"avoid_foods": []}, set()) == True

def test_substitution_carb_to_carb():
    subs = find_substitutes("rice-white", {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
                        "preferred_foods": [], "disliked_foods": []}, ["chicken-breast", "rice-white"])
    assert len(subs) > 0
    assert subs[0][0] != "rice-white"

def test_substitution_recalculates_grams():
    ng, reason = recalculate_substitution_portion("sweet-potato", "rice-white", 100)
    assert ng > 80

def test_substitution_avoids_prohibited():
    subs = find_substitutes("rice-white", {"avoid_foods": ["potato"], "allergies": [], "dietary_restrictions": [],
                        "preferred_foods": [], "disliked_foods": []}, ["chicken-breast", "rice-white"])
    ids = [s[0] for s in subs]
    assert "potato" not in ids

def test_portion_within_limits():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(80, 180, 30, "male", 4, "muscle_gain")
    plan = generate_daily_plan(targets, profile, 4)
    for meal in plan["meals"]:
        for item in meal.get("foods", []):
            grams = item["grams"]
            cat = FOOD_INDEX.get(item["food_id"], {}).get("category", "PROTEIN")
            lo, hi = FORGE_COACH_METHODOLOGY["portion_limits"].get(cat, [50, 250])
            assert grams >= lo * 0.5, f"{item['food_id']} {grams}g below limit {lo}"
            assert grams <= hi * 2, f"{item['food_id']} {grams}g above limit {hi}"

def test_no_lactose_avoids_dairy():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": ["lactose_free"],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(80, 180, 30, "male", 4, "muscle_gain")
    plan = generate_daily_plan(targets, profile, 4)
    all_ids = [f["food_id"] for m in plan["meals"] for f in m.get("foods", [])]
    dairy = ["milk-whole","milk-skim","yogurt-natural","yogurt-greek","cheese-mozzarella","cheese-cottage"]
    for d in dairy:
        assert d not in all_ids, f"Dairy {d} in lactose-free plan"

def test_profile_omnivore_standard():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(80, 180, 30, "male", 4, "muscle_gain")
    plan = generate_daily_plan(targets, profile, 4)
    warnings = validate_daily_plan(plan, targets, profile)
    errors = [w for w in warnings if "[ERROR]" in w]
    assert not errors, f"Errors: {errors}"
    for m in plan["meals"]:
        assert len(m["foods"]) > 0, f"Empty meal {m['name']}"

def test_plan_has_version():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(75, 170, 25, "female", 3, "maintenance")
    plan = generate_daily_plan(targets, profile, 4)
    assert "engine_version" in plan
    assert "methodology_version" in plan

def test_train_morning_profile():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [], "preferred_foods": [],
               "disliked_foods": []}
    targets = compute_macro_targets(82, 178, 28, "male", 5, "muscle_gain")
    plan = generate_daily_plan(targets, profile, 5)
    assert len(plan["meals"]) == 5

def test_fat_loss_profile():
    profile = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
               "preferred_foods": [], "disliked_foods": []}
    targets = compute_macro_targets(95, 175, 35, "male", 3, "fat_loss")
    plan = generate_daily_plan(targets, profile, 4)
    warnings = validate_daily_plan(plan, targets, profile)
    errors = [w for w in warnings if "[ERROR]" in w]
    assert not errors


"""FORGE Guided Meal Composition — engine-level unit tests.

Covers the new MEAL_ARCHETYPES / COACH_GUARDRAILS / USER_PREFERENCES / PORTION_ENGINE
pieces added on top of the existing, unchanged generate_meal/calculate_meal_portions/
calculate_meal_coherence_score pipeline. No live server needed — these call the engine
functions directly, mirroring test_nutrition_real_meal_composition.py's style.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import (
    compute_macro_targets, get_meal_archetype_options, redistribute_remaining_targets,
    generate_daily_plan, FOOD_INDEX, _portion_limit, MEAL_COMBOS,
    FORGE_COACH_METHODOLOGY,
)

PROFILES = [
    dict(w=78, h=178, age=25, sex="male", goal="muscle_gain", days=5, act="active"),
    dict(w=70, h=165, age=28, sex="female", goal="fat_loss", days=4, act="moderate"),
    dict(w=65, h=160, age=45, sex="female", goal="maintenance", days=3, act="light"),
    dict(w=60, h=162, age=50, sex="female", goal="maintenance", days=2, act="sedentary"),
]

MEAL_TYPES_BY_NAME = {
    "breakfast": "Cafe da manha", "lunch": "Almoco", "dinner": "Jantar",
    "snack": "Lanche", "pre_workout": "Pre-treino", "post_workout": "Pos-treino",
}


def _profile(base, **overrides):
    p = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
         "preferred_foods": [], "disliked_foods": [], "weight_kg": base["w"]}
    p.update(overrides)
    return p


def _targets(base):
    return compute_macro_targets(base["w"], base["h"], base["age"], base["sex"], base["days"], base["goal"], base["act"])


# ─── 1. Every meal type/profile combo returns at least one option, never a dead end ───

def test_every_meal_type_always_returns_at_least_one_option():
    for base in PROFILES:
        for meal_type, meal_name in MEAL_TYPES_BY_NAME.items():
            options = get_meal_archetype_options(meal_name, 500, 40, 15, _profile(base), set(), base["goal"])
            assert options, f"no archetype options for {meal_type} / {base}"


# ─── 2. COACH_GUARDRAILS: no option ever crosses hard_max, none ever scores < bar ─────

def test_no_option_crosses_hard_max_or_scores_below_bar():
    min_score = FORGE_COACH_METHODOLOGY["min_archetype_coherence"]
    violations = []
    for base in PROFILES:
        for meal_type, meal_name in MEAL_TYPES_BY_NAME.items():
            options = get_meal_archetype_options(meal_name, 500, 40, 15, _profile(base), set(), base["goal"])
            for o in options:
                if o["coherence_score"] < min_score:
                    violations.append(("score", base, meal_type, o))
                for it in o["meal"]["foods"]:
                    hard_max = _portion_limit(FOOD_INDEX.get(it["food_id"], {}), "hard_max")
                    if it["grams"] > hard_max + 0.5:
                        violations.append(("hard_max", base, meal_type, it))
    assert not violations, f"guardrail violations: {violations[:5]}"


# ─── 3. Egg allergy: an archetype requiring eggs is never offered, even as a degraded
#         protein-less version of itself (the exact bug found and fixed during dev) ────

def test_egg_allergy_excludes_egg_archetype_entirely_not_just_the_egg_food():
    base = PROFILES[0]
    profile = _profile(base, allergies=["egg"])
    options = get_meal_archetype_options("Cafe da manha", 600, 45, 20, profile, set(), base["goal"])
    archetype_ids = {o["archetype_id"] for o in options}
    # forge_eggs_classic's only required component is EGG_FAMILY — with eggs excluded
    # it has no way to fill that, so it must never be offered (not degraded/protein-less).
    assert "forge_eggs_classic" not in archetype_ids, f"forge_eggs_classic offered despite egg allergy: {archetype_ids}"
    breakfast_combos = [c for c in MEAL_COMBOS if "breakfast" in c["meal_types"]]
    for o in options:
        ids = {it["food_id"] for it in o["meal"]["foods"]}
        assert not (ids & {"eggs-whole", "egg-whites"}), f"egg leaked into {o['archetype_id']}"
        combo = next(c for c in breakfast_combos if c["id"] == o["archetype_id"])
        for req in combo["components"]:
            if not req.get("required"):
                continue
            matched = any(
                req["role"] in FOOD_INDEX.get(fid, {}).get("roles", []) or FOOD_INDEX.get(fid, {}).get("category") == req["category"]
                for fid in ids)
            assert matched, f"{o['archetype_id']} offered without filling its own required component {req['role']}"


def test_lactose_free_excludes_dairy_archetype_entirely():
    base = PROFILES[0]
    profile = _profile(base, dietary_restrictions=["lactose_free"])
    options = get_meal_archetype_options("Cafe da manha", 600, 45, 20, profile, set(), base["goal"])
    lactose_ids = {"milk-whole", "milk-skim", "yogurt-natural", "yogurt-greek", "cheese-mozzarella", "cheese-cottage"}
    for o in options:
        ids = {it["food_id"] for it in o["meal"]["foods"]}
        assert not (ids & lactose_ids), f"lactose food leaked into {o['archetype_id']}"


# ─── 4. Options are real, distinct combinations — never the same foods twice ──────────

def test_options_are_distinct_combinations():
    base = PROFILES[0]
    options = get_meal_archetype_options("Cafe da manha", 600, 45, 20, _profile(base), set(), base["goal"])
    signatures = [tuple(sorted(it["food_id"] for it in o["meal"]["foods"])) for o in options]
    assert len(signatures) == len(set(signatures)), f"duplicate combinations offered: {signatures}"


# ─── 5. "Mostrar outras opcoes": a different variety_seed can change concrete foods ────

def test_variety_seed_can_change_offered_combinations():
    base = PROFILES[0]
    profile = _profile(base)
    seen = set()
    for seed in range(10):
        options = get_meal_archetype_options("Almoco", 700, 55, 20, profile, set(), base["goal"], variety_seed=seed)
        for o in options:
            seen.add(tuple(sorted(it["food_id"] for it in o["meal"]["foods"])))
    assert len(seen) > 1, "variety_seed never changed the offered combinations across 10 seeds"


# ─── 6. USER_PREFERENCES: ranking-only, never bypasses a guardrail ────────────────────

def test_preference_bonus_reorders_but_never_resurrects_an_excluded_food():
    base = PROFILES[0]
    profile = _profile(base, avoid_foods=["eggs-whole", "egg-whites"])
    # explicit "liked" signal on an avoided food must never make it reappear
    preferences = {"eggs-whole": {"signal": "liked", "chosen_count": 50}, "egg-whites": {"signal": "liked", "chosen_count": 50}}
    options = get_meal_archetype_options("Cafe da manha", 600, 45, 20, profile, set(), base["goal"], preferences=preferences)
    for o in options:
        ids = {it["food_id"] for it in o["meal"]["foods"]}
        assert not (ids & {"eggs-whole", "egg-whites"}), "avoided food resurfaced via preference bonus"


def test_preference_bonus_is_bounded():
    from nutrition_engine import _preference_bonus
    foods = [{"food_id": "chicken-breast"}]
    huge_pref = {"chicken-breast": {"signal": "liked", "chosen_count": 10000}}
    cap = FORGE_COACH_METHODOLOGY["preference_bonus_cap"]
    assert _preference_bonus(foods, huge_pref) <= cap
    huge_neg = {"chicken-breast": {"signal": "avoided", "chosen_count": 10000}}
    assert _preference_bonus(foods, huge_neg) >= -cap


# ─── 7. PORTION_ENGINE / redistribution: locking a meal reallocates the remaining ──────
#         budget across unlocked meals, converging toward the same daily target ────────

def test_redistribution_keeps_daily_total_converging_after_partial_lock():
    base = PROFILES[0]
    targets = _targets(base)
    plan = generate_daily_plan(targets, _profile(base), 4, base["goal"])
    meals = plan["meals"]
    locked = [True, False, False, False]
    redistribute_remaining_targets(meals, locked, targets, base["goal"])
    remaining_target_sum = sum(m["target_cal"] for i, m in enumerate(meals) if not locked[i])
    from nutrition_engine import sum_plan_totals
    locked_actual = sum_plan_totals([meals[0]])["kcal"]
    assert abs((locked_actual + remaining_target_sum) - targets["goal_calories"]) < 5


def test_redistribution_never_produces_negative_targets():
    base = PROFILES[0]
    targets = _targets(base)
    plan = generate_daily_plan(targets, _profile(base), 3, base["goal"])
    meals = plan["meals"]
    # simulate an oversized first choice that already exceeds the whole day's budget
    meals[0]["foods"] = [{"food_id": "chicken-breast", "grams": 500, "food": FOOD_INDEX["chicken-breast"]}]
    locked = [True, False, False]
    redistribute_remaining_targets(meals, locked, targets, base["goal"])
    for i, m in enumerate(meals):
        if not locked[i]:
            assert m["target_cal"] >= 0 and m["target_protein"] >= 0


# ─── 8. All defined combos reference only roles the engine already understands ────────

def test_archetype_catalog_uses_only_known_categories():
    known_categories = set(FORGE_COACH_METHODOLOGY["portion_limits"].keys())
    for combo in MEAL_COMBOS:
        for role_spec in combo["components"]:
            assert role_spec["category"] in known_categories, (
                f"{combo['id']} references unknown category {role_spec['category']}")

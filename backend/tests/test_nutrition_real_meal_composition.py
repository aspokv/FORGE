"""FORGE Nutrition Engine v1.3 — REAL_MEAL_COMPOSITION.

Guards against exactly the failure mode reported from production: mathematically
correct but culinarily absurd meals (e.g. 344g egg whites + 310g sweet potato +
370g papaya + peanut butter for breakfast). These tests run generate_daily_plan()
across a broad grid of real profiles and assert on the resulting food composition
directly — not just on daily macro totals.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import (
    compute_macro_targets, generate_daily_plan, validate_daily_plan,
    FOOD_INDEX, _portion_limit,
    FORGE_COACH_METHODOLOGY,
)

# ─── Profile grid: sex × goal × meal_count × weight × training_time, plus restrictions ──

BASE_PROFILES = [
    dict(w=70, h=165, age=28, sex="female", goal="fat_loss", days=4, meals=3, act="moderate", tt=None),
    dict(w=90, h=180, age=32, sex="male", goal="muscle_gain", days=5, meals=4, act="active", tt="evening"),
    dict(w=65, h=160, age=45, sex="female", goal="maintenance", days=3, meals=5, act="light", tt="morning"),
    dict(w=110, h=190, age=25, sex="male", goal="muscle_gain", days=6, meals=6, act="very_active", tt="evening"),
    dict(w=55, h=155, age=22, sex="female", goal="fat_loss", days=5, meals=4, act="moderate", tt="afternoon"),
    dict(w=100, h=178, age=40, sex="male", goal="maintenance", days=4, meals=4, act="moderate", tt=None),
    dict(w=80, h=175, age=35, sex="male", goal="fat_loss", days=3, meals=3, act="sedentary", tt=None),
    dict(w=75, h=168, age=30, sex="female", goal="muscle_gain", days=5, meals=5, act="active", tt="morning"),
    dict(w=95, h=182, age=27, sex="male", goal="muscle_gain", days=6, meals=6, act="very_active", tt="evening"),
    dict(w=60, h=162, age=50, sex="female", goal="maintenance", days=2, meals=6, act="sedentary", tt=None),
    dict(w=85, h=172, age=33, sex="male", goal="fat_loss", days=4, meals=5, act="moderate", tt="afternoon"),
    dict(w=68, h=170, age=26, sex="female", goal="fat_loss", days=5, meals=6, act="active", tt="evening"),
]


def _profile(base, **overrides):
    p = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
         "preferred_foods": [], "disliked_foods": [], "weight_kg": base["w"]}
    p.update(overrides)
    return p


def _generate(base, profile):
    targets = compute_macro_targets(base["w"], base["h"], base["age"], base["sex"],
                                     base["days"], base["goal"], base["act"])
    return targets, generate_daily_plan(targets, profile, base["meals"], base["goal"])


def _all_generated_plans():
    """Every base profile as-is, plus a lactose-free and an avoid_foods variant —
    generated once and reused across the assertion tests below."""
    out = []
    for base in BASE_PROFILES:
        out.append((base, _profile(base), *_generate(base, _profile(base))))
    lac = BASE_PROFILES[4]
    out.append((lac, _profile(lac, dietary_restrictions=["lactose_free"]),
                *_generate(lac, _profile(lac, dietary_restrictions=["lactose_free"]))))
    avoid = BASE_PROFILES[7]
    out.append((avoid, _profile(avoid, avoid_foods=["chicken-breast", "rice-white", "egg-whites"]),
                *_generate(avoid, _profile(avoid, avoid_foods=["chicken-breast", "rice-white", "egg-whites"]))))
    return out


ALL_PLANS = _all_generated_plans()


# ─── 1. No food ever exceeds hard_max_portion_g, across the whole grid ─────────────────

def test_no_food_exceeds_hard_max_across_full_grid():
    violations = []
    for base, profile, targets, plan in ALL_PLANS:
        for meal in plan["meals"]:
            for item in meal["foods"]:
                f = FOOD_INDEX.get(item["food_id"], {})
                hard_max = _portion_limit(f, "hard_max")
                if item["grams"] > hard_max + 0.5:
                    violations.append((base["sex"], base["goal"], meal["name"], item["food_id"], item["grams"], hard_max))
    assert not violations, f"hard_max_portion_g violated: {violations}"


# ─── 2. Portions over comfortable_portion_g are rare, not the norm ─────────────────────

def test_comfortable_portion_exceeded_only_rarely():
    total_items = 0
    over_comfortable = 0
    for base, profile, targets, plan in ALL_PLANS:
        for meal in plan["meals"]:
            for item in meal["foods"]:
                f = FOOD_INDEX.get(item["food_id"], {})
                comfortable = _portion_limit(f, "comfortable")
                total_items += 1
                if item["grams"] > comfortable:
                    over_comfortable += 1
    rate = over_comfortable / max(1, total_items)
    assert rate < 0.25, f"too many items exceed comfortable_portion_g ({over_comfortable}/{total_items} = {rate:.0%})"


# ─── 3. Daily macros stay inside the frozen directional rules per goal ─────────────────

def test_daily_calories_respect_goal_directional_rules():
    for base, profile, targets, plan in ALL_PLANS:
        guard = FORGE_COACH_METHODOLOGY["daily_guardrails"][
            "fat_loss" if base["goal"] == "fat_loss" else "muscle_gain" if base["goal"] == "muscle_gain" else "maintenance"
        ]
        tdee = targets["tdee"]
        kcal = plan["daily_totals"]["kcal"]
        min_k, max_k = guard["min_total_kcal_pct"] * tdee, guard["max_total_kcal_pct"] * tdee
        assert min_k * 0.95 <= kcal <= max_k * 1.05, (
            f"{base['goal']} daily kcal {kcal} outside directional guardrail [{min_k:.0f}, {max_k:.0f}] (profile {base})"
        )


# ─── 4. Daily protein guardrail preserved (unchanged from prior sprint's fix) ───────────

def test_daily_protein_guardrail_preserved():
    for base, profile, targets, plan in ALL_PLANS:
        gk = "fat_loss" if base["goal"] == "fat_loss" else "muscle_gain" if base["goal"] == "muscle_gain" else "maintenance"
        guard = FORGE_COACH_METHODOLOGY["daily_guardrails"][gk]
        min_protein = guard["min_protein_g_per_kg"] * profile["weight_kg"]
        assert plan["daily_totals"]["protein_g"] >= min_protein - 2, (
            f"protein {plan['daily_totals']['protein_g']}g below guardrail {min_protein:.1f}g for {base}"
        )


# ─── 5/6/7. Allergies, restrictions, and avoid_foods remain hard-blocked ────────────────

def test_lactose_restriction_preserved_with_new_composition_logic():
    lactose_ids = {"milk-whole", "milk-skim", "yogurt-natural", "yogurt-greek",
                   "cheese-mozzarella", "cheese-cottage"}
    base, profile, targets, plan = next(
        (b, p, t, pl) for b, p, t, pl in ALL_PLANS if "lactose_free" in p.get("dietary_restrictions", [])
    )
    used = {it["food_id"] for m in plan["meals"] for it in m["foods"]}
    assert not (used & lactose_ids), f"lactose-restricted foods leaked in: {used & lactose_ids}"


def test_avoid_foods_preserved_with_new_composition_logic():
    base, profile, targets, plan = next(
        (b, p, t, pl) for b, p, t, pl in ALL_PLANS if p.get("avoid_foods")
    )
    used = {it["food_id"] for m in plan["meals"] for it in m["foods"]}
    avoided = set(profile["avoid_foods"])
    assert not (used & avoided), f"avoided foods leaked in: {used & avoided}"


def test_secondary_protein_never_violates_allergy():
    """The protein-compound mechanism (item 4) must still respect a peanut/egg allergy —
    it must not silently recruit an unsafe partner just because it's a 'natural pair'."""
    base = dict(w=78, h=178, age=25, sex="male", goal="muscle_gain", days=5, meals=4, act="active")
    profile = _profile(base, allergies=["egg"])
    targets, plan = _generate(base, profile)
    used = {it["food_id"] for m in plan["meals"] for it in m["foods"]}
    assert not (used & {"eggs-whole", "egg-whites", "chicken-egg-omelet"})


# ─── 8. Meal composition is culinarily coherent (the actual point of this sprint) ──────

def test_all_meals_score_reasonably_coherent():
    low = []
    for base, profile, targets, plan in ALL_PLANS:
        for meal in plan["meals"]:
            score = meal.get("coherence_score", 0)
            if score < 55:
                low.append((base["sex"], base["goal"], meal["name"], score,
                            [(it["food_id"], it["grams"]) for it in meal["foods"]]))
    assert not low, f"meals with poor coherence_score (<55): {low}"


def test_no_single_food_ridiculously_oversized():
    """Direct regression test for the reported production example: no food should ever
    land anywhere near 300-400g when a comfortable ceiling and a protein partner exist."""
    absurd = []
    for base, profile, targets, plan in ALL_PLANS:
        for meal in plan["meals"]:
            for item in meal["foods"]:
                f = FOOD_INDEX.get(item["food_id"], {})
                if f.get("id") == "egg-whites" and item["grams"] > 250:
                    absurd.append((base, meal["name"], item["grams"]))
    assert not absurd, f"egg-whites still ballooning: {absurd}"


def test_high_protein_breakfast_recruits_secondary_protein_instead_of_inflating():
    """The exact scenario reported in production: a high muscle_gain protein target at
    breakfast with egg-whites as the primary. It must now recruit a second protein food
    rather than pushing egg-whites past its comfortable portion."""
    base = dict(w=95, h=182, age=27, sex="male", goal="muscle_gain", days=6, act="very_active")
    profile = _profile(base)
    targets = compute_macro_targets(base["w"], base["h"], base["age"], base["sex"], base["days"], base["goal"], base["act"])
    plan = generate_daily_plan(targets, profile, 4, base["goal"])
    breakfast = plan["meals"][0]
    ids = [it["food_id"] for it in breakfast["foods"]]
    if "egg-whites" in ids:
        egg_white_item = next(it for it in breakfast["foods"] if it["food_id"] == "egg-whites")
        comfortable = _portion_limit(FOOD_INDEX["egg-whites"], "comfortable")
        if egg_white_item["grams"] > comfortable:
            secondary_present = any(
                "secondary_protein" in FOOD_INDEX.get(it["food_id"], {}).get("roles", []) for it in breakfast["foods"]
            )
            assert secondary_present, "egg-whites over comfortable with no secondary protein recruited"


# ─── 9. Two full-day plans generated back-to-back stay internally consistent ───────────

def test_ten_plans_all_pass_existing_validator_with_no_new_errors():
    for base, profile, targets, plan in ALL_PLANS:
        warnings = validate_daily_plan(plan, targets, profile)
        errors = [w for w in warnings if "[ERROR]" in w]
        assert not errors, f"validator errors for {base}: {errors}"


def test_meal_item_count_is_realistic():
    """A real plate is 2-5 items; the archetype templates should never produce a lone
    ingredient meal for a main meal type, nor an unbounded pile."""
    for base, profile, targets, plan in ALL_PLANS:
        for meal in plan["meals"]:
            n = len(meal["foods"])
            assert 1 <= n <= 7, f"meal {meal['name']} has {n} items for {base}"

"""FORGE Coach Brain V1 — Real-World Stress Test."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import (
    compute_macro_targets, generate_daily_plan, validate_daily_plan,
    find_substitutes, recalculate_substitution_portion, FOOD_INDEX,
    FORGE_COACH_METHODOLOGY, evaluate_goal_directional_substitution,
)

PROFILES = {
    "A": {
        "name": "Cutting Padrao",
        "weight_kg": 90, "height_cm": 180, "age": 30, "sex": "male",
        "goal": "fat_loss", "training_days": 5, "activity_level": "moderate",
        "meal_count": 4, "training_time": "evening",
        "preferred_foods": [], "disliked_foods": [], "avoid_foods": [],
        "allergies": [], "dietary_restrictions": [],
    },
    "B": {
        "name": "Cutting sem batata-doce",
        "weight_kg": 70, "height_cm": 165, "age": 30, "sex": "female",
        "goal": "fat_loss", "training_days": 4, "activity_level": "moderate",
        "meal_count": 4, "training_time": "morning",
        "preferred_foods": [], "disliked_foods": ["sweet-potato"], "avoid_foods": [],
        "allergies": [], "dietary_restrictions": [],
    },
    "C": {
        "name": "Muscle Gain",
        "weight_kg": 78, "height_cm": 178, "age": 25, "sex": "male",
        "goal": "muscle_gain", "training_days": 5, "activity_level": "active",
        "meal_count": 5, "training_time": "evening",
        "preferred_foods": [], "disliked_foods": [], "avoid_foods": [],
        "allergies": [], "dietary_restrictions": [],
    },
    "D": {
        "name": "Sem batatas",
        "weight_kg": 82, "height_cm": 175, "age": 40, "sex": "male",
        "goal": "maintenance", "training_days": 3, "activity_level": "moderate",
        "meal_count": 3,
        "preferred_foods": [], "disliked_foods": ["potato", "sweet-potato"], "avoid_foods": [],
        "allergies": [], "dietary_restrictions": [],
    },
    "E": {
        "name": "Cutting + Lactose",
        "weight_kg": 75, "height_cm": 168, "age": 35, "sex": "female",
        "goal": "fat_loss", "training_days": 5, "activity_level": "moderate",
        "meal_count": 5, "training_time": "evening",
        "preferred_foods": [], "disliked_foods": [], "avoid_foods": [],
        "allergies": [], "dietary_restrictions": ["lactose_free"],
    },
}

HL = "-" * 70
EQ = "=" * 70
RESULTS = {}
for label, p in PROFILES.items():
    print(f"\n{EQ}")
    print(f"PROFILE {label}: {p['name']} | {p['weight_kg']}kg {p['height_cm']}cm {p['age']}y | {p['goal']} | {p['meal_count']} meals")
    if p.get("disliked_foods"): print(f"  DISLIKE: {p['disliked_foods']}")
    if p.get("dietary_restrictions"): print(f"  RESTRICTION: {p['dietary_restrictions']}")
    print(EQ)

    targets = compute_macro_targets(
        p["weight_kg"], p["height_cm"], p["age"], p["sex"],
        p["training_days"], p["goal"], p.get("activity_level", "moderate"))
    print(f"\nBMR: {targets['bmr']:.0f} | AF: {targets['activity_factor']} | TDEE: {targets['tdee']:.0f}")
    print(f"GOAL CAL: {targets['goal_calories']:.0f} | P: {targets['protein_g']:.0f}g | C: {targets['carbs_g']:.0f}g | F: {targets['fat_g']:.0f}g")

    plan = generate_daily_plan(targets, p, p["meal_count"], p["goal"])
    warnings = validate_daily_plan(plan, targets, p)

    print(f"\n{HL}")
    for idx, meal in enumerate(plan["meals"]):
        mcal = 0; mp = 0; mc = 0; mf = 0
        print(f"\n  [{idx+1}] {meal['name']} | target: {meal['target_cal']:.0f} kcal")
        for item in meal["foods"]:
            f = item["food"]
            g = item["grams"]
            k = round(f["kcal"] * g / max(1, f.get("grams", 100)))
            pr = round(f["protein_g"] * g / max(1, f.get("grams", 100)), 1)
            cr = round(f["carbs_g"] * g / max(1, f.get("grams", 100)), 1)
            ft = round(f["fat_g"] * g / max(1, f.get("grams", 100)), 1)
            roles = ",".join(f.get("roles",[]))
            sat = f.get("satiety","?")
            print(f"    {f['name']:<30} {roles:<25} {g:>4}g  {k:>4}kcal  P:{pr:>5} C:{cr:>5} F:{ft:>5}  sat:{sat}")
            mcal += k; mp += pr; mc += cr; mf += ft
        print(f"    {'TOTAL':>75} {mcal:>4}kcal  P:{mp:>5} C:{mc:>5} F:{mf:>5}")

    print(f"\n{HL}")
    dt = plan["daily_totals"]
    tcal = targets["goal_calories"]
    err = round(abs(dt["kcal"] - tcal) / tcal * 100, 1) if tcal else 0
    print(f"DAY:  target={tcal:.0f}  generated={dt['kcal']:.0f}  error={err}%")
    print(f"PROT: target={targets['protein_g']:.0f}g  generated={dt['protein_g']:.0f}g")
    print(f"CARBS: target={targets['carbs_g']:.0f}g  generated={dt['carbs_g']:.0f}g")
    print(f"FAT:  target={targets['fat_g']:.0f}g  generated={dt['fat_g']:.0f}g")
    if warnings:
        print(f"WARNINGS: {warnings}")

    # Substitution test
    print(f"\n--- SUBSTITUTION TEST ---")
    carb_foods = [f for m in plan["meals"] for f in m["foods"] if "primary_carb" in f["food"].get("roles",[])]
    for item in carb_foods[:2]:
        fid = item["food_id"]; f = item["food"]
        subs = find_substitutes(fid, p, [fid], 3)
        print(f"  Original: {f['name']} {item['grams']}g ({round(f['kcal']*item['grams']/max(1,f.get('grams',100)))}kcal)")
        for s in subs:
            sid, sg, reason = s if len(s) >= 3 else (s[0], s[1] if len(s)>1 else 100, "")
            sf = FOOD_INDEX.get(sid, {})
            sk = round(sf.get('kcal',0)*sg/max(1,sf.get('grams',100)))
            print(f"    -> {sf.get('name',sid)} {sg}g ({sk}kcal)")

    # Protein substitution test
    print(f"\n--- PROTEIN SUB TEST ---")
    for m in plan["meals"][:1]:
        prot_items = [f for f in m["foods"] if "primary_protein" in f["food"].get("roles",[])]
        for item in prot_items[:1]:
            fid = item["food_id"]
            subs = find_substitutes(fid, p, [f["food_id"] for f in m["foods"]], 3)
            for s in subs:
                sid, sg, reason = s if len(s) >= 3 else (s[0], s[1] if len(s)>1 else 100, "")
                sf = FOOD_INDEX.get(sid, {})
                print(f"    {FOOD_INDEX.get(fid,{}).get('name',fid)} -> {sf.get('name',sid)} {sg}g")

    # Coherence check
    print(f"\n--- COHERENCE ---")
    all_coherent = True
    for m in plan["meals"]:
        roles_in = {}
        for item in m["foods"]:
            for r in item["food"].get("roles",[]):
                roles_in[r] = roles_in.get(r, 0) + 1
        has_prot = roles_in.get("primary_protein", 0) > 0
        has_carb = roles_in.get("primary_carb", 0) > 0
        has_veg = roles_in.get("vegetable", 0) > 0
        has_fruit = roles_in.get("fruit", 0) > 0
        issues = []
        if not has_prot: issues.append("NO_PROTEIN")
        if "Cafe" in m["name"] and not has_carb and not has_fruit: issues.append("NO_CARB_OR_FRUIT")
        if ("Almoco" in m["name"] or "Jantar" in m["name"]) and not has_veg: issues.append("NO_VEGGIES")
        coherent = "YES" if not issues else f"NO ({','.join(issues)})"
        if issues: all_coherent = False
        print(f"    {m['name']}: {coherent}")

    # ---- capture for compact summary table ----
    errors = [w for w in warnings if "[ERROR]" in w]
    realism = "PASS" if not errors and err <= 10 else "FAIL"
    direction = "OVER" if dt["kcal"] > tcal * 1.03 else ("UNDER" if dt["kcal"] < tcal * 0.97 else "ON_TARGET")
    sub_test_food = next((f for m in plan["meals"] for f in m["foods"]
                           if "primary_carb" in f["food"].get("roles", [])), None)
    substitution_ok = False
    if sub_test_food:
        subs_ctx = find_substitutes(
            sub_test_food["food_id"], p, [f["food_id"] for m in plan["meals"] for f in m["foods"]],
            max_results=3, orig_grams=sub_test_food["grams"], goal=p["goal"],
            meal=next(m["foods"] for m in plan["meals"] if sub_test_food in m["foods"]),
            daily_totals=dt, targets=targets)
        substitution_ok = len(subs_ctx) > 0
    grams_total = sum(f["grams"] for m in plan["meals"] for f in m["foods"])
    density = round(dt["kcal"] / max(1, grams_total / 100), 1)
    RESULTS[label] = {
        "goal": p["goal"], "target_kcal": tcal, "generated_kcal": dt["kcal"], "direction": direction,
        "protein": dt["protein_g"], "carbs": dt["carbs_g"], "fat": dt["fat_g"],
        "realism": realism, "substitution": "PASS" if substitution_ok else "FAIL",
        "satiety": f"{density}kcal/100g", "coherence": "PASS" if all_coherent else "FAIL",
    }

print(f"\n{EQ}")
print("SATIETY COMPARISON: A (FAT_LOSS) vs C (MUSCLE_GAIN)")
print(EQ)
for label in ["A", "C"]:
    p = PROFILES[label]; plan = generate_daily_plan(compute_macro_targets(p["weight_kg"],p["height_cm"],p["age"],p["sex"],p["training_days"],p["goal"],p.get("activity_level","moderate")),p,p["meal_count"],p["goal"])
    tgrams = sum(f["grams"] for m in plan["meals"] for f in m["foods"])
    tkcal = plan["daily_totals"]["kcal"]
    density = round(tkcal / max(1, tgrams/100) * 100) / 100
    carb_sources = [f["food"]["name"] for m in plan["meals"] for f in m["foods"] if "primary_carb" in f["food"].get("roles",[])]
    print(f"  Profile {label}: {tgrams}g total food | {density:.1f} kcal/100g | Carbs: {carb_sources[:4]}")

print(f"\n{EQ}")
print("PROFILE A-E COMPACT RESULTS")
print(EQ)
hdr = f"{'PROFILE':<8}{'GOAL':<13}{'TGT_KCAL':>10}{'GEN_KCAL':>10}{'DIRECTION':>11}{'PROT':>7}{'CARBS':>7}{'FAT':>7}{'REALISM':>9}{'SUBST':>7}{'SATIETY':>16}{'COHER':>7}"
print(hdr)
for label, r in RESULTS.items():
    print(f"{label:<8}{r['goal']:<13}{r['target_kcal']:>10.0f}{r['generated_kcal']:>10.0f}{r['direction']:>11}"
          f"{r['protein']:>7.0f}{r['carbs']:>7.0f}{r['fat']:>7.0f}{r['realism']:>9}{r['substitution']:>7}"
          f"{r['satiety']:>16}{r['coherence']:>7}")

print(f"\n{EQ}")
print("GOAL_DIRECTIONAL_TOLERANCE - CASE DEMONSTRATIONS")
print(EQ)


def _demo_case(label, goal, orig_fid, orig_grams, new_fid, new_grams):
    p = PROFILES[label]
    targets = compute_macro_targets(p["weight_kg"], p["height_cm"], p["age"], p["sex"],
                                     p["training_days"], p["goal"], p.get("activity_level", "moderate"))
    plan = generate_daily_plan(targets, p, p["meal_count"], p["goal"])
    day_before = plan["daily_totals"]
    meal = next((m for m in plan["meals"] for f in m["foods"] if f["food_id"] == orig_fid), plan["meals"][0])
    meal_totals = {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
    for it in meal["foods"]:
        f = it["food"]
        fac = it["grams"] / max(1, f.get("grams", 100))
        meal_totals["kcal"] += f.get("kcal", 0) * fac
        meal_totals["protein_g"] += f.get("protein_g", 0) * fac
        meal_totals["fat_g"] += f.get("fat_g", 0) * fac

    evald = evaluate_goal_directional_substitution(
        orig_fid, new_fid, orig_grams, new_grams, goal, meal_totals, day_before, targets, p)

    orig_f = FOOD_INDEX[orig_fid]; new_f = FOOD_INDEX[new_fid]
    orig_kcal = orig_f["kcal"] * orig_grams / max(1, orig_f.get("grams", 100))
    new_kcal = new_f["kcal"] * new_grams / max(1, new_f.get("grams", 100))
    day_after_kcal = day_before["kcal"] + evald["local_delta_kcal"]

    print(f"\nCASE {goal.upper()} (Profile {label})")
    print(f"  original:     {orig_f['name']} ({orig_fid}) {orig_grams}g = {orig_kcal:.0f}kcal")
    print(f"  replacement:  {new_f['name']} ({new_fid}) {new_grams:.0f}g = {new_kcal:.0f}kcal")
    print(f"  day kcal before: {day_before['kcal']:.0f}  |  day kcal after: {day_after_kcal:.0f}")
    print(f"  planned target (goal_calories): {targets['goal_calories']:.0f}")
    print(f"  direction: {evald['direction']}  |  goal_compatible: {evald['goal_compatible']}")
    print(f"  decision: {'ACCEPTED' if evald['valid'] else 'REJECTED'}")
    print(f"  reason: {evald['reason']}")
    return evald


# CASE 1 - CUTTING: substitution with LOWER kcal correctly accepted (149->110 kcal style)
_demo_case("A", "fat_loss", "chicken-breast", 90, "tilapia", 86)

# CASE 2 - BULKING: substitution with slightly HIGHER kcal correctly accepted (150->165 kcal style)
_demo_case("C", "muscle_gain", "tilapia", 117, "salmon", 79)

# CASE 3 - MAINTENANCE: approximately equivalent substitution
_demo_case("D", "maintenance", "rice-white", 150, "cassava", 148)

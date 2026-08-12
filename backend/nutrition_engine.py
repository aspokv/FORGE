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
    "macro_tolerance_g": {"protein": 5, "carbs": 10, "fat": 5},
    "goal_directional_tolerance": {
        "fat_loss": {"allow_undershoot_pct": 0.25, "allow_overshoot_pct": 0.05},
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
    "carb_hierarchy": {"tier_1": ["potato","sweet-potato"], "tier_2": ["cassava","rice-white","rice-brown"], "tier_3_contextual": ["rice-flour"]},
    "carb_meal_context": {
        "breakfast": ["oats","tapioca","rice-flour","corn-flour","sweet-potato"],
        "lunch": ["potato","sweet-potato","cassava","rice-white","rice-brown"],
        "dinner": ["potato","sweet-potato","cassava","rice-white","rice-brown"],
        "snack": ["oats","tapioca","rice-flour","banana","papaya","sweet-potato"],
    },
    "methodology_exclude_default": ["bread-whole","bread-white","pasta","pasta-whole"],
    "satiety_weight_by_goal": {"fat_loss": 3.0, "maintenance": 1.0, "muscle_gain": 0.3},
    "satiety_bonus": {"HIGH": 20, "MEDIUM": 10, "LOW": 0},
    "meal_role_scores": {"primary_protein": 50, "primary_carb": 40, "vegetable": 20,
                         "fruit": 15, "dairy": 15, "fat_source": 12, "legume": 10, "recipe_component": 0},
    "max_same_protein_per_day": 2,
}

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

def calculate_goal_calories(tdee, goal):
    gl = (goal or "").lower()
    if "fat" in gl or "perda" in gl: return round(tdee*0.80, 0)
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

def compute_macro_targets(w, h, age, sex, td, goal, al="moderate"):
    bmr = calculate_bmr(w,h,age,sex)
    af = calculate_activity_factor(td,al)
    tdee = calculate_tdee(bmr,af)
    gc = calculate_goal_calories(tdee,goal)
    pg = calculate_protein_target(w,goal)
    fg = calculate_fat_target(w,goal)
    cg = calculate_carb_target(gc,pg,fg)
    return {"bmr":bmr,"tdee":tdee,"activity_factor":af,"goal_calories":gc,
            "protein_g":pg,"fat_g":fg,"carbs_g":cg,
            "protein_kcal":round(pg*4),"fat_kcal":round(fg*9),"carbs_kcal":round(cg*4)}

def _food_compatible(food, pn, used_ids):
    if food["id"] in set(pn.get("avoid_foods") or []): return False
    for a in (pn.get("allergies") or []):
        if food["id"] in ALLERGY_EXCLUDE_IDS.get(str(a).lower().strip(), set()): return False
    rt = set(pn.get("dietary_restrictions") or [])
    vegetarian_ok_ids = {"eggs-whole","egg-whites","whey-protein","tofu","soy-protein",
        "beans-black","beans-carioca","lentils","chickpeas",
        "yogurt-greek","cheese-cottage","cheese-mozzarella","milk-whole","milk-skim","yogurt-natural"}
    lactose_ids = {"milk-whole","yogurt-natural","yogurt-greek","cheese-mozzarella","cheese-cottage"}
    if "vegetarian" in rt and food.get("category")=="PROTEIN" and food["id"] not in vegetarian_ok_ids:
        return False
    if "lactose_free" in rt and food["id"] in lactose_ids:
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
        R.shuffle([scored[-1][0]])
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored and scored[0][0] > 0 else None

def calculate_meal_portions(food_ids, target_cal, target_protein, target_fat=0, goal="maintenance"):
    """Size the primary_protein and fat_source foods directly from their macro targets
    first (so the meal actually converges on target_protein/target_fat), then split the
    remaining calorie budget evenly across the rest, as before."""
    portions = {}
    if not food_ids: return portions
    remaining_cal = target_cal
    sized = set()

    kcal_cap = FORGE_COACH_METHODOLOGY["meal_role_kcal_share_cap"]

    protein_fid = next((fid for fid in food_ids
                         if "primary_protein" in FOOD_INDEX.get(fid, {}).get("roles", [])), None)
    if protein_fid and target_protein > 0:
        f = FOOD_INDEX.get(protein_fid, {})
        ppg = f.get("protein_g", 0) / max(1, f.get("grams", 100))
        if ppg > 0:
            grams = target_protein / ppg
            lo, hi = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category", "PROTEIN"), [50, 250])
            grams = max(lo, min(hi, round(grams, -1)))
            cpg = f.get("kcal", 100) / max(1, f.get("grams", 100))
            max_kcal = target_cal * kcal_cap["primary_protein"]
            if cpg > 0 and grams * cpg > max_kcal:
                grams = max(lo, round(max_kcal / cpg, -1))
            portions[protein_fid] = grams
            sized.add(protein_fid)
            remaining_cal -= grams * cpg

    fat_fid = next((fid for fid in food_ids
                     if fid not in sized and "fat_source" in FOOD_INDEX.get(fid, {}).get("roles", [])), None)
    if fat_fid and target_fat > 0:
        f = FOOD_INDEX.get(fat_fid, {})
        fpg = f.get("fat_g", 0) / max(1, f.get("grams", 100))
        if fpg > 0:
            grams = target_fat / fpg
            lo, hi = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category", "FAT"), [5, 40])
            grams = max(lo, min(hi, round(grams, -1)))
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
    remaining_ids = [fid for fid in food_ids if fid not in sized]
    veg_weight = 3.0 if _goal_key(goal) == "fat_loss" else 1.0
    weights = {fid: (veg_weight if FOOD_INDEX.get(fid, {}).get("category") == "VEGETABLE" else 1.0)
               for fid in remaining_ids}
    total_w = sum(weights.values()) or 1
    for fid in remaining_ids:
        f = FOOD_INDEX.get(fid, {})
        share = remaining_cal * (weights[fid] / total_w)
        cpg = f.get("kcal",100)/max(1,f.get("grams",100))
        grams = share/max(0.1,cpg) if cpg>0 else 100
        lo,hi = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category","PROTEIN"),[50,250])
        portions[fid] = max(lo, min(hi, round(grams,-1)))
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

def generate_meal(meal_name, meal_type, target_cal, target_protein, target_fat,
                  pn, used_food_ids, goal="maintenance", daily_used_proteins=None,
                  day_index=0, is_later_meal=False):
    tn = meal_name.lower(); mt = "lunch"
    if "cafe" in tn or "manha" in tn: mt = "breakfast"
    elif "lanche" in tn or "tarde" in tn or "snack" in tn: mt = "snack"
    elif "jantar" in tn: mt = "dinner"
    elif "pre" in tn or "pos" in tn: mt = "snack"

    total_roles = []
    if mt in ("lunch","dinner"):
        total_roles = [("primary_protein","PROTEIN"),("primary_carb","CARBOHYDRATE"),
                       ("vegetable","VEGETABLE"),("legume","LEGUME"),("fat_source","FAT")]
        # Cutting: a second vegetable (like a real plate — main veg + salad) adds
        # near-free volume/satiety without meaningfully spending the calorie budget.
        if _goal_key(goal) == "fat_loss":
            total_roles.append(("vegetable","VEGETABLE"))
    elif mt == "breakfast":
        total_roles = [("primary_protein","PROTEIN"),("primary_carb","CARBOHYDRATE"),
                       ("fruit","FRUIT"),("fat_source","FAT")]
    else:
        total_roles = [("primary_protein","PROTEIN"),("primary_carb","CARBOHYDRATE"),
                       ("fruit","FRUIT")]

    ctx = FORGE_COACH_METHODOLOGY.get("carb_meal_context",{}).get(mt,[])
    exclude = set(FORGE_COACH_METHODOLOGY.get("methodology_exclude_default",[]))
    dislike = set(pn.get("disliked_foods") or [])

    # Deterministic variety: rotate protein/veg/legume/fruit per day_index
    if daily_used_proteins is None: daily_used_proteins = {}
    prot_count = daily_used_proteins.copy()
    max_same = FORGE_COACH_METHODOLOGY.get("max_same_protein_per_day", 2)

    selected = []; mu = set(used_food_ids)
    for role, cat in total_roles:
        if role == "fat_source" and target_fat < 5:
            continue
        cands = list(FOODS_BY_ROLE.get(role, FOODS_BY_CAT.get(cat, [])))
        cands = [c for c in cands if c not in exclude and c not in dislike]

        if role == "primary_carb":
            if ctx:
                ctxc = [c for c in cands if c in ctx]
                if ctxc: cands = ctxc
            remaining = [c for c in cands if c not in mu]
            if remaining: cands = remaining

        if role == "primary_protein":
            remaining = [c for c in cands if c not in mu]
            if remaining:
                varied = [c for c in remaining if prot_count.get(c, 0) < max_same]
                if varied: remaining = varied
            if remaining: cands = remaining

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
    foods = [{"food_id": fid, "grams": portions.get(fid, 100), "food": FOOD_INDEX.get(fid, {})} for fid in selected]
    return {"name": meal_name, "target_cal": round(target_cal), "target_protein": round(target_protein),
            "foods": foods}

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
    SATIETY_CATS = {"VEGETABLE", "FRUIT", "LEGUME"}

    for _ in range(max_iterations):
        totals = sum_plan_totals(meals)
        cal_gap = targets["goal_calories"] - totals["kcal"]
        fat_gap = targets["fat_g"] - totals["fat_g"]
        if abs(cal_gap) < targets["goal_calories"] * 0.03 and abs(fat_gap) < 5:
            break
        protein_room = totals["protein_g"] - min_daily_protein
        for m in meals:
            mk, mp, mc, mf = _meal_totals(m)
            if cal_gap < -30:
                for item in m.get("foods",[]):
                    f = FOOD_INDEX.get(item["food_id"],{})
                    if "fat_source" in f.get("roles",[]): continue  # fat has its own dedicated correction below
                    is_protein = "primary_protein" in f.get("roles",[])
                    is_satiety = f.get("category") in SATIETY_CATS
                    if is_protein:
                        if protein_room <= 0: continue  # never cut protein below the daily guardrail
                        ppg = f.get("protein_g", 0) / max(1, f.get("grams", 100))
                        max_room_grams = (protein_room / ppg) if ppg > 0 else 0
                        step = round(min(8, item["grams"] - 60, max_room_grams))
                        if step <= 0: continue
                        item["grams"] -= step
                        protein_room -= step * ppg
                    elif is_satiety and satiety_priority:
                        continue  # preserve satiety/volume foods in cutting; shrink dense carbs instead
                    else:
                        item["grams"] = max(50, item["grams"] - 20)
            elif cal_gap > 20:
                for item in m.get("foods",[]):
                    f = FOOD_INDEX.get(item["food_id"],{})
                    if "fat_source" in f.get("roles",[]): continue  # fat has its own dedicated correction below
                    is_protein = "primary_protein" in f.get("roles",[])
                    is_satiety = f.get("category") in SATIETY_CATS
                    if satiety_priority and not is_satiety and not is_protein:
                        continue  # in cutting, close the remaining gap with volume foods, not dense carbs
                    lo,hi = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category","PROTEIN"),[50,250])
                    item["grams"] = min(hi*1.2, item["grams"] + 15)

            # Fat correction runs independently of the overall calorie gap: a meal
            # already close to its calorie target would otherwise leave fat permanently
            # stuck (neither cal_gap branch above ever fires to nudge it).
            fat_items = [it for it in m.get("foods",[]) if "fat_source" in FOOD_INDEX.get(it["food_id"],{}).get("roles",[])]
            if fat_gap > 5:
                bumped = False
                for item in fat_items:
                    f = FOOD_INDEX.get(item["food_id"],{})
                    lo,hi = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category","FAT"),[5,40])
                    if item["grams"] < hi:
                        item["grams"] = min(hi, item["grams"] + min(8, max(1, round(abs(fat_gap)/6))))
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
                        lo,hi = FORGE_COACH_METHODOLOGY["portion_limits"].get(f.get("category","FAT"),[5,40])
                        grams = round(min(abs(fat_gap), 15) / max(0.01, fpg))
                        m["foods"].append({"food_id": fid, "grams": max(lo, min(hi, grams)), "food": f})
            elif fat_gap < -5:
                for item in fat_items:
                    item["grams"] = max(3, item["grams"] - 5)
    return meals

def generate_daily_plan(targets, pn, meal_count=4, goal="maintenance"):
    m = FORGE_COACH_METHODOLOGY
    dist = m["meal_distribution"].get(meal_count, m["meal_distribution"][4])
    names = m["meal_names"].get(meal_count, m["meal_names"][4])
    gc, gp, gf = targets["goal_calories"], targets["protein_g"], targets["fat_g"]
    meals = []; ug = set(); dp = {}
    for i in range(meal_count):
        mc = gc * dist[i]; mp = gp * dist[i]; mf = gf * dist[i]
        meals.append(generate_meal(names[i], names[i], mc, mp, mf, pn, ug, goal, dp, i))
        for f2 in meals[-1]["foods"]:
            ug.add(f2["food_id"])
            probe = FOOD_INDEX.get(f2["food_id"],{}).get("primary_muscle","")
            for r in FOOD_INDEX.get(f2["food_id"],{}).get("roles",[]):
                if r == "primary_protein": dp[f2["food_id"]] = dp.get(f2["food_id"], 0) + 1
    pre_reconciliation_totals = sum_plan_totals(meals)
    meals = _reconcile_daily(meals, targets, pn, goal)
    totals = sum_plan_totals(meals)
    return {"meals": meals, "daily_totals": totals, "pre_reconciliation_totals": pre_reconciliation_totals,
            "targets": targets, "engine_version": m["engine_version"], "methodology_version": m["coach_version"]}

def sum_plan_totals(meals):
    t = {"kcal":0,"protein_g":0,"carbs_g":0,"fat_g":0,"fiber_g":0}
    for m in meals:
        mk,mp,mc,mf = _meal_totals(m)
        t["kcal"]+=mk; t["protein_g"]+=mp; t["carbs_g"]+=mc; t["fat_g"]+=mf
    for k in t: t[k] = round(t[k], 1)
    return t

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

def find_substitutes(food_id, pn, current_meal_foods, max_results=3, orig_grams=100, goal="maintenance",
                      meal=None, daily_totals=None, targets=None):
    src = FOOD_INDEX.get(food_id)
    if not src: return []
    av = set(pn.get("avoid_foods") or [])
    dislike = set(pn.get("disliked_foods") or [])
    used = set(current_meal_foods)
    tier = SUB_TIER.get(food_id, [])
    group = None
    for g, ids in SUB_GROUPS.items():
        if food_id in ids: group = g; break
    all_cands = list(tier) + ([i for i in SUB_GROUPS.get(group,[]) if i != food_id and i not in tier]) if group else []

    full_context = meal is not None and daily_totals is not None and targets is not None
    meal_before = _meal_totals({"foods": meal}) if full_context else None
    if full_context:
        mk, mp, mc, mf = meal_before
        meal_before = {"kcal": mk, "protein_g": mp, "carbs_g": mc, "fat_g": mf}

    results = []
    for cid in all_cands:
        if len(results) >= max_results: break
        if cid in av or cid in dislike or cid in used: continue
        f = FOOD_INDEX.get(cid)
        if not f or not _food_compatible(f, pn, used): continue
        ng, reason = recalculate_substitution_portion(cid, food_id, orig_grams)
        if full_context:
            evald = evaluate_goal_directional_substitution(
                food_id, cid, orig_grams, ng, goal, meal_before, daily_totals, targets, pn)
            if not evald["valid"]: continue
            results.append((cid, ng, reason, evald))
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

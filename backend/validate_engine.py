"""Generate full programs for 5 validation profiles using the real engine."""
import sys, json, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

os.environ["PYTHONIOENCODING"] = "utf-8"

from engine import (
    EXERCISES, EXERCISE_INDEX, FRONTEND_EXERCISE_LIST,
    determine_split, get_day_targets, calculate_session_capacity,
    select_exercises_for_day, build_exercise_prescription,
    calculate_weekly_volume, build_all_sessions,
    validate_sessions, count_weekly_sets_per_muscle,
    SPLIT_FULL_BODY, SPLIT_UPPER_LOWER, SPLIT_PUSH_PULL_LEGS,
    SPLIT_UL_PPL, SPLIT_UPPER_LOWER_PPL,
)
from muscles import to_frontend, get_profile_priorities_internal

PROFILES = {
    "A": {
        "id": "val-a", "name": "Iniciante A",
        "experience": "Iniciante", "goal": "Hipertrofia",
        "days": 3, "session_minutes": 60,
        "priorities": [], "assessment": {},
        "equipment": ["Academia completa"],
    },
    "B": {
        "id": "val-b", "name": "Intermediario B",
        "experience": "Intermediario", "goal": "Hipertrofia",
        "days": 4, "session_minutes": 75,
        "priorities": ["Deltoide lateral", "Dorsais / largura"],
        "assessment": {
            "Deltoide lateral": {"development": "fraco", "priority": "alta"},
            "Dorsais / largura": {"development": "fraco", "priority": "alta"},
        },
        "equipment": ["Academia completa"],
    },
    "C": {
        "id": "val-c", "name": "Avancado C",
        "experience": "Bodybuilder", "goal": "Hipertrofia",
        "days": 5, "session_minutes": 90,
        "priorities": ["Deltoide lateral", "Posteriores", "Costas / espessura"],
        "assessment": {
            "Deltoide lateral": {"development": "muito fraco", "priority": "maxima"},
            "Posteriores": {"development": "fraco", "priority": "alta"},
            "Costas / espessura": {"development": "fraco", "priority": "alta"},
        },
        "equipment": ["Academia completa"],
    },
    "D": {
        "id": "val-d", "name": "Avancado D",
        "experience": "Avancado", "goal": "Hipertrofia",
        "days": 6, "session_minutes": 90,
        "priorities": ["Peitoral superior", "Deltoide lateral"],
        "assessment": {
            "Peitoral superior": {"development": "muito fraco", "priority": "maxima"},
            "Deltoide lateral": {"development": "fraco", "priority": "alta"},
        },
        "equipment": ["Academia completa"],
    },
    "E": {
        "id": "val-e", "name": "Limitado E",
        "experience": "Intermediario", "goal": "Hipertrofia",
        "days": 4, "session_minutes": 60,
        "priorities": [],
        "assessment": {},
        "equipment": ["dumbbell", "bench"],
        "avoid_exercises": ["bb-bench-press", "bb-squat"],
    },
}

print("=" * 100)
print("FORGE TRAINING ENGINE v2 -- VALIDATION RUN")
print("=" * 100)

all_sessions_for_schema = None

for label, profile in PROFILES.items():
    print("\n" + "-" * 100)
    print(f"PERFIL {label}: {profile['name']} | {profile['experience']} | {profile['days']}d/wk | {profile['session_minutes']}min")
    pri_display = profile.get('priorities', [])
    avoid_display = profile.get('avoid_exercises', [])
    eq_display = profile.get('equipment', [])
    if pri_display:
        print(f"  Priorities: {', '.join(pri_display)}")
    if avoid_display:
        print(f"  Avoid: {', '.join(avoid_display)}")
    if eq_display:
        print(f"  Equipment: {', '.join(eq_display)}")
    print("-" * 100)

    split_type = determine_split(profile['days'], profile['experience'])
    sessions = build_all_sessions(profile, split_type, profile['days'], profile['session_minutes'])
    warnings = validate_sessions(sessions, profile, split_type, profile['days'], profile['session_minutes'])
    if label == "A":
        all_sessions_for_schema = sessions

    for i, s in enumerate(sessions):
        day_targets = get_day_targets(split_type, i, profile['days'])[1]
        target_display = [to_frontend(t) for t in day_targets]
        total_sets = sum(e['sets'] for e in s['exercises'])
        print(f"\n  DIA {s['day']}: {s['label']} | DEMAND: {s['demand']} | {len(s['exercises'])} ex | {total_sets} sets")
        print(f"  Targets: {', '.join(target_display)}")
        print(f"  {'ID':<28} {'Name':<36} {'Primary':<20} {'Sets':>4} {'Reps':>8} {'RIR':>4} {'Rest':>8}  Reason")
        print(f"  {'-':-<28} {'-':-<36} {'-':-<20} {'-':-<4} {'-':-<8} {'-':-<4} {'-':-<8}  {'-':-<50}")

        for ex_item in s['exercises']:
            ex = EXERCISE_INDEX.get(ex_item['exercise_id'], {})
            if not ex:
                print(f"  {'!! MISSING: ' + ex_item['exercise_id']}")
                continue
            primary = to_frontend(ex.get('primary_muscle', '?'))
            is_pri = ex.get('primary_muscle') in get_profile_priorities_internal(profile)
            reason_parts = []
            if is_pri:
                reason_parts.append("PRIORITY")
            else:
                reason_parts.append("target")
            cat = ex.get('category', '?')
            reason_parts.append(cat)
            reason_parts.append(f"s:{ex.get('stability','?')}")
            reason_parts.append(f"f:{ex.get('fatigue','?')}")
            reason = ', '.join(reason_parts)

            print(f"  {ex_item['exercise_id']:<28} {ex.get('name','?')[:34]:<36} {primary:<20} {ex_item['sets']:>4} {ex_item['reps']:>8} {ex_item['rir']:>4} {ex_item['rest']:>8}  {reason}")

        total_time = sum(e['sets'] * (int(EXERCISE_INDEX.get(e['exercise_id'], {}).get('default_rest_seconds', 90)) + 40) for e in s['exercises'])
        total_min = total_time // 60
        print(f"  ~{total_min} min estimated")

    vol = count_weekly_sets_per_muscle(sessions)
    vol_plan = calculate_weekly_volume(profile, split_type, profile['days'])
    print(f"\n  ---- WEEKLY VOLUME ----")
    print(f"  {'Muscle':<22} {'Sets':>5} {'Tier':>14} {'Min':>5} {'Target':>6} {'Max':>5} {'Status':>14}")
    for m in sorted(vol_plan.keys(), key=lambda m: -vol.get(m, 0)):
        fn = to_frontend(m)
        actual = vol.get(m, 0)
        plan = vol_plan[m]
        if actual == 0:
            st = "zero OK" if plan['tier'] == 'maintenance' else "!! ZERO (needed)"
        elif actual < plan['min_sets']:
            st = "LOW (<min)"
        elif actual > plan['max_sets']:
            st = "HIGH (>max)"
        else:
            st = "OK"
        tier_label = f"({plan['tier']})"
        print(f"  {fn:<22} {actual:>5} {tier_label:>14} {plan['min_sets']:>5} {plan['target_sets']:>6} {plan['max_sets']:>5} {st:>14}")

    if warnings:
        print(f"\n  ---- !! WARNINGS ({len(warnings)}) ----")
        for w in warnings:
            print(f"  !! {w}")
    else:
        print(f"\n  ---- OK No warnings ----")

# Schema comparison
print(f"\n{'=' * 100}")
print("SCHEMA COMPARISON: program JSON output vs frontend Workout contract")
print(f"{'=' * 100}")
if all_sessions_for_schema and all_sessions_for_schema[0].get('exercises'):
    ex0 = all_sessions_for_schema[0]['exercises'][0]
    expected = ['exercise_id', 'sets', 'reps', 'rir', 'rest', 'load', 'technique', 'technique_id']
    present = [k for k in expected if k in ex0]
    missing = [k for k in expected if k not in ex0]
    print(f"  Workout expects: {expected}")
    print(f"  Engine provides:  {present}")
    print(f"  Missing:          {missing}")
    for k in present:
        print(f"    {k}: type={type(ex0[k]).__name__}, sample={ex0[k]}")

print(f"\n{'=' * 100}")
print("CRITICAL AUDIT QUESTIONS")
print(f"{'=' * 100}")
print("See analysis below.")

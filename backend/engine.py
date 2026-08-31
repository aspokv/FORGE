"""
FORGE Training Engine v3.0 — periodization + progression + deload + readiness integration.
"""
import json
import math
import random
from pathlib import Path
from datetime import datetime as dt_mod, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Set

from muscles import (
    to_internal, to_frontend, get_profile_priorities_internal, get_ranked_priorities,
    get_assessment_internal, MUSCLE_IDS as ALL_MUSCLE_IDS,
    LEGACY_TO_INTERNAL, FRONTEND_MUSCLES, REVERSE_MUSCLE_MAP,
)

ROOT_DIR = Path(__file__).parent
with open(ROOT_DIR / "exercises.json", encoding="utf-8") as f:
    EXERCISES: List[Dict[str, Any]] = json.load(f)

EXERCISE_INDEX: Dict[str, Dict[str, Any]] = {e["id"]: e for e in EXERCISES}
FRONTEND_EXERCISE_LIST: List[Dict[str, Any]] = [
    {"id": e["id"], "name": e["name"], "muscle": to_frontend(e["primary_muscle"]),
     "secondary": [to_frontend(s) for s in e.get("secondary_muscles", [])],
     "equipment": e.get("equipment", ["machine"])[0] if e.get("equipment") else "machine",
     "pattern": e.get("movement_pattern", ""),
     "fatigue": e.get("fatigue", "medium"),
     "alternatives": []}
    for e in EXERCISES
]
for ex in FRONTEND_EXERCISE_LIST:
    src = EXERCISE_INDEX[ex["id"]]
    alt_ids = [a["id"] for a in EXERCISES
               if a["id"] != ex["id"] and a["primary_muscle"] == src["primary_muscle"]
               and a.get("movement_pattern") == src.get("movement_pattern")][:3]
    if not alt_ids:
        alt_ids = [e["id"] for e in EXERCISES if e["id"] != ex["id"]][:1]
    # alternative_ids is what the substitution-apply endpoint validates a swap against
    # (item: real substitution, not just listing) — alternatives (names) is unchanged
    # for any existing frontend consumer that only ever read the display strings.
    ex["alternative_ids"] = alt_ids
    ex["alternatives"] = [EXERCISE_INDEX[aid]["name"] for aid in alt_ids]

RANDOM = random.Random()

SPLIT_FULL_BODY = "full_body"
SPLIT_UPPER_LOWER = "upper_lower"
SPLIT_PUSH_PULL_LEGS = "ppl"
SPLIT_UL_PPL = "ul_ppl"
SPLIT_UPPER_LOWER_PPL = "upper_lower_ppl"
SPLIT_ABC = "abc"
SPLIT_ABCD = "abcd"
SPLIT_ABCDE = "abcde"

SPLIT_LABELS = {
    SPLIT_FULL_BODY: "Full Body",
    SPLIT_UPPER_LOWER: "Upper / Lower",
    SPLIT_PUSH_PULL_LEGS: "Push / Pull / Legs",
    SPLIT_UL_PPL: "Upper / Lower + PPL",
    SPLIT_UPPER_LOWER_PPL: "Upper / Lower + PPL",
    SPLIT_ABC: "ABC clássico",
    SPLIT_ABCD: "ABCD",
    SPLIT_ABCDE: "ABCDE",
}

UPPER_TARGETS = ["mid_chest", "upper_chest", "lats", "upper_back", "front_delts", "side_delts", "rear_delts", "biceps", "triceps"]
LOWER_TARGETS = ["quads", "hamstrings", "glutes", "adductors", "calves"]
PUSH_TARGETS = ["mid_chest", "upper_chest", "front_delts", "side_delts", "triceps"]
PULL_TARGETS = ["lats", "upper_back", "rear_delts", "biceps"]
LEGS_TARGETS = ["quads", "hamstrings", "glutes", "adductors", "calves"]
FULL_BODY_A_TARGETS = ["quads", "mid_chest", "upper_chest", "lats", "upper_back", "side_delts", "biceps", "triceps"]
FULL_BODY_B_TARGETS = ["hamstrings", "glutes", "mid_chest", "lats", "upper_back", "front_delts", "rear_delts", "calves"]

# Muscles that the validator should NOT complain about when absent
# (they are not essential target muscles in most splits)
OPTIONAL_MUSCLES = {"abs", "obliques", "traps"}

VOLUME_TIERS = {
    "maintenance": {"min_sets": 4, "target_sets": 6, "max_sets": 8},
    "normal": {"min_sets": 6, "target_sets": 8, "max_sets": 12},
    # Prioridade secundaria: enfase real (acima de "normal"), mas abaixo da principal —
    # e o que impede que marcar tres regioes vire tres treinos de especializacao ao mesmo
    # tempo, estourando a recuperacao.
    "priority_secondary": {"min_sets": 8, "target_sets": 11, "max_sets": 16},
    "priority": {"min_sets": 10, "target_sets": 14, "max_sets": 20},
}

# Public, evidence-oriented programming styles. These are method families, not copied
# personalities or proprietary programs from individual coaches. The deterministic
# engine remains the authority; the LLM may explain the result but cannot bypass this
# contract.
TRAINING_METHOD_PROFILES = {
    "balanced_hypertrophy": {
        "label": "Hipertrofia equilibrada",
        "rir_range": "1-3",
        "progression": "double_progression",
        "volume_strategy": "minimum_effective_to_recoverable",
    },
    "high_intensity": {
        "label": "Alta intensidade e volume controlado",
        "rir_range": "0-2",
        "progression": "double_progression",
        "volume_strategy": "lower_volume_high_effort",
    },
    "specialization": {
        "label": "Especializacao de prioridades",
        "rir_range": "1-3",
        "progression": "double_progression",
        "volume_strategy": "priority_biased",
    },
    "progressive_volume": {
        "label": "Volume progressivo",
        "rir_range": "1-3",
        "progression": "double_progression",
        "volume_strategy": "gradual_volume_build",
    },
}

# Tiers com enfase declarada — usados onde "priority" sozinho ja nao descreve o conjunto.
PRIORITY_TIERS = ("priority", "priority_secondary")

EXERCISE_BY_MUSCLE: Dict[str, List[str]] = {
    m: [e["id"] for e in EXERCISES if e["primary_muscle"] == m]
    for m in ALL_MUSCLE_IDS
}


def _equipment_ok(exercise: dict, profile: dict) -> bool:
    """Hard filter: returns True if exercise equipment is compatible with profile."""
    equipment = profile.get("equipment") or []
    if not equipment:
        return True
    if "Academia completa" in equipment:
        return True
    ex_equip = exercise.get("equipment", [])
    if "bodyweight" in ex_equip:
        return True
    return any(eq in ex_equip for eq in equipment)


def compatible_splits(days: int, experience: str = "Intermediário") -> List[str]:
    """Return only divisions that fit the athlete's real weekly availability.

    The athlete may express a preference, but the engine never accepts a five-day
    division for a three-day schedule. The order is deliberate: the first option is
    the default recommendation and the remaining options are valid trade-offs.
    """
    days = max(1, min(7, int(days or 3)))
    advanced = (experience or "").lower() in ("avançado", "avancado", "bodybuilder")
    if days == 1:
        return [SPLIT_FULL_BODY]
    if days == 2:
        return [SPLIT_FULL_BODY, SPLIT_UPPER_LOWER]
    if days == 3:
        return ([SPLIT_PUSH_PULL_LEGS, SPLIT_FULL_BODY, SPLIT_ABC]
                if advanced else [SPLIT_FULL_BODY, SPLIT_PUSH_PULL_LEGS, SPLIT_ABC])
    if days == 4:
        return [SPLIT_UPPER_LOWER, SPLIT_ABCD]
    if days == 5:
        return ([SPLIT_UL_PPL, SPLIT_ABCDE, SPLIT_UPPER_LOWER_PPL]
                if advanced else [SPLIT_UPPER_LOWER_PPL, SPLIT_UL_PPL, SPLIT_ABCDE])
    # Six or seven scheduled sessions use a repeated three-day structure; readiness
    # and periodization still own volume reductions and deloads.
    return [SPLIT_PUSH_PULL_LEGS, SPLIT_ABC]


def determine_split(days: int, experience: str, goal: str = "Hipertrofia",
                    preference: Optional[str] = None) -> str:
    if days <= 0: days = 3
    options = compatible_splits(days, experience)
    return preference if preference in options else options[0]


def profile_split_preference(profile: dict) -> Optional[str]:
    """Accept the new stable id and understand the legacy free-text assessment field."""
    explicit = str(profile.get("split_preference") or "").strip().lower()
    if explicit in SPLIT_LABELS:
        return explicit
    raw = str(profile.get("split") or "").strip().lower()
    normalized = (raw.replace("–", "-").replace("—", "-")
                  .replace(" ", "").replace("/", ""))
    aliases = {
        "fullbody": SPLIT_FULL_BODY,
        "upperlower": SPLIT_UPPER_LOWER,
        "superiorinferior": SPLIT_UPPER_LOWER,
        "ppl": SPLIT_PUSH_PULL_LEGS,
        "pushpulllegs": SPLIT_PUSH_PULL_LEGS,
        "ulppl": SPLIT_UL_PPL,
        "upperlower+ppl": SPLIT_UL_PPL,
        "abc": SPLIT_ABC,
        "abcd": SPLIT_ABCD,
        "abcde": SPLIT_ABCDE,
    }
    return aliases.get(normalized)


def get_day_targets(split_type: str, day_index: int, days: int) -> Tuple[str, List[str]]:
    if split_type == SPLIT_FULL_BODY:
        is_a = (day_index % 2 == 0)
        label = f"Full Body {'A' if is_a else 'B'}"
        return label, list(FULL_BODY_A_TARGETS if is_a else FULL_BODY_B_TARGETS)

    if split_type == SPLIT_UPPER_LOWER:
        is_upper = (day_index % 2 == 0)
        label = f"{'Upper' if is_upper else 'Lower'} {(day_index // 2) + 1}"
        return label, list(UPPER_TARGETS if is_upper else LOWER_TARGETS)

    if split_type == SPLIT_PUSH_PULL_LEGS:
        names = ["Push", "Pull", "Legs"]
        tlists = [PUSH_TARGETS, PULL_TARGETS, LEGS_TARGETS]
        cycle = day_index % 3
        rnd = (day_index // 3) + 1
        label = f"{names[cycle]} {rnd}" if days >= 6 else names[cycle]
        return label, list(tlists[cycle])

    if split_type == SPLIT_UL_PPL:
        mapping = [(0, "Upper 1", UPPER_TARGETS), (1, "Lower 1", LOWER_TARGETS),
                   (2, "Push", PUSH_TARGETS), (3, "Pull", PULL_TARGETS), (4, "Legs", LEGS_TARGETS)]
        idx = day_index % 5
        return mapping[idx][1], list(mapping[idx][2])

    if split_type == SPLIT_UPPER_LOWER_PPL:
        mapping = [(0, "Upper 1", UPPER_TARGETS), (1, "Lower 1", LOWER_TARGETS),
                   (2, "Push", PUSH_TARGETS), (3, "Pull", PULL_TARGETS), (4, "Upper 2", UPPER_TARGETS)]
        idx = day_index % 5
        return mapping[idx][1], list(mapping[idx][2])

    if split_type == SPLIT_ABC:
        mapping = [("A · Peito, ombros e tríceps", PUSH_TARGETS),
                   ("B · Costas e bíceps", PULL_TARGETS),
                   ("C · Pernas", LEGS_TARGETS)]
        label, targets = mapping[day_index % 3]
        cycle = day_index // 3 + 1
        return (f"{label} {cycle}" if days >= 6 else label), list(targets)

    if split_type == SPLIT_ABCD:
        mapping = [
            ("A · Peito e tríceps", ["mid_chest", "upper_chest", "triceps"]),
            ("B · Costas e bíceps", ["lats", "upper_back", "rear_delts", "biceps"]),
            ("C · Pernas", LEGS_TARGETS),
            ("D · Ombros e braços", ["front_delts", "side_delts", "rear_delts", "biceps", "triceps"]),
        ]
        label, targets = mapping[day_index % 4]
        return label, list(targets)

    if split_type == SPLIT_ABCDE:
        mapping = [
            ("A · Peito", ["mid_chest", "upper_chest", "front_delts", "triceps"]),
            ("B · Costas", ["lats", "upper_back", "rear_delts", "biceps"]),
            ("C · Pernas", LEGS_TARGETS),
            ("D · Ombros", ["front_delts", "side_delts", "rear_delts", "triceps"]),
            ("E · Braços", ["biceps", "triceps", "side_delts"]),
        ]
        label, targets = mapping[day_index % 5]
        return label, list(targets)

    return f"Sessão {day_index + 1}", list(UPPER_TARGETS)


def get_experience_level(experience: str) -> str:
    exp = (experience or "intermediário").lower()
    if exp in ("iniciante", "recreativo"): return "beginner"
    if exp in ("intermediário", "intermediário"): return "intermediate"
    return "advanced"


def _get_day_type(split_type: str, day_index: int, days: int) -> str:
    """Returns upper/lower/full_body/push/pull/legs for a given day."""
    if split_type == SPLIT_FULL_BODY:
        return "full_body"
    if split_type == SPLIT_UPPER_LOWER:
        return "upper" if day_index % 2 == 0 else "lower"
    if split_type == SPLIT_PUSH_PULL_LEGS:
        return ["push", "pull", "legs"][day_index % 3]
    if split_type in (SPLIT_UL_PPL, SPLIT_UPPER_LOWER_PPL):
        if day_index >= 5:
            return get_day_targets(split_type, day_index, days)[0].split()[0].lower()
        return get_day_targets(split_type, day_index, days)[0].split()[0].lower()
    if split_type == SPLIT_ABC:
        return ["push", "pull", "legs"][day_index % 3]
    if split_type == SPLIT_ABCD:
        return ["push", "pull", "legs", "upper"][day_index % 4]
    if split_type == SPLIT_ABCDE:
        return ["push", "pull", "legs", "upper", "upper"][day_index % 5]
    return "upper"


def calculate_session_capacity(experience: str, session_minutes: int, demand: str,
                               day_targets: List[str], split_type: str,
                               target_count: int = 0) -> int:
    base = max(3, session_minutes // 10)
    level = get_experience_level(experience)
    level_bonus = {"beginner": -1, "intermediate": 0, "advanced": 1}
    base += level_bonus.get(level, 0)

    demand_mod = {"HIGH": -1, "MODERATE": 0, "LOW": 1}
    base += demand_mod.get(demand.upper(), 0)

    if split_type == SPLIT_FULL_BODY:
        base = min(base, max(5, len(day_targets)))

    if target_count > base:
        base = max(base, target_count)

    return max(3, min(10, base))


def compute_exercise_score(exercise: dict, target: str, profile: dict,
                           used_ids: Set[str], demand: str, day_index: int) -> float:
    """Deterministic score for exercise selection."""
    score = 100.0

    if exercise["primary_muscle"] == target:
        score += 30
    elif target in exercise.get("secondary_muscles", []):
        score += 10
    else:
        score -= 50

    priorities = get_profile_priorities_internal(profile)
    if exercise["primary_muscle"] in priorities:
        score += 25
    if any(m in priorities for m in exercise.get("secondary_muscles", [])):
        score += 5

    avoid_ids = profile.get("avoid_exercises") or []
    if exercise["id"] in avoid_ids:
        return -1000.0

    if exercise["id"] in used_ids:
        score -= 60
    same_muscle_used = any(EXERCISE_INDEX.get(uid, {}).get("primary_muscle") == exercise["primary_muscle"]
                           for uid in used_ids)
    same_pattern_used = any(EXERCISE_INDEX.get(uid, {}).get("movement_pattern") == exercise.get("movement_pattern")
                            for uid in used_ids)
    if same_muscle_used:
        score -= 25
    if same_pattern_used and same_muscle_used:
        score -= 15

    level = get_experience_level(profile.get("experience", "Intermediário"))
    skill = exercise.get("skill_level", "beginner")
    if skill == "advanced" and level == "beginner":
        score -= 20
    if skill == "beginner" and level == "advanced" and demand.upper() == "LOW":
        score -= 3

    stability = exercise.get("stability", "medium")
    fatigue = exercise.get("fatigue", "medium")
    if demand.upper() == "HIGH" and stability == "high" and fatigue == "low" and exercise.get("category") != "isolation":
        score -= 5
    if demand.upper() == "LOW" and fatigue == "high":
        score -= 10

    return score


def _filter_candidates(candidates: List[str], profile: dict, used_ids: Set[str]) -> List[str]:
    """Hard filter: remove incompatible exercises before scoring."""
    avoid_ids = set(profile.get("avoid_exercises") or [])
    equipment = profile.get("equipment") or []
    valid = []
    for eid in candidates:
        ex = EXERCISE_INDEX.get(eid)
        if not ex:
            continue
        if eid in avoid_ids:
            continue
        if not _equipment_ok(ex, profile):
            continue
        valid.append(eid)
    return valid


def _pick_best(candidates: List[str], target: str, profile: dict,
               used_ids: Set[str], demand: str, day_index: int,
               prefer_variety: bool = False) -> Optional[Dict[str, Any]]:
    """Pick the single best exercise for a target muscle."""
    filtered = _filter_candidates(candidates, profile, used_ids)
    if not filtered:
        return None

    if prefer_variety and len(filtered) >= 2:
        scored = []
        for eid in filtered:
            ex = EXERCISE_INDEX[eid]
            s = compute_exercise_score(ex, target, profile, used_ids, demand, day_index)
            scored.append((s, ex))
        scored.sort(key=lambda x: -x[0])
        top_score = scored[0][0]
        top_scored = [(s, e) for s, e in scored if s >= top_score - 5]
        if len(top_scored) > 1:
            best = top_scored[(day_index + len(used_ids)) % len(top_scored)][1]
        else:
            best = top_scored[0][1]
    else:
        best_score = -float("inf")
        best = None
        for eid in filtered:
            ex = EXERCISE_INDEX[eid]
            s = compute_exercise_score(ex, target, profile, used_ids, demand, day_index)
            if s > best_score:
                best_score = s
                best = ex

    if best and best["id"] not in used_ids:
        return best
    return None


def select_exercises_for_day(day_targets: List[str], profile: dict, count: int,
                             demand: str = "MODERATE", day_index: int = 0,
                             is_variation_of_same_type: bool = False
                             ) -> List[Dict[str, Any]]:
    used_ids: Set[str] = set()
    selected: List[Dict[str, Any]] = []
    priorities = get_profile_priorities_internal(profile)

    target_queue = list(day_targets)
    if priorities:
        priority_in_targets = [t for t in priorities if t in target_queue]
        other = [t for t in target_queue if t not in priorities]
        target_queue = priority_in_targets + other

    # First pass: major muscle group targets
    for target in target_queue:
        if len(selected) >= count:
            break
        candidates = EXERCISE_BY_MUSCLE.get(target, [])
        if not candidates:
            continue
        ex = _pick_best(candidates, target, profile, used_ids, demand, day_index,
                       prefer_variety=is_variation_of_same_type)
        if ex:
            selected.append(ex)
            used_ids.add(ex["id"])

    # Second pass: guarantee arms and side/rear delts if count allows and they're in targets
    reserved_targets = ["biceps", "triceps", "side_delts", "rear_delts"]
    reserved_in_targets = [t for t in reserved_targets if t in day_targets]
    skipped_reserved = [t for t in reserved_in_targets
                       if not any(e["primary_muscle"] == t for e in selected)]
    for target in skipped_reserved:
        if len(selected) >= count + 1:
            break
        candidates = EXERCISE_BY_MUSCLE.get(target, [])
        if not candidates:
            continue
        ex = _pick_best(candidates, target, profile, used_ids, demand, day_index)
        if ex:
            selected.append(ex)
            used_ids.add(ex["id"])

    # Third pass: fill remaining capacity
    if len(selected) < count:
        for target in day_targets:
            if len(selected) >= count:
                break
            if any(ex["primary_muscle"] == target for ex in selected):
                continue
            candidates = EXERCISE_BY_MUSCLE.get(target, [])
            ex = _pick_best(candidates, target, profile, used_ids, demand, day_index)
            if ex:
                selected.append(ex)
                used_ids.add(ex["id"])

    return selected


def build_exercise_prescription(exercise: dict, profile: dict, demand: str,
                                is_priority: bool, weekly_sets_count: int) -> Dict[str, Any]:
    category = exercise.get("category", "compound")
    rep_range = exercise.get("default_rep_range", [8, 12])
    base_sets = exercise.get("default_sets", 3)
    base_rir = exercise.get("default_rir", 2)
    base_rest = exercise.get("default_rest_seconds", 90)

    if is_priority:
        base_sets = min(6, base_sets + 2)

    if category == "compound":
        if demand.upper() == "HIGH":
            base_sets = max(3, base_sets)
            base_rir = max(1, base_rir - 1)
            base_rest = max(120, base_rest)
        elif demand.upper() == "LOW":
            base_sets = max(2, base_sets - 1)

    if category == "isolation":
        if demand.upper() == "LOW":
            base_sets = max(2, base_sets)

    low, high = rep_range[0], rep_range[1]
    reps = f"{low}–{high}"

    return {
        "sets": base_sets,
        "reps": reps,
        "rir": str(base_rir) if base_rir <= 2 else "1–2",
        "rest": f"{base_rest // 60 * 60}s" if base_rest % 60 == 0 else f"{base_rest // 60} min",
        "rest_seconds": base_rest,
    }


def calculate_weekly_volume(profile: dict, split_type: str, days: int) -> Dict[str, Dict[str, Any]]:
    primary, secondary = get_ranked_priorities(profile)
    assessment = get_assessment_internal(profile)
    result: Dict[str, Dict[str, Any]] = {}

    for muscle_id in ALL_MUSCLE_IDS:
        tier = "normal"
        if muscle_id == primary:
            tier = "priority"
        elif muscle_id in secondary:
            tier = "priority_secondary"
        else:
            muscle_assess = assessment.get(muscle_id, {})
            dev = "proporcional"
            if isinstance(muscle_assess, dict):
                dev = muscle_assess.get("development", "proporcional")
            if dev in ("forte", "muito forte"):
                tier = "maintenance"

        tc = VOLUME_TIERS[tier]
        result[muscle_id] = {
            "tier": tier,
            "min_sets": tc["min_sets"],
            "target_sets": tc["target_sets"],
            "max_sets": tc["max_sets"],
        }
    return result


def count_weekly_sets_per_muscle(sessions: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for session in sessions:
        for ex_item in session.get("exercises", []):
            ex = EXERCISE_INDEX.get(ex_item.get("exercise_id", ""))
            if not ex:
                continue
            muscle = ex["primary_muscle"]
            sets = ex_item.get("sets", 3)
            counts[muscle] = counts.get(muscle, 0) + sets
    return counts


def count_effective_sets_per_muscle(sessions: List[Dict[str, Any]]) -> Dict[str, float]:
    """Direct sets count 1.0 and secondary work counts 0.5.

    This is intentionally a planning estimate, not a claim that every indirect set is
    biologically identical. It prevents the quality gate from prescribing redundant
    front-delt/triceps work after presses or biceps work after every pull just to make a
    raw direct-set counter look larger.
    """
    counts: Dict[str, float] = {}
    for session in sessions:
        for item in session.get("exercises", []):
            ex = EXERCISE_INDEX.get(item.get("exercise_id", ""))
            if not ex:
                continue
            sets = max(0, int(item.get("sets", 0)))
            primary = ex.get("primary_muscle")
            if primary:
                counts[primary] = counts.get(primary, 0.0) + sets
            for secondary in ex.get("secondary_muscles", []):
                counts[secondary] = counts.get(secondary, 0.0) + sets * 0.5
    return {muscle: round(value, 1) for muscle, value in counts.items()}


def count_training_frequency(sessions: List[Dict[str, Any]]) -> Dict[str, int]:
    frequency: Dict[str, int] = {}
    for session in sessions:
        touched = set()
        for item in session.get("exercises", []):
            ex = EXERCISE_INDEX.get(item.get("exercise_id", ""))
            if not ex:
                continue
            touched.add(ex.get("primary_muscle"))
            touched.update(ex.get("secondary_muscles", []))
        for muscle in touched - {None}:
            frequency[muscle] = frequency.get(muscle, 0) + 1
    return frequency


def build_program_quality_report(sessions: List[Dict[str, Any]], profile: dict,
                                 split_type: str, days: int,
                                 session_minutes: int) -> Dict[str, Any]:
    """Deterministic final gate shared by every algorithmic plan.

    The score rewards recoverable target coverage and frequency. It does not reward
    adding sets forever: session density and excessive volume lower the score.
    """
    direct = count_weekly_sets_per_muscle(sessions)
    effective = count_effective_sets_per_muscle(sessions)
    frequency = count_training_frequency(sessions)
    targets = calculate_weekly_volume(profile, split_type, days)
    priorities = set(get_profile_priorities_internal(profile))
    warnings = validate_sessions(sessions, profile, split_type, days, session_minutes)

    evaluated = [m for m in ALL_MUSCLE_IDS if m not in OPTIONAL_MUSCLES and effective.get(m, 0) > 0]
    coverage = []
    for muscle in evaluated:
        plan = targets[muscle]
        minimum = plan["min_sets"]
        actual = effective.get(muscle, 0)
        coverage.append(min(1.0, actual / max(1, minimum)))

    score = 100.0
    if coverage:
        score -= (1 - sum(coverage) / len(coverage)) * 45
    score -= min(25, 7 * len([w for w in warnings if "[ERROR]" in w]))
    score -= min(15, 2 * len([w for w in warnings if "Excessive volume" in w]))
    if days >= 4:
        priority_low_freq = [m for m in priorities if frequency.get(m, 0) < 2]
        score -= 6 * len(priority_low_freq)
    else:
        priority_low_freq = []

    total_sets = sum(direct.values())
    per_session = round(total_sets / max(1, len(sessions)), 1)
    style_id = profile.get("training_method") or ("specialization" if priorities else "balanced_hypertrophy")
    if style_id not in TRAINING_METHOD_PROFILES:
        style_id = "balanced_hypertrophy"
    return {
        "score": round(max(0, min(100, score))),
        "status": "approved" if score >= 80 and not any("[ERROR]" in w for w in warnings) else "review",
        "method_profile": {"id": style_id, **TRAINING_METHOD_PROFILES[style_id]},
        "weekly_direct_sets": direct,
        "weekly_effective_sets": effective,
        "frequency": frequency,
        "total_weekly_sets": total_sets,
        "average_sets_per_session": per_session,
        "priority_frequency_flags": [to_frontend(m) for m in priority_low_freq],
        "warnings": warnings,
        "authority": "FORGE deterministic training engine",
    }


# ─── PERIODIZATION ─────────────────────────────────────────────────────

BLOCK_TYPES = ["accumulation", "progression", "intensification", "deload"]
BLOCK_LENGTH_WEEKS = {"accumulation": 2, "progression": 3, "intensification": 2, "deload": 1}


def _get_periodization_state(profile: dict) -> Dict[str, Any]:
    default = {
        "block_start": dt_mod.now(timezone.utc).isoformat(),
        "block_week": 1,
        "block_type": "accumulation",
        "phase_index": 0,
    }
    stored = profile.get("periodization")
    if not stored:
        return default
    return {**default, **stored}


def advance_periodization(profile: dict, recent_sets: List[Dict[str, Any]],
                          recovery_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    state = _get_periodization_state(profile)
    block_type = state["block_type"]
    block_week = state.get("block_week", 1)
    block_length = BLOCK_LENGTH_WEEKS.get(block_type, 2)
    pi = state.get("phase_index", 0)

    week_advanced = block_week + 1

    if block_type == "deload":
        next_type = "accumulation"
        block_length = BLOCK_LENGTH_WEEKS["accumulation"]
        state["block_type"] = next_type
        state["block_week"] = 1
        state["phase_index"] = pi + 1
        return state

    if week_advanced > block_length:
        idx = BLOCK_TYPES.index(block_type)
        next_idx = (idx + 1) % len(BLOCK_TYPES)
        next_type = BLOCK_TYPES[next_idx]
        if next_type == "deload":
            force_deload = False
            if recent_sets and len(recent_sets) >= 5:
                weights = [float(s.get("weight", 0)) for s in recent_sets[:50] if float(s.get("weight", 0)) > 0]
                if len(weights) >= 5:
                    half = len(weights) // 2
                    recent_avg = sum(weights[:half]) / len(weights[:half]) if weights[:half] else 1
                    older_avg = sum(weights[half:]) / len(weights[half:]) if weights[half:] else 1
                    if recent_avg < older_avg * 0.9:
                        force_deload = True
            if recovery_rows:
                avg_energy = sum(r.get("energy", 3) for r in recovery_rows[:7]) / max(1, len(recovery_rows[:7]))
                if avg_energy < 2.5:
                    force_deload = True
            if not force_deload:
                next_type = "accumulation"
                state["phase_index"] = pi + 1
        else:
            state["phase_index"] = pi
        state["block_type"] = next_type
        state["block_week"] = 1
        state["block_start"] = dt_mod.now(timezone.utc).isoformat()
    else:
        state["block_week"] = week_advanced

    return state


def _compute_block_modifier(block_type: str) -> Tuple[float, float, Optional[str]]:
    if block_type == "accumulation":
        return 1.0, 2.0, None
    elif block_type == "progression":
        return 0.95, 1.5, None
    elif block_type == "intensification":
        return 0.9, 1.0, None
    elif block_type == "deload":
        return 0.55, 3.0, "3+"
    return 1.0, 2.0, None


# ─── READINESS ─────────────────────────────────────────────────────────

READINESS_LEVELS = ["HIGH", "NORMAL", "LOW", "VERY_LOW"]


async def _get_recent_recovery(db, profile_id: str) -> Dict[str, Any]:
    if db is None:
        return {"level": "NORMAL", "avg_energy": 5, "avg_sleep": 7, "avg_stress": 2, "avg_soreness": 2}
    rows = await db.recovery.find({"profile_id": profile_id}).sort("created_at", -1).to_list(3)
    if not rows:
        return {"level": "NORMAL", "avg_energy": 5, "avg_sleep": 7, "avg_stress": 2, "avg_soreness": 2}
    avg_energy = sum(r.get("energy", 5) for r in rows) / len(rows)
    avg_sleep = sum(r.get("sleep", 7) for r in rows) / len(rows)
    avg_stress = sum(r.get("stress", 2) for r in rows) / len(rows)
    avg_soreness = sum(r.get("soreness", 2) for r in rows) / len(rows)
    recovery_score = avg_energy * 2 - avg_stress - avg_soreness
    level = "NORMAL"
    if recovery_score >= 7:
        level = "HIGH"
    elif recovery_score < 3:
        level = "VERY_LOW"
    elif recovery_score < 4.5:
        level = "LOW"
    return {"level": level, "avg_energy": avg_energy, "avg_sleep": avg_sleep,
            "avg_stress": avg_stress, "avg_soreness": avg_soreness, "score": round(recovery_score, 1)}


def _apply_recovery_adjustment(set_count: int, rir: str, demand: str,
                               recovery_level: str, category: str) -> Tuple[int, str]:
    s = set_count
    r = rir
    rir_floor = next((int(ch) for ch in str(rir) if ch.isdigit()), 2)
    if recovery_level == "LOW":
        if category == "compound":
            s = max(2, s - 1)
        elif s >= 4:
            s = s - 1
        r = str(max(3, rir_floor + 1))
    elif recovery_level == "VERY_LOW":
        s = max(1, s - 2)
        r = "3+"
    return s, r


def build_all_sessions(profile: dict, split_type: str, days: int,
                       session_minutes: int,
                       block_type: Optional[str] = None,
                       recovery_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    sessions = []
    priorities = get_profile_priorities_internal(profile)
    volume_plan = calculate_weekly_volume(profile, split_type, days)
    block_type = block_type or profile.get("periodization", {}).get("block_type", "accumulation")
    vol_mod, rir_base, override_rir = _compute_block_modifier(block_type)
    recovery_level = recovery_data.get("level", "NORMAL") if recovery_data else "NORMAL"
    method = profile.get("training_method") or ("specialization" if priorities else "balanced_hypertrophy")
    if method not in TRAINING_METHOD_PROFILES:
        method = "balanced_hypertrophy"
    method_set_factor = {"high_intensity": 0.78, "progressive_volume": 1.10}.get(method, 1.0)

    for day_index in range(days):
        demand = "HIGH" if day_index % 3 == 0 else ("LOW" if days >= 6 and day_index % 3 == 2 else "MODERATE")
        label, day_targets = get_day_targets(split_type, day_index, days)
        day_type = _get_day_type(split_type, day_index, days)

        is_variation = False
        if day_type == "upper" and day_index >= 2:
            is_variation = True
        elif day_type == "lower" and day_index >= 2:
            is_variation = True

        count = calculate_session_capacity(
            profile.get("experience", "Intermediário"), session_minutes, demand,
            day_targets, split_type, len(day_targets)
        )
        if day_type in ("upper", "full_body"):
            count = max(count, min(count + 2, 10))
        if day_type in ("pull",):
            count = max(count, min(count + 2, 8))
        if day_type in ("lower",):
            count = max(count, min(count, 8))

        exercises = select_exercises_for_day(
            day_targets, profile, count, demand, day_index,
            is_variation_of_same_type=is_variation
        )

        items = []
        for ex in exercises:
            muscle = ex["primary_muscle"]
            is_priority = muscle in priorities
            current_weekly = sum(
                sum(s2.get("sets", 3) for s2 in s1["exercises"]
                    if EXERCISE_INDEX.get(s2["exercise_id"], {}).get("primary_muscle") == muscle)
                for s1 in sessions
            )
            category = ex.get("category", "compound")
            scription = build_exercise_prescription(ex, profile, demand, is_priority, current_weekly)

            sets = max(2, round(scription["sets"] * vol_mod * method_set_factor))
            rir_val = override_rir if override_rir else scription["rir"]
            if not override_rir and int(scription["rir"].split("-")[0]) > rir_base:
                rir_val = str(int(rir_base))

            # Method choice changes a bounded prescription, never the safety rules.
            # High intensity reduces volume before it lowers RIR; progressive volume
            # adds at most one practical set per exercise through the factor above.
            if not override_rir and method == "high_intensity":
                rir_val = "1" if category == "compound" else "0–1"
            elif not override_rir and method == "progressive_volume":
                rir_val = "2"

            sets, rir_val = _apply_recovery_adjustment(sets, rir_val, demand, recovery_level, category)

            baseline = profile.get("baseline") or []
            load = next((b.get("weight", 0) for b in baseline if b.get("exercise_id") == ex["id"]), 0)
            items.append({
                "exercise_id": ex["id"],
                "sets": sets,
                "reps": scription["reps"],
                "rir": rir_val,
                "rest": scription["rest"],
                "load": load,
                "technique": "Straight Sets",
                "technique_id": "straight",
            })

        sessions.append({
            "day": day_index + 1,
            "label": label,
            "demand": demand,
            "focus": [to_frontend(t) for t in day_targets[:3]] if day_targets else [],
            "exercises": items,
        })

    return sessions


def validate_sessions(sessions: List[Dict[str, Any]], profile: dict,
                      split_type: str, days: int, session_minutes: int,
                      logger=None) -> List[str]:
    warnings: List[str] = []
    avoid_ids = set(profile.get("avoid_exercises") or [])
    equipment = profile.get("equipment") or []
    has_complete_gym = "Academia completa" in equipment

    for i, session in enumerate(sessions):
        exercises = session.get("exercises", [])
        label = session.get("label", f"Session {i+1}")
        day_targets = get_day_targets(split_type, i, days)[1] if i < days else []

        if not exercises:
            warnings.append(f"[{label}] Empty session")
            continue

        seen_ids = set()
        covered_muscles = set()
        for ex_item in exercises:
            eid = ex_item.get("exercise_id", "")
            if eid in seen_ids:
                warnings.append(f"[{label}] Duplicate exercise: {eid}")
            seen_ids.add(eid)

            if eid in avoid_ids:
                warnings.append(f"[ERROR] [{label}] Avoid exercise selected: {eid}")

            ex = EXERCISE_INDEX.get(eid)
            if not ex:
                warnings.append(f"[ERROR] [{label}] Unknown exercise ID: {eid}")
                continue

            covered_muscles.add(ex["primary_muscle"])
            if equipment and not has_complete_gym:
                if not _equipment_ok(ex, profile):
                    warnings.append(f"[ERROR] [{label}] Equipment mismatch: {eid} requires {ex.get('equipment', [])}")

            sets = ex_item.get("sets", 0)
            if sets <= 0 or sets > 10:
                warnings.append(f"[{label}] Unreasonable sets ({sets}) for {eid}")

        min_expected = max(3, min(4, len(day_targets)))
        if len(exercises) < min_expected and session_minutes >= 45:
            warnings.append(f"[{label}] Low exercise count ({len(exercises)}), expected >= {min_expected} for {session_minutes}min")

        essential_targets = [t for t in day_targets if t not in OPTIONAL_MUSCLES]
        for target in essential_targets[:5]:
            target_covered = any(
                EXERCISE_INDEX.get(e["exercise_id"], {}).get("primary_muscle") == target
                for e in exercises
            )
            if not target_covered:
                tf = to_frontend(target)
                warnings.append(f"[{label}] Missing primary target: {tf}")

    weekly_vol = count_weekly_sets_per_muscle(sessions)
    volume_plan = calculate_weekly_volume(profile, split_type, days)
    for muscle_id, plan in volume_plan.items():
        if muscle_id in OPTIONAL_MUSCLES:
            continue
        actual = weekly_vol.get(muscle_id, 0)
        if actual == 0 and plan["tier"] in ("normal",) + PRIORITY_TIERS:
            warnings.append(f"[weekly] Zero volume for {to_frontend(muscle_id)} (tier={plan['tier']})")
        if actual > plan["max_sets"] * 1.5:
            warnings.append(f"[weekly] Excessive volume for {to_frontend(muscle_id)}: {actual} sets (max={plan['max_sets']})")

    if logger:
        for w in warnings:
            logger.warning(w)

    return warnings


def _is_empty_profile(stored: dict) -> bool:
    has_assessment = bool(stored.get("assessment"))
    has_priorities = bool(stored.get("priorities"))
    return not has_assessment and not has_priorities


def _apply_exercise_substitutions(sessions: List[Dict[str, Any]], profile: dict) -> List[Dict[str, Any]]:
    """Applies persisted exercise swaps (POST /exercises/substitute) to a built session
    list — the only thing that changes is exercise_id; sets/reps/rest/rir/technique/load/
    note are all preserved exactly as generated. This is safe because /exercises/
    substitute only ever accepts a new_exercise_id that was already a real alternative
    for that exact exercise (same primary_muscle + movement_pattern, see
    FRONTEND_EXERCISE_LIST's alternative_ids) — the existing prescription is guaranteed
    still compatible, so no separate adaptation step is needed. Runs on both the manual
    (custom_program) and algorithmic session paths so a substitution survives either mode."""
    subs = profile.get("exercise_substitutions") or {}
    if not subs:
        return sessions
    for session in sessions:
        for item in session.get("exercises", []):
            new_id = subs.get(item.get("exercise_id"))
            if new_id and new_id in EXERCISE_INDEX:
                item["exercise_id"] = new_id
    return sessions


def _resolve_active_day(sessions: List[Dict[str, Any]], profile: dict) -> Optional[int]:
    """Program sequence progression (item: Concluir treino avanca imediatamente para o
    proximo, nunca por data): the active session is whichever "day" POST /workout/complete
    last advanced the profile's current_session_day pointer to — never sessions[0] by
    itself, and never derived from the calendar date. Falls back to the first available
    day when there's no pointer yet, or when the pointer no longer matches the program's
    current shape (e.g. the athlete changed days/split after it was set)."""
    if not sessions:
        return None
    day_values = sorted(s["day"] for s in sessions)
    current = profile.get("current_session_day")
    return current if current in day_values else day_values[0]


def summarize_training_memory(recent_sets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compact athlete memory derived only from logged performance.

    It is deliberately factual: no fabricated coach persona and no invented history.
    The summary is safe to expose to the Coach LLM and to future deterministic rules.
    """
    if not recent_sets:
        return {"logged_sets": 0, "exercises": 0, "average_rir": None,
                "signal": "insufficient_history"}
    valid_rir = []
    exercise_ids = set()
    for row in recent_sets:
        if row.get("exercise_id"):
            exercise_ids.add(row["exercise_id"])
        try:
            valid_rir.append(float(row.get("rir")))
        except (TypeError, ValueError):
            pass
    avg_rir = round(sum(valid_rir) / len(valid_rir), 1) if valid_rir else None
    if len(recent_sets) < 12:
        signal = "building_baseline"
    elif avg_rir is not None and avg_rir < 0.5:
        signal = "effort_above_target"
    else:
        signal = "usable_history"
    return {"logged_sets": len(recent_sets), "exercises": len(exercise_ids),
            "average_rir": avg_rir, "signal": signal}


def performance_volume_factor(recent_sets: List[Dict[str, Any]]) -> float:
    """Conservative fatigue signal using within-exercise performance only.

    The old implementation averaged kilograms from unrelated exercises, so changing
    from squat to lateral raise could look like a catastrophic strength loss. Here each
    exercise is compared only with itself using an estimated-rep-max proxy.
    """
    if len(recent_sets) < 12:
        return 1.0
    cutoff = (dt_mod.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    by_exercise: Dict[str, Dict[str, List[float]]] = {}
    for row in recent_sets:
        eid = row.get("exercise_id")
        if not eid:
            continue
        try:
            weight = float(row.get("weight", 0))
            reps = int(row.get("reps", 0))
        except (TypeError, ValueError):
            continue
        if weight <= 0 or reps <= 0:
            continue
        bucket = "recent" if str(row.get("created_at", ""))[:10] >= cutoff else "older"
        by_exercise.setdefault(eid, {"recent": [], "older": []})[bucket].append(
            weight * (1 + reps / 30.0))
    regressions = progressions = 0
    for values in by_exercise.values():
        if not values["recent"] or not values["older"]:
            continue
        ratio = max(values["recent"]) / max(values["older"])
        if ratio < 0.92:
            regressions += 1
        elif ratio > 1.02:
            progressions += 1
    return 0.90 if regressions >= 2 and regressions > progressions else 1.0


async def build_program_v2(profile: dict, db=None) -> Dict[str, Any]:
    if profile.get("onboarding_required") is True and _is_empty_profile(profile):
        return {
            "name": "Onboarding pendente", "week": "", "session": "", "duration": "",
            "focus": [], "sessions": [],
            "logic": {"split": "", "days": 0, "priority_scores": {}, "recovery_modifier": 1,
                      "mode": "ONBOARDING_REQUIRED", "manual": False},
            "onboarding_required": True,
        }

    custom = profile.get("custom_program")
    if custom and custom.get("sessions"):
        priorities = profile.get("priorities") or []
        sessions = []
        for i, s in enumerate(custom["sessions"]):
            sessions.append({
                "day": s.get("day", i + 1),
                "label": s.get("label") or f"Sessão {i+1}",
                "demand": s.get("demand", "MODERATE"),
                "focus": s.get("focus") or priorities[:2],
                "exercises": [{
                    "exercise_id": x.get("exercise_id"),
                    "sets": int(x.get("sets", 3)),
                    "reps": x.get("reps", "8–12"),
                    "rir": x.get("rir", "1–2"),
                    "rest": x.get("rest", "2 min"),
                    "load": float(x.get("load", 0) or 0),
                    "technique": x.get("technique", "Straight Sets"),
                    "technique_id": x.get("technique_id", "straight"),
                    "note": x.get("note", ""),
                } for x in s.get("exercises", [])]
            })
        sessions = _apply_exercise_substitutions(sessions, profile)
        active_day = _resolve_active_day(sessions, profile)
        active_label = next((s["label"] for s in sessions if s["day"] == active_day), sessions[0]["label"] if sessions else "Sessão")
        return {
            "name": custom.get("name", "Programa personalizado"), "week": custom.get("week", "Microciclo manual"),
            "session": active_label, "active_day": active_day,
            "duration": f"{custom.get('session_minutes', profile.get('session_minutes', 60))} min",
            "focus": priorities[:3], "sessions": sessions,
            "logic": {"split": "Programa manual (Program Builder Pro)", "days": len(sessions),
                      "priority_scores": {}, "recovery_modifier": 1,
                      "mode": profile.get("automation_mode", "FORGE_PRO"), "manual": True},
        }

    days = max(1, min(7, int(profile.get("days", 3))))
    experience = profile.get("experience", "Intermediário")
    goal = profile.get("goal", "Hipertrofia")
    session_minutes = int(profile.get("session_minutes", 60))

    split_preference = profile_split_preference(profile)
    split_type = determine_split(days, experience, goal, split_preference)
    split_name = SPLIT_LABELS.get(split_type, split_type)

    recovery = profile.get("recovery", {}) or {}
    sleep = float(recovery.get("sleep_hours", 7) or 7)
    volume_factor = 0.82 if sleep < 6 or recovery.get("stress") in [4, 5] else 1

    pid = profile.get("id")
    recent_sets = []
    if pid and db is not None:
        recent_sets = await db.set_logs.find({"profile_id": pid}).sort("created_at", -1).to_list(100)
        volume_factor = min(volume_factor, performance_volume_factor(recent_sets))

    # advance_periodization() steps the block forward by exactly one real week per
    # call (see test_perio_initial_state) — it must NOT be called once per bootstrap,
    # or the displayed week jitters/fast-forwards on every dashboard reload instead of
    # advancing once per real calendar week. Only step it forward the number of real
    # weeks that have actually elapsed since the current block started.
    stored_perio = _get_periodization_state(profile)
    try:
        block_start_dt = dt_mod.fromisoformat(stored_perio["block_start"])
        if block_start_dt.tzinfo is None:
            block_start_dt = block_start_dt.replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        block_start_dt = dt_mod.now(timezone.utc)
    weeks_elapsed = max(0, (dt_mod.now(timezone.utc) - block_start_dt).days // 7)
    target_week_in_block = weeks_elapsed + 1
    weeks_to_advance = max(0, target_week_in_block - stored_perio.get("block_week", 1))

    perio_state = stored_perio
    # first bootstrap ever also needs a write, so block_start is pinned to a real
    # instant instead of being silently recomputed as "now" on every subsequent call.
    perio_advanced = not profile.get("periodization")
    for _ in range(weeks_to_advance):
        perio_state = advance_periodization({**profile, "periodization": perio_state}, recent_sets, recovery_rows=[])
        perio_advanced = True
    block_type = perio_state["block_type"]
    block_week = perio_state["block_week"]
    recovery_data = {"level": "NORMAL"}
    if pid and db is not None:
        try:
            recovery_data = await _get_recent_recovery(db, pid)
        except Exception:
            pass

    sessions = build_all_sessions(profile, split_type, days, session_minutes,
                                  block_type=block_type, recovery_data=recovery_data)

    for session in sessions:
        for item in session.get("exercises", []):
            sets = item.get("sets", 3)
            item["sets"] = max(2, round(sets * volume_factor))

    sessions = _apply_exercise_substitutions(sessions, profile)

    quality = build_program_quality_report(
        sessions, profile, split_type, days, session_minutes)
    training_memory = summarize_training_memory(recent_sets)

    import logging as _logging
    logger = _logging.getLogger("forge.engine")
    validate_sessions(sessions, profile, split_type, days, session_minutes, logger)

    # Persist periodization state to MongoDB only when it actually advanced —
    # otherwise every bootstrap call would re-write the same state pointlessly.
    if pid and db is not None and perio_advanced:
        try:
            await db.profiles.update_one(
                {"id": pid},
                {"$set": {"periodization": perio_state}},
                upsert=False
            )
        except Exception:
            pass

    # Compute progression hints for each exercise
    progression_hints: Dict[str, Any] = {}
    if pid and db is not None:
        for session in sessions:
            for item in session.get("exercises", []):
                eid = item["exercise_id"]
                if eid in progression_hints:
                    continue
                try:
                    from progression import get_last_performance, compute_today_exercise_adjustment
                    last = await get_last_performance(db, pid, eid)
                    if last and last.get("avg_weight", 0) > 0:
                        cat = EXERCISE_INDEX.get(eid, {}).get("category", "compound")
                        adj = compute_today_exercise_adjustment(
                            eid, cat, item.get("sets", 3), item.get("reps", "8-12"),
                            item.get("rir", "2"), last, recovery_data.get("level", "NORMAL"), block_type)
                        progression_hints[eid] = {
                            "last_weight": last["avg_weight"],
                            "last_reps": last["min_reps"],
                            "last_date": last["date"],
                            "action": adj["action"],
                            "reason": adj["reason"],
                            "suggested_load": adj["suggested_load"] if adj["suggested_load"] > 0 else None,
                        }
                except Exception:
                    pass

    priorities_list = get_profile_priorities_internal(profile)
    active_day = _resolve_active_day(sessions, profile)
    active_label = next((s["label"] for s in sessions if s["day"] == active_day), sessions[0]["label"] if sessions else "Sessão")
    return {
        "name": f"{split_name} · {experience}",
        "week": f"Semana {block_week} · {split_name}",
        "session": active_label, "active_day": active_day,
        "duration": f"{session_minutes} min",
        "focus": [to_frontend(p) for p in priorities_list[:3]],
        "sessions": sessions,
        "progression_hints": progression_hints,
        "logic": {
            "split": split_name, "days": days,
            "split_id": split_type,
            "split_preference_applied": split_preference == split_type,
            "compatible_splits": [
                {"id": option, "label": SPLIT_LABELS.get(option, option)}
                for option in compatible_splits(days, experience)
            ],
            "priority_scores": {to_frontend(m): 5 for m in priorities_list},
            "recovery_modifier": volume_factor,
            "mode": profile.get("automation_mode", "FORGE_ASSISTED"),
            "manual": False,
            "block_type": block_type, "block_week": block_week,
            "recovery_level": recovery_data.get("level", "NORMAL"),
            "periodization": perio_state,
            "quality_gate": quality,
            "training_memory": training_memory,
            "generation_strategy": "structured_engine_with_ai_explanation",
        },
    }

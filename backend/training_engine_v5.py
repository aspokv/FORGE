"""FORGE Training Engine V5 — complete workout architecture + stimulus layer.

The existing engine keeps ownership of periodization, progression, volume, recovery,
loads and substitutions. V5 owns session architecture, exercise order, semantic roles,
stimulus labels and bounded technique selection.

Sex never implies an aesthetic goal. Specialization comes only from explicit priorities.
Automatic intensification requires a verified adult advanced profile, good recovery and
no deload.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

ACCESSORY = {"biceps", "triceps", "side_delts", "rear_delts", "calves", "adductors", "abs", "obliques"}
LARGE = {"upper_chest", "mid_chest", "lats", "upper_back", "quads", "hamstrings", "glutes"}

TECHNIQUES = {
    "straight": ("Straight Sets", "low"),
    "top-set-backoff": ("Top Set + Back-off", "moderate"),
    "superset": ("Superset", "moderate"),
    "drop-set": ("Drop Set", "high"),
    "mechanical-drop-set": ("Mechanical Drop Set", "high"),
    "rest-pause": ("Rest-Pause", "high"),
    "myo-reps": ("Myo-Reps", "high"),
    "cluster": ("Cluster Set", "moderate"),
    "lengthened-partials": ("Lengthened Partials", "moderate"),
}


def _experience(profile: dict) -> str:
    value = str(profile.get("experience") or "intermediário").strip().lower()
    if value in {"avançado", "avancado", "advanced", "bodybuilder"}:
        return "advanced"
    if value in {"iniciante", "beginner", "recreativo"}:
        return "beginner"
    return "intermediate"


def _verified_adult(profile: dict) -> bool:
    try:
        return int(profile.get("age")) >= 18
    except (TypeError, ValueError):
        return False


def _priorities(engine, profile: dict, targets: List[str]) -> List[str]:
    result: List[str] = []
    for raw in profile.get("priorities") or []:
        muscle = engine.to_internal(raw) if hasattr(engine, "to_internal") else raw
        if muscle in targets and muscle not in result:
            result.append(muscle)
    return result[:3]


def _ordered(engine, profile: dict, day_targets: List[str], candidates: List[str]) -> List[str]:
    present = [x for x in candidates if x in day_targets]
    priorities = _priorities(engine, profile, day_targets)
    return [x for x in priorities if x in present] + [x for x in present if x not in priorities]


def _infer(day_targets: List[str]) -> str:
    targets = set(day_targets)
    has_push = bool({"upper_chest", "mid_chest"} & targets) and "triceps" in targets
    has_pull = {"lats", "upper_back"}.issubset(targets) and "biceps" in targets
    has_lower = {"quads", "hamstrings"}.issubset(targets)
    if has_push and has_pull:
        return "upper"
    if has_pull:
        return "pull"
    if has_push:
        return "push"
    if has_lower:
        return "legs"
    return "upper"


def _archetype(engine, split_type: str, day: int, days: int, targets: List[str]) -> str:
    if split_type == engine.SPLIT_FULL_BODY:
        return "full_body_a" if day % 2 == 0 else "full_body_b"
    if split_type == engine.SPLIT_UPPER_LOWER:
        return "upper" if day % 2 == 0 else "lower"
    if split_type == engine.SPLIT_PUSH_PULL_LEGS:
        return ["push", "pull", "legs"][day % 3]
    if split_type in {engine.SPLIT_UL_PPL, engine.SPLIT_UPPER_LOWER_PPL}:
        label = engine.get_day_targets(split_type, day, days)[0].lower()
        for kind in ("upper", "lower", "push", "pull", "legs"):
            if label.startswith(kind):
                return kind
    if split_type == engine.SPLIT_ABC:
        return ["push", "pull", "legs"][day % 3]
    if split_type == engine.SPLIT_ABCD:
        return ["chest_triceps", "back_biceps", "legs", "shoulders_arms"][day % 4]
    if split_type == engine.SPLIT_ABCDE:
        return ["chest", "back", "legs", "shoulders", "arms"][day % 5]
    return _infer(targets)


def _count(archetype: str, requested: int, minutes: int) -> int:
    cap = 4 if minutes < 40 else 5 if minutes < 55 else 6 if minutes < 80 else 7
    floor = {
        "full_body_a": 5, "full_body_b": 5, "upper": 6, "lower": 5,
        "push": 5, "pull": 5, "legs": 5, "chest_triceps": 5,
        "back_biceps": 5, "shoulders_arms": 5, "chest": 5,
        "back": 5, "shoulders": 5, "arms": 4,
    }.get(archetype, 4)
    if minutes < 45:
        floor = min(floor, 4)
    return min(max(int(requested or 1), floor), cap)


def _slots(engine, profile: dict, targets: List[str], archetype: str) -> List[Tuple[str, Optional[str]]]:
    order = lambda xs: _ordered(engine, profile, targets, xs)
    if archetype in {"pull", "back", "back_biceps"}:
        back = order(["lats", "upper_back"])
        a = back[0] if back else "lats"
        b = back[1] if len(back) > 1 else "upper_back"
        result = [(a, "compound"), (b, "compound"), (a, None), (b, None), ("rear_delts", "isolation")]
        if archetype != "back":
            result.append(("biceps", "isolation"))
        return result
    if archetype in {"push", "chest", "chest_triceps"}:
        chest = order(["upper_chest", "mid_chest"])
        a = chest[0] if chest else "upper_chest"
        b = chest[1] if len(chest) > 1 else "mid_chest"
        result = [(a, "compound"), (b, "compound")]
        if archetype == "push":
            result.append(("front_delts", "compound"))
        result += [(a, "isolation"), ("side_delts", "isolation")]
        if archetype != "chest":
            result.append(("triceps", "isolation"))
        return result
    if archetype in {"legs", "lower"}:
        lower = order(["quads", "hamstrings", "glutes"])
        a = lower[0] if lower else "quads"
        rest = [x for x in ["quads", "hamstrings", "glutes"] if x != a]
        return [(a, "compound"), (rest[0], None), (rest[1], "compound"), (a, None), ("calves", "isolation"), ("adductors", "isolation")]
    if archetype == "upper":
        chest, back = order(["upper_chest", "mid_chest"]), order(["lats", "upper_back"])
        return [
            ((chest[0] if chest else "upper_chest"), "compound"),
            ((back[0] if back else "lats"), "compound"),
            ((chest[1] if len(chest) > 1 else "mid_chest"), None),
            ((back[1] if len(back) > 1 else "upper_back"), None),
            ("side_delts", "isolation"), ("biceps", "isolation"), ("triceps", "isolation"),
        ]
    if archetype in {"full_body_a", "full_body_b"}:
        lower, chest, back = order(["quads", "hamstrings", "glutes"]), order(["upper_chest", "mid_chest"]), order(["lats", "upper_back"])
        return [
            ((lower[0] if lower else "quads"), "compound"),
            ((chest[0] if chest else "mid_chest"), "compound"),
            ((back[0] if back else "lats"), "compound"),
            ((lower[1] if len(lower) > 1 else "glutes"), None),
            ("side_delts" if archetype == "full_body_a" else "rear_delts", "isolation"),
            ("biceps" if archetype == "full_body_a" else "triceps", "isolation"),
        ]
    if archetype == "shoulders_arms":
        return [("side_delts", "isolation"), ("rear_delts", "isolation"), ("front_delts", "compound"), ("biceps", "isolation"), ("triceps", "isolation"), ("biceps", "isolation"), ("triceps", "isolation")]
    if archetype == "shoulders":
        return [("front_delts", "compound"), ("side_delts", "isolation"), ("rear_delts", "isolation"), ("side_delts", "isolation"), ("rear_delts", "isolation")]
    if archetype == "arms":
        return [("biceps", "isolation"), ("triceps", "isolation"), ("biceps", "isolation"), ("triceps", "isolation"), ("side_delts", "isolation")]
    main = order([x for x in targets if x not in ACCESSORY])
    accessories = order([x for x in targets if x in ACCESSORY])
    return [(x, "compound") for x in main] + [(x, "isolation") for x in accessories] + [(x, None) for x in main]


def _sort(exercises: List[Dict[str, Any]], archetype: str) -> List[Dict[str, Any]]:
    if archetype in {"pull", "back", "back_biceps"}:
        rank = {"lats": 0, "upper_back": 0, "rear_delts": 1, "traps": 1, "biceps": 2}
    elif archetype in {"push", "chest", "chest_triceps"}:
        rank = {"upper_chest": 0, "mid_chest": 0, "front_delts": 1, "side_delts": 1, "triceps": 2}
    elif archetype in {"legs", "lower"}:
        rank = {"quads": 0, "hamstrings": 0, "glutes": 0, "adductors": 1, "calves": 2}
    else:
        return exercises
    return sorted(exercises, key=lambda ex: rank.get(ex.get("primary_muscle"), 1))


def _role(exercise: dict, position: int) -> str:
    category, muscle = exercise.get("category", "compound"), exercise.get("primary_muscle")
    if position < 2 and category != "isolation" and muscle in LARGE:
        return "PRIMARY"
    if category != "isolation" and muscle in LARGE:
        return "SECONDARY"
    return "ISOLATION" if category == "isolation" else "ACCESSORY"


def _stimulus(exercise: dict, role: str) -> str:
    if role == "PRIMARY":
        return "mechanical_tension"
    if exercise.get("category") == "isolation" and exercise.get("fatigue") == "low":
        return "local_hypertrophy"
    return "hypertrophy_volume" if exercise.get("resistance_profile") in {"descending", "bell"} else "hypertrophy_tension"


def _advanced_allowed(profile: dict, recovery: str, block: str) -> bool:
    return (
        _verified_adult(profile)
        and _experience(profile) == "advanced"
        and str(recovery).upper() not in {"LOW", "VERY_LOW"}
        and str(block).lower() != "deload"
        and bool(profile.get("advanced_mode", True))
    )


def _technique(exercise: dict, role: str, position: int, priority: bool) -> str:
    category = exercise.get("category", "compound")
    stability, fatigue = exercise.get("stability", "medium"), exercise.get("fatigue", "medium")
    if role == "PRIMARY" and category != "isolation":
        return "top-set-backoff" if position == 0 and fatigue in {"medium", "high"} else "straight"
    if category == "isolation" and stability in {"high", "medium"}:
        if priority and fatigue == "low":
            return "rest-pause"
        if priority:
            return "myo-reps"
        if fatigue == "low":
            return "lengthened-partials"
    return "straight"


def install(engine):
    if getattr(engine, "_TRAINING_ENGINE_V5_INSTALLED", False):
        return engine

    base_build, base_validate = engine.build_all_sessions, engine.validate_sessions

    def select_v5(day_targets: List[str], profile: dict, count: int, demand: str = "MODERATE",
                  day_index: int = 0, is_variation_of_same_type: bool = False) -> List[Dict[str, Any]]:
        archetype = profile.get("_forge_session_archetype") or _infer(day_targets)
        desired = _count(archetype, count, int(profile.get("session_minutes", 60) or 60))
        selected: List[Dict[str, Any]] = []
        used: Set[str] = set()
        patterns: Dict[str, Set[str]] = {}

        def pick(target: str, category_pref: Optional[str]) -> Optional[Dict[str, Any]]:
            if target not in day_targets:
                return None
            ids = [x for x in engine.EXERCISE_BY_MUSCLE.get(target, []) if x not in used]
            ids = engine._filter_candidates(ids, profile, used)
            if not ids:
                return None
            novel = [x for x in ids if engine.EXERCISE_INDEX[x].get("movement_pattern") not in patterns.get(target, set())]
            if novel:
                ids = novel
            if category_pref:
                if category_pref == "compound":
                    preferred = [x for x in ids if engine.EXERCISE_INDEX[x].get("category", "compound") != "isolation"]
                else:
                    preferred = [x for x in ids if engine.EXERCISE_INDEX[x].get("category") == "isolation"]
                if preferred:
                    ids = preferred
            ex = engine._pick_best(ids, target, profile, used, demand, day_index, prefer_variety=is_variation_of_same_type)
            if ex:
                used.add(ex["id"])
                patterns.setdefault(target, set()).add(ex.get("movement_pattern", ""))
            return ex

        for target, category in _slots(engine, profile, day_targets, archetype):
            if len(selected) >= desired:
                break
            ex = pick(target, category)
            if ex:
                selected.append(ex)

        while len(selected) < desired:
            added = False
            for target in _ordered(engine, profile, day_targets, list(day_targets)):
                ex = pick(target, None)
                if ex:
                    selected.append(ex)
                    added = True
                    if len(selected) >= desired:
                        break
            if not added:
                break
        return _sort(selected, archetype)

    def build_v5(profile: dict, split_type: str, days: int, session_minutes: int,
                 block_type: Optional[str] = None, recovery_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        recovery = (recovery_data or {}).get("level", "NORMAL")
        block = block_type or profile.get("periodization", {}).get("block_type", "accumulation")
        archetypes = {i: _archetype(engine, split_type, i, days, engine.get_day_targets(split_type, i, days)[1]) for i in range(days)}
        saved_selector = engine.select_exercises_for_day

        def contextual(targets, scoped, count, demand="MODERATE", day_index=0, is_variation_of_same_type=False):
            p = dict(scoped)
            p["session_minutes"] = session_minutes
            p["_forge_session_archetype"] = archetypes.get(day_index, _infer(targets))
            return select_v5(targets, p, count, demand, day_index, is_variation_of_same_type)

        engine.select_exercises_for_day = contextual
        try:
            sessions = base_build(profile, split_type, days, session_minutes, block_type=block_type, recovery_data=recovery_data)
        finally:
            engine.select_exercises_for_day = saved_selector

        priorities = {engine.to_internal(x) if hasattr(engine, "to_internal") else x for x in (profile.get("priorities") or [])}
        allow_advanced = _advanced_allowed(profile, recovery, block)

        for i, session in enumerate(sessions):
            archetype = archetypes.get(i, "upper")
            items = session.get("exercises", [])
            order_map = None
            if archetype in {"pull", "back", "back_biceps"}:
                order_map = {"lats": 0, "upper_back": 0, "rear_delts": 1, "traps": 1, "biceps": 2}
            elif archetype in {"push", "chest", "chest_triceps"}:
                order_map = {"upper_chest": 0, "mid_chest": 0, "front_delts": 1, "side_delts": 1, "triceps": 2}
            elif archetype in {"legs", "lower"}:
                order_map = {"quads": 0, "hamstrings": 0, "glutes": 0, "adductors": 1, "calves": 2}
            if order_map:
                items.sort(key=lambda item: order_map.get(engine.EXERCISE_INDEX.get(item.get("exercise_id", ""), {}).get("primary_muscle"), 1))

            total_advanced = high_fatigue = 0
            for pos, item in enumerate(items):
                ex = engine.EXERCISE_INDEX.get(item.get("exercise_id", ""), {})
                role = _role(ex, pos)
                item.update({"role": role, "stimulus": _stimulus(ex, role), "archetype": archetype})
                technique_id = "straight"
                if allow_advanced and total_advanced < 2:
                    candidate = _technique(ex, role, pos, ex.get("primary_muscle") in priorities)
                    fatigue_class = TECHNIQUES.get(candidate, TECHNIQUES["straight"])[1]
                    if candidate != "straight" and not (fatigue_class == "high" and high_fatigue >= 1):
                        technique_id = candidate
                        total_advanced += 1
                        if fatigue_class == "high":
                            high_fatigue += 1
                name, fatigue_class = TECHNIQUES[technique_id]
                item.update({"technique_id": technique_id, "technique": name, "technique_fatigue": fatigue_class})
            session.update({"archetype": archetype, "advanced_techniques_used": total_advanced})
        return sessions

    def validate_v5(sessions: List[Dict[str, Any]], profile: dict, split_type: str, days: int,
                    session_minutes: int, logger=None) -> List[str]:
        warnings = base_validate(sessions, profile, split_type, days, session_minutes, logger=None)
        for i, session in enumerate(sessions):
            targets = engine.get_day_targets(split_type, i, days)[1] if i < days else []
            archetype = _archetype(engine, split_type, i, days, targets)
            items, label = session.get("exercises", []), session.get("label", f"Session {i+1}")
            if session_minutes >= 50 and len(items) < min(5, _count(archetype, 1, session_minutes)):
                warnings.append(f"[ERROR] [{label}] Incomplete {archetype} architecture: {len(items)} exercises")
            if archetype in {"pull", "back_biceps", "push", "chest_triceps"}:
                primary = {"lats", "upper_back"} if archetype in {"pull", "back_biceps"} else {"upper_chest", "mid_chest"}
                arm = {"biceps"} if archetype in {"pull", "back_biceps"} else {"triceps"}
                ppos, apos = [], []
                for pos, item in enumerate(items):
                    muscle = engine.EXERCISE_INDEX.get(item.get("exercise_id", ""), {}).get("primary_muscle")
                    if muscle in primary:
                        ppos.append(pos)
                    if muscle in arm:
                        apos.append(pos)
                if ppos and apos and min(apos) < max(ppos):
                    warnings.append(f"[ERROR] [{label}] Accessory arm work interrupts primary work")
            if len([x for x in items if x.get("technique_fatigue") == "high"]) > 1:
                warnings.append(f"[ERROR] [{label}] Too many high-fatigue advanced techniques")
        if logger:
            for warning in warnings:
                logger.warning(warning)
        return warnings

    engine.select_exercises_for_day = select_v5
    engine.build_all_sessions = build_v5
    engine.validate_sessions = validate_v5
    engine._TRAINING_ENGINE_V5_INSTALLED = True
    engine.TRAINING_ENGINE_VERSION = "5.0-complete"
    return engine

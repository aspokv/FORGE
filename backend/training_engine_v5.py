"""FORGE Training Engine v5 — complete session architecture + stimulus + techniques.

V5 sits on top of the existing v3/v4 engine. It does not replace persistence,
periodization, progression or exercise substitution. It replaces the structural
selection layer and enriches generated items with role/stimulus/technique metadata.

Design rules:
- every split receives an explicit session archetype;
- priorities change emphasis/order, not whether the rest of the body exists;
- direct arm work never interrupts unfinished primary back/chest work;
- advanced techniques are tools, not decoration: bounded, exercise-compatible and
  recovery-aware;
- sex never decides an aesthetic emphasis. Explicit athlete priorities do;
- minors are never auto-prescribed intensification techniques.
"""
from typing import Any, Dict, List, Optional, Set, Tuple


ACCESSORY_MUSCLES = {
    "biceps", "triceps", "side_delts", "rear_delts", "calves", "adductors", "abs", "obliques"
}
LARGE_MUSCLES = {
    "upper_chest", "mid_chest", "lats", "upper_back", "quads", "hamstrings", "glutes"
}

TECHNIQUE_META = {
    "straight": {"name": "Straight Sets", "fatigue": "low"},
    "top-set-backoff": {"name": "Top Set + Back-off", "fatigue": "moderate"},
    "superset": {"name": "Superset", "fatigue": "moderate"},
    "drop-set": {"name": "Drop Set", "fatigue": "high"},
    "mechanical-drop-set": {"name": "Mechanical Drop Set", "fatigue": "high"},
    "rest-pause": {"name": "Rest-Pause", "fatigue": "high"},
    "myo-reps": {"name": "Myo-Reps", "fatigue": "high"},
    "cluster": {"name": "Cluster Set", "fatigue": "moderate"},
    "lengthened-partials": {"name": "Lengthened Partials", "fatigue": "moderate"},
}


def _experience(profile: dict) -> str:
    raw = str(profile.get("experience") or "intermediário").strip().lower()
    if raw in {"avançado", "avancado", "advanced", "bodybuilder"}:
        return "advanced"
    if raw in {"iniciante", "beginner", "recreativo"}:
        return "beginner"
    return "intermediate"


def _is_minor(profile: dict) -> bool:
    try:
        age = int(profile.get("age"))
        return age < 18
    except (TypeError, ValueError):
        return False


def _priorities(engine, profile: dict, day_targets: List[str]) -> List[str]:
    # V5 only treats explicit user-selected priorities as aesthetic/training emphasis.
    # This intentionally avoids sex-based assumptions.
    raw = []
    for value in (profile.get("priorities") or []):
        internal = engine.to_internal(value) if hasattr(engine, "to_internal") else value
        if internal in day_targets and internal not in raw:
            raw.append(internal)
    return raw[:3]


def _ordered(engine, profile: dict, day_targets: List[str], targets: List[str]) -> List[str]:
    priorities = _priorities(engine, profile, day_targets)
    existing = [t for t in targets if t in day_targets]
    return [t for t in priorities if t in existing] + [t for t in existing if t not in priorities]


def _session_archetype(engine, split_type: str, day_index: int, days: int, day_targets: List[str]) -> str:
    """Return the real programming archetype, not only upper/lower/push/pull."""
    if split_type == engine.SPLIT_FULL_BODY:
        return "full_body_a" if day_index % 2 == 0 else "full_body_b"
    if split_type == engine.SPLIT_UPPER_LOWER:
        return "upper" if day_index % 2 == 0 else "lower"
    if split_type == engine.SPLIT_PUSH_PULL_LEGS:
        return ["push", "pull", "legs"][day_index % 3]
    if split_type in {engine.SPLIT_UL_PPL, engine.SPLIT_UPPER_LOWER_PPL}:
        label = engine.get_day_targets(split_type, day_index, days)[0].lower()
        if label.startswith("upper"):
            return "upper"
        if label.startswith("lower"):
            return "lower"
        if label.startswith("push"):
            return "push"
        if label.startswith("pull"):
            return "pull"
        if label.startswith("legs"):
            return "legs"
    if split_type == engine.SPLIT_ABC:
        return ["push", "pull", "legs"][day_index % 3]
    if split_type == engine.SPLIT_ABCD:
        return ["chest_triceps", "back_biceps", "legs", "shoulders_arms"][day_index % 4]
    if split_type == engine.SPLIT_ABCDE:
        return ["chest", "back", "legs", "shoulders", "arms"][day_index % 5]

    targets = set(day_targets)
    if {"lats", "upper_back"} & targets and "biceps" in targets:
        return "pull"
    if ({"mid_chest", "upper_chest"} & targets) and "triceps" in targets:
        return "push"
    if {"quads", "hamstrings"}.issubset(targets):
        return "legs"
    return "upper"


def _desired_count(archetype: str, requested: int, minutes: int) -> int:
    requested = max(1, int(requested or 1))
    if minutes < 40:
        cap = 4
    elif minutes < 55:
        cap = 5
    elif minutes < 80:
        cap = 6
    else:
        cap = 7

    floors = {
        "full_body_a": 5, "full_body_b": 5,
        "upper": 6, "lower": 5,
        "push": 5, "pull": 5, "legs": 5,
        "chest_triceps": 5, "back_biceps": 5,
        "shoulders_arms": 5, "chest": 5, "back": 5,
        "shoulders": 5, "arms": 4,
    }
    floor = floors.get(archetype, 4)
    if minutes < 45:
        floor = min(floor, 4)
    return min(max(requested, floor), cap)


def _slot_templates(engine, profile: dict, day_targets: List[str], archetype: str) -> List[Tuple[str, Optional[str]]]:
    order = lambda ts: _ordered(engine, profile, day_targets, ts)

    if archetype in {"pull", "back", "back_biceps"}:
        back = order(["lats", "upper_back"])
        first = back[0] if back else "lats"
        second = back[1] if len(back) > 1 else "upper_back"
        base = [
            (first, "compound"), (second, "compound"),
            (first, None), (second, None),
            ("rear_delts", "isolation"),
        ]
        if archetype != "back":
            base.append(("biceps", "isolation"))
        return base

    if archetype in {"push", "chest", "chest_triceps"}:
        chest = order(["upper_chest", "mid_chest"])
        first = chest[0] if chest else "upper_chest"
        second = chest[1] if len(chest) > 1 else "mid_chest"
        base = [(first, "compound"), (second, "compound")]
        if archetype == "push":
            base.append(("front_delts", "compound"))
        base.extend([(first, "isolation"), ("side_delts", "isolation")])
        if archetype != "chest":
            base.append(("triceps", "isolation"))
        return base

    if archetype in {"legs", "lower"}:
        lower = order(["quads", "hamstrings", "glutes"])
        first = lower[0] if lower else "quads"
        remaining = [m for m in ["quads", "hamstrings", "glutes"] if m != first]
        second, third = remaining[0], remaining[1]
        return [
            (first, "compound"),
            (second, None),
            (third, "compound"),
            (first, None),
            ("calves", "isolation"),
            ("adductors", "isolation"),
        ]

    if archetype == "upper":
        push = order(["upper_chest", "mid_chest"])
        pull = order(["lats", "upper_back"])
        return [
            ((push[0] if push else "upper_chest"), "compound"),
            ((pull[0] if pull else "lats"), "compound"),
            ((push[1] if len(push) > 1 else "mid_chest"), None),
            ((pull[1] if len(pull) > 1 else "upper_back"), None),
            ("side_delts", "isolation"),
            ("biceps", "isolation"),
            ("triceps", "isolation"),
        ]

    if archetype in {"full_body_a", "full_body_b"}:
        lower = order(["quads", "hamstrings", "glutes"])
        push = order(["upper_chest", "mid_chest"])
        pull = order(["lats", "upper_back"])
        lower_first = lower[0] if lower else ("quads" if archetype == "full_body_a" else "hamstrings")
        return [
            (lower_first, "compound"),
            ((push[0] if push else "mid_chest"), "compound"),
            ((pull[0] if pull else "lats"), "compound"),
            ((lower[1] if len(lower) > 1 else "glutes"), None),
            ("side_delts" if archetype == "full_body_a" else "rear_delts", "isolation"),
            ("biceps" if archetype == "full_body_a" else "triceps", "isolation"),
        ]

    if archetype == "shoulders_arms":
        return [
            ("side_delts", "isolation"), ("rear_delts", "isolation"),
            ("front_delts", "compound"), ("biceps", "isolation"),
            ("triceps", "isolation"), ("biceps", "isolation"),
            ("triceps", "isolation"),
        ]

    if archetype == "shoulders":
        return [
            ("front_delts", "compound"), ("side_delts", "isolation"),
            ("rear_delts", "isolation"), ("side_delts", "isolation"),
            ("rear_delts", "isolation"),
        ]

    if archetype == "arms":
        return [
            ("biceps", "isolation"), ("triceps", "isolation"),
            ("biceps", "isolation"), ("triceps", "isolation"),
            ("side_delts", "isolation"),
        ]

    # Generic fallback remains structured: large muscles before accessories.
    main = order([m for m in day_targets if m not in ACCESSORY_MUSCLES])
    accessories = order([m for m in day_targets if m in ACCESSORY_MUSCLES])
    return [(m, "compound") for m in main] + [(m, "isolation") for m in accessories] + [(m, None) for m in main]


def _exercise_role(ex: dict, position: int, archetype: str) -> str:
    category = ex.get("category", "compound")
    muscle = ex.get("primary_muscle")
    if position < 2 and category != "isolation" and muscle in LARGE_MUSCLES:
        return "PRIMARY"
    if category != "isolation" and muscle in LARGE_MUSCLES:
        return "SECONDARY"
    if category == "isolation":
        return "ISOLATION"
    return "ACCESSORY"


def _stimulus(ex: dict, role: str) -> str:
    if role == "PRIMARY":
        return "mechanical_tension"
    if ex.get("category") == "isolation" and ex.get("fatigue") == "low":
        return "local_hypertrophy"
    if ex.get("resistance_profile") in {"descending", "bell"}:
        return "hypertrophy_volume"
    return "hypertrophy_tension"


def _technique_allowed(profile: dict, recovery_level: str, block_type: str) -> bool:
    if _is_minor(profile):
        return False
    if _experience(profile) != "advanced":
        return False
    if str(recovery_level or "NORMAL").upper() in {"LOW", "VERY_LOW"}:
        return False
    if str(block_type or "").lower() == "deload":
        return False
    return bool(profile.get("advanced_mode", True))


def _choose_technique(ex: dict, role: str, position: int, is_priority: bool) -> str:
    category = ex.get("category", "compound")
    stability = ex.get("stability", "medium")
    fatigue = ex.get("fatigue", "medium")

    # Primary compounds get controlled loading strategies rather than failure methods.
    if role == "PRIMARY" and category != "isolation":
        if position == 0 and fatigue in {"medium", "high"}:
            return "top-set-backoff"
        return "straight"

    # High-intensity methods are reserved for stable low-risk accessory work.
    if category == "isolation" and stability in {"high", "medium"}:
        if is_priority and fatigue == "low":
            return "rest-pause"
        if is_priority:
            return "myo-reps"
        if fatigue == "low":
            return "lengthened-partials"

    return "straight"


def install(engine):
    if getattr(engine, "_TRAINING_ENGINE_V5_INSTALLED", False):
        return engine

    original_build_all_sessions = engine.build_all_sessions
    original_validate = engine.validate_sessions

    def select_exercises_for_day_v5(
        day_targets: List[str],
        profile: dict,
        count: int,
        demand: str = "MODERATE",
        day_index: int = 0,
        is_variation_of_same_type: bool = False,
    ) -> List[Dict[str, Any]]:
        # select_exercises_for_day has no split parameter, so build_all_sessions injects
        # the current archetype into the profile for this one call.
        archetype = profile.get("_forge_session_archetype") or "upper"
        minutes = int(profile.get("session_minutes", 60) or 60)
        desired = _desired_count(archetype, count, minutes)
        slots = _slot_templates(engine, profile, day_targets, archetype)

        used_ids: Set[str] = set()
        used_patterns: Dict[str, Set[str]] = {}
        selected: List[Dict[str, Any]] = []

        def pick(target: str, category_pref: Optional[str]) -> Optional[Dict[str, Any]]:
            if target not in day_targets:
                return None
            ids = [eid for eid in engine.EXERCISE_BY_MUSCLE.get(target, []) if eid not in used_ids]
            ids = engine._filter_candidates(ids, profile, used_ids)
            if not ids:
                return None

            novel = [eid for eid in ids if engine.EXERCISE_INDEX[eid].get("movement_pattern") not in used_patterns.get(target, set())]
            if novel:
                ids = novel

            if category_pref == "compound":
                preferred = [eid for eid in ids if engine.EXERCISE_INDEX[eid].get("category", "compound") != "isolation"]
                if preferred:
                    ids = preferred
            elif category_pref == "isolation":
                preferred = [eid for eid in ids if engine.EXERCISE_INDEX[eid].get("category") == "isolation"]
                if preferred:
                    ids = preferred

            ex = engine._pick_best(
                ids, target, profile, used_ids, demand, day_index,
                prefer_variety=is_variation_of_same_type,
            )
            if ex:
                used_ids.add(ex["id"])
                used_patterns.setdefault(target, set()).add(ex.get("movement_pattern", ""))
            return ex

        for target, category in slots:
            if len(selected) >= desired:
                break
            ex = pick(target, category)
            if ex:
                selected.append(ex)

        fill_order = _ordered(engine, profile, day_targets, list(day_targets))
        while len(selected) < desired:
            added = False
            for target in fill_order:
                ex = pick(target, None)
                if ex:
                    selected.append(ex)
                    added = True
                    if len(selected) >= desired:
                        break
            if not added:
                break
        return selected

    def build_all_sessions_v5(
        profile: dict,
        split_type: str,
        days: int,
        session_minutes: int,
        block_type: Optional[str] = None,
        recovery_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        # The legacy builder remains responsible for periodization/sets/reps/RIR/load.
        # We only give it the correct archetype per day through a tiny per-call profile.
        sessions: List[Dict[str, Any]] = []
        recovery_level = (recovery_data or {}).get("level", "NORMAL")
        block = block_type or profile.get("periodization", {}).get("block_type", "accumulation")

        # Build each day independently so the selector receives the actual archetype.
        # Reuse the existing builder for one-day construction by translating day index
        # through a temporary split wrapper is unsafe, so we temporarily install context
        # on the profile and call the original all-session builder once; the selector reads
        # an archetype map populated below by day index.
        archetypes = {
            i: _session_archetype(engine, split_type, i, days, engine.get_day_targets(split_type, i, days)[1])
            for i in range(days)
        }

        # selector context lookup by day_index
        base_selector = engine.select_exercises_for_day

        def contextual_selector(day_targets, p, count, demand="MODERATE", day_index=0, is_variation_of_same_type=False):
            scoped = dict(p)
            scoped["session_minutes"] = session_minutes
            scoped["_forge_session_archetype"] = archetypes.get(day_index, "upper")
            return select_exercises_for_day_v5(
                day_targets, scoped, count, demand, day_index, is_variation_of_same_type
            )

        engine.select_exercises_for_day = contextual_selector
        try:
            sessions = original_build_all_sessions(
                profile, split_type, days, session_minutes,
                block_type=block_type, recovery_data=recovery_data,
            )
        finally:
            engine.select_exercises_for_day = base_selector

        explicit_priorities = {
            engine.to_internal(p) if hasattr(engine, "to_internal") else p
            for p in (profile.get("priorities") or [])
        }

        for day_index, session in enumerate(sessions):
            archetype = archetypes.get(day_index, "upper")
            advanced_budget = 1 if _technique_allowed(profile, recovery_level, block) else 0
            used_advanced = 0

            for position, item in enumerate(session.get("exercises", [])):
                ex = engine.EXERCISE_INDEX.get(item.get("exercise_id", ""), {})
                role = _exercise_role(ex, position, archetype)
                item["role"] = role
                item["stimulus"] = _stimulus(ex, role)
                item["archetype"] = archetype

                technique_id = "straight"
                if used_advanced < advanced_budget:
                    candidate = _choose_technique(
                        ex, role, position,
                        ex.get("primary_muscle") in explicit_priorities,
                    )
                    if candidate != "straight":
                        technique_id = candidate
                        used_advanced += 1

                meta = TECHNIQUE_META[technique_id]
                item["technique_id"] = technique_id
                item["technique"] = meta["name"]
                item["technique_fatigue"] = meta["fatigue"]

            session["archetype"] = archetype
            session["advanced_techniques_used"] = used_advanced

        return sessions

    def validate_sessions_v5(
        sessions: List[Dict[str, Any]], profile: dict, split_type: str,
        days: int, session_minutes: int, logger=None,
    ) -> List[str]:
        warnings = original_validate(sessions, profile, split_type, days, session_minutes, logger=None)
        recovery = str((profile.get("recovery") or {}).get("level", "NORMAL")).upper()

        for i, session in enumerate(sessions):
            archetype = _session_archetype(
                engine, split_type, i, days,
                engine.get_day_targets(split_type, i, days)[1],
            )
            exercises = session.get("exercises", [])
            label = session.get("label", f"Session {i+1}")
            expected = _desired_count(archetype, 0, session_minutes)
            if session_minutes >= 50 and len(exercises) < min(5, expected):
                warnings.append(f"[ERROR] [{label}] Incomplete {archetype} architecture: {len(exercises)} exercises")

            # Direct isolation must not interrupt primary work in pull/back or chest/push days.
            primary_groups = ({"lats", "upper_back"} if archetype in {"pull", "back", "back_biceps"}
                              else {"upper_chest", "mid_chest"} if archetype in {"push", "chest", "chest_triceps"}
                              else set())
            arm_group = ({"biceps"} if archetype in {"pull", "back_biceps"}
                         else {"triceps"} if archetype in {"push", "chest_triceps"}
                         else set())
            if primary_groups and arm_group:
                primary_pos, arm_pos = [], []
                for pos, item in enumerate(exercises):
                    ex = engine.EXERCISE_INDEX.get(item.get("exercise_id", ""), {})
                    if ex.get("primary_muscle") in primary_groups:
                        primary_pos.append(pos)
                    if ex.get("primary_muscle") in arm_group:
                        arm_pos.append(pos)
                if primary_pos and arm_pos and min(arm_pos) < max(primary_pos):
                    warnings.append(f"[ERROR] [{label}] Accessory arm work interrupts primary work")

            high_fatigue = [
                item for item in exercises
                if item.get("technique_fatigue") == "high"
            ]
            if len(high_fatigue) > 1:
                warnings.append(f"[ERROR] [{label}] Too many high-fatigue advanced techniques")
            if (_is_minor(profile) or _experience(profile) == "beginner") and high_fatigue:
                warnings.append(f"[ERROR] [{label}] Advanced intensification not allowed for this profile")
            if recovery in {"LOW", "VERY_LOW"} and high_fatigue:
                warnings.append(f"[ERROR] [{label}] Advanced intensification conflicts with low recovery")

        if logger:
            for warning in warnings:
                logger.warning(warning)
        return warnings

    engine.select_exercises_for_day = select_exercises_for_day_v5
    engine.build_all_sessions = build_all_sessions_v5
    engine.validate_sessions = validate_sessions_v5
    engine._TRAINING_ENGINE_V5_INSTALLED = True
    engine.TRAINING_ENGINE_VERSION = "5.0-complete"
    return engine

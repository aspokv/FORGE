"""FORGE Training Engine V5 — complete workout architecture and stimulus layer.

V5 keeps the existing deterministic periodization/progression core and replaces the
session-structure decision layer. It covers every supported split, attaches semantic
roles/stimuli to exercises and may prescribe a bounded advanced technique only when the
athlete is a verified adult, advanced, recovered and outside deload.

Important product rule: sex is profile data, not an aesthetic goal. Specialization is
always driven by explicit athlete priorities.
"""
from typing import Any, Dict, List, Optional, Set, Tuple


ACCESSORY_MUSCLES = {
    "biceps", "triceps", "side_delts", "rear_delts",
    "calves", "adductors", "abs", "obliques",
}
LARGE_MUSCLES = {
    "upper_chest", "mid_chest", "lats", "upper_back",
    "quads", "hamstrings", "glutes",
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


def _verified_adult(profile: dict) -> bool:
    """Fail closed: auto-intensification requires an explicit adult age."""
    try:
        return int(profile.get("age")) >= 18
    except (TypeError, ValueError):
        return False


def _explicit_priorities(engine, profile: dict, day_targets: List[str]) -> List[str]:
    result: List[str] = []
    for raw in profile.get("priorities") or []:
        muscle = engine.to_internal(raw) if hasattr(engine, "to_internal") else raw
        if muscle in day_targets and muscle not in result:
            result.append(muscle)
    return result[:3]


def _ordered(engine, profile: dict, day_targets: List[str], targets: List[str]) -> List[str]:
    priorities = _explicit_priorities(engine, profile, day_targets)
    existing = [target for target in targets if target in day_targets]
    return [p for p in priorities if p in existing] + [t for t in existing if t not in priorities]


def _infer_archetype_from_targets(day_targets: List[str]) -> str:
    targets = set(day_targets)
    if {"lats", "upper_back"}.issubset(targets) and "biceps" in targets:
        return "pull"
    if ({"upper_chest", "mid_chest"} & targets) and "triceps" in targets:
        return "push"
    if {"quads", "hamstrings"}.issubset(targets):
        return "legs"
    return "upper"


def _session_archetype(engine, split_type: str, day_index: int, days: int,
                       day_targets: List[str]) -> str:
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
    return _infer_archetype_from_targets(day_targets)


def _desired_count(archetype: str, requested: int, session_minutes: int) -> int:
    requested = max(1, int(requested or 1))
    if session_minutes < 40:
        cap = 4
    elif session_minutes < 55:
        cap = 5
    elif session_minutes < 80:
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
    if session_minutes < 45:
        floor = min(floor, 4)
    return min(max(requested, floor), cap)


def _slot_templates(engine, profile: dict, day_targets: List[str],
                    archetype: str) -> List[Tuple[str, Optional[str]]]:
    order = lambda targets: _ordered(engine, profile, day_targets, targets)

    if archetype in {"pull", "back", "back_biceps"}:
        back = order(["lats", "upper_back"])
        first = back[0] if back else "lats"
        second = back[1] if len(back) > 1 else "upper_back"
        slots = [
            (first, "compound"),
            (second, "compound"),
            (first, None),
            (second, None),
            ("rear_delts", "isolation"),
        ]
        if archetype != "back":
            slots.append(("biceps", "isolation"))
        return slots

    if archetype in {"push", "chest", "chest_triceps"}:
        chest = order(["upper_chest", "mid_chest"])
        first = chest[0] if chest else "upper_chest"
        second = chest[1] if len(chest) > 1 else "mid_chest"
        slots: List[Tuple[str, Optional[str]]] = [
            (first, "compound"), (second, "compound")
        ]
        if archetype == "push":
            slots.append(("front_delts", "compound"))
        slots.extend([(first, "isolation"), ("side_delts", "isolation")])
        if archetype != "chest":
            slots.append(("triceps", "isolation"))
        return slots

    if archetype in {"legs", "lower"}:
        lower = order(["quads", "hamstrings", "glutes"])
        first = lower[0] if lower else "quads"
        rest = [m for m in ["quads", "hamstrings", "glutes"] if m != first]
        second = rest[0]
        third = rest[1]
        return [
            (first, "compound"),
            (second, None),
            (third, "compound"),
            (first, None),
            ("calves", "isolation"),
            ("adductors", "isolation"),
        ]

    if archetype == "upper":
        chest = order(["upper_chest", "mid_chest"])
        back = order(["lats", "upper_back"])
        return [
            ((chest[0] if chest else "upper_chest"), "compound"),
            ((back[0] if back else "lats"), "compound"),
            ((chest[1] if len(chest) > 1 else "mid_chest"), None),
            ((back[1] if len(back) > 1 else "upper_back"), None),
            ("side_delts", "isolation"),
            ("biceps", "isolation"),
            ("triceps", "isolation"),
        ]

    if archetype in {"full_body_a", "full_body_b"}:
        lower = order(["quads", "hamstrings", "glutes"])
        chest = order(["upper_chest", "mid_chest"])
        back = order(["lats", "upper_back"])
        lower_first = lower[0] if lower else (
            "quads" if archetype == "full_body_a" else "hamstrings"
        )
        return [
            (lower_first, "compound"),
            ((chest[0] if chest else "mid_chest"), "compound"),
            ((back[0] if back else "lats"), "compound"),
            ((lower[1] if len(lower) > 1 else "glutes"), None),
            ("side_delts" if archetype == "full_body_a" else "rear_delts", "isolation"),
            ("biceps" if archetype == "full_body_a" else "triceps", "isolation"),
        ]

    if archetype == "shoulders_arms":
        return [
            ("side_delts", "isolation"),
            ("rear_delts", "isolation"),
            ("front_delts", "compound"),
            ("biceps", "isolation"),
            ("triceps", "isolation"),
            ("biceps", "isolation"),
            ("triceps", "isolation"),
        ]

    if archetype == "shoulders":
        return [
            ("front_delts", "compound"),
            ("side_delts", "isolation"),
            ("rear_delts", "isolation"),
            ("side_delts", "isolation"),
            ("rear_delts", "isolation"),
        ]

    if archetype == "arms":
        return [
            ("biceps", "isolation"),
            ("triceps", "isolation"),
            ("biceps", "isolation"),
            ("triceps", "isolation"),
            ("side_delts", "isolation"),
        ]

    main = order([m for m in day_targets if m not in ACCESSORY_MUSCLES])
    accessory = order([m for m in day_targets if m in ACCESSORY_MUSCLES])
    return (
        [(m, "compound") for m in main]
        + [(m, "isolation") for m in accessory]
        + [(m, None) for m in main]
    )


def _structural_sort(exercises: List[Dict[str, Any]], archetype: str) -> List[Dict[str, Any]]:
    """Final stable sort is a hard invariant, not a scoring preference."""
    if archetype in {"pull", "back", "back_biceps"}:
        rank = {
            "lats": 0, "upper_back": 0,
            "rear_delts": 1, "traps": 1,
            "biceps": 2,
        }
    elif archetype in {"push", "chest", "chest_triceps"}:
        rank = {
            "upper_chest": 0, "mid_chest": 0,
            "front_delts": 1, "side_delts": 1,
            "triceps": 2,
        }
    elif archetype in {"legs", "lower"}:
        rank = {
            "quads": 0, "hamstrings": 0, "glutes": 0,
            "adductors": 1, "calves": 2,
        }
    else:
        return exercises

    return sorted(exercises, key=lambda ex: rank.get(ex.get("primary_muscle"), 1))


def _exercise_role(exercise: dict, position: int) -> str:
    category = exercise.get("category", "compound")
    muscle = exercise.get("primary_muscle")
    if position < 2 and category != "isolation" and muscle in LARGE_MUSCLES:
        return "PRIMARY"
    if category != "isolation" and muscle in LARGE_MUSCLES:
        return "SECONDARY"
    if category == "isolation":
        return "ISOLATION"
    return "ACCESSORY"


def _stimulus(exercise: dict, role: str) -> str:
    if role == "PRIMARY":
        return "mechanical_tension"
    if exercise.get("category") == "isolation" and exercise.get("fatigue") == "low":
        return "local_hypertrophy"
    if exercise.get("resistance_profile") in {"descending", "bell"}:
        return "hypertrophy_volume"
    return "hypertrophy_tension"


def _advanced_allowed(profile: dict, recovery_level: str, block_type: str) -> bool:
    if not _verified_adult(profile):
        return False
    if _experience(profile) != "advanced":
        return False
    if str(recovery_level or "NORMAL").upper() in {"LOW", "VERY_LOW"}:
        return False
    if str(block_type or "").lower() == "deload":
        return False
    return bool(profile.get("advanced_mode", True))


def _choose_technique(exercise: dict, role: str, position: int,
                      is_priority: bool) -> str:
    category = exercise.get("category", "compound")
    stability = exercise.get("stability", "medium")
    fatigue = exercise.get("fatigue", "medium")

    # Primary compounds get controlled loading, never automatic failure methods.
    if role == "PRIMARY" and category != "isolation":
        if position == 0 and fatigue in {"medium", "high"}:
            return "top-set-backoff"
        return "straight"

    # Intensification is reserved for stable accessory/isolation work.
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
        archetype = (
            profile.get("_forge_session_archetype")
            or _infer_archetype_from_targets(day_targets)
        )
        session_minutes = int(profile.get("session_minutes", 60) or 60)
        desired = _desired_count(archetype, count, session_minutes)
        slots = _slot_templates(engine, profile, day_targets, archetype)

        used_ids: Set[str] = set()
        used_patterns: Dict[str, Set[str]] = {}
        selected: List[Dict[str, Any]] = []

        def pick(target: str, category_preference: Optional[str]) -> Optional[Dict[str, Any]]:
            if target not in day_targets:
                return None
            candidate_ids = [
                eid for eid in engine.EXERCISE_BY_MUSCLE.get(target, [])
                if eid not in used_ids
            ]
            candidate_ids = engine._filter_candidates(candidate_ids, profile, used_ids)
            if not candidate_ids:
                return None

            novel = [
                eid for eid in candidate_ids
                if engine.EXERCISE_INDEX[eid].get("movement_pattern")
                not in used_patterns.get(target, set())
            ]
            if novel:
                candidate_ids = novel

            if category_preference == "compound":
                preferred = [
                    eid for eid in candidate_ids
                    if engine.EXERCISE_INDEX[eid].get("category", "compound") != "isolation"
                ]
                if preferred:
                    candidate_ids = preferred
            elif category_preference == "isolation":
                preferred = [
                    eid for eid in candidate_ids
                    if engine.EXERCISE_INDEX[eid].get("category") == "isolation"
                ]
                if preferred:
                    candidate_ids = preferred

            exercise = engine._pick_best(
                candidate_ids, target, profile, used_ids, demand, day_index,
                prefer_variety=is_variation_of_same_type,
            )
            if exercise:
                used_ids.add(exercise["id"])
                used_patterns.setdefault(target, set()).add(
                    exercise.get("movement_pattern", "")
                )
            return exercise

        for target, category_preference in slots:
            if len(selected) >= desired:
                break
            exercise = pick(target, category_preference)
            if exercise:
                selected.append(exercise)

        # Fill unused capacity, then enforce the final anatomical order. Selection score
        # may choose exercises; it may never move an arm isolation ahead of unfinished
        # primary back/chest work.
        fill_order = _ordered(engine, profile, day_targets, list(day_targets))
        while len(selected) < desired:
            added = False
            for target in fill_order:
                exercise = pick(target, None)
                if exercise:
                    selected.append(exercise)
                    added = True
                    if len(selected) >= desired:
                        break
            if not added:
                break

        return _structural_sort(selected, archetype)

    def build_all_sessions_v5(
        profile: dict,
        split_type: str,
        days: int,
        session_minutes: int,
        block_type: Optional[str] = None,
        recovery_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        recovery_level = (recovery_data or {}).get("level", "NORMAL")
        block = block_type or profile.get("periodization", {}).get(
            "block_type", "accumulation"
        )
        archetypes = {
            day_index: _session_archetype(
                engine, split_type, day_index, days,
                engine.get_day_targets(split_type, day_index, days)[1],
            )
            for day_index in range(days)
        }

        base_selector = engine.select_exercises_for_day

        def contextual_selector(
            day_targets, scoped_profile, count, demand="MODERATE", day_index=0,
            is_variation_of_same_type=False,
        ):
            scoped = dict(scoped_profile)
            scoped["session_minutes"] = session_minutes
            scoped["_forge_session_archetype"] = archetypes.get(
                day_index, _infer_archetype_from_targets(day_targets)
            )
            return select_exercises_for_day_v5(
                day_targets, scoped, count, demand, day_index,
                is_variation_of_same_type,
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
            engine.to_internal(raw) if hasattr(engine, "to_internal") else raw
            for raw in (profile.get("priorities") or [])
        }

        for day_index, session in enumerate(sessions):
            archetype = archetypes.get(day_index, "upper")
            technique_budget = 1 if _advanced_allowed(
                profile, recovery_level, block
            ) else 0
            advanced_used = 0

            # Defensive reorder after prescription too, in case a future base-engine
            # refactor changes item ordering between selection and serialization.
            items = session.get("exercises", [])
            if archetype in {"pull", "back", "back_biceps", "push", "chest", "chest_triceps", "legs", "lower"}:
                rank = None
                if archetype in {"pull", "back", "back_biceps"}:
                    order_rank = {"lats": 0, "upper_back": 0, "rear_delts": 1, "traps": 1, "biceps": 2}
                elif archetype in {"push", "chest", "chest_triceps"}:
                    order_rank = {"upper_chest": 0, "mid_chest": 0, "front_delts": 1, "side_delts": 1, "triceps": 2}
                else:
                    order_rank = {"quads": 0, "hamstrings": 0, "glutes": 0, "adductors": 1, "calves": 2}
                items.sort(key=lambda item: order_rank.get(
                    engine.EXERCISE_INDEX.get(item.get("exercise_id", ""), {}).get("primary_muscle"), 1
                ))

            for position, item in enumerate(items):
                exercise = engine.EXERCISE_INDEX.get(item.get("exercise_id", ""), {})
                role = _exercise_role(exercise, position)
                item["role"] = role
                item["stimulus"] = _stimulus(exercise, role)
                item["archetype"] = archetype

                technique_id = "straight"
                if advanced_used < technique_budget:
                    candidate = _choose_technique(
                        exercise, role, position,
                        exercise.get("primary_muscle") in explicit_priorities,
                    )
                    if candidate != "straight":
                        technique_id = candidate
                        advanced_used += 1

                meta = TECHNIQUE_META[technique_id]
                item["technique_id"] = technique_id
                item["technique"] = meta["name"]
                item["technique_fatigue"] = meta["fatigue"]

            session["archetype"] = archetype
            session["advanced_techniques_used"] = advanced_used

        return sessions

    def validate_sessions_v5(
        sessions: List[Dict[str, Any]], profile: dict, split_type: str,
        days: int, session_minutes: int, logger=None,
    ) -> List[str]:
        warnings = original_validate(
            sessions, profile, split_type, days, session_minutes, logger=None
        )

        for day_index, session in enumerate(sessions):
            day_targets = engine.get_day_targets(
                split_type, day_index, days
            )[1] if day_index < days else []
            archetype = _session_archetype(
                engine, split_type, day_index, days, day_targets
            )
            exercises = session.get("exercises", [])
            label = session.get("label", f"Session {day_index + 1}")
            expected = _desired_count(archetype, 1, session_minutes)

            if session_minutes >= 50 and len(exercises) < min(5, expected):
                warnings.append(
                    f"[ERROR] [{label}] Incomplete {archetype} architecture: "
                    f"{len(exercises)} exercises"
                )

            if archetype in {"pull", "back_biceps"}:
                primary = {"lats", "upper_back"}
                accessory = {"biceps"}
            elif archetype in {"push", "chest_triceps"}:
                primary = {"upper_chest", "mid_chest"}
                accessory = {"triceps"}
            else:
                primary, accessory = set(), set()

            if primary and accessory:
                primary_positions: List[int] = []
                accessory_positions: List[int] = []
                for position, item in enumerate(exercises):
                    muscle = engine.EXERCISE_INDEX.get(
                        item.get("exercise_id", ""), {}
                    ).get("primary_muscle")
                    if muscle in primary:
                        primary_positions.append(position)
                    if muscle in accessory:
                        accessory_positions.append(position)
                if (
                    primary_positions and accessory_positions
                    and min(accessory_positions) < max(primary_positions)
                ):
                    warnings.append(
                        f"[ERROR] [{label}] Accessory arm work interrupts primary work"
                    )

            high_fatigue = [
                item for item in exercises
                if item.get("technique_fatigue") == "high"
            ]
            if len(high_fatigue) > 1:
                warnings.append(
                    f"[ERROR] [{label}] Too many high-fatigue advanced techniques"
                )
            if not _verified_adult(profile) and high_fatigue:
                warnings.append(
                    f"[ERROR] [{label}] Intensification requires verified adult profile"
                )

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

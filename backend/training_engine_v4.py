"""FORGE Training Engine v4 structural programming layer.

Fixes the v3 selector's main limitation: session capacity could request 6-8 exercises,
but selection stopped after one exercise per target muscle. This layer keeps the existing
periodization, progression, substitutions and volume system while enforcing a real
session structure: primary work first, accessories after, and enough exercise variety to
use the available session capacity.
"""
from typing import Any, Dict, List, Optional, Set


ACCESSORY_MUSCLES = {"biceps", "triceps", "side_delts", "rear_delts", "calves", "adductors"}


def _rir_floor(value: Any, default: int = 2) -> int:
    for ch in str(value):
        if ch.isdigit():
            return int(ch)
    return default


def _infer_day_type(engine, day_targets: List[str]) -> str:
    targets = set(day_targets)
    if {"lats", "upper_back", "biceps"}.issubset(targets):
        return "pull"
    if "triceps" in targets and ({"mid_chest", "upper_chest"} & targets):
        return "push"
    if {"quads", "hamstrings"}.issubset(targets):
        return "legs"
    return "generic"


def install(engine):
    """Install the v4 structural rules into the existing engine module.

    Idempotent by design. server.py and every endpoint continue importing the same
    ``engine`` module, so all existing contracts remain intact.
    """
    if getattr(engine, "_TRAINING_ENGINE_V4_INSTALLED", False):
        return engine

    original_validate = engine.validate_sessions

    def select_exercises_for_day_v4(
        day_targets: List[str],
        profile: dict,
        count: int,
        demand: str = "MODERATE",
        day_index: int = 0,
        is_variation_of_same_type: bool = False,
    ) -> List[Dict[str, Any]]:
        used_ids: Set[str] = set()
        used_patterns: Dict[str, Set[str]] = {}
        selected: List[Dict[str, Any]] = []
        day_type = _infer_day_type(engine, day_targets)

        # A 60-minute PPL session should normally land around six well-chosen exercises,
        # not eight rushed exercises and certainly not four generic ones. Shorter sessions
        # still respect the capacity computed by v3.
        desired = max(1, int(count or 1))
        if day_type in {"push", "pull", "legs"}:
            desired = min(desired, 6)
        else:
            desired = min(desired, 7)

        priorities = [
            p for p in engine.get_profile_priorities_internal(profile)
            if p in day_targets
        ]

        def ordered(targets: List[str]) -> List[str]:
            existing = [t for t in targets if t in day_targets]
            return [t for t in priorities if t in existing] + [
                t for t in existing if t not in priorities
            ]

        def pick(
            target: str,
            category_preference: Optional[str] = None,
            prefer_new_pattern: bool = True,
        ) -> Optional[Dict[str, Any]]:
            if target not in day_targets:
                return None

            candidate_ids = [
                eid for eid in engine.EXERCISE_BY_MUSCLE.get(target, [])
                if eid not in used_ids
            ]
            candidate_ids = engine._filter_candidates(candidate_ids, profile, used_ids)
            if not candidate_ids:
                return None

            if prefer_new_pattern and used_patterns.get(target):
                novel = [
                    eid for eid in candidate_ids
                    if engine.EXERCISE_INDEX[eid].get("movement_pattern")
                    not in used_patterns[target]
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
                candidate_ids,
                target,
                profile,
                used_ids,
                demand,
                day_index,
                prefer_variety=is_variation_of_same_type,
            )
            if exercise:
                used_ids.add(exercise["id"])
                used_patterns.setdefault(target, set()).add(
                    exercise.get("movement_pattern", "")
                )
            return exercise

        slots: List[tuple] = []

        if day_type == "pull":
            # Back is completed before direct elbow-flexor work. Priority may decide
            # whether lats or upper back opens the day, but biceps never jumps the queue.
            back = ordered(["lats", "upper_back"])
            if len(back) >= 2:
                first, second = back[0], back[1]
                slots = [
                    (first, "compound"),
                    (second, "compound"),
                    (first, None),
                    (second, None),
                    ("rear_delts", "isolation"),
                    ("biceps", "isolation"),
                ]

        elif day_type == "push":
            chest = ordered(["mid_chest", "upper_chest"])
            if len(chest) >= 2:
                first, second = chest[0], chest[1]
                slots = [
                    (first, "compound"),
                    (second, "compound"),
                    ("front_delts", "compound"),
                    (first, "isolation"),
                    ("side_delts", "isolation"),
                    ("triceps", "isolation"),
                ]

        elif day_type == "legs":
            main = ordered(["quads", "hamstrings", "glutes"])
            if len(main) >= 3:
                first, second, third = main[:3]
                slots = [
                    (first, "compound"),
                    (second, None),
                    (third, "compound"),
                    (first, None),
                    ("adductors", "isolation"),
                    ("calves", "isolation"),
                ]

        if not slots:
            # Upper/full-body/custom-compatible fallback: large-muscle work first,
            # then accessory targets, then a second pattern where capacity allows.
            main_targets = ordered([
                t for t in day_targets if t not in ACCESSORY_MUSCLES
            ])
            accessory_targets = ordered([
                t for t in day_targets if t in ACCESSORY_MUSCLES
            ])
            slots.extend((t, "compound") for t in main_targets)
            slots.extend((t, "isolation") for t in accessory_targets)
            slots.extend((t, None) for t in main_targets)

        for target, category_pref in slots:
            if len(selected) >= desired:
                break
            exercise = pick(target, category_pref)
            if exercise:
                selected.append(exercise)

        # Fill any still-unused capacity. Unlike v3, targets may repeat as long as the
        # exercise itself is unique; novel movement patterns are preferred automatically.
        fill_order = ordered(list(day_targets))
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

        return selected

    def apply_recovery_adjustment_v4(
        set_count: int,
        rir: str,
        demand: str,
        recovery_level: str,
        category: str,
    ):
        """Recovery changes dose before it changes session architecture."""
        sets = set_count
        result_rir = rir
        level = str(recovery_level or "NORMAL").upper()
        floor = _rir_floor(rir)

        if level == "LOW":
            if category == "compound":
                sets = max(2, sets - 1)
            elif sets >= 4:
                sets -= 1
            # Avoid turning every exercise into the same hard-coded RIR 3 prescription.
            result_rir = "2" if floor <= 1 else "2–3"
        elif level == "VERY_LOW":
            sets = max(1, sets - 2)
            result_rir = "3+"

        return sets, result_rir

    def validate_sessions_v4(
        sessions: List[Dict[str, Any]],
        profile: dict,
        split_type: str,
        days: int,
        session_minutes: int,
        logger=None,
    ) -> List[str]:
        warnings = original_validate(
            sessions, profile, split_type, days, session_minutes, logger=None
        )

        for index, session in enumerate(sessions):
            exercises = session.get("exercises", [])
            label = session.get("label", f"Session {index + 1}")
            day_type = engine._get_day_type(split_type, index, days)

            if session_minutes >= 50 and day_type in {"push", "pull", "legs"} and len(exercises) < 5:
                warnings.append(
                    f"[ERROR] [{label}] Session structure too short: "
                    f"{len(exercises)} exercises for {session_minutes}min"
                )

            if day_type == "pull":
                main_back_positions = []
                biceps_positions = []
                for pos, item in enumerate(exercises):
                    ex = engine.EXERCISE_INDEX.get(item.get("exercise_id", ""), {})
                    muscle = ex.get("primary_muscle")
                    if muscle in {"lats", "upper_back"}:
                        main_back_positions.append(pos)
                    elif muscle == "biceps":
                        biceps_positions.append(pos)
                if main_back_positions and biceps_positions and min(biceps_positions) < max(main_back_positions):
                    warnings.append(
                        f"[ERROR] [{label}] Direct biceps work appears before primary back work is complete"
                    )

        if logger:
            for warning in warnings:
                logger.warning(warning)
        return warnings

    engine.select_exercises_for_day = select_exercises_for_day_v4
    engine._apply_recovery_adjustment = apply_recovery_adjustment_v4
    engine.validate_sessions = validate_sessions_v4
    engine._TRAINING_ENGINE_V4_INSTALLED = True
    engine.TRAINING_ENGINE_VERSION = "4.0-structural"
    return engine

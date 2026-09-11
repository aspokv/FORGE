"""Select complete female programs already present in the FORGE library.

This module never creates sessions or exercises. It only chooses one complete program
from training_programs.TRAINING_PROGRAMS, clones its selected phase, and persists that
snapshot so the same library program is shown after reloads and reassessments.
"""
from copy import deepcopy
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

from training_programs import TRAINING_PROGRAMS


FEMALE_VALUES = {"female", "feminino", "f", "mulher"}
FEMALE_LIBRARY_SOURCE = "female_library_program_auto"
FEMALE_LIBRARY_AUTO_SOURCES = frozenset({
    "female_library_auto",  # legacy synthetic snapshot; migrate it
    FEMALE_LIBRARY_SOURCE,
})

# Kept as a compatibility alias for clients/tests that imported the old constant.
# The values are now complete library program IDs, not template IDs.
FEMALE_AUTO_TEMPLATE_IDS = (
    "abcd-wellness-advanced",
    "female-november-abcd",
    "female-shape-de-cavala",
    "female-advanced-7",
)

FEMALE_LIBRARY_PROGRAM_IDS = FEMALE_AUTO_TEMPLATE_IDS

# Stable tie-break order: a standard library program is preferred when the profile
# does not explicitly name a reference. Expert/high-volume references remain visible
# in the catalog and are selected only when the profile clearly asks for that program.
_PROGRAM_ORDER = {
    "abcd-wellness-advanced": 0,
    "female-november-abcd": 1,
    "female-shape-de-cavala": 2,
    "female-advanced-7": 3,
}

_EXPLICIT_PROGRAM_TERMS = {
    "abcd-wellness-advanced": ("wellness", "abcd wellness"),
    "female-november-abcd": ("novembro", "november"),
    "female-shape-de-cavala": ("shape de cavala", "cavala", "legday"),
    "female-advanced-7": ("avancado 7", "advanced 7", "abcdef"),
}

_RESISTANCE_TERMS = (
    "resistencia",
    "endurance",
    "conditioning",
    "condicionamento",
    "stamina",
    "resist",
)

_BUILD_MUSCLE_TERMS = (
    "hipertrofia",
    "hipertrofia",
    "ganhar massa",
    "massa muscular",
    "muscle gain",
    "build muscle",
    "bulking",
    "forca",
    "strength",
)

_GENERAL_TERMS = (
    "emagrecimento",
    "emagrecer",
    "fat loss",
    "general fitness",
    "fitness",
    "saude",
    "saude",
    "manutencao",
    "maintenance",
)

_LOWER_FOCUS_TERMS = (
    "glute",
    "quadriceps",
    "posterior",
    "pernas",
    "lower",
    "wellness",
    "shape",
)

def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _values(value: Any) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from _values(key)
            yield from _values(nested)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _values(item)
        return
    yield str(value)


def is_female_profile(profile: Optional[Dict[str, Any]]) -> bool:
    """Match the values accepted by the assessment/profile UI."""
    profile = profile or {}
    raw = profile.get("sex") or profile.get("gender") or profile.get("sexo")
    return _normalize(raw) in FEMALE_VALUES


def is_female_library_source(source: Any) -> bool:
    return str(source or "") in FEMALE_LIBRARY_AUTO_SOURCES


def _profile_text(profile: Dict[str, Any]) -> str:
    fields = (
        profile.get("priorities"),
        profile.get("focus"),
        profile.get("training_method"),
        profile.get("goal"),
        profile.get("body_goal"),
        profile.get("secondary_goal"),
        profile.get("split_preference"),
        profile.get("split"),
        profile.get("experience"),
    )
    return " ".join(_normalize(item) for field in fields for item in _values(field))


def _requested_days(profile: Dict[str, Any]) -> int:
    try:
        return max(1, min(7, int(profile.get("days", 3) or 3)))
    except (TypeError, ValueError):
        return 3


def _first_phase(program: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    phases = program.get("phases") or []
    for item in phases:
        if item.get("sessions"):
            return item
    return None


def _session_count(program: Dict[str, Any]) -> int:
    phase = _first_phase(program)
    return len(phase.get("sessions") or []) if phase else 0


def _program_text(program: Dict[str, Any]) -> str:
    values: List[str] = []
    for key in ("id", "category", "name", "level", "audience", "description",
                "reference", "safety", "warning"):
        values.extend(_values(program.get(key)))
    for phase in program.get("phases") or []:
        for key in ("id", "label", "method", "weeks", "note"):
            values.extend(_values(phase.get(key)))
        for workout in phase.get("sessions") or []:
            values.extend(_values(workout.get("label")))
            values.extend(_values(workout.get("focus")))
    return _normalize(values)


def _goal_key(profile_text: str) -> str:
    if any(term in profile_text for term in _RESISTANCE_TERMS):
        return "resistance"
    if any(term in profile_text for term in _BUILD_MUSCLE_TERMS):
        return "build_muscle"
    if any(term in profile_text for term in _GENERAL_TERMS):
        return "general"
    return "general"


def _score(program: Dict[str, Any], profile: Dict[str, Any], profile_text: str) -> int:
    program_id = str(program.get("id") or "")
    program_text = _program_text(program)
    requested_days = _requested_days(profile)
    count = _session_count(program)
    score = 0

    # Exact availability is useful, but never outweighs the safer standard catalog
    # entry when the user has not explicitly requested a high-volume reference.
    score += max(0, 14 - (abs(count - requested_days) * 3))
    if count == requested_days:
        score += 4

    safety = _normalize(program.get("safety"))
    score += {"standard": 24, "advanced": 10, "expert": 0}.get(safety, 6)

    experience = _normalize(profile.get("experience"))
    level = _normalize(program.get("level"))
    if "avancado" in experience or "bodybuilder" in experience:
        if "avancado" in level or "especialista" in level:
            score += 5
    elif "intermediario" in experience:
        if "standard" in safety:
            score += 3
    elif "iniciante" in experience or "recreativo" in experience:
        if safety == "standard":
            score += 5

    goal = _goal_key(profile_text)
    if goal == "resistance":
        # The catalog has no record named "resistance"; keep the choice inside the
        # existing female library and prefer the broad, four-session reference.
        if program_id == "female-november-abcd":
            score += 8
        if count >= 4:
            score += 2
    elif goal == "build_muscle":
        if "hipertrofia" in program_text or "wellness" in program_text:
            score += 4
    else:
        if safety == "standard":
            score += 4

    # A named reference is an explicit request and is allowed to override the
    # conservative tie-break. It still selects only that complete catalog program.
    for term in _EXPLICIT_PROGRAM_TERMS.get(program_id, ()):
        if _normalize(term) in profile_text:
            score += 100

    # Lower-body/Wellness priorities select the existing Wellness reference when no
    # named expert program was requested.
    if any(term in profile_text for term in _LOWER_FOCUS_TERMS):
        if program_id == "abcd-wellness-advanced":
            score += 10
        elif program_id in {"female-shape-de-cavala", "female-november-abcd"}:
            score += 3

    return score


def _catalog_candidates() -> List[Dict[str, Any]]:
    return [
        item for item in TRAINING_PROGRAMS
        if _normalize(item.get("audience_type")) == "female"
        and _first_phase(item) is not None
    ]


def _unique_focus(sessions: List[Dict[str, Any]]) -> List[str]:
    focus: List[str] = []
    for workout in sessions:
        values = workout.get("focus") or []
        if not isinstance(values, (list, tuple)):
            values = [values]
        for item in values:
            if item and item not in focus:
                focus.append(item)
    return focus[:8]


def _duration_average(sessions: List[Dict[str, Any]], fallback: Any = 60) -> int:
    durations: List[int] = []
    for workout in sessions:
        try:
            durations.append(int(workout.get("duration", fallback) or fallback))
        except (TypeError, ValueError):
            continue
    return round(sum(durations) / len(durations)) if durations else int(fallback or 60)


def build_female_library_program(profile: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return one complete, persisted snapshot from the female program catalog.

    The phase and every session/exercise are copied verbatim from the selected
    catalog record. The only added field inside a session is its display day index;
    no new workout content is generated here.
    """
    profile = profile or {}
    if not is_female_profile(profile):
        return None

    candidates = _catalog_candidates()
    if not candidates:
        return None

    profile_text = _profile_text(profile)
    selected = max(
        candidates,
        key=lambda item: (
            _score(item, profile, profile_text),
            -_PROGRAM_ORDER.get(str(item.get("id")), 999),
        ),
    )
    selected = deepcopy(selected)
    selected_phase = _first_phase(selected)
    if not selected_phase:
        return None

    source_sessions = selected_phase.get("sessions") or []
    sessions: List[Dict[str, Any]] = []
    for day, workout in enumerate(source_sessions, start=1):
        copied = deepcopy(workout)
        copied["day"] = day
        sessions.append(copied)

    program_id = selected.get("id")
    phase_id = selected_phase.get("id")
    program_name = selected.get("name") or "Programa feminino FORGE"
    phase_label = selected_phase.get("label") or "Fase da biblioteca"
    reason = (
        "Programa completo selecionado da biblioteca feminina FORGE: "
        + str(program_name)
        + ". Nenhuma sessão ou exercício novo foi criado."
    )

    return {
        "profile_id": profile.get("id") or profile.get("user_id"),
        "name": program_name,
        "program_name": program_name,
        "program_id": program_id,
        "source_program_id": program_id,
        "phase_id": phase_id,
        "source_phase_id": phase_id,
        "program_category": selected.get("category"),
        "reference": selected.get("reference"),
        "safety": selected.get("safety"),
        "warning": selected.get("warning"),
        "week": phase_label,
        "requested_days": _requested_days(profile),
        "session_minutes": _duration_average(sessions, profile.get("session_minutes", 60)),
        "source": FEMALE_LIBRARY_SOURCE,
        "selection_reason": reason,
        "selection_method": "female_library_catalog",
        "focus": _unique_focus(sessions),
        "sessions": sessions,
    }

"""Deterministic, conservative selection of existing female library sessions.

The onboarding path uses only MODERATE session templates already curated in the
FORGE library. Expert/high-volume references stay opt-in in the library so a new
assessment never silently assigns a demanding plan.
"""
from copy import deepcopy
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

from workout_templates import WORKOUT_TEMPLATES


FEMALE_VALUES = {"female", "feminino", "f", "mulher"}
FEMALE_AUTO_TEMPLATE_IDS = (
    "full-body-female-athlete",
    "push-female-performance",
    "pull-female-posture",
)
FULL_BODY_TEMPLATE_ID = "full-body-female-athlete"

RESISTANCE_TERMS = (
    "resistencia",
    "endurance",
    "conditioning",
    "condicionamento",
    "stamina",
    "resist",
)

CATEGORY_TERMS = {
    "full_body": (
        "full body",
        "fullbody",
        "corpo inteiro",
        "corpo todo",
        "resistencia",
        "endurance",
        "conditioning",
        "condicionamento",
        "stamina",
    ),
    "push": (
        "push",
        "peito",
        "peitoral",
        "triceps",
        "ombro",
        "ombros",
        "press",
    ),
    "pull": (
        "pull",
        "costas",
        "dorsal",
        "dorsais",
        "biceps",
        "bracos",
        "braco",
        "puxada",
        "remada",
    ),
    "upper": (
        "upper",
        "tronco",
        "parte superior",
        "peito e costas",
        "ombros",
        "bracos",
    ),
}


def _normalize(value: Any) -> str:
    """Fold accents and punctuation so Portuguese/English variants compare safely."""
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
    """Return True for the sex/profile values accepted by the existing assessment UI."""
    profile = profile or {}
    raw = profile.get("sex") or profile.get("gender") or profile.get("sexo")
    return _normalize(raw) in FEMALE_VALUES


def _profile_text(profile: Dict[str, Any]) -> str:
    fields = (
        profile.get("priorities"),
        profile.get("focus"),
        profile.get("training_method"),
        profile.get("goal"),
        profile.get("body_goal"),
        profile.get("secondary_goal"),
        profile.get("split_preference"),
    )
    return " ".join(_normalize(item) for field in fields for item in _values(field))


def _contains(text: str, term: str) -> bool:
    return _normalize(term) in text


def _score(template: Dict[str, Any], profile_text: str, resistance: bool) -> int:
    category = _normalize(template.get("category")).replace(" ", "_")
    score = 1 if category == "full_body" else 0
    if resistance and category == "full_body":
        score += 12
    for candidate_category, terms in CATEGORY_TERMS.items():
        if any(_contains(profile_text, term) for term in terms):
            if category == candidate_category:
                score += 5
            elif candidate_category == "full_body" and category in {"push", "pull", "upper"}:
                score -= 1
    # Keep automatic assignment conservative even if metadata is edited later.
    if str(template.get("demand", "")).upper() != "MODERATE":
        score -= 100
    return score


def _catalog_candidates() -> List[Dict[str, Any]]:
    by_id = {item.get("id"): item for item in WORKOUT_TEMPLATES}
    candidates = []
    for template_id in FEMALE_AUTO_TEMPLATE_IDS:
        item = by_id.get(template_id)
        if not item or str(item.get("audience", "")).casefold() != "female":
            continue
        if str(item.get("demand", "")).upper() != "MODERATE":
            continue
        candidates.append(item)
    return candidates


def build_female_library_program(profile: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Build a persisted custom-program snapshot from the curated female catalog.

    This is intentionally deterministic and contains no AI call. The full-body
    session is kept in the sequence to avoid a female default that only covers
    upper-body patterns; resistance aliases bias the sequence toward it.
    """
    profile = profile or {}
    if not is_female_profile(profile):
        return None

    candidates = _catalog_candidates()
    if not candidates:
        return None

    try:
        days = max(1, min(7, int(profile.get("days", 3) or 3)))
    except (TypeError, ValueError):
        days = 3

    profile_text = _profile_text(profile)
    resistance = any(_contains(profile_text, term) for term in RESISTANCE_TERMS)
    by_id = {item["id"]: item for item in candidates}
    full_body = by_id.get(FULL_BODY_TEMPLATE_ID) or candidates[0]
    used: Dict[str, int] = {}
    sessions: List[Dict[str, Any]] = []

    for slot in range(days):
        # Full body is the first session and is repeated on alternating slots for
        # resistance requests. For longer schedules the final slot also restores
        # whole-body coverage instead of turning into an unbalanced PPL default.
        force_full_body = (
            slot == 0
            or (resistance and slot % 2 == 0)
            or (not resistance and days >= 4 and slot == days - 1)
        )
        if force_full_body:
            selected = full_body
        else:
            available = [item for item in candidates if used.get(item["id"], 0) == 0]
            pool = available or candidates
            selected = max(
                pool,
                key=lambda item: (
                    _score(item, profile_text, resistance) - (used.get(item["id"], 0) * 4),
                    -FEMALE_AUTO_TEMPLATE_IDS.index(item["id"]),
                ),
            )

        used[selected["id"]] = used.get(selected["id"], 0) + 1
        sessions.append({
            "day": slot + 1,
            "label": selected.get("name", f"Sessão {slot + 1}"),
            "demand": "MODERATE",
            "focus": deepcopy(selected.get("focus") or []),
            "template_id": selected["id"],
            "category": selected.get("category"),
            "style": selected.get("style"),
            "description": selected.get("description"),
            "exercises": deepcopy(selected.get("exercises") or []),
        })

    focus: List[str] = []
    if resistance:
        focus.extend(["Resistência", "Corpo inteiro"])
    for session in sessions:
        for item in session["focus"]:
            if item not in focus:
                focus.append(item)
    if not focus:
        focus = ["Corpo inteiro"]

    reason = (
        "Foco em resistência: sequência moderada da biblioteca feminina, "
        "com sessões de corpo inteiro intercaladas."
        if resistance
        else
        "Seleção automática da biblioteca feminina: sessões moderadas "
        "priorizadas pelo foco informado, com cobertura global."
    )

    minutes = [int(item.get("duration", 60) or 60) for item in sessions]
    return {
        "profile_id": profile.get("id") or profile.get("user_id"),
        "name": "Programa feminino · Biblioteca FORGE",
        "week": f"{days} sessões · seleção da biblioteca",
        "session_minutes": round(sum(minutes) / len(minutes)),
        "source": "female_library_auto",
        "selection_reason": reason,
        "selection_method": profile.get("training_method") or "library_moderate",
        "focus": focus[:5],
        "source_templates": list(dict.fromkeys(item["template_id"] for item in sessions)),
        "sessions": sessions,
    }

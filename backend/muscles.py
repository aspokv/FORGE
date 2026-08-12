"""
FORGE Muscle Taxonomy — consistent muscle IDs with backward compatibility.
Maps frontend display names to internal IDs and vice versa.
"""
from typing import Dict, List, Optional

MUSCLE_MAP: Dict[str, str] = {
    "upper_chest": "Peitoral superior",
    "mid_chest": "Peitoral esternal",
    "front_delts": "Deltóide anterior",
    "side_delts": "Deltóide lateral",
    "rear_delts": "Deltóide posterior",
    "lats": "Dorsais / largura",
    "upper_back": "Costas / espessura",
    "traps": "Trapézio",
    "biceps": "Bíceps",
    "triceps": "Tríceps",
    "quads": "Quadríceps",
    "hamstrings": "Posteriores",
    "glutes": "Glúteos",
    "adductors": "Adutores",
    "calves": "Panturrilhas",
    "abs": "Abdômen",
    "obliques": "Oblíquos",
}

REVERSE_MUSCLE_MAP: Dict[str, str] = {v: k for k, v in MUSCLE_MAP.items()}

MUSCLE_IDS: List[str] = list(MUSCLE_MAP.keys())

FRONTEND_MUSCLES = [
    "Peitoral superior", "Peitoral esternal", "Deltóide anterior",
    "Deltóide lateral", "Deltóide posterior", "Dorsais / largura",
    "Costas / espessura", "Trapézio", "Bíceps", "Braquial", "Tríceps",
    "Quadríceps", "Posteriores", "Glúteos", "Adutores",
    "Panturrilhas", "Abdômen", "Oblíquos",
]

# Backward compatibility: old schema uses frontend names in assessment
# This mapping helps convert old profile assessment keys to internal IDs
LEGACY_TO_INTERNAL: Dict[str, str] = {
    "Peitoral superior": "upper_chest",
    "Peitoral esternal": "mid_chest",
    "Deltóide anterior": "front_delts",
    "Deltóide lateral": "side_delts",
    "Deltóide posterior": "rear_delts",
    "Dorsais / largura": "lats",
    "Costas / espessura": "upper_back",
    "Trapézio": "traps",
    "Bíceps": "biceps",
    "Braquial": "biceps",
    "Tríceps": "triceps",
    "Quadríceps": "quads",
    "Posteriores": "hamstrings",
    "Glúteos": "glutes",
    "Adutores": "adductors",
    "Panturrilhas": "calves",
    "Abdômen": "abs",
    "Oblíquos": "obliques",
}

MUSCLE_GROUPS: Dict[str, List[str]] = {
    "CHEST": ["upper_chest", "mid_chest"],
    "SHOULDERS": ["front_delts", "side_delts", "rear_delts"],
    "BACK": ["lats", "upper_back", "traps"],
    "ARMS": ["biceps", "triceps"],
    "LEGS": ["quads", "hamstrings", "glutes", "adductors", "calves"],
    "CORE": ["abs", "obliques"],
}

ORDERED_MUSCLES: List[str] = [
    "upper_chest", "mid_chest", "front_delts", "side_delts", "rear_delts",
    "lats", "upper_back", "traps", "biceps", "triceps",
    "quads", "hamstrings", "glutes", "adductors", "calves", "abs", "obliques",
]


def to_frontend(muscle_id: str) -> str:
    return MUSCLE_MAP.get(muscle_id, muscle_id)


def to_internal(frontend_name: str) -> str:
    return LEGACY_TO_INTERNAL.get(frontend_name, REVERSE_MUSCLE_MAP.get(frontend_name, frontend_name))


def get_profile_priorities_internal(profile: dict) -> List[str]:
    """Extract priorities from a profile, converting legacy names to internal IDs."""
    priorities = profile.get("priorities") or []
    return [to_internal(p) for p in priorities]


def get_assessment_internal(profile: dict) -> Dict[str, Dict[str, str]]:
    """Convert legacy assessment keys to internal muscle IDs."""
    raw = profile.get("assessment") or {}
    result = {}
    for key, value in raw.items():
        internal = to_internal(key)
        if isinstance(value, dict):
            result[internal] = value
        else:
            result[internal] = {"development": value if value else "proporcional", "priority": "normal"}
    return result

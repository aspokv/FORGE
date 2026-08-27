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


# Teto de prioridades simultaneas. Sem isso o onboarding aceita marcar as 17 regioes
# como "maxima", o que nao e priorizar nada: o volume extra se dilui e estoura a
# recuperacao. A ORDEM da lista e o ranking — o primeiro item e a prioridade principal.
MAX_PRIORITIES = 3

# Ponto de partida por perfil, aplicado SOMENTE quando o atleta ainda nao declarou
# nenhuma prioridade. Nao restringe escolha: qualquer pessoa pode priorizar qualquer
# regiao, e a prioridade declarada sempre substitui este ponto de partida.
DEFAULT_EMPHASIS_BY_SEX: Dict[str, List[str]] = {
    "female": ["glutes", "hamstrings", "quads"],
    "male": ["mid_chest", "lats", "side_delts"],
}


def normalize_sex(value) -> Optional[str]:
    v = str(value or "").strip().lower()
    if v in ("f", "female", "feminino", "mulher"):
        return "female"
    if v in ("m", "male", "masculino", "homem"):
        return "male"
    return None


def get_ranked_priorities(profile: dict) -> tuple:
    """(principal, [secundarias]) em IDs internos, ja com o teto aplicado.

    Sem prioridade declarada, cai no ponto de partida do perfil (sexo). Perfil antigo sem
    sexo e sem prioridade continua sem enfase nenhuma — exatamente como era antes."""
    raw = [to_internal(p) for p in (profile.get("priorities") or [])]
    seen, ordered = set(), []
    for m in raw:
        if m and m not in seen:
            seen.add(m)
            ordered.append(m)
    ordered = ordered[:MAX_PRIORITIES]
    if ordered:
        return ordered[0], ordered[1:]
    seed = DEFAULT_EMPHASIS_BY_SEX.get(normalize_sex(profile.get("sex")) or "", [])
    seed = seed[:MAX_PRIORITIES]
    return (seed[0] if seed else None), seed[1:]


def get_profile_priorities_internal(profile: dict) -> List[str]:
    """Prioridades efetivas (principal + secundarias), ja limitadas e com o ponto de
    partida do perfil quando nada foi declarado."""
    primary, secondary = get_ranked_priorities(profile)
    return ([primary] if primary else []) + list(secondary)


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

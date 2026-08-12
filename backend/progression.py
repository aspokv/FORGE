"""
FORGE Progression Engine v1.0 — Double Progression + Load Increments + Performance History.
Deterministic, profile_id isolated, backward compatible.
"""
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

from muscles import to_frontend, to_internal

LOAD_DECISION = {
    "LOAD_UP": "Aumentar carga",
    "KEEP_LOAD": "Manter carga",
    "ADD_REPS": "Buscar mais reps",
    "REDUCE_LOAD": "Reduzir carga",
    "FIRST_TIME": "Primeira vez",
}

RIR_TARGET_ZONE = 0.5


async def get_recent_sets(db, profile_id: str, exercise_id: str, limit: int = 20):
    rows = await db.set_logs.find(
        {"profile_id": profile_id, "exercise_id": exercise_id},
        {"_id": 0, "profile_id": 0}
    ).sort("created_at", -1).to_list(limit)
    return rows


async def get_last_performance(db, profile_id: str, exercise_id: str) -> Optional[Dict[str, Any]]:
    rows = await get_recent_sets(db, profile_id, exercise_id, 10)
    if not rows:
        return None
    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        date_key = r.get("created_at", "")[:10]
        if date_key:
            by_date.setdefault(date_key, []).append(r)
    if not by_date:
        return None
    latest_date = max(by_date.keys())
    latest_sets = by_date[latest_date]
    total_reps = sum(int(s.get("reps", 0)) for s in latest_sets)
    min_reps = min((int(s.get("reps", 0)) for s in latest_sets), default=0)
    weights = [float(s.get("weight", 0)) for s in latest_sets if float(s.get("weight", 0)) > 0]
    avg_weight = sum(weights) / len(weights) if weights else 0.0
    avg_rir = sum(float(s.get("rir", 2)) for s in latest_sets) / max(1, len(latest_sets))
    return {
        "date": latest_date, "sets_completed": len(latest_sets),
        "total_reps": total_reps, "min_reps": min_reps,
        "avg_weight": round(avg_weight, 1), "avg_rir": round(avg_rir, 1),
    }


def clear_old_state_keep_defaults(profile, state_dict):
    """Elimina local double dictionaries default triggers."""
    return {k: v for k, v in state_dict.items()}


def compute_block_weight(exercise_id, cat, equipment_list):
    """Suggested load increment based on exercise category."""
    lower_compound = cat == "compound" and any(
        p in (equipment_list or []) for p in ["squat", "lunge", "hinge", "hip", "knee"]
    ) or any(e in (equipment_list or []) for e in exercise_id.lower().split("-") if e in ("squat", "deadlift", "press", "leg"))
    if "squat" in exercise_id.lower() or "deadlift" in exercise_id.lower() or "leg" in exercise_id.lower() or "hip" in exercise_id.lower():
        return 5.0
    if cat == "compound":
        return 2.5
    if cat == "isolation":
        return 1.5
    return 2.0


def decide_load_action(prescribed_range: str, last_perf: Optional[Dict[str, Any]],
                       prescribed_sets: int, prescribed_rir: str,
                       rir_threshold: float = 2.0) -> Tuple[str, float, str]:
    if not last_perf or last_perf.get("avg_weight", 0) <= 0:
        return "FIRST_TIME", 0.0, "Sem historico. Informe a carga inicial."

    try:
        lo, hi = prescribed_range.replace(chr(8211), "-").replace(chr(8212), "-").split("-")
        lo, hi = int(lo.strip()), int(hi.strip())
    except Exception:
        return "FIRST_TIME", 0.0, "Faixa de reps invalida."

    try:
        target_rir = float(prescribed_rir.split("-")[0])
    except Exception:
        target_rir = 2.0

    weight = last_perf["avg_weight"]
    min_reps = last_perf["min_reps"]
    sets_done = last_perf["sets_completed"]
    avg_rir = last_perf["avg_rir"]

    rir_met = sets_done >= max(prescribed_sets - 1, 1)
    rir_in_zone = abs(avg_rir - target_rir) <= rir_threshold

    if min_reps >= hi and rir_met and rir_in_zone:
        return "LOAD_UP", weight, f"Topo da faixa atingido ({min_reps} reps). Aumentar carga."

    if min_reps < lo:
        if sets_done >= prescribed_sets:
            return "REDUCE_LOAD", max(0, weight - 5), f"Abaixo da faixa minima ({min_reps} reps). Reduzir carga."
        return "KEEP_LOAD", weight, f"Abaixo da faixa. Tentar novamente com mesma carga."

    if lo <= min_reps < hi:
        if rir_in_zone:
            return "ADD_REPS", weight, f"Dentro da faixa. Buscar {min(hi, min_reps + 2)} reps antes do aumento."
        return "ADD_REPS", weight, f"Progredir reps dentro da faixa."

    return "KEEP_LOAD", weight, "Manter e reavaliar."


def compute_today_exercise_adjustment(exercise_id: str, cat: str, prescribed_sets: int,
                                       prescribed_reps: str, prescribed_rir: str,
                                       last_perf: Optional[Dict[str, Any]],
                                       readiness_level: str = "NORMAL",
                                       block_type: str = "accumulation") -> Dict[str, Any]:
    action, rec_weight, reason = decide_load_action(prescribed_reps, last_perf, prescribed_sets, prescribed_rir)

    suggested_load = rec_weight
    if action == "LOAD_UP" and suggested_load > 0:
        inc = compute_block_weight(exercise_id, cat, exercise_id.split("-"))
        suggested_load = round(rec_weight + inc, 1)
    elif action == "REDUCE_LOAD" and suggested_load > 0:
        inc = compute_block_weight(exercise_id, cat, exercise_id.split("-"))
        suggested_load = round(max(0, rec_weight - inc * 2), 1)

    sets = prescribed_sets
    rir = prescribed_rir

    if readiness_level in ("LOW", "VERY_LOW"):
        if cat == "compound" or "deadlift" in exercise_id.lower() or "squat" in exercise_id.lower():
            sets = max(2, prescribed_sets - 1)
        rir = str(max(3, int(prescribed_rir.split("-")[0]) + 1))

    if block_type == "deload":
        sets = max(2, prescribed_sets // 2 + 1)
        rir = "3+"
        suggested_load = round(rec_weight * 0.7, 1) if rec_weight > 0 else 0

    return {
        "action": action, "reason": reason,
        "last_weight": rec_weight, "suggested_load": suggested_load,
        "adjusted_sets": sets, "adjusted_rir": rir,
        "readiness": readiness_level, "block": block_type,
    }

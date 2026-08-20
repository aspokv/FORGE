"""FORGE manual workout API routes — build or import a program by hand.

Follows the same conventions as nutrition_routes: own APIRouter with an /api prefix,
db from request.app.state.db, auth via get_current_user, no import of server (which
would be circular). The activated plan is written to profile.custom_program — the exact
document engine.build_program_v2 already consumes — so the imported program flows through
Today/Workout, /workout/complete and /exercises/substitute with zero changes there.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth import get_current_user
from engine import EXERCISE_INDEX, build_program_v2
from exercise_ai_match import (
    ai_matching_available, load_learned_aliases, record_missing_exercise,
    resolve_names_with_ai, save_learned_alias,
)
from manual_workout import (
    MAX_DAYS, MAX_EXERCISES_PER_DAY, MAX_IMPORT_CHARS, MAX_LABEL_CHARS, MAX_NOTE_CHARS,
    MAX_SETS, REVIEW_AMBIGUOUS, REVIEW_EXERCISE_UNMATCHED, REVIEW_LOW_CONFIDENCE,
    REVIEW_MULTIPLE_OPTIONS, REVIEW_REPS_MISSING, REVIEW_SETS_MISSING,
    apply_ai_matches, apply_learned_aliases, draft_to_custom_program,
    parse_workout_text, resolve_exercise_name, sanitize, unmatched_names,
    validate_draft,
)

router = APIRouter(prefix="/api/workouts/manual", tags=["manual-workout"])


class ParseIn(BaseModel):
    text: str
    name: str = ""


class DraftExerciseIn(BaseModel):
    exercise_id: Optional[str] = None
    raw_name: str = ""
    sets: Optional[int] = None
    reps: str = ""
    rir: str = ""
    rest: str = ""
    load: float = 0
    technique: str = "Straight Sets"
    technique_id: str = "straight"
    note: str = ""


class DraftDayIn(BaseModel):
    day: int = 1
    label: str = "Sessão"
    demand: str = "MODERATE"
    focus: List[str] = []
    exercises: List[DraftExerciseIn] = []


class DraftIn(BaseModel):
    name: str = "Treino manual"
    source: str = "manual"
    sessions: List[DraftDayIn] = []
    session_minutes: int = Field(default=60, ge=15, le=240)


class DraftSaveIn(BaseModel):
    draft: DraftIn


class PreviewIn(BaseModel):
    draft: Optional[DraftIn] = None


class ActivateIn(BaseModel):
    draft: Optional[DraftIn] = None
    # Client-generated id for the activation attempt: a double click sends the same token
    # twice and the second call is a no-op instead of a second archive + second write.
    activation_token: str = Field(min_length=8, max_length=64)
    session_minutes: int = Field(default=60, ge=15, le=240)


def owned_workout_target(user: dict, requested: Optional[str] = None) -> str:
    """ATHLETE always resolves to their own id — an arbitrary athlete_id in the body is
    ignored, never trusted. Only SUPER_ADMIN may address another profile."""
    if user.get("role") == "SUPER_ADMIN":
        return requested or user["id"]
    return user["id"]


async def _load_profile(db, profile_id: str) -> Dict[str, Any]:
    return await db.profiles.find_one({"id": profile_id}, {"_id": 0}) or {
        "id": profile_id, "user_id": profile_id, "days": 3, "session_minutes": 60,
        "priorities": [], "assessment": {},
    }


def _rehydrate(draft: Dict[str, Any]) -> Dict[str, Any]:
    """Re-derives review flags server-side after any client edit, so needs_review can
    never be spoofed from the browser and always reflects the values actually stored."""
    sessions = []
    for i, s in enumerate((draft.get("sessions") or [])[:MAX_DAYS]):
        items = []
        for x in (s.get("exercises") or [])[:MAX_EXERCISES_PER_DAY]:
            exercise_id = x.get("exercise_id") or None
            raw_name = sanitize(x.get("raw_name") or "", MAX_LABEL_CHARS)
            confidence = "manual" if exercise_id else "none"
            suggestions: List[str] = []
            options: List[str] = [exercise_id] if exercise_id else []
            if exercise_id and exercise_id not in EXERCISE_INDEX:
                exercise_id = None
            if not exercise_id and raw_name:
                resolution = resolve_exercise_name(raw_name)
                exercise_id = resolution["exercise_id"]
                confidence = resolution["confidence"]
                suggestions = resolution["suggestions"]
                options = resolution["options"]

            sets = x.get("sets")
            if isinstance(sets, bool) or not isinstance(sets, int) or not (1 <= sets <= MAX_SETS):
                sets = None
            reps = sanitize(x.get("reps") or "", 20)

            reasons: List[str] = []
            if confidence == "options":
                reasons.append(REVIEW_MULTIPLE_OPTIONS)
            elif confidence == "ambiguous":
                reasons.append(REVIEW_AMBIGUOUS)
            elif not exercise_id:
                reasons.append(REVIEW_EXERCISE_UNMATCHED)
            elif confidence == "fuzzy":
                reasons.append(REVIEW_LOW_CONFIDENCE)
            if sets is None:
                reasons.append(REVIEW_SETS_MISSING)
            if not reps:
                reasons.append(REVIEW_REPS_MISSING)

            items.append({
                "exercise_id": exercise_id,
                "raw_name": raw_name or (EXERCISE_INDEX.get(exercise_id, {}).get("name", "") if exercise_id else ""),
                "match_confidence": confidence,
                "suggestions": suggestions[:5],
                "options": options,
                "sets": sets,
                "reps": reps,
                "rir": sanitize(x.get("rir") or "", 20),
                "rest": sanitize(x.get("rest") or "", 20),
                "load": float(x.get("load") or 0),
                "technique": sanitize(x.get("technique") or "Straight Sets", 60),
                "technique_id": sanitize(x.get("technique_id") or "straight", 40),
                "note": sanitize(x.get("note") or "", MAX_NOTE_CHARS),
                "needs_review": bool(reasons),
                "review_reasons": reasons,
            })
        sessions.append({
            "day": i + 1,
            "label": sanitize(s.get("label") or f"Sessão {i+1}", MAX_LABEL_CHARS),
            "demand": s.get("demand") if s.get("demand") in ("HIGH", "MODERATE", "LOW") else "MODERATE",
            "focus": [sanitize(f, MAX_LABEL_CHARS) for f in (s.get("focus") or [])][:3],
            "exercises": items,
        })

    total = sum(len(s["exercises"]) for s in sessions)
    review = sum(1 for s in sessions for x in s["exercises"] if x["needs_review"])
    return {
        "name": sanitize(draft.get("name") or "", MAX_LABEL_CHARS) or "Treino manual",
        "source": draft.get("source") if draft.get("source") in ("manual", "manual_import") else "manual",
        "session_minutes": int(draft.get("session_minutes") or 60),
        "sessions": sessions,
        "warnings": [sanitize(w, 200) for w in (draft.get("warnings") or [])][:20],
        "stats": {"days": len(sessions), "exercises": total, "needs_review": review},
    }


async def _save_draft(db, profile_id: str, draft: Dict[str, Any]) -> Dict[str, Any]:
    doc = {**draft, "profile_id": profile_id, "status": "draft",
           "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.manual_workout_drafts.update_one({"profile_id": profile_id}, {"$set": doc}, upsert=True)
    return doc


def _plan_summary(profile: Dict[str, Any], program: Dict[str, Any]) -> Dict[str, Any]:
    """What the athlete is about to replace — shown in the confirmation before activating."""
    custom = profile.get("custom_program") or {}
    sessions = program.get("sessions") or []
    return {
        "name": program.get("name") or custom.get("name") or "Programa atual",
        "days": len(sessions),
        "manual": bool(custom.get("sessions")),
        "source": custom.get("source") or ("manual" if custom.get("sessions") else "engine"),
        "labels": [s.get("label") for s in sessions][:MAX_DAYS],
    }


async def _resolve_layers(db, profile_id: str, draft: Dict[str, Any]) -> Dict[str, Any]:
    """Camada 1b (aliases aprendidos, sem custo) e camada 2 (IA restrita ao catalogo,
    UMA chamada, so para o que sobrou). Nada aqui pode derrubar a importacao: sem chave
    de IA, sem rede ou com resposta invalida, o item simplesmente segue para escolha
    manual — que e o comportamento da camada 1."""
    draft = apply_learned_aliases(draft, await load_learned_aliases(db))

    pending = unmatched_names(draft)
    if pending and ai_matching_available():
        resolved = await resolve_names_with_ai(pending)
        if resolved:
            draft = apply_ai_matches(draft, resolved)
            # O que a IA resolveu vira alias: da proxima vez a camada 1 acerta sozinha.
            for name, exercise_id in resolved.items():
                await save_learned_alias(db, name, exercise_id, source="ai", profile_id=profile_id)

    # O que ninguem reconheceu fica registrado como sugestao de inclusao no catalogo.
    for name in unmatched_names(draft):
        await record_missing_exercise(db, name, profile_id)
    return draft


@router.post("/parse")
async def parse_manual_workout(payload: ParseIn, request: Request, user=Depends(get_current_user)):
    """Free text -> structured draft. Persists the draft so a page refresh never loses it.
    Nothing about the active plan is touched here."""
    db = request.app.state.db
    target = owned_workout_target(user)
    if len(payload.text or "") > MAX_IMPORT_CHARS:
        raise HTTPException(413, f"Texto muito grande: máximo de {MAX_IMPORT_CHARS} caracteres.")
    try:
        draft = parse_workout_text(payload.text, payload.name)
    except ValueError as e:
        raise HTTPException(400, str(e))

    draft["session_minutes"] = int((await _load_profile(db, target)).get("session_minutes") or 60)
    draft = await _resolve_layers(db, target, _rehydrate(draft))
    stored = await _save_draft(db, target, draft)
    return {"draft": {k: v for k, v in stored.items() if k != "_id"},
            "blocking_errors": validate_draft(stored)}


@router.get("/draft")
async def get_manual_draft(request: Request, user=Depends(get_current_user), profile_id: Optional[str] = None):
    db = request.app.state.db
    target = owned_workout_target(user, profile_id)
    doc = await db.manual_workout_drafts.find_one({"profile_id": target}, {"_id": 0})
    # An activated draft is done: it already became the active plan. Returning it here
    # would reopen the screen on the old import and hide the "paste a workout" box,
    # which is only shown when there is no draft in progress.
    if not doc or doc.get("status") == "activated":
        return {"draft": None, "blocking_errors": []}
    return {"draft": doc, "blocking_errors": validate_draft(doc)}


@router.delete("/draft")
async def delete_manual_draft(request: Request, user=Depends(get_current_user)):
    """Throws the whole draft away — every day and every exercise — so the athlete can
    start from scratch and paste a new workout. Only the in-progress import is removed:
    the active plan, the archived versions and the training history are untouched."""
    db = request.app.state.db
    target = owned_workout_target(user)
    result = await db.manual_workout_drafts.delete_many({"profile_id": target})
    return {"draft": None, "blocking_errors": [], "deleted": result.deleted_count}


@router.put("/draft")
async def save_manual_draft(payload: DraftSaveIn, request: Request, user=Depends(get_current_user)):
    """Saves the edited preview as a draft. A draft may be incomplete — review flags are
    recomputed here, and blocking_errors says what still stands between it and activation."""
    db = request.app.state.db
    target = owned_workout_target(user)
    draft = apply_learned_aliases(_rehydrate(payload.draft.model_dump()),
                                  await load_learned_aliases(db))
    # An empty draft is a legitimate state: it is how "erase everything and start over"
    # persists. Emptiness only blocks activation, and validate_draft already says so.
    stored = await _save_draft(db, target, draft)
    return {"draft": {k: v for k, v in stored.items() if k != "_id"},
            "blocking_errors": validate_draft(stored)}


@router.post("/preview")
async def preview_manual_workout(payload: PreviewIn, request: Request, user=Depends(get_current_user)):
    """Renders the draft exactly as the engine would render it once active — without
    persisting anything — plus a summary of the plan it would replace."""
    db = request.app.state.db
    target = owned_workout_target(user)
    profile = await _load_profile(db, target)

    if payload.draft is not None:
        draft = _rehydrate(payload.draft.model_dump())
    else:
        stored = await db.manual_workout_drafts.find_one({"profile_id": target}, {"_id": 0})
        if not stored:
            raise HTTPException(404, "Nenhum rascunho encontrado.")
        draft = stored

    errors = validate_draft(draft)
    current_program = await build_program_v2(profile, db)
    preview_program = None
    if not errors:
        candidate = draft_to_custom_program(draft, target, draft.get("session_minutes", 60))
        # Substitutions are deliberately not applied to the preview: activation clears
        # them, so what is previewed is exactly what will be activated.
        synthetic = {**profile, "custom_program": candidate, "exercise_substitutions": {},
                     "current_session_day": 1, "onboarding_required": False}
        preview_program = await build_program_v2(synthetic, db)

    return {"program": preview_program, "blocking_errors": errors,
            "replaces": _plan_summary(profile, current_program)}


@router.post("/activate")
async def activate_manual_workout(payload: ActivateIn, request: Request, user=Depends(get_current_user)):
    """Activates the manual plan. Archives the plan being replaced, points the next
    session at day 1 of the new plan, and never touches set_logs or workout_completions —
    training history and metrics survive activation untouched."""
    db = request.app.state.db
    target = owned_workout_target(user)
    profile = await _load_profile(db, target)

    previous = profile.get("manual_activation") or {}
    if previous.get("token") and previous["token"] == payload.activation_token:
        # Same click, second delivery: return the result of the first, archive nothing.
        return {"program": await build_program_v2(profile, db),
                "archived_version_id": previous.get("archived_version_id"),
                "already_applied": True}

    if payload.draft is not None:
        draft = _rehydrate(payload.draft.model_dump())
    else:
        stored = await db.manual_workout_drafts.find_one({"profile_id": target}, {"_id": 0})
        if not stored:
            raise HTTPException(404, "Nenhum rascunho para ativar.")
        draft = stored

    errors = validate_draft(draft)
    if errors:
        raise HTTPException(422, {"message": "Revise o treino antes de ativar.", "errors": errors})

    candidate = draft_to_custom_program(draft, target, payload.session_minutes or draft.get("session_minutes", 60))
    now = datetime.now(timezone.utc).isoformat()

    archived_version_id = None
    if profile.get("custom_program"):
        archived_version_id = str(uuid.uuid4())
        await db.program_versions.insert_one({
            "id": archived_version_id,
            "profile_id": target,
            "archived_at": now,
            "reason": "manual_activation",
            "program": profile["custom_program"],
            "exercise_substitutions": profile.get("exercise_substitutions") or {},
            "current_session_day": profile.get("current_session_day"),
        })

    # One atomic document update: plan, mode, sequence pointer and idempotency marker
    # land together or not at all. Substitutions belonged to the plan being replaced,
    # so they are cleared here — the activated plan is exactly what was confirmed.
    await db.profiles.update_one(
        {"id": target},
        {"$set": {
            "custom_program": candidate,
            "automation_mode": "FORGE_PRO",
            "current_session_day": 1,
            "exercise_substitutions": {},
            "user_id": target,
            "manual_activation": {
                "token": payload.activation_token,
                "activated_at": now,
                "archived_version_id": archived_version_id,
                "source": candidate.get("source", "manual"),
            },
        }},
        upsert=True,
    )
    await db.manual_workout_drafts.update_one(
        {"profile_id": target},
        {"$set": {"status": "activated", "activated_at": now}},
    )

    profile = await _load_profile(db, target)
    program = await build_program_v2(profile, db)
    return {
        "program": program,
        "custom": candidate,
        "archived_version_id": archived_version_id,
        "already_applied": False,
        "summary": {"days": len(candidate["sessions"]),
                    "exercises": sum(len(s["exercises"]) for s in candidate["sessions"]),
                    "next_session": program.get("session")},
    }


@router.get("/versions")
async def list_program_versions(request: Request, user=Depends(get_current_user), profile_id: Optional[str] = None):
    """Archived plans, newest first — this is what makes a replaced plan recoverable."""
    db = request.app.state.db
    target = owned_workout_target(user, profile_id)
    rows = await db.program_versions.find({"profile_id": target}, {"_id": 0}).sort("archived_at", -1).to_list(50)
    return {"versions": [{
        "id": r["id"],
        "archived_at": r["archived_at"],
        "name": (r.get("program") or {}).get("name", "Programa"),
        "source": (r.get("program") or {}).get("source", "manual"),
        "days": len((r.get("program") or {}).get("sessions") or []),
    } for r in rows]}


@router.post("/versions/{version_id}/restore")
async def restore_program_version(version_id: str, request: Request, user=Depends(get_current_user)):
    """Puts an archived plan back in place, archiving the current one on the way out."""
    db = request.app.state.db
    target = owned_workout_target(user)
    row = await db.program_versions.find_one({"id": version_id, "profile_id": target}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Versão não encontrada.")

    profile = await _load_profile(db, target)
    now = datetime.now(timezone.utc).isoformat()
    if profile.get("custom_program"):
        await db.program_versions.insert_one({
            "id": str(uuid.uuid4()), "profile_id": target, "archived_at": now,
            "reason": "version_restore", "program": profile["custom_program"],
            "exercise_substitutions": profile.get("exercise_substitutions") or {},
            "current_session_day": profile.get("current_session_day"),
        })

    await db.profiles.update_one(
        {"id": target},
        {"$set": {"custom_program": row["program"], "automation_mode": "FORGE_PRO",
                  "current_session_day": 1, "user_id": target}},
        upsert=True,
    )
    profile = await _load_profile(db, target)
    return {"program": await build_program_v2(profile, db), "restored_version_id": version_id}

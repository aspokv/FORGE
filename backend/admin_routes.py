"""FORGE admin router: athlete management, audit log, AI usage."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import uuid

from auth import require_super_admin, new_invite_token, INVITE_TTL_DAYS
from auth import AGUARDANDO_PAGAMENTO
from billing_plans import plano_ativo
from entitlements import ORIGEM_CONVITE_PARA_ASSINAR, ORIGEM_CORTESIA_CONCEDIDA

router = APIRouter(prefix="/api/admin", tags=["admin"])

VALID_PLANS = ["FORGE_ACCESS", "FORGE_PRO", "LIFETIME"]
VALID_STATUS = ["PENDING", "ACTIVE", "SUSPENDED", "EXPIRED"]
VALIDITY_MAP = {"30": 30, "90": 90, "180": 180, "365": 365, "LIFETIME": None}

# As duas formas de trazer alguem para dentro. Nomes explicitos porque a diferenca entre
# elas e quem paga a conta.
CORTESIA = "courtesy"
ASSINATURA = "subscription"
MODOS_DE_ACESSO = (CORTESIA, ASSINATURA)


class CreateAthlete(BaseModel):
    email: EmailStr
    name: str = "Novo atleta"
    plan: str = "FORGE_ACCESS"
    validity: str = "30"  # "30" | "90" | "180" | "365" | "LIFETIME" | "CUSTOM"
    custom_days: Optional[int] = None
    admin_note: str = ""
    # "courtesy" = acesso concedido pelo proprietario; "subscription" = a pessoa paga.
    # O padrao continua sendo cortesia para nao mudar o comportamento de quem ja usa a
    # tela, mas agora conceder de graca exige dizer por que.
    access_mode: str = CORTESIA
    confirm_courtesy: bool = False
    courtesy_reason: str = ""
    plan_code: Optional[str] = None   # so para access_mode="subscription"


class UpdateAthlete(BaseModel):
    name: Optional[str] = None
    plan: Optional[str] = None
    validity: Optional[str] = None
    custom_days: Optional[int] = None
    admin_note: Optional[str] = None


class AIUsageLimit(BaseModel):
    daily_limit: Optional[int] = None
    monthly_limit: Optional[int] = None
    ai_enabled: Optional[bool] = None


def compute_expiry(validity: str, custom_days: Optional[int]) -> Optional[str]:
    if validity == "LIFETIME":
        return None
    if validity == "CUSTOM":
        days = int(custom_days or 0) or 30
    else:
        days = int(validity) if validity in {"30", "90", "180", "365"} else 30
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


async def log_audit(db, actor: dict, action: str, target_id: Optional[str] = None, meta: Optional[Dict[str, Any]] = None):
    await db.admin_audit_log.insert_one({
        "id": str(uuid.uuid4()),
        "actor_id": actor["id"],
        "actor_email": actor["email"],
        "action": action,
        "target_user_id": target_id,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


@router.get("/stats")
async def stats(request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    athletes = {"role": "ATHLETE"}
    counts = {}
    counts["total"] = await db.users.count_documents(athletes)
    for st in VALID_STATUS:
        counts[st.lower()] = await db.users.count_documents({**athletes, "status": st})
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    counts["new_this_month"] = await db.users.count_documents({**athletes, "created_at": {"$gte": month_start}})
    # AI usage snapshot for the day
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_calls = 0
    async for row in db.ai_usage.find({"date": today}):
        day_calls += int(row.get("count", 0))
    counts["ai_calls_today"] = day_calls
    return counts


@router.get("/athletes")
async def list_athletes(request: Request, admin=Depends(require_super_admin), status: Optional[str] = None, q: Optional[str] = None):
    db = request.app.state.db
    query: Dict[str, Any] = {"role": "ATHLETE"}
    if status: query["status"] = status.upper()
    if q:
        query["$or"] = [{"email": {"$regex": q, "$options": "i"}}, {"name": {"$regex": q, "$options": "i"}}]
    rows = await db.users.find(query, {"_id": 0, "password_hash": 0, "invite_token": 0}).sort("created_at", -1).to_list(500)
    return {"athletes": rows}


@router.post("/athletes")
async def create_athlete(payload: CreateAthlete, request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    email = payload.email.lower()
    if payload.plan not in VALID_PLANS: raise HTTPException(400, "Plano inválido")
    if payload.access_mode not in MODOS_DE_ACESSO:
        raise HTTPException(400, "Modo de acesso inválido")
    if await db.users.find_one({"email": email}): raise HTTPException(409, "Já existe um usuário com esse e-mail")

    cortesia = payload.access_mode == CORTESIA
    motivo = (payload.courtesy_reason or "").strip()
    if cortesia:
        # Dar acesso de graca e uma decisao com custo. Exigir confirmacao e motivo torna
        # a decisao explicita e deixa rastro de quem concedeu, quando e por que.
        if not payload.confirm_courtesy:
            raise HTTPException(400, {
                "message": "Confirme a concessão de acesso cortesia.",
                "reason": "courtesy_confirmation_required"})
        if len(motivo) < 3:
            raise HTTPException(400, {
                "message": "Informe o motivo da cortesia.",
                "reason": "courtesy_reason_required"})
    elif payload.plan_code and not plano_ativo(payload.plan_code):
        raise HTTPException(400, "Plano inválido")

    uid = str(uuid.uuid4())
    invite = new_invite_token()
    doc = {
        "id": uid,
        "email": email,
        "name": payload.name.strip() or "Novo atleta",
        "role": "ATHLETE",
        # Convidado para assinar entra ja bloqueado: o convite da a conta, nao o acesso.
        "status": "PENDING" if cortesia else AGUARDANDO_PAGAMENTO,
        "signup_source": ORIGEM_CORTESIA_CONCEDIDA if cortesia else ORIGEM_CONVITE_PARA_ASSINAR,
        "plan": payload.plan,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": compute_expiry(payload.validity, payload.custom_days),
        "invite_token": invite,
        "invite_expires": (datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)).isoformat(),
        "admin_note": payload.admin_note,
        "created_by": admin["id"],
        **({"courtesy_reason": motivo, "courtesy_granted_by": admin["id"],
            "courtesy_granted_at": datetime.now(timezone.utc).isoformat()} if cortesia
           else {"plan_code_escolhido": payload.plan_code}),
        "ai_daily_limit": 40,
        "ai_monthly_limit": 800,
        "ai_enabled": True,
    }
    await db.users.insert_one(doc)
    # empty profile shell so the athlete lands into onboarding cleanly
    await db.profiles.insert_one({"id": uid, "user_id": uid, "name": doc["name"], "automation_mode": "FORGE_ASSISTED", "assessment": {}, "priorities": [], "onboarding_required": True})
    await log_audit(db, admin, "athlete.courtesy_granted" if cortesia else "athlete.invited_to_subscribe",
                    uid, {"email": email, "plan": payload.plan, "validity": payload.validity,
                          "access_mode": payload.access_mode,
                          **({"reason": motivo} if cortesia else
                             {"plan_code": payload.plan_code})})
    doc.pop("_id", None); doc.pop("password_hash", None)
    return {"athlete": doc, "invite_url": f"/invite/{invite}"}


@router.get("/athletes/{athlete_id}")
async def get_athlete(athlete_id: str, request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    user = await db.users.find_one({"id": athlete_id, "role": "ATHLETE"}, {"_id": 0, "password_hash": 0})
    if not user: raise HTTPException(404, "Atleta não encontrado")
    profile = await db.profiles.find_one({"id": athlete_id}, {"_id": 0})
    workouts = await db.set_logs.count_documents({"profile_id": athlete_id})
    return {"athlete": user, "profile": profile, "workouts": workouts}


@router.patch("/athletes/{athlete_id}")
async def update_athlete(athlete_id: str, payload: UpdateAthlete, request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    updates: Dict[str, Any] = {}
    if payload.name is not None: updates["name"] = payload.name.strip()
    if payload.plan:
        if payload.plan not in VALID_PLANS: raise HTTPException(400, "Plano inválido")
        updates["plan"] = payload.plan
    if payload.validity:
        updates["expires_at"] = compute_expiry(payload.validity, payload.custom_days)
    if payload.admin_note is not None: updates["admin_note"] = payload.admin_note
    if not updates: return {"updated": False}
    result = await db.users.update_one({"id": athlete_id, "role": "ATHLETE"}, {"$set": updates})
    if not result.matched_count: raise HTTPException(404, "Atleta não encontrado")
    await log_audit(db, admin, "athlete.updated", athlete_id, updates)
    return {"updated": True, "changes": updates}


@router.post("/athletes/{athlete_id}/suspend")
async def suspend_athlete(athlete_id: str, request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    result = await db.users.update_one({"id": athlete_id, "role": "ATHLETE"}, {"$set": {"status": "SUSPENDED", "suspended_at": datetime.now(timezone.utc).isoformat()}})
    if not result.matched_count: raise HTTPException(404, "Atleta não encontrado")
    await log_audit(db, admin, "athlete.suspended", athlete_id)
    return {"suspended": True}


@router.post("/athletes/{athlete_id}/reactivate")
async def reactivate_athlete(athlete_id: str, request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    user = await db.users.find_one({"id": athlete_id, "role": "ATHLETE"})
    if not user: raise HTTPException(404, "Atleta não encontrado")
    new_status = "ACTIVE" if user.get("activated_at") else "PENDING"
    await db.users.update_one({"id": athlete_id}, {"$set": {"status": new_status, "reactivated_at": datetime.now(timezone.utc).isoformat()}})
    await log_audit(db, admin, "athlete.reactivated", athlete_id, {"status": new_status})
    return {"reactivated": True, "status": new_status}


@router.post("/athletes/{athlete_id}/regenerate-invite")
async def regenerate_invite(athlete_id: str, request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    user = await db.users.find_one({"id": athlete_id, "role": "ATHLETE"})
    if not user: raise HTTPException(404, "Atleta não encontrado")
    invite = new_invite_token()
    await db.users.update_one({"id": athlete_id}, {"$set": {
        "invite_token": invite,
        "invite_expires": (datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)).isoformat(),
        "status": "PENDING" if not user.get("activated_at") else user.get("status"),
    }})
    await log_audit(db, admin, "athlete.invite_regenerated", athlete_id)
    return {"invite_url": f"/invite/{invite}", "invite_token": invite}


@router.get("/audit-log")
async def audit_log(request: Request, admin=Depends(require_super_admin), limit: int = 100):
    db = request.app.state.db
    rows = await db.admin_audit_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 500))
    return {"log": rows}


@router.get("/ai-usage")
async def ai_usage(request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    # aggregate per user last 30 days
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"date": {"$gte": since}}},
        {"$group": {"_id": "$user_id", "total": {"$sum": "$count"}, "last": {"$max": "$date"}}},
        {"$sort": {"total": -1}},
        {"$limit": 100},
    ]
    agg = await db.ai_usage.aggregate(pipeline).to_list(200)
    users = {u["id"]: u for u in await db.users.find({"id": {"$in": [r["_id"] for r in agg]}}, {"_id": 0, "id": 1, "email": 1, "name": 1, "ai_daily_limit": 1, "ai_monthly_limit": 1, "ai_enabled": 1}).to_list(200)}
    return {"usage": [{"user_id": r["_id"], "email": users.get(r["_id"], {}).get("email"), "name": users.get(r["_id"], {}).get("name"), "count_30d": r["total"], "last": r["last"], "ai_enabled": users.get(r["_id"], {}).get("ai_enabled", True), "ai_daily_limit": users.get(r["_id"], {}).get("ai_daily_limit", 40), "ai_monthly_limit": users.get(r["_id"], {}).get("ai_monthly_limit", 800)} for r in agg]}


@router.patch("/ai-usage/{athlete_id}")
async def update_ai_limit(athlete_id: str, payload: AIUsageLimit, request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    updates: Dict[str, Any] = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates: return {"updated": False}
    r = await db.users.update_one({"id": athlete_id}, {"$set": updates})
    if not r.matched_count: raise HTTPException(404, "Usuário não encontrado")
    await log_audit(db, admin, "ai_usage.limit_updated", athlete_id, updates)
    return {"updated": True, "changes": updates}

"""FORGE admin router: athlete management, audit log, AI usage."""
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import uuid

from auth import require_super_admin, new_invite_token, INVITE_TTL_DAYS
from auth import AGUARDANDO_PAGAMENTO
from billing_plans import ELITE, PLANOS, plano_ativo
from entitlements import (ATIVA, ORIGEM_CONVITE_PARA_ASSINAR, ORIGEM_CORTESIA,
                          ORIGEM_CORTESIA_CONCEDIDA, ORIGEM_MERCADOPAGO, resolver_acesso)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Os planos que existem de verdade, os mesmos de `billing_plans`. O painel mostrava
# FORGE_ACCESS / FORGE_PRO / LIFETIME, nomes de antes de existir cobranca, e gravava o
# escolhido em `users.plan` — um campo que `resolver_acesso` NUNCA le. O administrador
# escolhia um plano, a tela dizia "atualizado", e o acesso da pessoa continuava
# exatamente o mesmo. Nao havia nem como conceder o Elite, que e onde mora o Conselho.
PLANOS_DO_PAINEL = [p["code"] for p in PLANOS if p.get("ativo")]

# Valores antigos ainda gravados em contas existentes. Entram so na LEITURA, para as
# fichas antigas continuarem abrindo; nenhuma escrita nova usa esta lista.
PLANOS_LEGADOS = ["FORGE_ACCESS", "FORGE_PRO", "LIFETIME"]
VALID_PLANS = PLANOS_DO_PAINEL + PLANOS_LEGADOS
VALID_STATUS = ["PENDING", "PENDING_PAYMENT", "ACTIVE", "SUSPENDED", "EXPIRED"]
VALIDITY_MAP = {"30": 30, "90": 90, "180": 180, "365": 365, "LIFETIME": None}

# As duas formas de trazer alguem para dentro. Nomes explicitos porque a diferenca entre
# elas e quem paga a conta.
CORTESIA = "courtesy"
ASSINATURA = "subscription"
MODOS_DE_ACESSO = (CORTESIA, ASSINATURA)


class CreateAthlete(BaseModel):
    email: EmailStr
    name: str = "Novo atleta"
    # Campo legado, mantido so para nao quebrar cliente antigo. Ele grava em `users.plan`,
    # que nao decide acesso nenhum. Quem manda e `plan_code`.
    plan: Optional[str] = None
    validity: str = "30"  # "30" | "90" | "180" | "365" | "LIFETIME" | "CUSTOM"
    custom_days: Optional[int] = None
    admin_note: str = ""
    # "courtesy" = acesso concedido pelo proprietario; "subscription" = a pessoa paga.
    # O padrao continua sendo cortesia para nao mudar o comportamento de quem ja usa a
    # tela, mas agora conceder de graca exige dizer por que.
    access_mode: str = CORTESIA
    confirm_courtesy: bool = False
    courtesy_reason: str = ""
    # O plano, nos DOIS modos: em cortesia ele e concedido de verdade; em assinatura ele
    # e a sugestao que o checkout abre. Sem valor, o Elite continua sendo o padrao da
    # cortesia, que era o comportamento antes desta tela saber escolher.
    plan_code: Optional[str] = None


class UpdateAthlete(BaseModel):
    """Edicao de ficha. O plano NAO mora aqui.

    Havia um campo `plan` que gravava em `users.plan` e nao mudava acesso nenhum. Quem
    concede plano e `POST /athletes/{id}/plano`, que escreve uma assinatura de verdade e
    exige motivo, porque dar acesso de graca e uma decisao com custo.
    """
    name: Optional[str] = None
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
        # re.escape: sem isto, uma busca como "(a+)+$" vira regex catastrofico e
        # trava a consulta. E rota administrativa, mas o custo de escapar e zero.
        alvo = re.escape(q.strip())[:80]
        query["$or"] = [{"email": {"$regex": alvo, "$options": "i"}}, {"name": {"$regex": alvo, "$options": "i"}}]
    rows = await db.users.find(query, {"_id": 0, "password_hash": 0, "invite_token": 0}).sort("created_at", -1).to_list(500)
    return {"athletes": await _com_acesso(db, rows)}


async def _com_acesso(db, usuarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Anexa a cada atleta o acesso que REALMENTE vale, nao o campo `plan` do documento.

    A lista mostrava `users.plan`, que ninguem consulta para decidir nada: a tela dizia
    "vitalicio" para uma conta bloqueada por falta de pagamento. Aqui cada linha passa
    por `resolver_acesso`, a mesma funcao que o backend usa para liberar ou negar, entao
    o que o administrador le e o que a pessoa vive.

    Uma consulta so para todas as assinaturas: sao ate 500 atletas por pagina, e uma
    consulta por linha transformaria abrir a tela em 500 idas ao banco.
    """
    if not usuarios:
        return []
    ids = [u["id"] for u in usuarios]
    assinaturas = {a["user_id"]: a for a in
                   await db.subscriptions.find({"user_id": {"$in": ids}}, {"_id": 0}).to_list(None)}
    saida = []
    for usuario in usuarios:
        acesso = resolver_acesso(usuario, assinaturas.get(usuario["id"]))
        saida.append({**usuario, "acesso": {
            "plan_code": acesso["plan_code"],
            "source": acesso["source"],
            "status": acesso["status"],
            "awaiting_payment": acesso["awaiting_payment"],
            "capabilities": acesso["capabilities"],
        }})
    return saida


@router.post("/athletes")
async def create_athlete(payload: CreateAthlete, request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    email = payload.email.lower()
    plano_escolhido = payload.plan_code or ELITE
    if not plano_ativo(plano_escolhido):
        raise HTTPException(400, "Plano inválido")
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
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": compute_expiry(payload.validity, payload.custom_days),
        "invite_token": invite,
        "invite_expires": (datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)).isoformat(),
        "admin_note": payload.admin_note,
        "created_by": admin["id"],
        **({"courtesy_reason": motivo, "courtesy_granted_by": admin["id"],
            "courtesy_granted_at": datetime.now(timezone.utc).isoformat()} if cortesia
           else {"plan_code_escolhido": plano_escolhido}),
        "ai_daily_limit": 40,
        "ai_monthly_limit": 800,
        "ai_enabled": True,
    }
    await db.users.insert_one(doc)
    if cortesia:
        # A cortesia vira assinatura de verdade para entregar as capacidades do plano
        # ESCOLHIDO. Antes ela dependia de `signup_source`, que sempre resolvia Elite:
        # nao havia como conceder Essencial ou Pro de graca.
        await db.subscriptions.update_one({"user_id": uid}, {"$set": {
            "user_id": uid, "plan_code": plano_escolhido, "status": ATIVA,
            "provider": ORIGEM_CORTESIA, "amount_cents": 0, "currency": "BRL",
            "granted_by": admin["id"], "granted_at": doc["created_at"],
            "courtesy_reason": motivo,
        }}, upsert=True)
    # empty profile shell so the athlete lands into onboarding cleanly
    await db.profiles.insert_one({"id": uid, "user_id": uid, "name": doc["name"], "automation_mode": "FORGE_ASSISTED", "assessment": {}, "priorities": [], "onboarding_required": True})
    await log_audit(db, admin, "athlete.courtesy_granted" if cortesia else "athlete.invited_to_subscribe",
                    uid, {"email": email, "plan_code": plano_escolhido,
                          "validity": payload.validity,
                          "access_mode": payload.access_mode,
                          **({"reason": motivo} if cortesia else {})})
    doc.pop("_id", None); doc.pop("password_hash", None)
    return {"athlete": doc, "invite_url": f"/invite/{invite}"}


@router.get("/athletes/{athlete_id}")
async def get_athlete(athlete_id: str, request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    user = await db.users.find_one({"id": athlete_id, "role": "ATHLETE"}, {"_id": 0, "password_hash": 0})
    if not user: raise HTTPException(404, "Atleta não encontrado")
    profile = await db.profiles.find_one({"id": athlete_id}, {"_id": 0})
    workouts = await db.set_logs.count_documents({"profile_id": athlete_id})
    assinatura = await db.subscriptions.find_one({"user_id": athlete_id}, {"_id": 0})
    acesso = resolver_acesso(user, assinatura)
    return {"athlete": user, "profile": profile, "workouts": workouts,
            "acesso": acesso, "planos": PLANOS_DO_PAINEL}


@router.patch("/athletes/{athlete_id}")
async def update_athlete(athlete_id: str, payload: UpdateAthlete, request: Request, admin=Depends(require_super_admin)):
    db = request.app.state.db
    updates: Dict[str, Any] = {}
    if payload.name is not None: updates["name"] = payload.name.strip()
    if payload.validity:
        updates["expires_at"] = compute_expiry(payload.validity, payload.custom_days)
    if payload.admin_note is not None: updates["admin_note"] = payload.admin_note
    if not updates: return {"updated": False}
    result = await db.users.update_one({"id": athlete_id, "role": "ATHLETE"}, {"$set": updates})
    if not result.matched_count: raise HTTPException(404, "Atleta não encontrado")
    await log_audit(db, admin, "athlete.updated", athlete_id, updates)
    return {"updated": True, "changes": updates}


class ConcederPlano(BaseModel):
    plan_code: Optional[str] = None      # None remove a concessao
    motivo: str = ""
    substituir_assinatura_paga: bool = False


@router.post("/athletes/{athlete_id}/plano")
async def conceder_plano(athlete_id: str, payload: ConcederPlano, request: Request,
                         admin=Depends(require_super_admin)):
    """Concede (ou remove) um plano de cortesia, com efeito REAL sobre o acesso.

    Por que este endpoint existe
    ----------------------------
    O painel tinha um campo "plano" que gravava em `users.plan`. `resolver_acesso` nunca
    le esse campo: quem decide o acesso e o papel de administrador, uma linha ativa em
    `subscriptions`, ou `signup_source == courtesy_granted`. O administrador escolhia um
    plano, a tela confirmava, e nada mudava — e nao havia como conceder o Elite, que e
    onde mora o Conselho.

    Aqui a concessao vira uma assinatura de verdade, com `provider = courtesy`: ela passa
    por `assinatura_da_acesso` como qualquer outra e entrega exatamente as capacidades
    daquele plano. Cortesia continua sendo acesso concedido, e nao pagamento falso: valor
    zero, sem id do Mercado Pago, e fora de qualquer relatorio de receita.

    A trava que importa
    -------------------
    Uma assinatura PAGA e ativa nao e sobrescrita por acidente. Trocar o plano de quem
    paga por cortesia apagaria o vinculo com o Mercado Pago e a cobranca seguiria
    correndo sem o FORGE saber de que plano ela e. E preciso dizer, explicitamente, que e
    isso mesmo que se quer.
    """
    db = request.app.state.db
    user = await db.users.find_one({"id": athlete_id, "role": "ATHLETE"})
    if not user:
        raise HTTPException(404, "Atleta não encontrado")

    motivo = (payload.motivo or "").strip()
    atual = await db.subscriptions.find_one({"user_id": athlete_id})
    paga_ativa = (atual and atual.get("provider") == ORIGEM_MERCADOPAGO
                  and atual.get("status") in (ATIVA, "past_due"))
    if paga_ativa and not payload.substituir_assinatura_paga:
        raise HTTPException(409, {
            "message": "Este atleta tem uma assinatura paga ativa. Confirme que quer "
                       "substituí-la por cortesia.",
            "reason": "paid_subscription"})

    agora = datetime.now(timezone.utc).isoformat()

    if not payload.plan_code:
        if atual and atual.get("provider") == ORIGEM_CORTESIA:
            await db.subscriptions.delete_one({"user_id": athlete_id})
        await log_audit(db, admin, "athlete.courtesy_plan_revoked", athlete_id,
                        {"previous_plan": (atual or {}).get("plan_code"), "reason": motivo})
        return {"plan_code": None, "revoked": True}

    if not plano_ativo(payload.plan_code):
        raise HTTPException(400, "Plano inválido")
    if len(motivo) < 3:
        raise HTTPException(400, {"message": "Informe o motivo da cortesia.",
                                  "reason": "courtesy_reason_required"})

    await db.subscriptions.update_one({"user_id": athlete_id}, {"$set": {
        "user_id": athlete_id,
        "plan_code": payload.plan_code,
        "status": ATIVA,
        "provider": ORIGEM_CORTESIA,
        "amount_cents": 0,          # cortesia nao e receita
        "currency": "BRL",
        "granted_by": admin["id"],
        "granted_at": agora,
        "courtesy_reason": motivo,
    }, "$unset": {"provider_subscription_id": ""}}, upsert=True)

    # A conta precisa poder entrar: quem estava aguardando pagamento ja tem acesso agora.
    if user.get("status") == AGUARDANDO_PAGAMENTO:
        await db.users.update_one({"id": athlete_id}, {"$set": {"status": "ACTIVE"}})

    await log_audit(db, admin, "athlete.courtesy_plan_granted", athlete_id, {
        "plan_code": payload.plan_code, "reason": motivo,
        "previous_plan": (atual or {}).get("plan_code"),
        "replaced_paid": bool(paga_ativa)})

    atualizado = await db.users.find_one({"id": athlete_id}, {"_id": 0, "password_hash": 0})
    assinatura = await db.subscriptions.find_one({"user_id": athlete_id}, {"_id": 0})
    return {"plan_code": payload.plan_code,
            "acesso": resolver_acesso(atualizado, assinatura)}


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


@router.post("/athletes/{athlete_id}/require-payment")
async def require_payment(athlete_id: str, request: Request,
                          admin=Depends(require_super_admin)):
    """Reaproveita a conta existente e a envia ao fluxo de nova assinatura.

    Suspensao continua sendo bloqueio total. Esta acao e explicita porque muda o motivo
    do bloqueio: o atleta volta a poder entrar, mas so enxerga avaliacao, planos e
    pagamento ate o webhook confirmar uma nova assinatura.
    """
    db = request.app.state.db
    user = await db.users.find_one({"id": athlete_id, "role": "ATHLETE"})
    if not user:
        raise HTTPException(404, "Atleta não encontrado")

    assinatura = await db.subscriptions.find_one({"user_id": athlete_id})
    if assinatura and assinatura.get("status") in ("active", "past_due"):
        raise HTTPException(409, {
            "message": "Este atleta ainda tem uma assinatura ativa. Cancele-a antes de liberar uma nova compra.",
            "reason": "active_subscription"})

    plano_sugerido = user.get("plan_code_escolhido")
    if not plano_ativo(plano_sugerido or ""):
        plano_sugerido = "pro"
    agora = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"id": athlete_id}, {"$set": {
        "status": AGUARDANDO_PAGAMENTO,
        "plan": None,
        "plan_code_escolhido": plano_sugerido,
        "payment_required_at": agora,
        "payment_required_by": admin["id"],
    }})
    await log_audit(db, admin, "athlete.payment_required", athlete_id,
                    {"previous_status": user.get("status"),
                     "previous_plan": user.get("plan"),
                     "suggested_plan": plano_sugerido})
    return {"payment_required": True, "status": AGUARDANDO_PAGAMENTO,
            "plan_code": plano_sugerido}


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

"""FORGE auth: JWT + bcrypt + invite flow. Bearer token in Authorization header."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timedelta, timezone
from typing import Optional
import os, uuid, secrets, bcrypt, jwt

JWT_ALGO = "HS256"
ACCESS_TTL_MIN = 60 * 12  # 12h — comfortable for daily athletes without frequent re-login
LOCKOUT_MAX = 6
LOCKOUT_MIN = 15
INVITE_TTL_DAYS = 14

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AcceptInviteIn(BaseModel):
    token: str
    password: str = Field(min_length=8)
    name: Optional[str] = None


def secret() -> str:
    return os.environ["FORGE_JWT_SECRET"]


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_token(user_id: str, role: str) -> str:
    payload = {"sub": user_id, "role": role, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TTL_MIN)}
    return jwt.encode(payload, secret(), algorithm=JWT_ALGO)


def new_invite_token() -> str:
    return secrets.token_urlsafe(32)


def is_expired(user: dict) -> bool:
    exp = user.get("expires_at")
    if not exp: return False
    try:
        return datetime.fromisoformat(exp) < datetime.now(timezone.utc)
    except Exception:
        return False


def sanitize(user: dict) -> dict:
    if not user: return {}
    return {k: v for k, v in user.items() if k not in {"password_hash", "invite_token", "_id"}}


# Conta nascida no funil publico e ainda sem pagamento confirmado. Nome proprio, separado
# do "PENDING" do convite administrativo, que significa outra coisa (convite ainda nao
# aceito) e nao deve herdar este bloqueio.
AGUARDANDO_PAGAMENTO = "PENDING_PAYMENT"

# As unicas rotas autenticadas que uma conta aguardando pagamento alcanca.
#
# Lista de PERMISSAO, nao de bloqueio. A aplicacao tem mais de noventa rotas e ganha
# outras a cada entrega; uma lista de bloqueio liberaria cada rota nova por esquecimento,
# e o esquecimento apareceria como acesso gratuito, nao como erro. Aqui o padrao e negar:
# rota nova nasce fechada para quem nao pagou, e abri-la exige escrever o caminho abaixo.
ROTAS_LIBERADAS_SEM_PAGAMENTO = frozenset({
    "/api/auth/me",          # saber quem esta logado, para a tela renderizar
    "/api/billing/plans",    # ver os planos
    "/api/billing/me",       # estado da assinatura / retorno do checkout
    "/api/billing/checkout", # pagar, inclusive retomando um checkout abandonado
})


def get_db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.state.db


async def get_current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Não autenticado")
    token = auth[7:]
    try:
        payload = jwt.decode(token, secret(), algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido")
    if payload.get("type") != "access":
        raise HTTPException(401, "Tipo de token inválido")
    db = request.app.state.db
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "Conta não encontrada")
    if user.get("status") == "SUSPENDED":
        raise HTTPException(403, "Conta suspensa. Fale com o administrador.")

    # A trava mora aqui, e nao em cada rota, porque esta e a dependencia por onde passa
    # toda requisicao autenticada: trocar o localStorage, o corpo, a rota ou o plano no
    # navegador nao muda nada, porque o estado e relido do banco a cada chamada.
    if (user.get("status") == AGUARDANDO_PAGAMENTO
            and user.get("role") != "SUPER_ADMIN"
            and request.url.path.rstrip("/") not in ROTAS_LIBERADAS_SEM_PAGAMENTO):
        raise HTTPException(403, {
            "message": "Conclua o pagamento para liberar seu acesso.",
            "reason": "payment_pending"})

    if is_expired(user):
        if user.get("status") != "EXPIRED":
            await db.users.update_one({"id": user["id"]}, {"$set": {"status": "EXPIRED"}})
            user["status"] = "EXPIRED"
        if user.get("role") != "SUPER_ADMIN":
            raise HTTPException(403, "Acesso expirado. Renove seu plano.")
    return user


async def require_super_admin(user=Depends(get_current_user)):
    if user.get("role") != "SUPER_ADMIN":
        raise HTTPException(403, "Acesso restrito ao administrador")
    return user


async def _check_lockout(db, ident: str):
    row = await db.login_attempts.find_one({"identifier": ident})
    if row and row.get("count", 0) >= LOCKOUT_MAX:
        last = row.get("last")
        if last and datetime.fromisoformat(last) + timedelta(minutes=LOCKOUT_MIN) > datetime.now(timezone.utc):
            raise HTTPException(429, f"Muitas tentativas. Tente novamente em {LOCKOUT_MIN} minutos.")


async def _record_attempt(db, ident: str, success: bool):
    if success:
        await db.login_attempts.delete_one({"identifier": ident})
    else:
        await db.login_attempts.update_one(
            {"identifier": ident},
            {"$inc": {"count": 1}, "$set": {"last": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )


@router.post("/login")
async def login(payload: LoginIn, request: Request):
    db = get_db(request)
    ident = f"{request.client.host if request.client else 'unknown'}:{payload.email.lower()}"
    await _check_lockout(db, ident)
    user = await db.users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await _record_attempt(db, ident, False)
        raise HTTPException(401, "E-mail ou senha inválidos")
    if user.get("status") == "SUSPENDED":
        raise HTTPException(403, "Conta suspensa. Fale com o administrador.")
    if user.get("status") == "PENDING":
        raise HTTPException(403, "Conta ainda não ativada. Use o link de convite.")
    if is_expired(user) and user.get("role") != "SUPER_ADMIN":
        await db.users.update_one({"id": user["id"]}, {"$set": {"status": "EXPIRED"}})
        raise HTTPException(403, "Plano expirado. Fale com o administrador.")
    await _record_attempt(db, ident, True)
    await db.users.update_one({"id": user["id"]}, {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}})
    return {"token": create_token(user["id"], user["role"]), "user": sanitize(user)}


@router.get("/me")
async def me(user=Depends(get_current_user)):
    return {"user": sanitize(user)}


@router.get("/invite/{token}")
async def invite_lookup(token: str, request: Request):
    db = get_db(request)
    user = await db.users.find_one({"invite_token": token}, {"_id": 0, "password_hash": 0})
    if not user: raise HTTPException(404, "Convite inválido")
    if user.get("status") != "PENDING":
        raise HTTPException(410, "Convite já utilizado")
    exp = user.get("invite_expires")
    if exp and datetime.fromisoformat(exp) < datetime.now(timezone.utc):
        raise HTTPException(410, "Convite expirado. Peça um novo ao administrador.")
    return {"email": user["email"], "name": user.get("name", ""), "plan": user.get("plan"), "expires_at": user.get("expires_at")}


@router.post("/accept-invite")
async def accept_invite(payload: AcceptInviteIn, request: Request):
    db = get_db(request)
    user = await db.users.find_one({"invite_token": payload.token})
    if not user: raise HTTPException(404, "Convite inválido")
    if user.get("status") != "PENDING": raise HTTPException(410, "Convite já utilizado")
    exp = user.get("invite_expires")
    if exp and datetime.fromisoformat(exp) < datetime.now(timezone.utc):
        raise HTTPException(410, "Convite expirado")
    updates = {"password_hash": hash_password(payload.password), "status": "ACTIVE", "invite_token": None, "invite_expires": None, "activated_at": datetime.now(timezone.utc).isoformat()}
    if payload.name: updates["name"] = payload.name.strip()
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    user.update(updates)
    return {"token": create_token(user["id"], user["role"]), "user": sanitize(user)}


async def seed_super_admin(db, email: str):
    email = email.lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        # ensure the seeded admin keeps SUPER_ADMIN + ACTIVE (no password reset here)
        patches = {}
        if existing.get("role") != "SUPER_ADMIN": patches["role"] = "SUPER_ADMIN"
        if existing.get("status") not in ("ACTIVE", "PENDING"): patches["status"] = "ACTIVE"
        if patches: await db.users.update_one({"id": existing["id"]}, {"$set": patches})
        return existing["id"], None
    uid = str(uuid.uuid4())
    invite = new_invite_token()
    doc = {
        "id": uid,
        "email": email,
        "name": "Super Admin",
        "role": "SUPER_ADMIN",
        "status": "PENDING",
        "plan": "LIFETIME",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": None,
        "invite_token": invite,
        "invite_expires": (datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)).isoformat(),
        "admin_note": "Seeded from FORGE_SUPER_ADMIN_EMAIL",
    }
    await db.users.insert_one(doc)
    return uid, invite

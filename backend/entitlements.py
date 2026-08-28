"""Quem pode o que, no FORGE.

Regra central: PERMISSAO E VERIFICADA NO BACKEND. A interface pode esconder um botao,
mas isso nao protege endpoint nenhum — quem decide e daqui.

Nao existe condicional de plano espalhada pelas rotas: elas perguntam por CAPACIDADE
(`exigir_capacidade(...)`), e este modulo resolve capacidade a partir do estado real da
assinatura. Assim, criar um plano novo nao obriga a caçar `if plano == ...` pelo codigo.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

from billing_plans import (
    CAPACIDADES_ELITE, ELITE, capacidades_do_plano, plano,
)

# ── Estados da assinatura ────────────────────────────────────────────────────────────
# Mapeados a partir do que o Mercado Pago devolve; ver billing.py.
PENDENTE = "pending"
ATIVA = "active"
EM_ATRASO = "past_due"
PAUSADA = "paused"
CANCELADA = "cancelled"
EXPIRADA = "expired"
RECUSADA = "rejected"

ESTADOS = (PENDENTE, ATIVA, EM_ATRASO, PAUSADA, CANCELADA, EXPIRADA, RECUSADA)

# Origens de acesso. Cortesia NAO cria pagamento falso: e um acesso concedido, registrado
# como tal, sem valor, sem id do Mercado Pago e sem aparecer como receita.
ORIGEM_MERCADOPAGO = "mercadopago"
ORIGEM_CORTESIA = "courtesy"

# Tres dias de tolerancia apos falha de renovacao: o acesso segue enquanto o atleta
# atualiza o pagamento. Nao se aplica a cancelamento deliberado nem a recusa.
DIAS_DE_TOLERANCIA = 3


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _quando(valor) -> Optional[datetime]:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def cobranca_ativa() -> bool:
    """Feature flag. Enquanto desligada, ninguem e bloqueado por falta de assinatura —
    a pagina de planos e o checkout funcionam, mas o acesso continua liberado. E o que
    permite publicar o sistema inteiro sem cortar nenhum usuario atual."""
    return (os.environ.get("BILLING_ENFORCED") or "").strip().lower() in ("1", "true", "yes")


def _limite_do_grandfathering() -> Optional[datetime]:
    return _quando(os.environ.get("BILLING_GRANDFATHER_BEFORE"))


def e_administrador(user: Dict[str, Any]) -> bool:
    """Proprietario/admin nunca e bloqueado por cobranca. O papel vem do banco, semeado
    por FORGE_SUPER_ADMIN_EMAIL — nenhum e-mail pessoal no codigo, muito menos no
    frontend."""
    return (user or {}).get("role") == "SUPER_ADMIN"


def e_usuario_antigo(user: Dict[str, Any]) -> bool:
    """Conta anterior a cobranca. Sem BILLING_GRANDFATHER_BEFORE definido, TODO usuario
    conta como antigo: e o estado seguro durante a implantacao, quando ninguem deve ser
    cortado por uma feature que acabou de subir."""
    # Quem entrou pelo cadastro publico NUNCA e antigo: essa conta nasceu para pagar, e
    # trata-la como legado daria acesso de graca a todo mundo que se cadastrasse.
    if (user or {}).get("signup_source") == "public":
        return False
    limite = _limite_do_grandfathering()
    if limite is None:
        return True
    criado = _quando((user or {}).get("created_at"))
    return criado is not None and criado < limite


def acesso_por_tolerancia(assinatura: Dict[str, Any]) -> bool:
    """Renovacao falhou: o acesso segue por DIAS_DE_TOLERANCIA a partir do momento em que
    entrou em atraso."""
    desde = _quando(assinatura.get("past_due_since"))
    if desde is None:
        return False
    return _agora() <= desde + timedelta(days=DIAS_DE_TOLERANCIA)


def assinatura_da_acesso(assinatura: Optional[Dict[str, Any]]) -> bool:
    if not assinatura:
        return False
    estado = assinatura.get("status")
    if estado == ATIVA:
        return True
    if estado == EM_ATRASO:
        return acesso_por_tolerancia(assinatura)
    # pendente/cancelada/expirada/recusada/pausada nao liberam nada. Em especial:
    # pendente NAO libera — o retorno visual do checkout nao e confirmacao.
    return False


async def assinatura_do_usuario(db, user_id: str) -> Optional[Dict[str, Any]]:
    """A assinatura corrente. Um usuario tem no maximo uma (indice unico em user_id)."""
    return await db.subscriptions.find_one({"user_id": user_id}, {"_id": 0})


def resolver_acesso(user: Dict[str, Any], assinatura: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Estado de acesso completo do usuario. Uma so funcao decide, e todo mundo consulta
    ela — backend e interface leem exatamente a mesma resposta."""
    if e_administrador(user):
        return {"plan_code": ELITE, "capabilities": sorted(CAPACIDADES_ELITE),
                "source": "admin", "status": ATIVA, "subscription": None,
                "grandfathered": False, "billing_enforced": cobranca_ativa()}

    if assinatura_da_acesso(assinatura):
        code = assinatura.get("plan_code")
        return {"plan_code": code, "capabilities": sorted(capacidades_do_plano(code)),
                "source": assinatura.get("provider", ORIGEM_MERCADOPAGO),
                "status": assinatura.get("status"), "subscription": assinatura,
                "grandfathered": False, "billing_enforced": cobranca_ativa()}

    # Sem assinatura valida: cobranca desligada, ou conta anterior a cobranca, mantem
    # acesso de cortesia equivalente ao Elite. Ninguem perde o que ja usava.
    if not cobranca_ativa() or e_usuario_antigo(user):
        return {"plan_code": ELITE, "capabilities": sorted(CAPACIDADES_ELITE),
                "source": ORIGEM_CORTESIA, "status": ATIVA, "subscription": assinatura,
                "grandfathered": True, "billing_enforced": cobranca_ativa()}

    return {"plan_code": None, "capabilities": [],
            "source": None, "status": (assinatura or {}).get("status"),
            "subscription": assinatura, "grandfathered": False,
            "billing_enforced": cobranca_ativa()}


async def acesso_de(db, user: Dict[str, Any]) -> Dict[str, Any]:
    return resolver_acesso(user, await assinatura_do_usuario(db, user["id"]))


async def exigir_capacidade(db, user: Dict[str, Any], capacidade: str) -> Dict[str, Any]:
    """Porta unica das rotas pagas. Devolve o acesso quando permitido; 402 quando nao.

    402 e nao 403 de proposito: nao e falta de permissao, e falta de plano — a interface
    usa isso para levar a pagina de planos em vez de mostrar "acesso negado"."""
    acesso = await acesso_de(db, user)
    if capacidade in acesso["capabilities"]:
        return acesso
    p = plano(acesso.get("plan_code"))
    raise HTTPException(402, {
        "message": "Seu plano atual não inclui este recurso.",
        "capability": capacidade,
        "current_plan": p["nome"] if p else None,
        "upgrade": True,
    })

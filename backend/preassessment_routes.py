"""Rotas da pre-avaliacao do funil publico.

Alcancaveis por quem ainda nao pagou — sao das poucas que estao em
`ROTAS_LIBERADAS_SEM_PAGAMENTO`. Por isso valem duas precaucoes que nao seriam
necessarias em rota paga:

  - as capacidades vem do plano ESCOLHIDO, nao do acesso atual. Quem ainda nao pagou tem
    acesso vazio; se a previa lesse dali, todo mundo veria a versao Essencial;
  - a gravacao tem limite de taxa. A geracao e barata e deterministica, mas escrita em
    banco por conta anonima-ate-pagar merece teto de qualquer jeito.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

import preassessment as pa
from auth import get_current_user
from ratelimit import limitar
from billing_plans import capacidades_do_plano, plano_ativo
from entitlements import acesso_de

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/preassessment", tags=["preassessment"])

# Teto generoso: quem esta escolhendo mexe nas respostas varias vezes para ver a previa
# mudar, e isso e uso legitimo. O limite existe contra laco automatizado, nao contra
# indecisao.
MAX_GRAVACOES_POR_JANELA = 60
JANELA_MINUTOS = 60


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat()


class RespostasIn(BaseModel):
    sex: str = Field(min_length=1, max_length=16)
    experience: str = Field(min_length=1, max_length=32)
    goal: Optional[str] = Field(default=None, max_length=32)
    days: int
    priorities: List[str] = []
    body_goal: Optional[str] = Field(default=None, max_length=32)
    goal_intensity: Optional[str] = Field(default=None, max_length=32)


def _plano_em_questao(user: Dict[str, Any], acesso: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """O plano de que a previa fala.

    Quem ja pagou tem um plano de verdade; quem nao pagou tem o que escolheu no funil. A
    previa precisa falar do segundo, senao mostra o Essencial para todo mundo."""
    code = acesso.get("plan_code") or user.get("plan_code_escolhido")
    return plano_ativo(code)


async def _limitar(db, user_id: str) -> None:
    await limitar(db, f"preassessment:{user_id}", MAX_GRAVACOES_POR_JANELA,
                  JANELA_MINUTOS,
                  mensagem="Muitas alterações seguidas. Aguarde um instante.")


def _resposta(user: Dict[str, Any], p: Optional[Dict[str, Any]], caps: set,
              doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "catalog": pa.catalogo(caps),
        "answers": doc,
        "preview": pa.montar_previa(doc, caps, p) if doc else None,
        "plan_code": (p or {}).get("code"),
        "plan_name": (p or {}).get("nome"),
        "awaiting_payment": user.get("status") == "PENDING_PAYMENT",
    }


@router.get("")
async def ler(request: Request, user=Depends(get_current_user)):
    """Catalogo, respostas salvas e previa. Retomar um cadastro abandonado cai aqui."""
    db = request.app.state.db
    p = _plano_em_questao(user, await acesso_de(db, user))
    caps = capacidades_do_plano((p or {}).get("code"))
    return _resposta(user, p, caps, user.get("pre_assessment"))


@router.post("")
async def salvar(payload: RespostasIn, request: Request, user=Depends(get_current_user)):
    """Guarda as respostas e devolve a previa.

    As respostas ficam no usuario, e nao na tentativa de cadastro, porque precisam
    sobreviver ao pagamento: e delas que o questionario completo se abastece para nao
    perguntar duas vezes."""
    db = request.app.state.db
    await _limitar(db, user["id"])

    p = _plano_em_questao(user, await acesso_de(db, user))
    caps = capacidades_do_plano((p or {}).get("code"))
    try:
        doc = pa.normalizar(payload.model_dump(), caps)
    except pa.RespostaInvalida as e:
        raise HTTPException(400, {"message": e.mensagem, "field": e.campo,
                                  "reason": "invalid_answer"})

    doc["answered_at"] = _iso(_agora())
    doc["plan_code_at_answer"] = (p or {}).get("code")
    await db.users.update_one({"id": user["id"]}, {"$set": {"pre_assessment": doc}})
    logger.info("pre-avaliacao salva user=%s plano=%s", user["id"], doc["plan_code_at_answer"])
    return _resposta(user, p, caps, doc)

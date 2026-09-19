from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request

from auth import get_current_user
from cardio import CardioLogIn, cardio_doc


router = APIRouter(prefix="/api/cardio", tags=["cardio"])


@router.post("")
async def log_cardio(payload: CardioLogIn, request: Request, user=Depends(get_current_user)):
    target = user["id"]
    doc = cardio_doc(payload, target, datetime.now(timezone.utc).isoformat())
    # A client token makes a retry idempotent instead of creating duplicate cardio logs.
    await request.app.state.db.cardio_logs.replace_one(
        {"profile_id": target, "client_token": doc["client_token"]},
        doc,
        upsert=True,
    )
    return {k: v for k, v in doc.items() if k != "user_id"}


@router.get("/recent")
async def recent_cardio(request: Request, limit: int = Query(default=20, ge=1, le=100), user=Depends(get_current_user)):
    rows = await request.app.state.db.cardio_logs.find(
        {"profile_id": user["id"], "completed": True}, {"_id": 0, "user_id": 0}
    ).sort("created_at", -1).to_list(length=limit)
    return {"items": rows}


# ── A aba de cardio ─────────────────────────────────────────────────────────────────
# As duas rotas acima nasceram para o finalizador que aparece depois do treino e por isso
# gravam uma sessao e leem as ultimas. A aba precisa de mais: a lista de uma janela, a
# leitura semanal que o Conselho usa, e apagar um registro errado.

from datetime import date as CalendarDate, timedelta  # noqa: E402

from fastapi import HTTPException  # noqa: E402

from cardio import MODALITIES, cardio_reading  # noqa: E402

JANELA_PADRAO = 28          # quatro semanas: uma media semanal que nao oscila por um dia
TETO_DA_LISTA = 200


@router.get("/modalities")
async def cardio_modalities(_user=Depends(get_current_user)):
    """As modalidades que a tela oferece, na ordem.

    Vem do servidor para a tela nao manter uma segunda lista: duas listas de modalidade no
    mesmo produto viram dois relatorios que nao batem.
    """
    return {"modalities": MODALITIES}


@router.get("")
async def list_cardio(request: Request, user=Depends(get_current_user),
                      janela_dias: int = JANELA_PADRAO):
    janela_dias = max(1, min(365, int(janela_dias or JANELA_PADRAO)))
    rows = await _rows(request.app.state.db, user["id"], janela_dias)
    return {"sessoes": rows, "leitura": cardio_reading(rows, janela_dias),
            "janela_dias": janela_dias}


@router.delete("/{client_token}")
async def delete_cardio(client_token: str, request: Request, user=Depends(get_current_user)):
    r = await request.app.state.db.cardio_logs.delete_one(
        {"profile_id": user["id"], "client_token": client_token})
    if not r.deleted_count:
        raise HTTPException(404, "Esse registro de cardio não existe.")
    return {"removido": client_token}


async def _rows(db, profile_id: str, janela_dias: int):
    """As sessoes da janela, do mais novo para o mais antigo.

    Filtra por `date` quando ele existe e cai em `created_at` quando nao: os registros
    gravados antes do campo `date` nascer nao podem sumir da lista de quem ja usava.
    """
    desde = (CalendarDate.today() - timedelta(days=max(1, janela_dias) - 1)).isoformat()
    rows = await db.cardio_logs.find(
        {"profile_id": profile_id, "completed": True,
         "$or": [{"date": {"$gte": desde}},
                 {"date": {"$exists": False}, "created_at": {"$gte": desde}}]},
        {"_id": 0, "user_id": 0}).sort("created_at", -1).to_list(TETO_DA_LISTA)
    for r in rows:
        r.setdefault("date", str(r.get("created_at") or "")[:10])
    return rows


async def ler_cardio(db, perfil_id: str, janela_dias: int) -> dict:
    """A leitura que o Conselho usa, pelo MESMO caminho da tela.

    Se a rota do Conselho montasse a leitura por conta propria, os dois lados poderiam
    divergir e o atleta veria um total no cardio e outro no conselho da mesma semana.
    """
    return cardio_reading(await _rows(db, perfil_id, janela_dias), janela_dias)

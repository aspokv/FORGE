"""Limite de taxa por chave, guardado no proprio Mongo.

Janela fixa, e nao janela deslizante: o objetivo aqui e conter laco automatizado e abuso
de rota cara, nao distribuir trafego com precisao. Uma janela fixa erra por permitir ate
o dobro na virada, o que e irrelevante para "nao deixe alguem abrir mil checkouts".

Fica no Mongo porque o backend pode rodar em mais de um container: um contador em memoria
seria zerado a cada restart e contaria separado por processo, o que na pratica multiplica
o limite pelo numero de replicas.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _agora() -> datetime:
    return datetime.now(timezone.utc)


async def limitar(db, chave: str, maximo: int, janela_minutos: int,
                  mensagem: str = "Muitas tentativas seguidas. Aguarde um instante.",
                  motivo: str = "rate_limited") -> None:
    """Conta um uso de `chave`. Levanta 429 quando o teto da janela e atingido."""
    agora = _agora()
    registro = await db.rate_limits.find_one({"key": chave})

    inicio: Optional[datetime] = None
    if registro and registro.get("window_start"):
        try:
            inicio = datetime.fromisoformat(registro["window_start"])
        except (TypeError, ValueError):
            inicio = None

    if inicio is None or agora - inicio > timedelta(minutes=janela_minutos):
        await db.rate_limits.update_one(
            {"key": chave},
            {"$set": {"window_start": agora.isoformat(), "count": 1}}, upsert=True)
        return

    if int(registro.get("count", 0)) >= maximo:
        # A chave entra no log; o valor que a originou (e-mail, token) nunca.
        logger.warning("limite de taxa atingido para %s", chave.split(":")[0])
        raise HTTPException(429, {"message": mensagem, "reason": motivo})

    await db.rate_limits.update_one({"key": chave}, {"$inc": {"count": 1}})

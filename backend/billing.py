"""Cliente do Mercado Pago e validacao de webhook.

Diferente do Omega Vault, que usa Checkout Pro com pagamento UNICO
(`/checkout/preferences`), o FORGE usa a API de Assinaturas: `/preapproval_plan` define
o plano recorrente e `/preapproval` cria a assinatura do atleta. Por isso nada de
`create-preference` aqui — uma preferencia nao renova sozinha.

O que foi reaproveitado conceitualmente do Omega Vault: a convencao de token
(`TEST-` = sandbox, `APP_USR-` = producao) para escolher a URL de checkout sem flag
separada, e o esquema de assinatura do webhook (manifest + HMAC-SHA256 + comparacao em
tempo constante). Nenhuma credencial, tabela ou regra de autenticacao foi copiada.
"""
import hashlib
import hmac
import logging
import os
from typing import Any, Dict, Optional, Protocol

import httpx

logger = logging.getLogger(__name__)

API = "https://api.mercadopago.com"
TIMEOUT = 12.0


def token_de_acesso() -> str:
    return (os.environ.get("MP_ACCESS_TOKEN") or "").strip()


def modo_sandbox(token: Optional[str] = None) -> bool:
    """Convencao do proprio Mercado Pago: token de teste comeca com "TEST-", o de
    producao com "APP_USR-". E o que deixa o fluxo escolher sandbox ou producao sem uma
    segunda variavel de ambiente para manter em sincronia (e para esquecer de trocar)."""
    return (token if token is not None else token_de_acesso()).startswith("TEST-")


def url_de_checkout(recurso: Dict[str, Any], token: Optional[str] = None) -> Optional[str]:
    """Um recurso criado com token de teste so funciona pelo sandbox_init_point; um
    criado com token de producao precisa do init_point. Trocar os dois leva a um
    checkout que abre e falha."""
    if modo_sandbox(token):
        return recurso.get("sandbox_init_point") or recurso.get("init_point")
    return recurso.get("init_point")


# ── Assinatura do webhook ────────────────────────────────────────────────────────────

def validar_assinatura_do_webhook(segredo: str, cabecalho_assinatura: Optional[str],
                                  request_id: Optional[str], data_id: Optional[str]) -> bool:
    """`x-signature: ts=<unix_ms>,v1=<hex_hmac>`, manifest
    `id:{data.id em minusculo};request-id:{x-request-id};ts:{ts};`, HMAC-SHA256 com o
    segredo do webhook. O data.id vai em MINUSCULO — com maiuscula a assinatura nao bate.

    Sem segredo configurado a resposta e False: um webhook que aceita qualquer corpo e
    um endpoint que qualquer pessoa usa para liberar assinatura de graca."""
    if not segredo or not cabecalho_assinatura or not data_id:
        return False

    partes = {}
    for pedaco in cabecalho_assinatura.split(","):
        if "=" in pedaco:
            chave, _, valor = pedaco.partition("=")
            partes[chave.strip()] = valor.strip()

    ts, recebido = partes.get("ts"), partes.get("v1")
    if not ts or not recebido:
        return False

    manifest = f"id:{str(data_id).lower()};request-id:{request_id or ''};ts:{ts};"
    esperado = hmac.new(segredo.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    # compare_digest: comparacao em tempo constante, para a validacao nao virar um
    # oraculo que revela o segredo byte a byte pelo tempo de resposta.
    return hmac.compare_digest(esperado, recebido)


# ── Cliente ──────────────────────────────────────────────────────────────────────────

class ClienteMercadoPago(Protocol):
    """Interface que as rotas consomem. Os testes injetam um duble e exercitam webhook,
    idempotencia, estados e tolerancia sem tocar na rede nem em credencial real."""

    async def criar_assinatura(self, corpo: Dict[str, Any]) -> Dict[str, Any]: ...
    async def obter_assinatura(self, assinatura_id: str) -> Dict[str, Any]: ...
    async def cancelar_assinatura(self, assinatura_id: str) -> Dict[str, Any]: ...
    async def obter_pagamento_autorizado(self, pagamento_id: str) -> Dict[str, Any]: ...


class ErroMercadoPago(Exception):
    def __init__(self, status: int, detalhe: str):
        super().__init__(f"Mercado Pago respondeu {status}")
        self.status = status
        self.detalhe = detalhe

    @property
    def transitorio(self) -> bool:
        """5xx e 429 sao temporarios: vale reprocessar. 4xx nao — reprocessar so repete
        o mesmo erro."""
        return self.status >= 500 or self.status == 429


class MercadoPagoHTTP:
    def __init__(self, token: Optional[str] = None):
        self._token = token if token is not None else token_de_acesso()

    @property
    def sandbox(self) -> bool:
        return modo_sandbox(self._token)

    async def _chamar(self, metodo: str, caminho: str,
                      corpo: Optional[Dict[str, Any]] = None,
                      idempotencia: Optional[str] = None) -> Dict[str, Any]:
        cabecalhos = {"Authorization": f"Bearer {self._token}",
                      "Content-Type": "application/json"}
        if idempotencia:
            # O Mercado Pago desduplica pela chave: um retry nosso nao cria uma segunda
            # assinatura para o mesmo atleta.
            cabecalhos["X-Idempotency-Key"] = idempotencia
        async with httpx.AsyncClient(timeout=TIMEOUT) as cliente:
            resposta = await cliente.request(metodo, f"{API}{caminho}",
                                             json=corpo, headers=cabecalhos)
        if resposta.status_code >= 400:
            # Corpo truncado e sem cabecalhos: nunca registrar token nem dado de cartao.
            raise ErroMercadoPago(resposta.status_code, resposta.text[:400])
        return resposta.json() if resposta.content else {}

    async def criar_assinatura(self, corpo: Dict[str, Any]) -> Dict[str, Any]:
        return await self._chamar("POST", "/preapproval", corpo,
                                  idempotencia=corpo.get("external_reference"))

    async def obter_assinatura(self, assinatura_id: str) -> Dict[str, Any]:
        return await self._chamar("GET", f"/preapproval/{assinatura_id}")

    async def cancelar_assinatura(self, assinatura_id: str) -> Dict[str, Any]:
        return await self._chamar("PUT", f"/preapproval/{assinatura_id}",
                                  {"status": "cancelled"})

    async def obter_pagamento_autorizado(self, pagamento_id: str) -> Dict[str, Any]:
        return await self._chamar("GET", f"/authorized_payments/{pagamento_id}")

    async def criar_plano(self, corpo: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um preapproval_plan. Usado apenas pela rotina administrativa de setup —
        nunca por requisicao de usuario."""
        return await self._chamar("POST", "/preapproval_plan", corpo)


def cliente_padrao() -> MercadoPagoHTTP:
    return MercadoPagoHTTP()


# ── Estados ──────────────────────────────────────────────────────────────────────────
# O Mercado Pago fala "authorized"/"paused"/"cancelled" para a assinatura e
# "approved"/"rejected" para o pagamento. Traduzimos para os estados do FORGE em um
# lugar so, para nao espalhar string magica pelas rotas.
MAPA_DE_ESTADO_DA_ASSINATURA = {
    "pending": "pending",
    "authorized": "active",
    "paused": "paused",
    "cancelled": "cancelled",
    "finished": "expired",
}


def estado_do_forge(status_mp: Optional[str]) -> str:
    return MAPA_DE_ESTADO_DA_ASSINATURA.get((status_mp or "").lower(), "pending")

"""Envio de e-mail do FORGE.

O FORGE nao tinha nenhuma infraestrutura de e-mail: o convite administrativo devolve a
URL e o admin a entrega por fora. O cadastro publico precisa mandar um codigo de
verificacao, entao o envio entra aqui — atras de uma interface, com um provedor
"console" como padrao.

O provedor console NAO entrega e-mail: registra o codigo no log do servidor. Serve para
sandbox e desenvolvimento. Por isso o cadastro publico so liga com
PUBLIC_SIGNUP_ENABLED=true, e ligar isso em producao sem um provedor real deixaria o
codigo inalcancavel para o usuario.

Trocar por Resend/SendGrid/SMTP e implementar uma classe com o mesmo `enviar` e
devolve-la em `provedor()`. Nada do Omega Vault foi copiado — a configuracao de e-mail
dele e de outro dominio e de outra conta.
"""
import logging
import os
from typing import Optional, Protocol

import httpx

logger = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com/emails"
TIMEOUT = 10.0
REMETENTE_PADRAO = "FORGE <acesso@mail.aiexec.com.br>"


class Provedor(Protocol):
    async def enviar(self, para: str, assunto: str, texto: str) -> bool: ...

    @property
    def entrega_de_verdade(self) -> bool: ...


class ProvedorConsole:
    """Registra no log em vez de enviar. O codigo aparece no log do servidor de
    proposito: e o unico jeito de exercitar o fluxo sem provedor. Nunca deve ser o
    provedor de producao."""

    @property
    def entrega_de_verdade(self) -> bool:
        return False

    async def enviar(self, para: str, assunto: str, texto: str) -> bool:
        logger.warning("[email:console] para=%s assunto=%r\n%s", para, assunto, texto)
        return True


class ProvedorResend:
    """Envio real pelo Resend.

    A chave e lida do ambiente e NUNCA aparece em log: so o codigo de status e o id da
    mensagem sao registrados. O corpo tambem nao e logado — ele carrega o codigo de
    verificacao.

    Usa httpx, que o projeto ja tem; nao foi preciso adicionar dependencia."""

    def __init__(self, api_key: str, remetente: str):
        self._api_key = api_key
        self._remetente = remetente

    @property
    def entrega_de_verdade(self) -> bool:
        return True

    async def enviar(self, para: str, assunto: str, texto: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as cliente:
                resposta = await cliente.post(
                    RESEND_API,
                    headers={"Authorization": f"Bearer {self._api_key}",
                             "Content-Type": "application/json"},
                    json={"from": self._remetente, "to": [para],
                          "subject": assunto, "text": texto})
        except httpx.HTTPError as e:
            logger.error("[email:resend] falha de rede: %s", type(e).__name__)
            return False

        if resposta.status_code >= 400:
            # Corpo truncado e sem cabecalhos: a chave vai no header de autorizacao.
            logger.error("[email:resend] recusado status=%s detalhe=%s",
                         resposta.status_code, resposta.text[:200])
            return False
        try:
            id_mensagem = resposta.json().get("id")
        except ValueError:
            id_mensagem = None
        logger.info("[email:resend] enviado id=%s", id_mensagem)
        return True


def _do_ambiente() -> Provedor:
    """Resend quando ha chave configurada; console caso contrario.

    A selecao e por presenca de credencial, e nao por mais uma flag para manter em
    sincronia — o mesmo raciocinio do TEST-/APP_USR- do Mercado Pago."""
    chave = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not chave:
        return ProvedorConsole()
    remetente = (os.environ.get("FORGE_EMAIL_FROM") or "").strip() or REMETENTE_PADRAO
    return ProvedorResend(chave, remetente)


_provedor: Optional[Provedor] = None


def definir_provedor(novo: Provedor) -> None:
    """Usado pelos testes e por quem for plugar um provedor real."""
    global _provedor
    _provedor = novo


def provedor() -> Provedor:
    """Resolvido na primeira chamada, nao no import: o processo pode subir antes das
    variaveis existirem, e os testes precisam trocar o provedor sem reimportar."""
    global _provedor
    if _provedor is None:
        _provedor = _do_ambiente()
    return _provedor


def cadastro_publico_ativo() -> bool:
    """Cadastro publico so existe quando explicitamente ligado. Padrao desligado porque
    sem provedor real de e-mail o codigo de verificacao nao chega a lugar nenhum."""
    return (os.environ.get("PUBLIC_SIGNUP_ENABLED") or "").strip().lower() in ("1", "true", "yes")


async def enviar_codigo(email: str, codigo: str) -> bool:
    return await provedor().enviar(
        email,
        "Seu código de verificação do FORGE",
        f"Seu código de verificação é {codigo}.\n"
        f"Ele vale por 15 minutos e só pode ser usado uma vez.\n\n"
        f"Se você não pediu este código, ignore esta mensagem.",
    )

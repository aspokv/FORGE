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
from typing import Protocol

logger = logging.getLogger(__name__)


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


_provedor: Provedor = ProvedorConsole()


def definir_provedor(novo: Provedor) -> None:
    """Usado pelos testes e por quem for plugar um provedor real."""
    global _provedor
    _provedor = novo


def provedor() -> Provedor:
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

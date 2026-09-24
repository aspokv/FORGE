# -*- coding: utf-8 -*-
"""A análise da foto de corpo não pode prender o atleta.

O relato: o atleta envia a foto na aba Evolução e a tela fica em "Lendo a foto…" sem fim.
Esse texto não é a leitura do arquivo — o componente mostra "Enviando X%" até 95% e troca
para "Lendo a foto…" quando o upload TERMINOU e ele está esperando o servidor responder.

Do lado do servidor, o que demora é `analyze_physique`: uma cadeia de modelos de visão,
três tentativas em cada, com espera entre elas — e a chamada do SDK sem prazo nenhum.
Provedor lento vira minutos; provedor pendurado vira para sempre.

O que estes testes prendem
--------------------------
Que existe um teto, e que estourar o teto NÃO perde o envio. A foto já foi guardada no
bucket antes da análise; o que se perde é a leitura automática, e a tela já sabe mostrar
`status: unavailable`. Ficar com a foto no histórico e sem a leitura é infinitamente melhor
que uma tela girando.
"""
import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

import server  # noqa: E402

# Assinatura de JPEG, montada por bytes() para o arquivo nao depender de escapes.
JPEG_DE_TESTE = bytes([0xFF, 0xD8, 0xFF])


@pytest.fixture
def prazo_curto(monkeypatch):
    """Um prazo de teste: o real é 45s, e ninguém espera isso numa suíte."""
    monkeypatch.setattr(server, "PRAZO_DA_ANALISE_VISUAL", 0.35)
    monkeypatch.setattr(server, "ESPERA_ENTRE_TENTATIVAS", (0.01, 0.01))
    monkeypatch.setenv("GEMINI_API_KEY", "chave-de-teste")
    return 0.35


class _ClienteQuePendura:
    """Um provedor que aceita a chamada e nunca responde — o caso que motivou tudo."""

    def __init__(self, atraso=3.0):
        self.chamadas = 0
        self.models = self
        self._atraso = atraso

    def generate_content(self, **kwargs):
        self.chamadas += 1
        time.sleep(self._atraso)
        raise AssertionError("não deveria chegar aqui dentro do prazo")


async def _medir():
    """Mede a CORROTINA, e não o `asyncio.run`.

    `wait_for` desiste da espera, mas a thread do SDK continua viva — não dá para matar
    thread em Python. No fim, `asyncio.run` espera por ela antes de devolver, e medir por
    fora somaria esse encerramento ao tempo do atleta, que já recebeu a resposta.
    """
    comeco = time.monotonic()
    r = await server.analyze_physique(JPEG_DE_TESTE, "image/jpeg", ["front"])
    return r, time.monotonic() - comeco


def _instalar(monkeypatch, cliente):
    monkeypatch.setattr(server, "google_genai",
                        type("G", (), {"Client": lambda **k: cliente,
                                       "types": server.google_genai.types}))


def test_provedor_pendurado_desiste_dentro_do_prazo(prazo_curto, monkeypatch):
    cliente = _ClienteQuePendura(atraso=3.0)
    _instalar(monkeypatch, cliente)
    r, gasto = asyncio.run(_medir())
    # Uma folga generosa: o que se mede é "não são 30 segundos", e não o relógio exato.
    assert gasto < 1.5, "a análise passou de %.2fs com prazo de %.2fs" % (gasto, prazo_curto)
    assert r["status"] == "unavailable"
    assert r["reason"] == "prazo_esgotado"


# O envio não pode virar perda: a foto já está no bucket, e a avaliação é gravada com o
# status que a tela sabe mostrar.
def test_ao_estourar_o_prazo_a_resposta_e_a_que_a_tela_entende(prazo_curto, monkeypatch):
    _instalar(monkeypatch, _ClienteQuePendura(atraso=3.0))
    r = asyncio.run(server.analyze_physique(JPEG_DE_TESTE, "image/jpeg", ["front"]))
    assert r["observations"] == {}
    assert r["suggested_priorities"] == []
    assert "salva" in r["message"].lower(), r["message"]
    assert r["status"] != "completed"


# O prazo é da CADEIA inteira, e não de cada tentativa: contando por tentativa, o total
# cresceria com o número de modelos — que é justamente o que fazia a espera virar minutos.
def test_o_prazo_vale_para_a_cadeia_inteira(prazo_curto, monkeypatch):
    cliente = _ClienteQuePendura(atraso=3.0)
    _instalar(monkeypatch, cliente)
    _, gasto = asyncio.run(_medir())
    modelos = len(server._cadeia_de_modelos_de_visao())
    assert modelos >= 1
    assert gasto < 1.5, ("gastou %.2fs com %d modelos: o prazo está por tentativa, "
                         "e não pela cadeia" % (gasto, modelos))


def test_sem_chave_responde_na_hora_e_nao_espera(monkeypatch):
    """Sem credencial não há o que esperar — e havia quem esperasse assim mesmo."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    comeco = time.monotonic()
    r = asyncio.run(server.analyze_physique(JPEG_DE_TESTE, "image/jpeg", ["front"]))
    assert time.monotonic() - comeco < 1
    assert r["status"] == "unavailable"
    assert r["reason"] == "sem_chave"


def test_o_prazo_e_configuravel_e_tem_padrao_curto():
    """Padrão curto o bastante para caber na paciência de quem está com o celular na mão."""
    assert 10 <= server.PRAZO_DA_ANALISE_VISUAL <= 90

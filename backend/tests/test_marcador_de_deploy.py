# -*- coding: utf-8 -*-
"""Provar de fora que um deploy de BACKEND entrou no ar.

Por que este arquivo existe
---------------------------
Deploy de frontend se confere pelo pacote servido: os nomes trazem hash de conteudo, entao
`main.226b393d.js` virar outro nome e prova de que o build novo esta no ar, e da para
procurar um marcador dentro dele.

Deploy de BACKEND nao deixava marca nenhuma na rede. Toda rota nova exige login, entao de
fora todas respondem 401 tanto antes quanto depois de subir. `version` e uma string escrita
a mao em `server.py` que ninguem lembra de incrementar — ficou em "2.0.1" enquanto o produto
ganhou cardio, observacao de exercicio, Food Card e motor hibrido.

Sem marcador, "o backend subiu" e afirmacao sem prova, e a unica alternativa e acreditar que
o merge basta. Que e exatamente o que nao se pode fazer.

O que este teste defende, e que e facil de errar sem perceber
-------------------------------------------------------------
`started_at` tem de ser a hora em que o PROCESSO subiu, fixada no import. Calcular
`datetime.now()` dentro da rota devolveria um campo com a mesma aparencia, passaria em
qualquer inspecao superficial, e seria INUTIL: mudaria a cada requisicao, e comparar com o
horario do merge nao diria nada. O teste que sustenta isso e o da estabilidade entre duas
requisicoes.

O que este campo NAO e, de proposito
------------------------------------
Nao e o SHA do commit. SHA em rota sem autenticacao e impressao digital da versao exata do
codigo em execucao, entregue a quem pedir. A hora resolve o problema sem dizer isso: o
Coolify troca o container a cada deploy, entao `started_at` posterior ao horario do merge e
o deploy daquele merge.
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# `server` le MONGO_URL e DB_NAME na importacao para construir o cliente do Motor, que nao
# conecta enquanto ninguem consulta — e esta suite nao consulta. `setdefault` para nunca
# sobrescrever o ambiente de quem roda a suite inteira.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

fastapi_testclient = pytest.importorskip("fastapi.testclient")
import server  # noqa: E402


@pytest.fixture(scope="module")
def cliente():
    return fastapi_testclient.TestClient(server.app)


def test_a_raiz_responde_sem_login(cliente):
    """Se exigisse login, nao serviria para conferir deploy de fora."""
    assert cliente.get("/api/").status_code == 200


def test_a_raiz_diz_quando_o_processo_subiu(cliente):
    corpo = cliente.get("/api/").json()
    assert "started_at" in corpo, corpo
    # Tem de ser data-hora com fuso. Sem fuso, comparar com o horario do merge (que vem do
    # GitHub em UTC) obrigaria a adivinhar o fuso do container.
    lido = datetime.fromisoformat(corpo["started_at"])
    assert lido.tzinfo is not None, corpo["started_at"]


def test_a_hora_e_do_processo_e_nao_da_requisicao(cliente):
    """O teste que sustenta o marcador.

    `datetime.now()` dentro da rota devolveria um campo identico na aparencia e inutil na
    pratica: mudaria a cada chamada, e nao haveria nada para comparar com o merge.
    """
    primeira = cliente.get("/api/").json()["started_at"]
    segunda = cliente.get("/api/").json()["started_at"]
    assert primeira == segunda, "started_at muda entre requisicoes: nao e a hora do processo"
    assert primeira == server.SUBIU_EM


def test_a_hora_nao_esta_no_futuro(cliente):
    from datetime import timezone
    lido = datetime.fromisoformat(cliente.get("/api/").json()["started_at"])
    assert lido <= datetime.now(timezone.utc), lido


def test_a_raiz_nao_entrega_nada_sensivel(cliente):
    """Rota publica: o que sai dali sai para qualquer um que peca.

    Um SHA de commit, um caminho de arquivo do servidor ou um nome de variavel de ambiente
    sao coisas que ja apareceram em endpoint de saude por descuido.
    """
    corpo = cliente.get("/api/").json()
    assert set(corpo) == {"message", "version", "started_at"}, corpo
    texto = str(corpo)
    assert not re.search(r"\b[0-9a-f]{7,40}\b", texto), "parece um SHA de commit: " + texto
    for proibido in ("MONGO_URL", "mongodb://", "SECRET", "/home/", "C:\\", "Traceback"):
        assert proibido not in texto, proibido


def test_a_mensagem_e_a_versao_continuam_iguais(cliente):
    """Compatibilidade: algo pode estar lendo esses dois campos. O marcador SOMA, nao troca."""
    corpo = cliente.get("/api/").json()
    assert corpo["message"] == "FORGE API online"
    assert corpo["version"] == "2.0.1"


def test_o_modulo_que_o_docker_sobe_tambem_expoe_o_marcador():
    """Producao roda `runtime_server:app`, nao `server:app`.

    Conferir so `server` provaria que o marcador existe numa aplicacao que ninguem executa —
    foi exatamente esse o erro com as rotas de cardio, que estavam montadas em um e nao no
    outro.
    """
    import runtime_server
    r = fastapi_testclient.TestClient(runtime_server.app).get("/api/")
    assert r.status_code == 200
    assert r.json()["started_at"] == server.SUBIU_EM

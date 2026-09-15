"""O navegador precisa conseguir ENVIAR um PUT — e nao so recebe-lo.

Por que este arquivo existe
---------------------------
A lista `allow_methods` do CORS nao tinha PUT. Toda requisicao PUT de outra origem morria
no preflight: o navegador mandava um OPTIONS, tomava 400, e nunca chegava a enviar o PUT.
No aplicativo isso aparecia como "erro de rede" sem mensagem ao trocar o objetivo.

Em producao o front e a API vivem no MESMO dominio, entao nao ha preflight e o defeito
ficou invisivel desde que a primeira rota PUT foi escrita. Ele so aparece em
desenvolvimento (localhost:3000 -> localhost:8000) e apareceria em qualquer dia em que o
front passasse a ser servido de outro dominio.

Este teste nao precisa de banco: exercita a camada de middleware, que responde ao
preflight antes de qualquer rota.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# `server` le MONGO_URL e DB_NAME na importacao para construir o cliente do Motor. O
# cliente do Motor NAO conecta ao ser construido — a conexao so acontece na primeira
# consulta, e este arquivo nunca faz nenhuma. Os valores abaixo existem so para a
# importacao funcionar sem banco; `setdefault` garante que um ambiente ja configurado
# (o do CI, o da maquina de quem roda a suite inteira) nunca e sobrescrito.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
# O nome precisa parecer banco de TESTE: o conftest da suite recusa rodar contra
# qualquer outro, e essa guarda vale mais do que a conveniencia deste arquivo.
os.environ.setdefault("DB_NAME", "test_database")

fastapi_testclient = pytest.importorskip("fastapi.testclient")
import server  # noqa: E402

# A allowlist de origens e exata e muda com o ambiente (CORS_ORIGINS, FORGE_SITE_URL).
# Fixar "http://localhost:3000" aqui faria o teste falhar por motivo ERRADO — origem
# recusada — escondendo o que ele existe para medir: quais METODOS a allowlist libera.
# Perguntar ao proprio servidor qual origem ele aceita mantem o teste sobre o verbo.
ORIGEM = server._origens_permitidas()[0]

# Rotas com verbo diferente de GET/POST: todas dependem do preflight passar.
VERBOS_QUE_O_APP_USA = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


@pytest.fixture(scope="module")
def cliente():
    return fastapi_testclient.TestClient(server.app)


@pytest.mark.parametrize("verbo", VERBOS_QUE_O_APP_USA)
def test_preflight_libera_o_verbo(cliente, verbo):
    r = cliente.options(
        "/api/nutrition/goal",
        headers={
            "Origin": ORIGEM,
            "Access-Control-Request-Method": verbo,
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    assert r.status_code == 200, f"{verbo} recusado no preflight: {r.text}"
    liberados = r.headers.get("access-control-allow-methods", "")
    assert verbo in liberados, f"{verbo} fora de allow-methods ({liberados})"


def test_put_com_corpo_json_passa_do_preflight(cliente):
    """O caso exato da troca de objetivo: PUT + Content-Type: application/json.

    Corpo JSON obriga o navegador a pedir permissao antes. Era aqui que travava.
    """
    r = cliente.options(
        "/api/nutrition/goal",
        headers={
            "Origin": ORIGEM,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == ORIGEM
    permitidos = r.headers.get("access-control-allow-headers", "").lower()
    assert "content-type" in permitidos and "authorization" in permitidos

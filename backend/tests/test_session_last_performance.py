"""FORGE — a ultima carga de cada exercicio da sessao de hoje.

A tela de Evolucao passou a abrir com os exercicios do treino do dia e o que o atleta
levantou da ultima vez em cada um, para ele saber exatamente o que superar. Estes testes
defendem o que essa leitura promete:

  - "ultima vez" e a sessao MAIS RECENTE em que o exercicio aparece, nunca uma mistura de
    dias (o defeito classico seria pegar a maior carga de todos os tempos e chamar de ultima);
  - dentro dessa sessao a referencia e a serie mais PESADA, a mesma leitura do grafico de
    evolucao, para os dois numeros nao se contradizerem na mesma tela;
  - o atleta so enxerga o proprio historico;
  - exercicio sem registro nenhum simplesmente nao volta, em vez de voltar zerado.

Usa o mesmo harness em processo de test_seguranca: sem servidor vivo, para que a suite rode
no CI como qualquer outra e nao vire teste que nunca executa.
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from test_signup_publico import (  # noqa: E402
    APP, DB, _cliente, asincrono, correio, mp,
)

from auth import create_token  # noqa: E402

__all__ = ["mp", "correio", "APP"]

ROTA = "/api/session-last-performance"


async def _atleta(email):
    uid = str(uuid.uuid4())
    await DB.users.delete_many({"email": email})
    await DB.users.insert_one({
        "id": uid, "email": email, "name": "Ultima Carga", "role": "ATHLETE", "status": "ACTIVE",
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.set_logs.delete_many({"profile_id": uid})
    return uid, {"Authorization": "Bearer " + create_token(uid, "ATHLETE")}


async def _registrar(profile_id, linhas):
    """Grava series cruas, como o produto grava quando a pessoa marca uma serie."""
    docs = [{
        "id": str(uuid.uuid4()), "profile_id": profile_id, "user_id": profile_id,
        "exercise_id": exercise_id, "created_at": f"{dia}T10:00:00",
        "weight": weight, "reps": reps, "set_number": 1, "rir": 2,
    } for exercise_id, dia, weight, reps in linhas]
    if docs:
        await DB.set_logs.insert_many(docs)


async def _buscar(cliente, headers, ids):
    r = await cliente.get(ROTA, params={"ids": ",".join(ids)}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["performances"]


@asincrono
async def test_traz_a_sessao_mais_recente_e_nao_a_carga_de_sempre():
    uid, headers = await _atleta("lastperf-recente@example.com")
    # A carga mais alta esta no passado; a ultima sessao foi mais leve.
    await _registrar(uid, [("supino", "2026-08-01", 100.0, 5), ("supino", "2026-09-10", 80.0, 10)])
    async with await _cliente() as c:
        perf = await _buscar(c, headers, ["supino"])
    assert perf["supino"]["date"] == "2026-09-10"
    assert perf["supino"]["weight"] == 80.0, "pegou a maior de todos os tempos em vez da ultima sessao"


@asincrono
async def test_dentro_da_sessao_a_referencia_e_a_serie_mais_pesada():
    uid, headers = await _atleta("lastperf-pesada@example.com")
    await _registrar(uid, [
        ("supino", "2026-09-10", 60.0, 12),
        ("supino", "2026-09-10", 80.0, 8),
        ("supino", "2026-09-10", 70.0, 10),
    ])
    async with await _cliente() as c:
        perf = await _buscar(c, headers, ["supino"])
    assert perf["supino"]["weight"] == 80.0
    assert perf["supino"]["reps"] == 8, "as repeticoes tem de ser as da serie mais pesada"
    assert perf["supino"]["sets"] == 3


@asincrono
async def test_empate_de_carga_fica_com_mais_repeticoes():
    uid, headers = await _atleta("lastperf-empate@example.com")
    await _registrar(uid, [("supino", "2026-09-10", 80.0, 6), ("supino", "2026-09-10", 80.0, 11)])
    async with await _cliente() as c:
        perf = await _buscar(c, headers, ["supino"])
    assert perf["supino"]["reps"] == 11


@asincrono
async def test_cada_exercicio_tem_a_propria_ultima_sessao():
    uid, headers = await _atleta("lastperf-varios@example.com")
    await _registrar(uid, [("supino", "2026-09-10", 80.0, 8), ("remada", "2026-09-03", 70.0, 10)])
    async with await _cliente() as c:
        perf = await _buscar(c, headers, ["supino", "remada"])
    assert perf["supino"]["date"] == "2026-09-10"
    assert perf["remada"]["date"] == "2026-09-03"


@asincrono
async def test_exercicio_sem_registro_nao_volta_zerado():
    uid, headers = await _atleta("lastperf-vazio@example.com")
    await _registrar(uid, [("supino", "2026-09-10", 80.0, 8)])
    async with await _cliente() as c:
        perf = await _buscar(c, headers, ["supino", "nunca-feito"])
    assert "supino" in perf
    assert "nunca-feito" not in perf, "exercicio sem historico nao pode virar 0 kg na tela"


@asincrono
async def test_lista_vazia_responde_vazio_sem_erro():
    _, headers = await _atleta("lastperf-semids@example.com")
    async with await _cliente() as c:
        r = await c.get(ROTA, params={"ids": ""}, headers=headers)
    assert r.status_code == 200
    assert r.json()["performances"] == {}


@asincrono
async def test_um_atleta_nao_le_o_historico_do_outro():
    dono, headers_dono = await _atleta("lastperf-dono@example.com")
    _, headers_intruso = await _atleta("lastperf-intruso@example.com")
    await _registrar(dono, [("supino", "2026-09-10", 140.0, 3)])
    async with await _cliente() as c:
        assert (await _buscar(c, headers_dono, ["supino"]))["supino"]["weight"] == 140.0
        assert await _buscar(c, headers_intruso, ["supino"]) == {}, "vazou historico entre atletas"


@asincrono
async def test_nao_e_possivel_ler_o_historico_de_outro_perfil_pelo_parametro():
    """profile_id na query nao pode virar chave para o historico alheio (IDOR)."""
    dono, _ = await _atleta("lastperf-alvo@example.com")
    _, headers_intruso = await _atleta("lastperf-ladrao@example.com")
    await _registrar(dono, [("supino", "2026-09-10", 140.0, 3)])
    async with await _cliente() as c:
        r = await c.get(ROTA, params={"ids": "supino", "profile_id": dono}, headers=headers_intruso)
    assert r.status_code in (200, 403, 404)
    if r.status_code == 200:
        assert r.json()["performances"] == {}, "IDOR: leu o historico de outro atleta"


@asincrono
async def test_exige_autenticacao():
    async with await _cliente() as c:
        r = await c.get(ROTA, params={"ids": "supino"})
    assert r.status_code in (401, 403), f"rota aberta sem token: {r.status_code}"

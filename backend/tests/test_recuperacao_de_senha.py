"""Recuperacao de senha: anti-enumeracao, token, limites e revogacao de sessao.

O que estes testes protegem: o fluxo nao pode virar um oraculo de quem tem conta, o link
nao pode valer duas vezes nem sobreviver ao prazo, e trocar a senha tem que expulsar quem
ja estava dentro.
"""
import asyncio
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from test_signup_publico import DB, _cliente, asincrono, correio  # noqa: E402

import password_reset_routes as pr  # noqa: E402
from auth import create_token, hash_password, senha_fraca, sessao_revogada  # noqa: E402

__all__ = ["correio"]

SENHA_ANTIGA = "SenhaAntiga#2026"
SENHA_NOVA = "SenhaNova#2026"


async def _conta(email="reset@example.com", status="ACTIVE"):
    uid = str(uuid.uuid4())
    await DB.users.delete_many({"email": email})
    await DB.password_resets.delete_many({"user_id": {"$exists": True}})
    await DB.users.insert_one({
        "id": uid, "email": email, "name": "Reset", "role": "ATHLETE", "status": status,
        "password_hash": hash_password(SENHA_ANTIGA),
        "created_at": datetime.now(timezone.utc).isoformat()})
    return uid


async def _limpar(uid, email):
    await DB.users.delete_many({"id": uid})
    await DB.password_resets.delete_many({"user_id": uid})
    await DB.rate_limits.delete_many({"key": {"$regex": "^(forgot|reset)"}})


def _link(correio):
    """Extrai o token do e-mail — e so daqui, porque ele nao aparece em resposta nenhuma."""
    for m in reversed(correio.enviados):
        achado = re.search(r"/recuperar/([A-Za-z0-9_\-]+)", m["body"])
        if achado:
            return achado.group(1)
    return None


async def _pedir(c, email):
    return await c.post("/api/auth/forgot-password", json={"email": email})


# ── Anti-enumeracao ──────────────────────────────────────────────────────────────────

@asincrono
async def test_a_resposta_e_identica_para_conta_existente_e_inexistente(correio):
    uid = await _conta("reset.existe@example.com")
    async with await _cliente() as c:
        existe = await _pedir(c, "reset.existe@example.com")
        nao_existe = await _pedir(c, "reset.naoexiste@example.com")
    assert existe.status_code == nao_existe.status_code == 200
    assert existe.json() == nao_existe.json()
    await _limpar(uid, "reset.existe@example.com")


@asincrono
async def test_conta_inexistente_nao_dispara_e_mail(correio):
    async with await _cliente() as c:
        await _pedir(c, "ninguem.aqui@example.com")
    assert correio.enviados == []
    await DB.rate_limits.delete_many({"key": {"$regex": "^forgot"}})


@asincrono
async def test_o_limite_por_conta_tambem_devolve_a_resposta_neutra(correio):
    """Um 429 que so aparece para e-mail existente diria o que se quer esconder."""
    email = "reset.limite@example.com"
    uid = await _conta(email)
    async with await _cliente() as c:
        respostas = [await _pedir(c, email)
                     for _ in range(pr.MAX_POR_CONTA_POR_HORA + 2)]
    assert all(r.status_code == 200 for r in respostas), [r.status_code for r in respostas]
    assert len({r.text for r in respostas}) == 1, "as respostas divergiram"
    # e o envio parou no teto
    assert len(correio.enviados) == pr.MAX_POR_CONTA_POR_HORA
    await _limpar(uid, email)


@asincrono
async def test_conta_suspensa_nao_recebe_link(correio):
    email = "reset.suspensa@example.com"
    uid = await _conta(email, status="SUSPENDED")
    async with await _cliente() as c:
        r = await _pedir(c, email)
    assert r.status_code == 200
    assert correio.enviados == []
    await _limpar(uid, email)


# ── O token ──────────────────────────────────────────────────────────────────────────

@asincrono
async def test_o_token_e_guardado_com_hash_e_nunca_volta_na_resposta(correio):
    email = "reset.hash@example.com"
    uid = await _conta(email)
    async with await _cliente() as c:
        r = await _pedir(c, email)
    token = _link(correio)
    assert token and len(token) >= 32
    assert token not in r.text, "o token vazou na resposta"
    guardado = await DB.password_resets.find_one({"user_id": uid})
    assert guardado["token_hash"] != token
    assert token not in str(guardado), "o token esta em claro no banco"
    await _limpar(uid, email)


@asincrono
async def test_o_link_troca_a_senha_uma_unica_vez(correio):
    email = "reset.unico@example.com"
    uid = await _conta(email)
    async with await _cliente() as c:
        await _pedir(c, email)
        token = _link(correio)
        primeira = await c.post("/api/auth/reset-password",
                                json={"token": token, "password": SENHA_NOVA})
        segunda = await c.post("/api/auth/reset-password",
                               json={"token": token, "password": "OutraSenha#2026"})
    assert primeira.status_code == 200
    assert segunda.status_code == 410
    assert segunda.json()["detail"]["reason"] == "reset_token_invalid"
    await _limpar(uid, email)


@asincrono
async def test_token_expirado_e_recusado(correio):
    email = "reset.expirado@example.com"
    uid = await _conta(email)
    async with await _cliente() as c:
        await _pedir(c, email)
        token = _link(correio)
        await DB.password_resets.update_one(
            {"user_id": uid},
            {"$set": {"expires_at": (datetime.now(timezone.utc)
                                     - timedelta(minutes=1)).isoformat()}})
        r = await c.post("/api/auth/reset-password",
                         json={"token": token, "password": SENHA_NOVA})
    assert r.status_code == 410
    await _limpar(uid, email)


@asincrono
async def test_token_inventado_e_recusado(correio):
    async with await _cliente() as c:
        r = await c.post("/api/auth/reset-password",
                         json={"token": "x" * 43, "password": SENHA_NOVA})
    assert r.status_code == 410
    await DB.rate_limits.delete_many({"key": {"$regex": "^reset"}})


@asincrono
async def test_pedido_novo_invalida_o_link_anterior(correio):
    email = "reset.substitui@example.com"
    uid = await _conta(email)
    async with await _cliente() as c:
        await _pedir(c, email)
        antigo = _link(correio)
        await _pedir(c, email)
        novo = _link(correio)
        assert antigo != novo
        r_antigo = await c.post("/api/auth/reset-password",
                                json={"token": antigo, "password": SENHA_NOVA})
        r_novo = await c.post("/api/auth/reset-password",
                              json={"token": novo, "password": SENHA_NOVA})
    assert r_antigo.status_code == 410, "o link antigo continuou valendo"
    assert r_novo.status_code == 200
    await _limpar(uid, email)


@asincrono
async def test_conferir_token_responde_antes_de_mostrar_o_formulario(correio):
    email = "reset.conferir@example.com"
    uid = await _conta(email)
    async with await _cliente() as c:
        await _pedir(c, email)
        token = _link(correio)
        bom = await c.get(f"/api/auth/reset-password/{token}")
        ruim = await c.get("/api/auth/reset-password/" + "z" * 43)
    assert bom.status_code == 200 and bom.json()["valid"] is True
    assert ruim.status_code == 410
    await _limpar(uid, email)


@asincrono
async def test_excesso_de_tentativas_queima_o_link(correio):
    """Senao o link viraria alvo com tentativas ilimitadas."""
    email = "reset.tentativas@example.com"
    uid = await _conta(email)
    async with await _cliente() as c:
        await _pedir(c, email)
        token = _link(correio)
        for _ in range(pr.MAX_TENTATIVAS_DE_USO):
            await c.post("/api/auth/reset-password", json={"token": token, "password": "123"})
        r = await c.post("/api/auth/reset-password",
                         json={"token": token, "password": SENHA_NOVA})
    assert r.status_code == 410, "o link sobreviveu ao limite de tentativas"
    await _limpar(uid, email)


# ── Politica de senha ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("senha,motivo", [
    ("curta1", "menos de 8"),
    ("semnumeros", "sem numero"),
    ("12345678", "sem letra"),
    ("aaaaaaaa", "tudo igual"),
])
def test_senha_fraca_e_descrita_em_vez_de_apenas_recusada(senha, motivo):
    problema = senha_fraca(senha, "alguem@example.com")
    assert problema, motivo
    assert problema.endswith("."), "a mensagem deve ser uma frase util"


def test_senha_nao_pode_conter_o_proprio_email():
    assert senha_fraca("anasouza123", "anasouza@example.com")
    assert senha_fraca("Treino2026", "anasouza@example.com") is None


@asincrono
async def test_senha_fraca_e_recusada_pelo_servidor(correio):
    email = "reset.fraca@example.com"
    uid = await _conta(email)
    async with await _cliente() as c:
        await _pedir(c, email)
        token = _link(correio)
        r = await c.post("/api/auth/reset-password", json={"token": token, "password": "12345678"})
    assert r.status_code == 400
    assert r.json()["detail"]["reason"] == "weak_password"
    await _limpar(uid, email)


# ── Efeitos da troca ─────────────────────────────────────────────────────────────────

@asincrono
async def test_a_senha_nova_funciona_e_a_antiga_nao(correio):
    email = "reset.troca@example.com"
    uid = await _conta(email)
    async with await _cliente() as c:
        await _pedir(c, email)
        await c.post("/api/auth/reset-password",
                     json={"token": _link(correio), "password": SENHA_NOVA})
        nova = await c.post("/api/auth/login", json={"email": email, "password": SENHA_NOVA})
        antiga = await c.post("/api/auth/login", json={"email": email, "password": SENHA_ANTIGA})
    assert nova.status_code == 200
    assert antiga.status_code == 401
    await _limpar(uid, email)


@asincrono
async def test_trocar_a_senha_derruba_as_sessoes_anteriores(correio):
    """Conta invadida so volta a ser da pessoa quando o acesso de quem invadiu acaba."""
    email = "reset.sessao@example.com"
    uid = await _conta(email)
    antes = {"Authorization": "Bearer " + create_token(uid, "ATHLETE")}
    async with await _cliente() as c:
        assert (await c.get("/api/auth/me", headers=antes)).status_code == 200
        await _pedir(c, email)
        # espera 1s para o carimbo da troca ficar depois do iat do token antigo
        await asyncio.sleep(1.2)
        r = await c.post("/api/auth/reset-password",
                         json={"token": _link(correio), "password": SENHA_NOVA})
        assert r.status_code == 200
        assert r.json()["sessions_revoked"] is True
        depois = await c.get("/api/auth/me", headers=antes)
        # e a sessao nova, criada pelo login seguinte, funciona
        entrada = await c.post("/api/auth/login", json={"email": email, "password": SENHA_NOVA})
        nova = {"Authorization": "Bearer " + entrada.json()["token"]}
        ainda_vale = await c.get("/api/auth/me", headers=nova)
    assert depois.status_code == 401, "a sessao antiga continuou valendo"
    assert ainda_vale.status_code == 200, "a sessao nova foi derrubada junto"
    await _limpar(uid, email)


def test_quem_nunca_trocou_a_senha_nao_e_afetado():
    assert sessao_revogada({"id": "x"}, {"iat": 1}) is False
    assert sessao_revogada({}, {}) is False


def test_token_sem_iat_cai_apos_uma_troca():
    """Token anterior a existencia do campo: depois de uma troca, o certo e fechar tudo."""
    trocada = datetime.now(timezone.utc).isoformat()
    assert sessao_revogada({"password_changed_at": trocada}, {}) is True


def test_carimbo_ilegivel_nao_tranca_ninguem_fora():
    assert sessao_revogada({"password_changed_at": "nao e data"}, {"iat": 1}) is False


@asincrono
async def test_a_troca_libera_o_bloqueio_de_login_da_conta(correio):
    """Quem acabou de provar o controle do e-mail nao deve seguir travado."""
    email = "reset.bloqueio@example.com"
    uid = await _conta(email)
    async with await _cliente() as c:
        for _ in range(7):
            await c.post("/api/auth/login", json={"email": email, "password": "errada"})
        travado = await c.post("/api/auth/login", json={"email": email, "password": SENHA_ANTIGA})
        assert travado.status_code == 429, "o bloqueio de login nem chegou a acontecer"
        await _pedir(c, email)
        await c.post("/api/auth/reset-password",
                     json={"token": _link(correio), "password": SENHA_NOVA})
        depois = await c.post("/api/auth/login", json={"email": email, "password": SENHA_NOVA})
    assert depois.status_code == 200
    await _limpar(uid, email)


# ── Limite de taxa ───────────────────────────────────────────────────────────────────

@asincrono
async def test_o_pedido_tem_limite_por_ip(correio):
    await DB.rate_limits.delete_many({"key": {"$regex": "^forgot"}})
    estourou = None
    async with await _cliente() as c:
        for i in range(pr.MAX_POR_IP_POR_HORA + 3):
            r = await _pedir(c, f"anonimo{i}@example.com")
            if r.status_code == 429:
                estourou = r
                break
    assert estourou is not None, "o pedido aceitou chamadas sem limite por IP"
    await DB.rate_limits.delete_many({"key": {"$regex": "^forgot"}})


@asincrono
async def test_a_troca_tem_limite_por_ip(correio):
    await DB.rate_limits.delete_many({"key": {"$regex": "^reset"}})
    estourou = None
    async with await _cliente() as c:
        for _ in range(pr.MAX_POR_IP_POR_HORA + 3):
            r = await c.post("/api/auth/reset-password",
                             json={"token": "y" * 43, "password": SENHA_NOVA})
            if r.status_code == 429:
                estourou = r
                break
    assert estourou is not None, "a troca aceitou chamadas sem limite por IP"
    await DB.rate_limits.delete_many({"key": {"$regex": "^reset"}})


# ── Segredos fora do log ─────────────────────────────────────────────────────────────

@asincrono
async def test_nem_token_nem_senha_entram_em_log(correio, caplog):
    import logging
    email = "reset.log@example.com"
    uid = await _conta(email)
    with caplog.at_level(logging.DEBUG):
        async with await _cliente() as c:
            await _pedir(c, email)
            token = _link(correio)
            await c.post("/api/auth/reset-password",
                         json={"token": token, "password": SENHA_NOVA})
    registrado = "\n".join(r.getMessage() for r in caplog.records)
    assert token not in registrado, "o token apareceu no log"
    assert SENHA_NOVA not in registrado, "a senha apareceu no log"
    await _limpar(uid, email)

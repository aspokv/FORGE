"""Pre-avaliacao ponta a ponta: persistencia, bloqueio, retomada e diferenca entre planos.

Reaproveita o harness do funil publico (mesmo app em processo, mesmos dubles, mesmo event
loop). Importar os ajudantes de la em vez de copia-los mantem uma fonte so: se o funil
mudar, estes testes mudam junto em vez de testar um fluxo que nao existe mais.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from test_signup_publico import (  # noqa: E402
    DB, SENHA, _ate_a_senha, _cliente, _limpar, _pagar, asincrono, correio, mp,
)

# Marca os ajudantes importados como usados: sao fixtures do pytest, e sem isto um
# formatador poderia remover o import por parecer morto.
__all__ = ["mp", "correio"]

RESPOSTAS = {
    "sex": "female",
    "experience": "Intermediário",
    "goal": "Hipertrofia",
    "days": 4,
    "priorities": ["Glúteos", "Posteriores"],
    "body_goal": "fat_loss",
    "goal_intensity": "moderado",
}


def _cabecalho(jwt):
    return {"Authorization": "Bearer " + jwt}


# ── Alcance antes do pagamento ───────────────────────────────────────────────────────

@asincrono
async def test_a_pre_avaliacao_exige_login():
    async with await _cliente() as c:
        r = await c.get("/api/preassessment")
    assert r.status_code in (401, 403)


@asincrono
async def test_conta_pendente_alcanca_a_pre_avaliacao(mp, correio):
    """E das poucas rotas liberadas antes do pagamento — sem ela nao ha o que responder."""
    email = "previa.acesso@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email, plano="pro")
        h = _cabecalho(jwt)
        r = await c.get("/api/preassessment", headers=h)
        assert r.status_code == 200, r.text
        assert (await c.get("/api/bootstrap", headers=h)).status_code == 403
    d = r.json()
    assert d["plan_code"] == "pro"
    assert d["awaiting_payment"] is True
    assert d["answers"] is None
    assert d["preview"] is None
    assert d["catalog"]["includes_nutrition"] is True
    await _limpar(email)


# ── Persistencia ─────────────────────────────────────────────────────────────────────

@asincrono
async def test_as_respostas_persistem_e_devolvem_a_previa(mp, correio):
    email = "previa.persiste@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email, plano="pro")
        h = _cabecalho(jwt)
        r = await c.post("/api/preassessment", json=RESPOSTAS, headers=h)
        assert r.status_code == 200, r.text
        previa = r.json()["preview"]
        assert previa["training"]["days"] == 4
        assert previa["cta"] == "Ativar meu plano e liberar o FORGE"
        de_volta = await c.get("/api/preassessment", headers=h)

    salvo = de_volta.json()
    assert salvo["answers"]["priorities"] == ["Glúteos", "Posteriores"]
    assert salvo["answers"]["goal_intensity"] == "moderado"
    assert salvo["preview"] == previa
    u = await DB.users.find_one({"email": email})
    assert u["pre_assessment"]["days"] == 4
    await _limpar(email)


@asincrono
async def test_responder_de_novo_substitui_a_resposta_anterior(mp, correio):
    email = "previa.reenvio@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email, plano="pro")
        h = _cabecalho(jwt)
        await c.post("/api/preassessment", json=RESPOSTAS, headers=h)
        r = await c.post("/api/preassessment",
                         json={**RESPOSTAS, "days": 6, "priorities": []}, headers=h)
    assert r.json()["answers"]["days"] == 6
    assert r.json()["answers"]["priorities"] == []
    assert r.json()["preview"]["focus"]["declared"] is False
    u = await DB.users.find_one({"email": email})
    assert u["pre_assessment"]["days"] == 6
    await _limpar(email)


# ── Bloqueio antes do pagamento ──────────────────────────────────────────────────────

@asincrono
async def test_a_previa_nao_entrega_treino_nem_dieta_antes_de_pagar(mp, correio):
    email = "previa.bloqueada@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email, plano="elite")
        h = _cabecalho(jwt)
        r = await c.post("/api/preassessment", json=RESPOSTAS, headers=h)
    previa = r.json()["preview"]
    assert previa["locked"] is True
    assert all(s["locked"] for s in previa["training"]["sessions"])
    bruto = r.text.lower()
    for proibido in ("supino", "agachamento", "remada", "rosca direta", "kcal"):
        assert proibido not in bruto, proibido
    await _limpar(email)


@asincrono
async def test_responder_a_pre_avaliacao_nao_abre_o_aplicativo(mp, correio):
    email = "previa.sem.acesso@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email, plano="elite")
        h = _cabecalho(jwt)
        await c.post("/api/preassessment", json=RESPOSTAS, headers=h)
        for caminho in ("/api/bootstrap", "/api/nutrition/plan", "/api/weekly-report"):
            assert (await c.get(caminho, headers=h)).status_code == 403, caminho
    u = await DB.users.find_one({"email": email})
    assert u["status"] == "PENDING_PAYMENT"
    assert u["plan"] is None
    await _limpar(email)


# ── Diferencas entre planos ──────────────────────────────────────────────────────────

@asincrono
async def test_o_essencial_nao_recebe_nem_pergunta_nem_promessa_de_alimentacao(mp, correio):
    email = "previa.essencial@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email, plano="essential")
        h = _cabecalho(jwt)
        cat = await c.get("/api/preassessment", headers=h)
        r = await c.post("/api/preassessment", json=RESPOSTAS, headers=h)
    assert cat.json()["catalog"]["includes_nutrition"] is False
    assert cat.json()["catalog"]["body_goals"] == []
    n = r.json()["preview"]["nutrition"]
    assert n["included"] is False
    assert "protocol" not in n
    assert "body_goal" not in r.json()["answers"]
    await _limpar(email)


@asincrono
async def test_o_ritmo_agressivo_e_recusado_fora_do_elite(mp, correio):
    email = "previa.agressivo@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email, plano="pro")
        h = _cabecalho(jwt)
        r = await c.post("/api/preassessment",
                         json={**RESPOSTAS, "goal_intensity": "agressivo"}, headers=h)
    assert r.status_code == 400
    assert r.json()["detail"]["field"] == "goal_intensity"
    await _limpar(email)


@asincrono
async def test_planos_diferentes_produzem_previas_diferentes(mp, correio):
    previas = {}
    for code in ("essential", "pro", "elite"):
        email = "previa.plano." + code + "@example.com"
        async with await _cliente() as c:
            _, jwt = await _ate_a_senha(c, correio, email, plano=code)
            corpo = dict(RESPOSTAS)
            if code == "elite":
                corpo["goal_intensity"] = "agressivo"
            r = await c.post("/api/preassessment", json=corpo, headers=_cabecalho(jwt))
            assert r.status_code == 200, code + ": " + r.text[:200]
            previas[code] = r.json()["preview"]
        await _limpar(email)

    assert previas["essential"]["nutrition"]["included"] is False
    assert previas["pro"]["nutrition"]["included"] is True
    assert previas["elite"]["nutrition"]["protocol"]["intensity"] == "agressivo"
    # O treino nao muda com o plano: o que muda e o que o acompanha.
    assert previas["essential"]["training"] == previas["pro"]["training"]


# ── Validacao e limite de taxa ───────────────────────────────────────────────────────

@asincrono
async def test_resposta_invalida_diz_qual_campo_corrigir(mp, correio):
    email = "previa.invalida@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email)
        r = await c.post("/api/preassessment", json={**RESPOSTAS, "days": 9},
                         headers=_cabecalho(jwt))
    assert r.status_code == 400
    assert r.json()["detail"]["field"] == "days"
    assert r.json()["detail"]["reason"] == "invalid_answer"
    await _limpar(email)


@asincrono
async def test_a_gravacao_tem_limite_de_taxa(mp, correio):
    import preassessment_routes as pr
    email = "previa.limite@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email, plano="pro")
        h = _cabecalho(jwt)
        u = await DB.users.find_one({"email": email})
        chave = "preassessment:" + u["id"]
        await DB.rate_limits.delete_many({"key": chave})
        estourou = None
        for _ in range(pr.MAX_GRAVACOES_POR_JANELA + 1):
            r = await c.post("/api/preassessment", json=RESPOSTAS, headers=h)
            if r.status_code == 429:
                estourou = r
                break
    assert estourou is not None, "o limite de taxa nunca disparou"
    assert estourou.json()["detail"]["reason"] == "rate_limited"
    await DB.rate_limits.delete_many({"key": chave})
    await _limpar(email)


# ── Retomada e continuidade ──────────────────────────────────────────────────────────

@asincrono
async def test_retomar_o_cadastro_traz_as_respostas_de_volta(mp, correio):
    """Fechar o navegador no meio do checkout nao pode custar as respostas."""
    email = "previa.retomada@example.com"
    async with await _cliente() as c:
        _, jwt = await _ate_a_senha(c, correio, email, plano="pro")
        await c.post("/api/preassessment", json=RESPOSTAS, headers=_cabecalho(jwt))

        entrada = await c.post("/api/auth/login", json={"email": email, "password": SENHA})
        assert entrada.status_code == 200
        h2 = _cabecalho(entrada.json()["token"])
        r = await c.get("/api/preassessment", headers=h2)
        assert r.json()["answers"]["days"] == 4
        assert r.json()["preview"] is not None
        assert (await c.get("/api/bootstrap", headers=h2)).status_code == 403
    u = await DB.users.find_one({"email": email})
    assert u["status"] == "PENDING_PAYMENT"
    await _limpar(email)


@asincrono
async def test_apos_o_pagamento_o_perfil_ja_vem_com_as_respostas(mp, correio):
    """O questionario completo nao pode perguntar de novo o que acabou de ser respondido."""
    email = "previa.aplicada@example.com"
    async with await _cliente() as c:
        signup, jwt = await _ate_a_senha(c, correio, email, plano="pro")
        await c.post("/api/preassessment", json=RESPOSTAS, headers=_cabecalho(jwt))
        _sid, resp = await _pagar(c, mp, signup)
        assert resp.json()["resultado"] == "aplicado"

    u = await DB.users.find_one({"email": email})
    assert u["status"] == "ACTIVE"
    perfil = await DB.profiles.find_one({"user_id": u["id"]})
    assert perfil["sex"] == "female"
    assert perfil["experience"] == "Intermediário"
    assert perfil["days"] == 4
    assert perfil["goal"] == "Hipertrofia"
    assert perfil["priorities"] == ["Glúteos", "Posteriores"]
    assert perfil["nutrition_assessment"]["goal"] == "fat_loss"
    assert perfil["nutrition_assessment"]["intensity"] == "moderado"
    # Idade, altura e peso ainda faltam, entao o questionario completo segue necessario.
    assert perfil["onboarding_required"] is True
    await _limpar(email)


@asincrono
async def test_a_semeadura_nao_sobrescreve_resposta_ja_existente(mp, correio):
    email = "previa.nao.sobrescreve@example.com"
    async with await _cliente() as c:
        signup, jwt = await _ate_a_senha(c, correio, email, plano="pro")
        await c.post("/api/preassessment", json=RESPOSTAS, headers=_cabecalho(jwt))
        u = await DB.users.find_one({"email": email})
        await DB.profiles.update_one({"id": u["id"]},
                                     {"$set": {"days": 6, "experience": "Avançado"}})
        await _pagar(c, mp, signup)
    perfil = await DB.profiles.find_one({"user_id": u["id"]})
    assert perfil["days"] == 6
    assert perfil["experience"] == "Avançado"
    assert perfil["sex"] == "female", "o que faltava continua sendo preenchido"
    await _limpar(email)


@asincrono
async def test_pagar_sem_ter_respondido_a_pre_avaliacao_nao_quebra(mp, correio):
    email = "previa.pulada@example.com"
    async with await _cliente() as c:
        signup, _ = await _ate_a_senha(c, correio, email)
        _sid, resp = await _pagar(c, mp, signup)
    assert resp.json()["resultado"] == "aplicado"
    u = await DB.users.find_one({"email": email})
    assert u["status"] == "ACTIVE"
    await _limpar(email)

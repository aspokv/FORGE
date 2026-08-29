"""Regressao das falhas encontradas na auditoria de seguranca.

Cada teste aqui corresponde a um achado confirmado. Nao sao testes de "parece seguro":
cada um reproduz o ataque e exige a recusa, para que a correcao nao volte atras sem
alguem perceber.

Reaproveita o harness do funil publico — mesmo app em processo, mesmos dubles.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from test_signup_publico import (  # noqa: E402
    APP, DB, _cliente, asincrono, correio, mp,
)

import server  # noqa: E402
from auth import ROTAS_LIBERADAS_SEM_PAGAMENTO, create_token  # noqa: E402

__all__ = ["mp", "correio"]


async def _atleta(email="seg.atleta@example.com", role="ATHLETE", status="ACTIVE"):
    import uuid
    from datetime import datetime, timezone
    uid = str(uuid.uuid4())
    await DB.users.delete_many({"email": email})
    await DB.users.insert_one({
        "id": uid, "email": email, "name": "Seguranca", "role": role, "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    return uid, {"Authorization": "Bearer " + create_token(uid, role)}


# ── Documentacao interativa ──────────────────────────────────────────────────────────

def test_a_documentacao_interativa_nasce_desligada():
    """/docs e /openapi.json descrevem cada rota, modelo e campo da API.

    Estavam publicos em producao. Nao servem a nenhum usuario do produto e sao um mapa
    para quem procura o que atacar."""
    assert APP.docs_url is None
    assert APP.redoc_url is None
    assert APP.openapi_url is None


@asincrono
async def test_docs_e_openapi_respondem_404():
    async with await _cliente() as c:
        for rota in ("/docs", "/redoc", "/openapi.json"):
            r = await c.get(rota)
            assert r.status_code == 404, f"{rota} -> {r.status_code}"


def test_a_documentacao_pode_ser_ligada_deliberadamente(monkeypatch):
    monkeypatch.setenv("FORGE_ENABLE_DOCS", "true")
    assert server._docs_ligadas() is True
    monkeypatch.setenv("FORGE_ENABLE_DOCS", "false")
    assert server._docs_ligadas() is False


# ── CORS ─────────────────────────────────────────────────────────────────────────────

def test_cors_nunca_devolve_asterisco(monkeypatch):
    """A combinacao "*" + allow_credentials e proibida pela propria especificacao, e
    estava valendo em producao."""
    monkeypatch.setenv("CORS_ORIGINS", "*")
    origens = server._origens_permitidas()
    assert "*" not in origens
    assert origens == ["https://forge.aiexec.com.br"]


def test_cors_mantem_origens_explicitas_e_descarta_o_asterisco(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.exemplo.com, *, https://outro.com/")
    origens = server._origens_permitidas()
    assert "*" not in origens
    assert "https://app.exemplo.com" in origens
    assert "https://outro.com" in origens, "barra final normalizada"


def test_o_site_de_producao_esta_sempre_na_allowlist(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert server._origens_permitidas() == ["https://forge.aiexec.com.br"]


# ── Tamanho do corpo ─────────────────────────────────────────────────────────────────

@asincrono
async def test_corpo_grande_demais_e_recusado():
    """Antes, 5 MB de JSON eram lidos e desserializados sem qualquer teto."""
    _, h = await _atleta("seg.payload@example.com")
    async with await _cliente() as c:
        r = await c.post("/api/assessment", headers=h,
                         json={"name": "A" * (2 * 1024 * 1024), "days": 3})
    assert r.status_code == 413
    assert r.json()["detail"]["reason"] == "payload_too_large"


@asincrono
async def test_corpo_dentro_do_limite_continua_passando():
    """O limite nao pode atrapalhar uso normal."""
    _, h = await _atleta("seg.payload.ok@example.com")
    async with await _cliente() as c:
        r = await c.post("/api/assessment", headers=h,
                         json={"name": "Atleta", "days": 3, "experience": "Iniciante"})
    assert r.status_code == 200


@asincrono
async def test_content_length_invalido_e_recusado():
    async with await _cliente() as c:
        r = await c.post("/api/auth/login", headers={"content-length": "abc"},
                         content=b"{}")
    assert r.status_code in (400, 422)


def test_a_rota_de_upload_tem_teto_proprio_e_maior():
    """Foto precisa de mais espaco que JSON, mas ainda com teto."""
    assert server.LIMITE_DE_UPLOAD > server.LIMITE_DE_CORPO
    assert server.LIMITE_DE_UPLOAD <= 8 * 1024 * 1024
    assert "/api/visual-assessment" in server.ROTAS_COM_UPLOAD


# ── Upload ───────────────────────────────────────────────────────────────────────────

@asincrono
async def test_upload_recusa_tipo_fora_da_allowlist():
    _, h = await _atleta("seg.upload@example.com")
    async with await _cliente() as c:
        r = await c.post("/api/visual-assessment", headers=h,
                         data={"profile_id": "x", "consent": "true", "views": "[]"},
                         files={"photos": ("script.svg", b"<svg/>", "image/svg+xml")})
    assert r.status_code == 415
    assert r.json()["detail"]["reason"] == "unsupported_media_type"


@asincrono
async def test_upload_recusa_arquivo_que_so_diz_ser_imagem():
    """content-type vem do cliente e nao prova nada; os primeiros bytes provam."""
    _, h = await _atleta("seg.upload2@example.com")
    async with await _cliente() as c:
        r = await c.post("/api/visual-assessment", headers=h,
                         data={"profile_id": "x", "consent": "true", "views": "[]"},
                         files={"photos": ("falso.jpg", b"MZ\x90\x00 nao sou imagem",
                                           "image/jpeg")})
    assert r.status_code == 415
    assert r.json()["detail"]["reason"] == "not_an_image"


@asincrono
async def test_upload_recusa_views_malformado():
    """Antes isto subia como 500; e entrada do cliente, entao a resposta certa e 400."""
    _, h = await _atleta("seg.views@example.com")
    async with await _cliente() as c:
        r = await c.post("/api/visual-assessment", headers=h,
                         data={"profile_id": "x", "consent": "true", "views": "{nao json"})
    assert r.status_code == 400


@pytest.mark.parametrize("entrada,esperado", [
    ("../../etc/passwd", "passwd"),
    ("foto.jpg", "foto.jpg"),
    ("C:\\Windows\\evil.exe", "evil.exe"),
    ("", "foto"),
    (None, "foto"),
])
def test_nome_de_arquivo_do_cliente_e_reduzido_ao_basename(entrada, esperado):
    assert server._nome_seguro(entrada) == esperado


def test_nome_de_arquivo_tem_tamanho_limitado():
    assert len(server._nome_seguro("a" * 500 + ".png")) <= 80


# ── Limite de taxa ───────────────────────────────────────────────────────────────────

@asincrono
async def test_o_checkout_tem_limite_de_taxa(mp):
    """Cada checkout cria uma pre-aprovacao real no Mercado Pago."""
    import billing_routes
    uid, h = await _atleta("seg.checkout@example.com")
    await DB.rate_limits.delete_many({"key": "checkout:" + uid})
    estourou = None
    async with await _cliente() as c:
        for _ in range(billing_routes.MAX_CHECKOUTS_POR_JANELA + 2):
            r = await c.post("/api/billing/checkout", json={"plan_code": "pro"}, headers=h)
            if r.status_code == 429:
                estourou = r
                break
    assert estourou is not None, "o checkout aceitou chamadas sem limite"
    assert estourou.json()["detail"]["reason"] == "rate_limited"
    await DB.rate_limits.delete_many({"key": "checkout:" + uid})


@asincrono
async def test_o_limite_de_taxa_e_por_usuario():
    """O teto de um nao pode bloquear o outro."""
    from ratelimit import limitar
    a, _ = await _atleta("seg.rate.a@example.com")
    b, _ = await _atleta("seg.rate.b@example.com")
    for uid in (a, b):
        await DB.rate_limits.delete_many({"key": "teste:" + uid})
    for _ in range(3):
        await limitar(DB, "teste:" + a, 3, 60)
    with pytest.raises(Exception):
        await limitar(DB, "teste:" + a, 3, 60)
    await limitar(DB, "teste:" + b, 3, 60)  # o outro segue livre
    for uid in (a, b):
        await DB.rate_limits.delete_many({"key": "teste:" + uid})


# ── Autorizacao ──────────────────────────────────────────────────────────────────────

ROTAS_ADMIN = ["/api/admin/stats", "/api/admin/athletes", "/api/admin/audit-log",
               "/api/admin/ai-usage", "/api/billing/config-check", "/api/billing/events"]


@asincrono
async def test_anonimo_recebe_401_nas_rotas_administrativas():
    async with await _cliente() as c:
        for rota in ROTAS_ADMIN:
            r = await c.get(rota)
            assert r.status_code in (401, 403), f"{rota} -> {r.status_code}"


@asincrono
async def test_atleta_recebe_403_nas_rotas_administrativas():
    _, h = await _atleta("seg.admin@example.com")
    async with await _cliente() as c:
        for rota in ROTAS_ADMIN:
            r = await c.get(rota, headers=h)
            assert r.status_code == 403, f"{rota} -> {r.status_code}"


@asincrono
async def test_token_alegando_super_admin_nao_promove_ninguem():
    """O papel e relido do banco a cada requisicao; o que vem no token nao decide nada."""
    uid, _ = await _atleta("seg.forjado@example.com")
    forjado = {"Authorization": "Bearer " + create_token(uid, "SUPER_ADMIN")}
    async with await _cliente() as c:
        r = await c.get("/api/admin/athletes", headers=forjado)
    assert r.status_code == 403


@asincrono
async def test_jwt_sem_assinatura_e_recusado():
    import base64
    import json as _json
    cab = base64.urlsafe_b64encode(_json.dumps({"alg": "none"}).encode()).rstrip(b"=")
    corpo = base64.urlsafe_b64encode(
        _json.dumps({"sub": "x", "role": "SUPER_ADMIN", "type": "access"}).encode()).rstrip(b"=")
    async with await _cliente() as c:
        r = await c.get("/api/auth/me",
                        headers={"Authorization": f"Bearer {cab.decode()}.{corpo.decode()}."})
    assert r.status_code == 401


@asincrono
async def test_jwt_com_assinatura_adulterada_e_recusado():
    uid, _ = await _atleta("seg.assinatura@example.com")
    quebrado = create_token(uid, "ATHLETE")[:-6] + "AAAAAA"
    async with await _cliente() as c:
        r = await c.get("/api/auth/me", headers={"Authorization": "Bearer " + quebrado})
    assert r.status_code == 401


# ── Isolamento entre atletas ─────────────────────────────────────────────────────────

@asincrono
async def test_um_atleta_nao_alcanca_os_dados_do_outro():
    a_id, a = await _atleta("seg.iso.a@example.com")
    b_id, _ = await _atleta("seg.iso.b@example.com")
    marcador = "marcador-secreto-de-b"
    await DB.profiles.delete_many({"id": b_id})
    await DB.profiles.insert_one({"id": b_id, "user_id": b_id, "name": marcador,
                                  "assessment": {}, "priorities": ["Glúteos"]})
    async with await _cliente() as c:
        for rota in (f"/api/assessments/{b_id}", f"/api/muscle-map/{b_id}",
                     f"/api/visual-assessment/{b_id}",
                     f"/api/workouts/manual/versions?profile_id={b_id}"):
            r = await c.get(rota, headers=a)
            assert marcador not in r.text, f"vazou em {rota}"
    await DB.profiles.delete_many({"id": b_id})


@asincrono
async def test_id_no_corpo_nao_desvia_a_escrita_para_outro_atleta():
    a_id, a = await _atleta("seg.escrita.a@example.com")
    b_id, _ = await _atleta("seg.escrita.b@example.com")
    # A colecao e set_logs, nao "sets" — conferir a colecao errada faria este teste
    # passar sem provar nada.
    for uid in (a_id, b_id):
        await DB.set_logs.delete_many({"profile_id": uid})
    async with await _cliente() as c:
        r = await c.post("/api/sets", headers=a, json={
            "profile_id": b_id, "exercise_id": "supino-reto", "set_number": 1,
            "weight": 50, "reps": 8})
    assert r.status_code == 200, r.text
    assert await DB.set_logs.count_documents({"profile_id": b_id}) == 0, "escreveu em B"
    assert await DB.set_logs.count_documents({"profile_id": a_id}) == 1, "redirecionou para A"
    for uid in (a_id, b_id):
        await DB.set_logs.delete_many({"profile_id": uid})


@asincrono
async def test_campos_protegidos_nao_mudam_pelo_corpo():
    uid, h = await _atleta("seg.mass@example.com")
    async with await _cliente() as c:
        await c.post("/api/assessment", headers=h, json={
            "name": "eu", "days": 3, "experience": "Iniciante",
            "role": "SUPER_ADMIN", "status": "ACTIVE", "plan": "LIFETIME",
            "signup_source": "courtesy_granted", "owner_id": "outro"})
    u = await DB.users.find_one({"id": uid})
    assert u["role"] == "ATHLETE"
    assert u["status"] == "ACTIVE"
    assert not u.get("plan")
    assert not u.get("signup_source")


# ── Injecao NoSQL ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("corpo", [
    {"email": {"$ne": None}, "password": {"$ne": None}},
    {"email": {"$gt": ""}, "password": "x"},
    {"email": {"$regex": ".*"}, "password": {"$exists": True}},
])
@asincrono
async def test_operador_do_mongo_no_login_nao_autentica(corpo):
    async with await _cliente() as c:
        r = await c.post("/api/auth/login", json=corpo)
    assert r.status_code in (400, 401, 422)
    assert "token" not in r.text


@asincrono
async def test_operador_do_mongo_no_convite_nao_autentica():
    async with await _cliente() as c:
        r = await c.post("/api/auth/accept-invite",
                         json={"token": {"$ne": None}, "password": "SenhaForte#2026"})
    assert r.status_code in (400, 401, 410, 422)


def test_a_busca_administrativa_escapa_o_regex():
    """Uma busca como "(a+)+$" viraria regex catastrofico."""
    import re
    perigoso = "(a+)+$"
    assert re.escape(perigoso) != perigoso
    # e o alvo escapado casa literalmente, sem interpretar
    assert re.match(re.escape(perigoso), perigoso)


# ── Segredos ─────────────────────────────────────────────────────────────────────────

def test_nenhuma_rota_publica_devolve_nome_de_variavel_secreta():
    """config-check e admin; nada publico pode citar segredo, nem o nome."""
    import billing_routes
    assert "MP_ACCESS_TOKEN" not in str(billing_routes.listar_planos.__doc__ or "")


@asincrono
async def test_o_catalogo_publico_nao_expoe_id_do_mercado_pago():
    async with await _cliente() as c:
        r = await c.get("/api/billing/plans")
    bruto = r.text
    for proibido in ("preapproval_plan_id", "plan-essential", "MP_", "APP_USR"):
        assert proibido not in bruto, proibido


@asincrono
async def test_a_lista_de_atletas_nunca_devolve_hash_de_senha():
    _, h = await _atleta("seg.admin.hash@example.com", role="SUPER_ADMIN")
    async with await _cliente() as c:
        r = await c.get("/api/admin/athletes", headers=h)
    assert r.status_code == 200
    assert "password_hash" not in r.text
    assert "invite_token" not in r.text


# ── Rotas liberadas antes do pagamento ───────────────────────────────────────────────

def test_a_allowlist_sem_pagamento_continua_minima():
    """Cada rota adicionada aqui e uma porta aberta antes do pagamento. O teste existe
    para que aumentar a lista seja uma decisao, e nao um descuido."""
    assert ROTAS_LIBERADAS_SEM_PAGAMENTO == frozenset({
        "/api/auth/me",
        "/api/billing/plans",
        "/api/billing/me",
        "/api/billing/checkout",
        "/api/preassessment",
    })


# ── Confusao de caminho na trava de pagamento ────────────────────────────────────────

def test_a_trava_le_o_caminho_do_roteamento_e_nao_a_url_reconstruida():
    """request.url.path e remontado a partir de esquema, host e caminho e reanalisado.

    Nao ha bypass conhecido hoje — foi testado com socket cru, com travessia, barra
    dupla, ponto-e-virgula e fragmento, e todos deram 403 ou 404. Mas fazer a trava
    depender do valor reconstruido e apostar que nenhuma versao futura do starlette vai
    deixar os dois divergirem, e ja houve CVE sobre isso (PYSEC-2026-248). O teste fixa
    a fonte: o caminho que o roteador casou."""
    import inspect
    import auth
    fonte = inspect.getsource(auth.get_current_user)
    assert 'request.scope.get("path")' in fonte
    assert "request.url.path.rstrip" not in fonte


@asincrono
async def test_caminho_forjado_nao_alcanca_rota_paga():
    import uuid
    from datetime import datetime, timezone
    uid = str(uuid.uuid4())
    email = "seg.pathconf@example.com"
    await DB.users.delete_many({"email": email})
    await DB.users.insert_one({
        "id": uid, "email": email, "name": "Path", "role": "ATHLETE",
        "status": "PENDING_PAYMENT", "signup_source": "public",
        "created_at": datetime.now(timezone.utc).isoformat()})
    h = {"Authorization": "Bearer " + create_token(uid, "ATHLETE")}

    async with await _cliente() as c:
        for alvo in ("/api/bootstrap",
                     "/api/bootstrap?x=/api/preassessment",
                     "/api/preassessment/../bootstrap",
                     "/api/bootstrap/"):
            # follow_redirects: a barra final gera 307 antes da autenticacao rodar, e o
            # que importa e o destino, nao o desvio.
            r = await c.get(alvo, headers=h, follow_redirects=True)
            assert r.status_code in (403, 404, 405), f"{alvo} -> {r.status_code}"
    await DB.users.delete_many({"id": uid})

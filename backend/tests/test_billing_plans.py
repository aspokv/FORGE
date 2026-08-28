"""Catalogo de planos, matriz de capacidades e validacao do webhook.

Testes puros: nao precisam de banco, de servidor nem de credencial do Mercado Pago.
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import billing
import billing_plans as bp
import entitlements as ent


def _iso(d):
    return d.isoformat()


def _agora():
    return datetime.now(timezone.utc)


# ── Catalogo ─────────────────────────────────────────────────────────────────────────

def test_os_tres_planos_com_nome_e_preco_exatos():
    catalogo = {p["code"]: p for p in bp.catalogo_publico()}
    assert set(catalogo) == {"essential", "pro", "elite"}
    assert catalogo["essential"]["nome"] == "FORGE ESSENCIAL"
    assert catalogo["essential"]["preco"] == 39.90
    assert catalogo["pro"]["nome"] == "FORGE PRO"
    assert catalogo["pro"]["preco"] == 69.90
    assert catalogo["elite"]["nome"] == "FORGE ELITE"
    assert catalogo["elite"]["preco"] == 99.90


def test_precos_em_centavos_para_comparar_sem_erro_de_float():
    assert [p["preco_centavos"] for p in bp.PLANOS] == [3990, 6990, 9990]


def test_todo_plano_tem_para_quem_e_cobranca_mensal():
    for p in bp.catalogo_publico():
        assert p["para_quem"].strip()
        assert p["moeda"] == "BRL"
        assert p["periodicidade"] == "mensal"
        assert p["frequencia"] == 1 and p["tipo_de_frequencia"] == "months"
        assert p["cobranca"] == "Cobrança mensal recorrente"


def test_apenas_o_pro_e_recomendado():
    recomendados = [p["code"] for p in bp.catalogo_publico() if p["recomendado"]]
    assert recomendados == ["pro"]


def test_a_ordem_de_exibicao_e_essencial_pro_elite():
    assert [p["code"] for p in bp.catalogo_publico()] == ["essential", "pro", "elite"]


def test_recursos_futuros_ficam_separados_dos_disponiveis():
    """Anunciar como pronto o que ainda nao existe seria vender o que nao entregamos."""
    elite = next(p for p in bp.catalogo_publico() if p["code"] == "elite")
    assert elite["em_breve"], "Elite deveria listar recursos futuros"
    assert not set(elite["recursos"]) & set(elite["em_breve"])
    for p in bp.catalogo_publico():
        if p["code"] != "elite":
            assert p["em_breve"] == []


def test_o_catalogo_publico_nao_expoe_id_do_mercado_pago_nem_capacidades():
    for p in bp.catalogo_publico():
        assert "env_plan_id" not in p and "capacidades" not in p


def test_plano_desconhecido_nao_resolve():
    for entrada in (None, "", "gratuito", "ELITE_PLUS", "  "):
        assert bp.plano_ativo(entrada) is None


def test_codigo_e_normalizado():
    assert bp.plano_ativo(" PRO ")["code"] == "pro"


# ── Matriz de capacidades ────────────────────────────────────────────────────────────

def test_capacidades_sao_cumulativas():
    assert bp.CAPACIDADES_ESSENCIAL < bp.CAPACIDADES_PRO < bp.CAPACIDADES_ELITE


def test_essencial_tem_treino_e_nao_tem_alimentacao():
    caps = bp.capacidades_do_plano("essential")
    assert bp.TREINO in caps and bp.PROGRESSAO in caps
    assert bp.ALIMENTACAO not in caps
    assert bp.PROTOCOLOS_AGRESSIVOS not in caps


def test_pro_tem_alimentacao_e_nao_tem_agressivo():
    caps = bp.capacidades_do_plano("pro")
    assert bp.ALIMENTACAO in caps and bp.SUBSTITUICAO_DE_ALIMENTO in caps
    assert bp.PROTOCOLOS_AGRESSIVOS not in caps


def test_elite_tem_protocolos_avancados():
    assert bp.PROTOCOLOS_AGRESSIVOS in bp.capacidades_do_plano("elite")


# ── Resolucao de acesso ──────────────────────────────────────────────────────────────

def _limpar_ambiente():
    for chave in ("BILLING_ENFORCED", "BILLING_GRANDFATHER_BEFORE"):
        os.environ.pop(chave, None)


@pytest.fixture(autouse=True)
def ambiente_limpo():
    _limpar_ambiente()
    yield
    _limpar_ambiente()


def _assinatura(status="active", plan="pro", **extra):
    return {"user_id": "u1", "plan_code": plan, "status": status,
            "provider": "mercadopago", **extra}


def _atleta(**extra):
    return {"id": "u1", "role": "ATHLETE", "created_at": _iso(_agora()), **extra}


def test_admin_nunca_e_bloqueado():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = _iso(_agora() - timedelta(days=365))
    acesso = ent.resolver_acesso({"id": "a", "role": "SUPER_ADMIN"}, None)
    assert acesso["source"] == "admin"
    assert bp.PROTOCOLOS_AGRESSIVOS in acesso["capabilities"]


def test_com_cobranca_desligada_ninguem_perde_acesso():
    acesso = ent.resolver_acesso(_atleta(), None)
    assert acesso["grandfathered"] is True
    assert bp.ALIMENTACAO in acesso["capabilities"]


def test_usuario_anterior_a_cobranca_mantem_acesso_de_cortesia():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = _iso(_agora())
    antigo = _atleta(created_at=_iso(_agora() - timedelta(days=30)))
    acesso = ent.resolver_acesso(antigo, None)
    assert acesso["source"] == ent.ORIGEM_CORTESIA
    assert acesso["plan_code"] == "elite"


def test_cortesia_nao_inventa_pagamento():
    acesso = ent.resolver_acesso(_atleta(), None)
    assert acesso["subscription"] is None
    assert acesso["source"] == ent.ORIGEM_CORTESIA


def test_conta_nova_sem_assinatura_nao_tem_acesso():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = _iso(_agora() - timedelta(days=1))
    nova = _atleta(created_at=_iso(_agora()))
    assert ent.resolver_acesso(nova, None)["capabilities"] == []


def test_cadastro_publico_nunca_recebe_cortesia():
    """Senao bastaria se cadastrar para usar de graca."""
    os.environ["BILLING_ENFORCED"] = "true"
    publico = _atleta(signup_source="public")
    assert ent.e_usuario_antigo(publico) is False
    assert ent.resolver_acesso(publico, None)["capabilities"] == []


def test_assinatura_ativa_libera_o_plano_contratado():
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = _iso(_agora() - timedelta(days=1))
    acesso = ent.resolver_acesso(_atleta(created_at=_iso(_agora())), _assinatura(plan="pro"))
    assert acesso["plan_code"] == "pro"
    assert bp.ALIMENTACAO in acesso["capabilities"]
    assert bp.PROTOCOLOS_AGRESSIVOS not in acesso["capabilities"]


@pytest.mark.parametrize("estado", ["pending", "cancelled", "expired", "rejected", "paused"])
def test_estado_que_nao_libera_acesso(estado):
    """Pendente em especial: o retorno visual do checkout nao e confirmacao."""
    assert ent.assinatura_da_acesso(_assinatura(status=estado)) is False


def test_todos_os_estados_exigidos_existem():
    assert set(ent.ESTADOS) == {"pending", "active", "past_due", "paused",
                                "cancelled", "expired", "rejected"}


# ── Tolerancia ───────────────────────────────────────────────────────────────────────

def test_atraso_recente_mantem_acesso():
    a = _assinatura(status="past_due", past_due_since=_iso(_agora() - timedelta(days=1)))
    assert ent.assinatura_da_acesso(a) is True


def test_atraso_alem_da_tolerancia_bloqueia():
    a = _assinatura(status="past_due",
                    past_due_since=_iso(_agora() - timedelta(days=ent.DIAS_DE_TOLERANCIA + 1)))
    assert ent.assinatura_da_acesso(a) is False


def test_atraso_sem_data_nao_vira_acesso_infinito():
    assert ent.assinatura_da_acesso(_assinatura(status="past_due")) is False


def test_a_tolerancia_e_de_tres_dias():
    assert ent.DIAS_DE_TOLERANCIA == 3


def test_cancelamento_nao_recebe_tolerancia():
    a = _assinatura(status="cancelled", past_due_since=_iso(_agora()))
    assert ent.assinatura_da_acesso(a) is False


# ── Webhook: assinatura ──────────────────────────────────────────────────────────────

SEGREDO = "segredo-de-teste"


def _cabecalho(data_id, request_id, segredo=SEGREDO, ts=None):
    import hashlib
    import hmac
    ts = ts or str(int(time.time() * 1000))
    manifest = f"id:{str(data_id).lower()};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(segredo.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def test_assinatura_valida_e_aceita():
    assert billing.validar_assinatura_do_webhook(
        SEGREDO, _cabecalho("ABC123", "req-1"), "req-1", "ABC123") is True


def test_o_data_id_entra_em_minusculo():
    """Com maiuscula a assinatura nao bate — e a pegadinha classica deste esquema."""
    cab = _cabecalho("abc123", "req-1")
    assert billing.validar_assinatura_do_webhook(SEGREDO, cab, "req-1", "ABC123") is True


def test_segredo_errado_e_recusado():
    cab = _cabecalho("abc", "req-1", segredo="outro")
    assert billing.validar_assinatura_do_webhook(SEGREDO, cab, "req-1", "abc") is False


def test_sem_segredo_configurado_nada_e_aceito():
    """Um webhook que aceita qualquer corpo libera assinatura de graca."""
    cab = _cabecalho("abc", "req-1")
    assert billing.validar_assinatura_do_webhook("", cab, "req-1", "abc") is False


@pytest.mark.parametrize("cabecalho", [None, "", "lixo", "ts=1", "v1=abc", "ts=1,v1="])
def test_cabecalho_malformado_e_recusado(cabecalho):
    assert billing.validar_assinatura_do_webhook(SEGREDO, cabecalho, "req-1", "abc") is False


def test_request_id_diferente_invalida():
    cab = _cabecalho("abc", "req-1")
    assert billing.validar_assinatura_do_webhook(SEGREDO, cab, "req-2", "abc") is False


# ── Sandbox x producao ───────────────────────────────────────────────────────────────

def test_token_de_teste_indica_sandbox():
    assert billing.modo_sandbox("TEST-123") is True
    assert billing.modo_sandbox("APP_USR-123") is False


def test_sandbox_usa_o_init_point_de_sandbox():
    recurso = {"init_point": "https://prod", "sandbox_init_point": "https://sandbox"}
    assert billing.url_de_checkout(recurso, "TEST-1") == "https://sandbox"
    assert billing.url_de_checkout(recurso, "APP_USR-1") == "https://prod"


def test_sem_sandbox_init_point_cai_no_init_point():
    assert billing.url_de_checkout({"init_point": "https://x"}, "TEST-1") == "https://x"


# ── Traducao de estados ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mp,forge", [
    ("authorized", "active"), ("pending", "pending"), ("paused", "paused"),
    ("cancelled", "cancelled"), ("finished", "expired"), ("desconhecido", "pending"),
    (None, "pending"),
])
def test_estado_do_mercado_pago_vira_estado_do_forge(mp, forge):
    assert billing.estado_do_forge(mp) == forge


def test_erro_transitorio_e_distinguido_do_permanente():
    assert billing.ErroMercadoPago(500, "x").transitorio is True
    assert billing.ErroMercadoPago(429, "x").transitorio is True
    assert billing.ErroMercadoPago(400, "x").transitorio is False
    assert billing.ErroMercadoPago(404, "x").transitorio is False

# -*- coding: utf-8 -*-
"""
A analise de foto nao pode morrer por um nome de modelo ou por um filtro de seguranca.

O caso real: o atleta enviava a foto no Perfil e a tela respondia "Nao foi possivel
concluir a analise agora", sempre. O texto na tela e unico de proposito — o motivo tecnico
nao ajuda quem esta olhando e vazaria informacao de servidor — mas isso tambem significa
que a falha era CEGA: chave ausente, modelo aposentado e resposta barrada produziam
exatamente a mesma tela.

Este arquivo prende as tres defesas:
  1. uma cadeia de modelos, para um nome que deixou de existir nao derrubar tudo;
  2. leitura da resposta que sobrevive a uma devolucao sem texto — que e o que o filtro de
     seguranca do provedor devolve para foto de corpo, justamente o nosso caso de uso;
  3. nenhum nome de variavel de ambiente no que volta para o cliente.
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import (  # noqa: E402
    MODELOS_DE_VISAO_PADRAO,
    TENTATIVAS_POR_MODELO,
    _cadeia_de_modelos_de_visao,
    _e_transitorio,
    _texto_da_resposta,
    analyze_physique,
)


# ── A cadeia de modelos ──────────────────────────────────────────────────────────────

def test_o_modelo_configurado_e_sempre_o_primeiro(monkeypatch):
    monkeypatch.setenv("GEMINI_VISION_MODEL", "gemini-experimental-do-nicolas")
    cadeia = _cadeia_de_modelos_de_visao()
    assert cadeia[0] == "gemini-experimental-do-nicolas"
    assert len(cadeia) > 1, "sem reserva, um nome errado derruba a analise inteira"


def test_sem_configuracao_a_cadeia_e_a_padrao(monkeypatch):
    monkeypatch.delenv("GEMINI_VISION_MODEL", raising=False)
    assert _cadeia_de_modelos_de_visao() == list(MODELOS_DE_VISAO_PADRAO)


def test_o_modelo_configurado_nao_aparece_duas_vezes(monkeypatch):
    """Configurar justamente o padrao nao pode gastar duas tentativas na mesma coisa."""
    monkeypatch.setenv("GEMINI_VISION_MODEL", MODELOS_DE_VISAO_PADRAO[1])
    cadeia = _cadeia_de_modelos_de_visao()
    assert cadeia.count(MODELOS_DE_VISAO_PADRAO[1]) == 1
    assert cadeia[0] == MODELOS_DE_VISAO_PADRAO[1]


def test_espaco_em_branco_na_variavel_nao_vira_modelo(monkeypatch):
    monkeypatch.setenv("GEMINI_VISION_MODEL", "   ")
    assert _cadeia_de_modelos_de_visao() == list(MODELOS_DE_VISAO_PADRAO)


# ── Leitura da resposta ──────────────────────────────────────────────────────────────

class _Parte:
    def __init__(self, text=None):
        self.text = text


class _Conteudo:
    def __init__(self, partes):
        self.parts = partes


class _Candidato:
    def __init__(self, partes=None, finish_reason=None):
        self.content = _Conteudo(partes or [])
        self.finish_reason = finish_reason


class _Resposta:
    def __init__(self, text=None, candidates=None, prompt_feedback=None):
        self.text = text
        self.candidates = candidates or []
        self.prompt_feedback = prompt_feedback


class _Bloqueio:
    def __init__(self, motivo):
        self.block_reason = motivo


def test_o_caminho_normal_le_o_texto():
    assert _texto_da_resposta(_Resposta(text='  {"ok": 1}  ')) == '{"ok": 1}'


def test_resposta_sem_text_ainda_e_lida_pelas_partes():
    """
    Nem toda resposta valida preenche `.text`. Sem este degrau, uma resposta boa era
    descartada como falha.
    """
    r = _Resposta(text=None, candidates=[_Candidato(partes=[_Parte(None), _Parte('{"ok": 2}')])])
    assert _texto_da_resposta(r) == '{"ok": 2}'


def test_resposta_barrada_pelo_filtro_vira_erro_com_motivo():
    """
    O caso que quebrava de verdade: foto de corpo barrada pelo filtro de seguranca volta
    sem texto nenhum. Antes, `response.text.strip()` estourava em AttributeError e o motivo
    real sumia dentro do except generico.
    """
    r = _Resposta(text=None, candidates=[], prompt_feedback=_Bloqueio("SAFETY"))
    with pytest.raises(ValueError) as erro:
        _texto_da_resposta(r)
    assert "SAFETY" in str(erro.value)


def test_sem_texto_e_sem_motivo_tambem_falha_de_forma_limpa():
    r = _Resposta(text=None, candidates=[_Candidato(partes=[], finish_reason="MAX_TOKENS")])
    with pytest.raises(ValueError) as erro:
        _texto_da_resposta(r)
    assert "MAX_TOKENS" in str(erro.value)


def test_nunca_devolve_AttributeError():
    """Qualquer forma inesperada de resposta tem de virar ValueError, nunca AttributeError:
    o chamador trata ValueError como 'tente o proximo modelo'."""
    for esquisita in (_Resposta(), object()):
        with pytest.raises(ValueError):
            _texto_da_resposta(esquisita)


# ── O que volta para o cliente ───────────────────────────────────────────────────────

def _rodar(coro):
    """O projeto nao usa pytest-asyncio; um laco proprio evita somar dependencia."""
    return asyncio.new_event_loop().run_until_complete(coro)


def test_sem_chave_nao_vaza_o_nome_da_variavel(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = _rodar(analyze_physique(b"\xff\xd8\xff", "image/jpeg", ["front"]))
    assert r["status"] == "unavailable"
    assert r["reason"] == "sem_chave"
    texto = str(r)
    for proibido in ("GEMINI", "API_KEY", "gemini", "google", "Gemini"):
        assert proibido not in texto, f"{proibido!r} vazou para o cliente"


def test_a_forma_da_resposta_de_falha_nao_quebra_a_tela(monkeypatch):
    """
    A tela le `observations` e `suggested_priorities` sem checar antes. Devolver a falha
    sem esses campos trocaria um aviso por uma tela branca.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = _rodar(analyze_physique(b"\xff\xd8\xff", "image/jpeg", ["front"]))
    assert r["observations"] == {}
    assert r["suggested_priorities"] == []


# ── Erro transitorio contra erro definitivo ──────────────────────────────────────────
#
# O log de producao mostrou os dois lado a lado, e a diferenca decide o comportamento:
#
#   gemini-3.7-flash -> 503 UNAVAILABLE  "high demand ... temporary. Please try again"
#   gemini-2.5-flash -> 404 NOT_FOUND    "no longer available to new users"
#
# O primeiro pede repeticao no mesmo modelo. O segundo nao passa a existir esperando.

def test_sobrecarga_do_provedor_e_transitoria():
    """Foi o 503 que derrubou a analise em producao, com o modelo CERTO."""
    for erro in [
        "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently "
        "experiencing high demand. Spikes in demand are usually temporary.'}}",
        "429 RESOURCE_EXHAUSTED",
        "500 INTERNAL",
        "Deadline exceeded",
    ]:
        assert _e_transitorio(erro), erro[:60]


def test_modelo_aposentado_nao_e_transitorio():
    """Esperar nao ressuscita um modelo removido: tem de passar ao proximo na hora."""
    for erro in [
        "404 NOT_FOUND. {'error': {'code': 404, 'message': 'This model models/gemini-2.5-flash "
        "is no longer available to new users.'}}",
        "400 INVALID_ARGUMENT",
        "403 PERMISSION_DENIED",
        "API key not valid",
    ]:
        assert not _e_transitorio(erro), erro[:60]


def test_ha_mais_de_uma_tentativa_por_modelo():
    assert TENTATIVAS_POR_MODELO >= 2, "sem repeticao, um 503 passageiro derruba a analise"


def test_a_cadeia_nao_carrega_modelo_que_o_provedor_ja_aposentou(monkeypatch):
    """
    Nomes que o proprio provedor devolveu como 404 em producao. Mante-los na cadeia gasta
    tentativa e atrasa a resposta de quem esta esperando a analise.
    """
    monkeypatch.delenv("GEMINI_VISION_MODEL", raising=False)
    aposentados = {"gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"}
    assert not (set(_cadeia_de_modelos_de_visao()) & aposentados)

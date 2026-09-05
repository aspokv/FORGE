# -*- coding: utf-8 -*-
"""
Contrato do armazenamento das fotos de avaliacao.

O modulo ainda nao fala com bucket nenhum, mas as decisoes que ele fixa — forma da chave,
limites de entrada, e sobretudo o desligamento seguro quando falta credencial — precisam
valer desde ja. Sao elas que impedem que a implementacao futura invente um caminho, ou que
o recurso suba meio configurado guardando foto onde nao devia.
"""
import pytest

from visual_storage import (
    ANGULOS,
    MAXIMO_DE_FOTOS,
    TAMANHO_MAXIMO_BYTES,
    TIPOS_ACEITOS,
    carregar_configuracao,
    chave_da_foto,
    prefixo_da_avaliacao,
    prefixo_do_usuario,
)


def test_sem_credencial_o_recurso_fica_desligado(monkeypatch):
    """
    Fail-closed. Meio configurado nao pode virar "guarda em qualquer lugar": sem bucket ou
    sem chave, o modulo se declara inativo e a avaliacao segue funcionando sem foto.
    """
    for var in ("FORGE_FOTOS_BUCKET", "FORGE_FOTOS_CHAVE_ID", "FORGE_FOTOS_CHAVE_SECRETA"):
        monkeypatch.delenv(var, raising=False)
    assert carregar_configuracao().ativo is False


@pytest.mark.parametrize("faltando", ["FORGE_FOTOS_BUCKET", "FORGE_FOTOS_CHAVE_ID",
                                      "FORGE_FOTOS_CHAVE_SECRETA"])
def test_qualquer_variavel_faltando_desliga(monkeypatch, faltando):
    monkeypatch.setenv("FORGE_FOTOS_BUCKET", "forge-fotos")
    monkeypatch.setenv("FORGE_FOTOS_CHAVE_ID", "id")
    monkeypatch.setenv("FORGE_FOTOS_CHAVE_SECRETA", "segredo")
    monkeypatch.delenv(faltando, raising=False)
    assert carregar_configuracao().ativo is False


def test_configuracao_completa_ativa(monkeypatch):
    monkeypatch.setenv("FORGE_FOTOS_BUCKET", "forge-fotos")
    monkeypatch.setenv("FORGE_FOTOS_CHAVE_ID", "id")
    monkeypatch.setenv("FORGE_FOTOS_CHAVE_SECRETA", "segredo")
    cfg = carregar_configuracao()
    assert cfg.ativo is True
    # A URL assinada tem de ser curta: endereco longo vira link compartilhavel sem querer.
    assert cfg.url_segundos <= 900


def test_a_chave_comeca_pelo_usuario(monkeypatch):
    """
    O user_id vem antes do id da avaliacao de proposito: e o que torna a exclusao de conta
    uma varredura por prefixo em vez de uma busca objeto a objeto.
    """
    chave = chave_da_foto("avaliacoes/", "u1", "a1", "front")
    assert chave == "avaliacoes/u1/a1/front.jpg"
    assert chave.startswith(prefixo_do_usuario("avaliacoes/", "u1"))
    assert chave.startswith(prefixo_da_avaliacao("avaliacoes/", "u1", "a1"))


def test_prefixo_da_avaliacao_nao_alcanca_outra(monkeypatch):
    """Apagar uma avaliacao nao pode levar junto as vizinhas — o historico e o produto."""
    alvo = prefixo_da_avaliacao("avaliacoes/", "u1", "a1")
    outra = chave_da_foto("avaliacoes/", "u1", "a2", "front")
    assert not outra.startswith(alvo)


def test_prefixo_de_um_usuario_nao_alcanca_outro():
    de_um = prefixo_do_usuario("avaliacoes/", "u1")
    do_outro = chave_da_foto("avaliacoes/", "u2", "a1", "front")
    assert not do_outro.startswith(de_um)


def test_angulo_invalido_e_recusado():
    with pytest.raises(ValueError):
        chave_da_foto("avaliacoes/", "u1", "a1", "de-cima")


def test_prefixo_sem_barra_final_continua_valido():
    assert chave_da_foto("avaliacoes", "u1", "a1", "back") == "avaliacoes/u1/a1/back.jpg"


def test_limites_de_entrada_declarados():
    assert set(ANGULOS) == {"front", "back", "left", "right"}
    assert MAXIMO_DE_FOTOS == 4
    assert TAMANHO_MAXIMO_BYTES == 12 * 1024 * 1024
    # HEIC nao entra na lista do servidor: o navegador converte antes de enviar.
    assert "image/heic" not in TIPOS_ACEITOS
    assert "image/jpeg" in TIPOS_ACEITOS

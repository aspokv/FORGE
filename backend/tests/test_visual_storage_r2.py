# -*- coding: utf-8 -*-
"""
Ciclo completo contra um S3 de verdade (simulado): guardar, assinar, listar, apagar.

Os testes de `test_visual_storage.py` cobrem as decisoes — forma da chave, limites,
desligamento seguro. Estes cobrem a conversa com o servidor: se `put_object` recebe o
que devia, se a URL assinada aponta para a chave certa e expira, e se apagar por prefixo
apaga a avaliacao PEDIDA e nao a vizinha.

Sem isto, a unica forma de descobrir um erro de chamada seria em producao, com foto de
pessoa real no meio.
"""
import pytest

pytest.importorskip("moto", reason="moto nao instalado; o ciclo com S3 nao roda aqui")

from urllib.parse import parse_qs, urlparse  # noqa: E402

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

import visual_storage  # noqa: E402

BUCKET = "forge-avaliacoes"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 512


@pytest.fixture()
def ambiente(monkeypatch):
    """Configuracao completa, com credencial de mentira — o moto nao valida nenhuma."""
    monkeypatch.setenv("FORGE_FOTOS_BUCKET", BUCKET)
    monkeypatch.setenv("FORGE_FOTOS_KEY_ID", "teste")
    monkeypatch.setenv("FORGE_FOTOS_KEY_SECRET", "teste")
    monkeypatch.setenv("FORGE_FOTOS_REGION", "us-east-1")
    monkeypatch.setenv("FORGE_FOTOS_PREFIX", "avaliacoes/")
    monkeypatch.setenv("FORGE_FOTOS_URL_SEGUNDOS", "300")
    # Endpoint vazio = S3 padrao, que e o que o moto simula. Em producao ele aponta para
    # o R2, e a unica diferenca de comportamento esta no cabecalho de criptografia.
    monkeypatch.delenv("FORGE_FOTOS_ENDPOINT", raising=False)
    return visual_storage.carregar_configuracao()


@mock_aws
def test_ciclo_completo(ambiente):
    cfg = ambiente
    assert cfg.ativo is True
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
    cli = visual_storage.cliente(cfg)
    assert cli is not None

    # 1. guardar as quatro fotos de uma avaliacao
    chaves = [
        visual_storage.guardar_foto(cfg, cli, "u1", "a1", angulo, JPEG, "image/jpeg")
        for angulo in visual_storage.ANGULOS
    ]
    assert chaves == [f"avaliacoes/u1/a1/{a}.jpg" for a in visual_storage.ANGULOS]

    # 2. o objeto existe, e com o tipo certo
    obj = cli.get_object(Bucket=BUCKET, Key=chaves[0])
    assert obj["Body"].read() == JPEG
    assert obj["ContentType"] == "image/jpeg"

    # 3. a URL assinada aponta para a chave e carrega prazo
    url = visual_storage.url_assinada(cfg, cli, chaves[0])
    partes = urlparse(url)
    consulta = parse_qs(partes.query)
    assert chaves[0] in partes.path
    assert "X-Amz-Signature" in consulta
    assert int(consulta["X-Amz-Expires"][0]) == 300
    # A chave nao pode ir na URL como parametro legivel de credencial.
    assert "teste" not in consulta.get("X-Amz-Signature", [""])[0]


@mock_aws
def test_apagar_uma_avaliacao_nao_leva_a_vizinha(ambiente):
    cfg = ambiente
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
    cli = visual_storage.cliente(cfg)

    visual_storage.guardar_foto(cfg, cli, "u1", "a1", "front", JPEG, "image/jpeg")
    visual_storage.guardar_foto(cfg, cli, "u1", "a2", "front", JPEG, "image/jpeg")
    visual_storage.guardar_foto(cfg, cli, "u2", "a1", "front", JPEG, "image/jpeg")

    apagados = visual_storage.apagar_prefixo(
        cfg, cli, visual_storage.prefixo_da_avaliacao(cfg.prefixo, "u1", "a1"))
    assert apagados == 1

    restantes = [o["Key"] for o in cli.list_objects_v2(Bucket=BUCKET).get("Contents", [])]
    # A outra avaliacao do mesmo usuario e a do outro usuario continuam de pe. Enviar
    # fotos novas nunca pode apagar historico, e apagar uma nunca pode alcancar outra.
    assert "avaliacoes/u1/a2/front.jpg" in restantes
    assert "avaliacoes/u2/a1/front.jpg" in restantes
    assert "avaliacoes/u1/a1/front.jpg" not in restantes


@mock_aws
def test_apagar_a_conta_leva_tudo_daquela_pessoa_e_so(ambiente):
    cfg = ambiente
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
    cli = visual_storage.cliente(cfg)

    for avaliacao in ("a1", "a2", "a3"):
        for angulo in ("front", "back"):
            visual_storage.guardar_foto(cfg, cli, "u1", avaliacao, angulo, JPEG, "image/jpeg")
    visual_storage.guardar_foto(cfg, cli, "u2", "a1", "front", JPEG, "image/jpeg")

    apagados = visual_storage.apagar_prefixo(
        cfg, cli, visual_storage.prefixo_do_usuario(cfg.prefixo, "u1"))
    assert apagados == 6

    restantes = [o["Key"] for o in cli.list_objects_v2(Bucket=BUCKET).get("Contents", [])]
    assert restantes == ["avaliacoes/u2/a1/front.jpg"]


@mock_aws
def test_apagar_prefixo_vazio_nao_quebra(ambiente):
    """Avaliacao gravada antes do bucket existir nao tem objeto; apagar nao pode explodir."""
    cfg = ambiente
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
    cli = visual_storage.cliente(cfg)
    assert visual_storage.apagar_prefixo(cfg, cli, "avaliacoes/inexistente/") == 0

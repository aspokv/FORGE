# -*- coding: utf-8 -*-
"""
Armazenamento das fotos de avaliacao visual.

Provedor: Cloudflare R2, por endpoint compativel com S3. O contrato, as variaveis e a
politica de exclusao foram fixados antes de existir bucket — que e a ordem certa para dado
de corpo de pessoa: decidir onde vive e quando morre antes de comecar a acumular.

Sem credencial no ambiente, o modulo se declara desligado e NAO derruba nada: a avaliacao
visual continua funcionando, so nao guarda a foto. Isso e proposital — a interface nao pode
ficar bloqueada esperando configuracao de infraestrutura.

O QUE E ARMAZENADO ONDE
-----------------------
Bucket privado compativel com S3      as imagens, e nada alem delas
MongoDB (colecao visual_assessments)  so metadados; NUNCA os bytes da imagem

Guardar imagem no Mongo foi descartado de proposito: infla o banco, entra em todo backup,
viaja em toda replica e nao tem como servir com URL assinada de validade curta.

O metadado gravado por avaliacao:

    {
      "id":            identificador da avaliacao,
      "user_id":       dono,
      "created_at":    data da avaliacao (ISO, UTC),
      "photos": [
        {"angle": "front|back|left|right",
         "key":   chave privada no bucket,
         "bytes": tamanho apos compressao,
         "mime":  "image/jpeg" | "image/png" | "image/webp"}
      ],
      "analysis":      resultado da analise,
      "observations":  observacoes geradas,
      "limitations":   limitacoes identificadas
    }

Nao ha URL no documento. A chave e privada e a URL e assinada na hora do acesso — endereco
gravado envelhece e vaza; chave nao serve para nada sem credencial.

VARIAVEIS DE AMBIENTE
---------------------
FORGE_FOTOS_BUCKET        nome do bucket privado. Sem valor, o recurso fica desligado e a
                          avaliacao segue funcionando sem guardar foto.
FORGE_FOTOS_ENDPOINT      endpoint S3 (ex.: https://<conta>.r2.cloudflarestorage.com).
                          Vazio = AWS S3 padrao.
FORGE_FOTOS_REGION        regiao do bucket ("auto" no R2).
FORGE_FOTOS_KEY_ID        credencial de acesso.
FORGE_FOTOS_KEY_SECRET    credencial secreta.
FORGE_FOTOS_PREFIX        prefixo das chaves. Padrao "avaliacoes/".
FORGE_FOTOS_URL_SEGUNDOS  validade da URL assinada. Padrao 300 (5 min).

Nenhum valor e inventado aqui, e nenhum default aponta para bucket real: sem as variaveis
preenchidas o modulo se declara indisponivel.

O BUCKET PRECISA ESTAR
----------------------
- privado, sem leitura anonima e sem listagem publica;
- com criptografia em repouso ligada (SSE-S3 ou SSE-KMS; no R2, ligada por padrao);
- sem CDN e sem dominio publico na frente;
- com CORS permitindo apenas a origem da aplicacao, e so os metodos usados.

FORMA DA CHAVE
--------------
    avaliacoes/{user_id}/{assessment_id}/{angle}.jpg

O user_id no caminho e proposital: torna trivial apagar tudo de uma pessoa com uma
varredura por prefixo, que e o que uma solicitacao de exclusao de conta exige.

POLITICA DE EXCLUSAO
--------------------
1. O usuario pode apagar UMA avaliacao. Apaga os objetos do prefixo dela e o documento no
   Mongo. Nao ha lixeira: pediu para apagar, apaga.
2. Enviar novas fotos NUNCA apaga avaliacao anterior. O historico e o produto; sobrescrever
   destruiria a comparacao entre datas, que e a razao de existir da secao.
3. Excluir a conta apaga todas as avaliacoes da pessoa, por varredura do prefixo
   `avaliacoes/{user_id}/`.
4. Nao ha expiracao automatica por tempo. Apagar foto de progresso de quem ainda usa o
   aplicativo seria perder justamente o "antes" que da sentido ao "depois". Se um dia
   houver retencao por tempo, ela precisa ser anunciada ao usuario antes de valer.
5. Objeto orfao — arquivo no bucket sem documento correspondente no Mongo — e sobra de
   upload interrompido e pode ser removido por rotina de limpeza. O contrario (documento
   sem arquivo) e mostrado como avaliacao sem imagem, nunca apagado em silencio.

LIMITES DE ENTRADA
------------------
- ate 4 fotos por avaliacao, uma por angulo;
- JPG, PNG, WebP e HEIC quando o navegador conseguir converter;
- ate 8 MB por arquivo ANTES da compressao;
- comprimidas no cliente antes do upload, com o maior lado em 1600px;
- o tipo e conferido pelo conteudo no servidor, e nao pela extensao nem pelo
  Content-Type que o cliente informou.

O QUE NAO SAI DAQUI
-------------------
As imagens vao para o bucket e para o provedor de analise visual, e para mais nenhum
lugar. Sem terceiros de analitica, sem log de corpo de requisicao com imagem dentro, sem
copia para pasta publica do frontend.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

ANGULOS = ("front", "back", "left", "right")
MAXIMO_DE_FOTOS = 4
TAMANHO_MAXIMO_BYTES = 8 * 1024 * 1024
TIPOS_ACEITOS = ("image/jpeg", "image/png", "image/webp")
MAIOR_LADO_APOS_COMPRESSAO = 1600


@dataclass(frozen=True)
class ConfiguracaoDeFotos:
    """O que o modulo precisa para funcionar. Sem isso, ele se declara desligado."""

    bucket: str
    endpoint: Optional[str]
    regiao: str
    chave_id: str
    chave_secreta: str
    prefixo: str
    url_segundos: int

    @property
    def ativo(self) -> bool:
        return bool(self.bucket and self.chave_id and self.chave_secreta)


def carregar_configuracao() -> ConfiguracaoDeFotos:
    """Le o ambiente. Nao valida credencial — isso e trabalho de quem for usar."""
    return ConfiguracaoDeFotos(
        bucket=os.environ.get("FORGE_FOTOS_BUCKET", "").strip(),
        endpoint=(os.environ.get("FORGE_FOTOS_ENDPOINT", "").strip() or None),
        regiao=os.environ.get("FORGE_FOTOS_REGION", "auto").strip() or "auto",
        chave_id=os.environ.get("FORGE_FOTOS_KEY_ID", "").strip(),
        chave_secreta=os.environ.get("FORGE_FOTOS_KEY_SECRET", "").strip(),
        prefixo=(os.environ.get("FORGE_FOTOS_PREFIX", "avaliacoes/").strip() or "avaliacoes/"),
        url_segundos=int(os.environ.get("FORGE_FOTOS_URL_SEGUNDOS", "300") or 300),
    )


def chave_da_foto(prefixo: str, user_id: str, assessment_id: str, angulo: str) -> str:
    """
    Caminho do objeto no bucket.

    O user_id vem antes do id da avaliacao para que apagar tudo de uma pessoa seja uma
    varredura por prefixo, e nao uma busca objeto a objeto.
    """
    if angulo not in ANGULOS:
        raise ValueError(f"angulo invalido: {angulo!r}")
    limpo = prefixo if prefixo.endswith("/") else prefixo + "/"
    return f"{limpo}{user_id}/{assessment_id}/{angulo}.jpg"


def prefixo_do_usuario(prefixo: str, user_id: str) -> str:
    """Prefixo que cobre TODAS as avaliacoes de uma pessoa — usado na exclusao de conta."""
    limpo = prefixo if prefixo.endswith("/") else prefixo + "/"
    return f"{limpo}{user_id}/"


def prefixo_da_avaliacao(prefixo: str, user_id: str, assessment_id: str) -> str:
    """Prefixo de uma avaliacao — usado quando o usuario apaga uma avaliacao especifica."""
    limpo = prefixo if prefixo.endswith("/") else prefixo + "/"
    return f"{limpo}{user_id}/{assessment_id}/"


# ── Cliente R2 ─────────────────────────────────────────────────────────────────────────
#
# Tudo abaixo e opcional em tempo de execucao: se `carregar_configuracao().ativo` for
# falso, nada aqui e chamado e o restante do produto segue igual.

def _boto3():
    """Importa boto3 so quando ha o que fazer com ele, para nao pesar o start do servidor."""
    import boto3  # noqa: WPS433 — import tardio de proposito
    from botocore.config import Config

    return boto3, Config


def cliente(cfg: "ConfiguracaoDeFotos"):
    """
    Cliente S3 apontado para o R2, ou None quando falta configuracao.

    `signature_version="s3v4"` e exigencia do R2 para URL assinada. `addressing_style`
    virtual e o que o R2 espera; com o estilo de caminho ele recusa a assinatura.
    """
    if not cfg.ativo:
        return None
    boto3, Config = _boto3()
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint,
        region_name=cfg.regiao,
        aws_access_key_id=cfg.chave_id,
        aws_secret_access_key=cfg.chave_secreta,
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


# Assinatura dos formatos aceitos. O tipo e decidido pelos primeiros bytes, e nao pela
# extensao nem pelo Content-Type que o cliente informou — os dois sao texto que o cliente
# escreve, e nenhum dos dois prova o que o arquivo e.
_ASSINATURAS = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


def detectar_tipo(dados: bytes) -> Optional[str]:
    """Tipo real do arquivo, pelo conteudo. None quando nao e imagem aceita."""
    for assinatura, mime in _ASSINATURAS:
        if dados.startswith(assinatura):
            return mime
    # WebP: "RIFF" ....  "WEBP"
    if len(dados) >= 12 and dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    return None


def validar_foto(dados: bytes) -> str:
    """
    Confere tamanho e tipo. Devolve o mime detectado ou levanta ValueError.

    A mensagem de erro fala de arquivo, nunca de infraestrutura: ela chega ao usuario.
    """
    if not dados:
        raise ValueError("Arquivo vazio.")
    if len(dados) > TAMANHO_MAXIMO_BYTES:
        raise ValueError("Imagem acima do tamanho permitido.")
    mime = detectar_tipo(dados)
    if mime not in TIPOS_ACEITOS:
        raise ValueError("Formato de imagem não suportado.")
    return mime


def guardar_foto(cfg, cli, user_id: str, assessment_id: str, angulo: str,
                 dados: bytes, mime: str) -> str:
    """Sobe um objeto privado e devolve a chave. Nunca devolve URL."""
    chave = chave_da_foto(cfg.prefixo, user_id, assessment_id, angulo)
    extras = {}
    # No R2 a criptografia em repouso e sempre ligada e o cabecalho de SSE e recusado.
    # Em S3 da AWS (endpoint vazio) ele e necessario para o mesmo efeito.
    if not cfg.endpoint:
        extras["ServerSideEncryption"] = "AES256"
    cli.put_object(
        Bucket=cfg.bucket,
        Key=chave,
        Body=dados,
        ContentType=mime,
        # O objeto e privado; nao ha ACL publica em nenhum caminho.
        **extras,
    )
    return chave


def url_assinada(cfg, cli, chave: str) -> str:
    """
    URL de leitura com validade curta.

    Curta de proposito: endereco de foto de corpo que dura horas vira link compartilhavel
    sem querer. O padrao e cinco minutos, o suficiente para a tela carregar.
    """
    return cli.generate_presigned_url(
        "get_object",
        Params={"Bucket": cfg.bucket, "Key": chave},
        ExpiresIn=cfg.url_segundos,
    )


def apagar_prefixo(cfg, cli, prefixo: str) -> int:
    """
    Apaga todos os objetos sob um prefixo. Devolve quantos foram.

    Usado tanto para apagar uma avaliacao quanto para apagar a conta inteira — a diferenca
    esta so no prefixo recebido, e e por isso que a chave comeca pelo user_id.
    """
    apagados = 0
    token = None
    while True:
        argumentos = {"Bucket": cfg.bucket, "Prefix": prefixo}
        if token:
            argumentos["ContinuationToken"] = token
        pagina = cli.list_objects_v2(**argumentos)
        objetos = [{"Key": o["Key"]} for o in pagina.get("Contents", [])]
        if objetos:
            cli.delete_objects(Bucket=cfg.bucket, Delete={"Objects": objetos})
            apagados += len(objetos)
        if not pagina.get("IsTruncated"):
            return apagados
        token = pagina.get("NextContinuationToken")

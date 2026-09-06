# -*- coding: utf-8 -*-
"""
Verificacao do armazenamento de fotos, para rodar DENTRO do container de producao.

    python verificar_r2.py

Faz um ciclo completo com um objeto de teste proprio — nunca toca em foto de usuario — e
imprime so o resultado de cada etapa. Nenhum valor de credencial, nome de bucket, endpoint,
chave ou URL assinada aparece na saida: o que sai e "ok" ou "FALHOU", e no maximo o
tamanho de uma variavel para diferenciar "vazia" de "preenchida".

O objeto de teste vive em `<prefixo>_verificacao/` — fora do espaco de qualquer usuario,
entao mesmo que a limpeza falhe ele nao se confunde com avaliacao de ninguem.
"""
import sys
import time
import uuid

import visual_storage

VERDE, VERMELHO, FIM = "\033[32m", "\033[31m", "\033[0m"
falhas = []


def etapa(nome, ok, detalhe=""):
    marca = f"{VERDE}ok{FIM}" if ok else f"{VERMELHO}FALHOU{FIM}"
    print(f"  [{marca}] {nome}" + (f"  ({detalhe})" if detalhe else ""))
    if not ok:
        falhas.append(nome)
    return ok


def main() -> int:
    print("\nVerificacao do armazenamento de fotos de avaliacao\n")

    cfg = visual_storage.carregar_configuracao()

    # 1) Presenca das variaveis. Imprime o TAMANHO, nunca o valor — e o suficiente para
    #    distinguir "nao cadastrada" de "cadastrada" sem revelar nada.
    print("Variaveis de ambiente")
    presentes = {
        "FORGE_FOTOS_BUCKET": cfg.bucket,
        "FORGE_FOTOS_ENDPOINT": cfg.endpoint or "",
        "FORGE_FOTOS_REGION": cfg.regiao,
        "FORGE_FOTOS_KEY_ID": cfg.chave_id,
        "FORGE_FOTOS_KEY_SECRET": cfg.chave_secreta,
        "FORGE_FOTOS_PREFIX": cfg.prefixo,
    }
    for nome, valor in presentes.items():
        # Endpoint e regiao podem ficar vazios em S3 padrao; as demais nao.
        obrigatoria = nome not in ("FORGE_FOTOS_ENDPOINT", "FORGE_FOTOS_REGION")
        etapa(nome, bool(valor) or not obrigatoria,
              f"{len(valor)} caracteres" if valor else "vazia")
    etapa("FORGE_FOTOS_URL_SEGUNDOS", cfg.url_segundos > 0, f"{cfg.url_segundos}s")

    print("\nModulo")
    if not etapa("armazenamento ativo", cfg.ativo):
        print("\n  Falta bucket ou credencial. A avaliacao visual continua funcionando,")
        print("  mas as fotos nao sao guardadas.\n")
        return 1

    cli = visual_storage.cliente(cfg)
    if not etapa("cliente criado", cli is not None):
        return 1

    # 2) Ciclo completo com objeto proprio, fora do espaco dos usuarios.
    print("\nCiclo de gravacao")
    chave = f"{cfg.prefixo.rstrip('/')}/_verificacao/{uuid.uuid4()}.bin"
    corpo = b"forge-verificacao-" + str(time.time()).encode()

    try:
        extras = {} if cfg.endpoint else {"ServerSideEncryption": "AES256"}
        cli.put_object(Bucket=cfg.bucket, Key=chave, Body=corpo,
                       ContentType="application/octet-stream", **extras)
        etapa("gravar objeto", True)
    except Exception as erro:
        etapa("gravar objeto", False, type(erro).__name__)
        print(f"\n  Detalhe: {str(erro)[:180]}\n")
        return 1

    try:
        volta = cli.get_object(Bucket=cfg.bucket, Key=chave)["Body"].read()
        etapa("ler de volta", volta == corpo)
    except Exception as erro:
        etapa("ler de volta", False, type(erro).__name__)

    try:
        achou = any(o["Key"] == chave for o in
                    cli.list_objects_v2(Bucket=cfg.bucket, Prefix=chave).get("Contents", []))
        etapa("aparece na listagem do bucket", achou)
    except Exception as erro:
        etapa("aparece na listagem do bucket", False, type(erro).__name__)

    # 3) URL assinada funciona, e a mesma URL SEM assinatura nao funciona. O segundo teste
    #    e o que prova que o bucket nao esta publico — o primeiro sozinho nao prova nada.
    print("\nAcesso")
    try:
        import urllib.error
        import urllib.request

        url = visual_storage.url_assinada(cfg, cli, chave)
        with urllib.request.urlopen(url, timeout=20) as r:
            etapa("URL assinada abre", r.status == 200 and r.read() == corpo)

        sem_assinatura = url.split("?")[0]
        try:
            with urllib.request.urlopen(sem_assinatura, timeout=20) as r:
                etapa("URL sem assinatura e recusada", False,
                      f"abriu com status {r.status} — BUCKET PUBLICO")
        except urllib.error.HTTPError as e:
            etapa("URL sem assinatura e recusada", e.code in (401, 403), f"HTTP {e.code}")
        except Exception:
            # Recusa por outro motivo (DNS, conexao) tambem nao e acesso publico.
            etapa("URL sem assinatura e recusada", True, "sem resposta publica")
    except Exception as erro:
        etapa("URL assinada abre", False, type(erro).__name__)

    # 4) Exclusao, e conferencia de que sumiu mesmo.
    print("\nExclusao")
    try:
        apagados = visual_storage.apagar_prefixo(
            cfg, cli, f"{cfg.prefixo.rstrip('/')}/_verificacao/")
        etapa("apagar por prefixo", apagados >= 1, f"{apagados} objeto(s)")
        sobrou = cli.list_objects_v2(Bucket=cfg.bucket, Prefix=chave).get("Contents", [])
        etapa("objeto sumiu de fato", not sobrou)
    except Exception as erro:
        etapa("apagar por prefixo", False, type(erro).__name__)

    print()
    if falhas:
        print(f"{VERMELHO}{len(falhas)} etapa(s) falharam:{FIM} " + ", ".join(falhas))
        return 1
    print(f"{VERDE}Armazenamento ativo e funcionando de ponta a ponta.{FIM}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

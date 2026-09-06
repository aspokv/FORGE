# -*- coding: utf-8 -*-
"""
Validacao de ponta a ponta do armazenamento de fotos (Cloudflare R2) em producao.

Cobre os oito pontos que so o ambiente real responde: o backend reconhece o bucket, uma
foto sobe, aparece no historico, a URL assinada abre, existe mais de uma data para
comparar, a exclusao leva o objeto junto e o bucket continua privado.

O que este roteiro NUNCA imprime: senha, token, chave de bucket, nome de objeto ou URL
assinada. Uma URL assinada e ela propria uma credencial de leitura — colar uma no terminal
deixa no historico do shell um acesso que deveria durar cinco minutos. Sai daqui apenas
"ok" ou "FALHOU", codigo de status e contagem.

So biblioteca padrao de proposito: um roteiro de verificacao que exige instalar pacote
antes de rodar acaba nao sendo rodado.

Uso:
    python scripts/validar-r2-producao.py
    python scripts/validar-r2-producao.py --base https://outro-host/api

A senha e lida sem eco e nao entra no historico. Nada e gravado em disco.
"""
import argparse
import getpass
import io
import json
import sys
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlsplit, urlunsplit

TEMPO = 120
placar = []


def marcar(item, condicao, detalhe=""):
    placar.append((item, bool(condicao)))
    print(f"  [{'ok' if condicao else 'FALHOU'}] {item}{(' — ' + detalhe) if detalhe else ''}")
    return bool(condicao)


def pedir(url, dados=None, cabecalhos=None, metodo=None):
    """
    Devolve (status, corpo_em_bytes, cabecalhos) sem levantar excecao por status.

    Erro de status aqui e resultado, e nao acidente: metade das verificacoes existe
    justamente para confirmar que o servidor RECUSA alguma coisa.
    """
    req = urllib.request.Request(url, data=dados, method=metodo)
    for k, v in (cabecalhos or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=TEMPO) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})
    except urllib.error.URLError as e:
        return 0, str(e.reason).encode(), {}


def como_json(corpo):
    try:
        return json.loads(corpo.decode("utf-8"))
    except Exception:
        return {}


def jpeg_de_teste():
    """Imagem valida de verdade quando ha Pillow; um JPEG minimo aceitavel quando nao ha."""
    try:
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (900, 1200), (90, 92, 96)).save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except ImportError:
        return (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00" + bytes([16] * 64) +
            b"\xff\xc0\x00\x0b\x08\x00\x10\x00\x10\x01\x01\x11\x00"
            b"\xff\xc4\x00\x14\x00\x01" + bytes(15) + b"\x08"
            b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xaa\xff\xd9"
        )


def multipart(campos, arquivo):
    """Corpo multipart/form-data montado a mao — evita depender de `requests`."""
    limite = f"----forge{uuid.uuid4().hex}"
    partes = []
    for nome, valor in campos.items():
        partes.append(
            f"--{limite}\r\nContent-Disposition: form-data; name=\"{nome}\"\r\n\r\n{valor}\r\n"
            .encode("utf-8")
        )
    nome, arq, conteudo, tipo = arquivo
    partes.append(
        f"--{limite}\r\nContent-Disposition: form-data; name=\"{nome}\"; filename=\"{arq}\"\r\n"
        f"Content-Type: {tipo}\r\n\r\n".encode("utf-8")
    )
    partes.append(conteudo)
    partes.append(f"\r\n--{limite}--\r\n".encode("utf-8"))
    return b"".join(partes), f"multipart/form-data; boundary={limite}"


def main():
    p = argparse.ArgumentParser(description="Valida o armazenamento de fotos em producao.")
    p.add_argument("--base", default="https://forge.aiexec.com.br/api")
    base = p.parse_args().base.rstrip("/")

    print("Validacao do armazenamento de fotos em producao")
    print(f"Servidor: {base}\n")

    email = input("e-mail: ").strip()
    senha = getpass.getpass("senha (nao aparece): ")

    corpo = json.dumps({"email": email, "password": senha}).encode("utf-8")
    senha = None  # fora da memoria assim que deixa de ser necessaria
    st, dados, _ = pedir(f"{base}/auth/login", corpo, {"Content-Type": "application/json"})
    if st != 200:
        print(f"\nLogin recusado (HTTP {st}). Nada foi alterado.")
        return 1
    sessao = como_json(dados)
    auth = {"Authorization": f"Bearer {sessao['token']}"}
    perfil = sessao["user"]["id"]
    print(f"\nAutenticado. Perfil ...{perfil[-6:]}\n")

    # ── 1. O backend reconhece o R2 ────────────────────────────────────────────
    print("1. Backend reconhece o R2")
    st, corpo, _ = pedir(f"{base}/visual-history/{perfil}", cabecalhos=auth)
    hist = como_json(corpo)
    pronto = st == 200 and hist.get("storage_ready") is True
    marcar("storage_ready verdadeiro", pronto,
           "" if pronto else "sem isto, os itens 2 a 8 nao tem como passar")
    antes = hist.get("assessments", []) if st == 200 else []
    print(f"       historico atual: {len(antes)} avaliacao(oes)\n")

    # ── 2. Enviar uma foto ─────────────────────────────────────────────────────
    print("2. Enviar uma foto")
    envio, tipo = multipart(
        {"profile_id": perfil, "consent": "true", "views": '["front"]'},
        ("photos", "front.jpg", jpeg_de_teste(), "image/jpeg"),
    )
    st, corpo, _ = pedir(f"{base}/visual-assessment", envio,
                         {**auth, "Content-Type": tipo})
    if not marcar("envio aceito", st == 200, f"HTTP {st}"):
        return 1
    nova = como_json(corpo)["id"]
    print(f"       avaliacao criada ...{nova[-6:]}\n")

    # ── 3. Aparece no historico ────────────────────────────────────────────────
    print("3. Aparece no historico")
    st, corpo, _ = pedir(f"{base}/visual-history/{perfil}", cabecalhos=auth)
    itens = como_json(corpo).get("assessments", [])
    achada = next((a for a in itens if a["id"] == nova), None)
    marcar("avaliacao presente", achada is not None)
    marcar("historico anterior preservado", len(itens) == len(antes) + 1,
           f"{len(antes)} -> {len(itens)}")
    fotos = (achada or {}).get("photos") or []
    tem_url = len(fotos) == 1 and bool(fotos[0].get("url"))
    marcar("veio com foto assinada", tem_url)
    print()
    if not tem_url:
        print("Sem URL assinada nao da para seguir para os itens 4 e 8.")
        return 1
    assinada = fotos[0]["url"]

    # ── 4. A URL assinada funciona ─────────────────────────────────────────────
    print("4. URL assinada")
    st, _, cab = pedir(assinada)
    marcar("abre a imagem", st == 200, f"HTTP {st}")
    marcar("responde como imagem", cab.get("Content-Type", "").startswith("image/"),
           cab.get("Content-Type", "sem tipo"))
    marcar("tem validade curta", "X-Amz-Expires" in assinada)
    print()

    # ── 5 e 6. Segunda data e comparacao ───────────────────────────────────────
    print("5/6. Segunda data e comparacao Antes/Agora")
    dias = sorted({a["created_at"][:10] for a in itens if a.get("created_at")})
    marcar("existem avaliacoes de mais de uma data", len(dias) >= 2,
           f"{len(dias)} data(s) distintas")
    print("       " + ("a tela deve mostrar Antes/Agora; confira no aparelho"
                       if len(dias) >= 2 else
                       "so ha uma data: a tela DEVE mostrar uma foto so e 'Primeira avaliacao'"))
    print()

    # ── 7. Exclusao ────────────────────────────────────────────────────────────
    print("7. Exclusao (apaga somente a avaliacao criada por este roteiro)")
    st, _, _ = pedir(f"{base}/visual-assessment/{nova}", cabecalhos=auth, metodo="DELETE")
    marcar("exclusao aceita", st == 200, f"HTTP {st}")
    st, corpo, _ = pedir(f"{base}/visual-history/{perfil}", cabecalhos=auth)
    restantes = como_json(corpo).get("assessments", [])
    marcar("sumiu do historico", all(a["id"] != nova for a in restantes))
    marcar("as demais continuam intactas", len(restantes) == len(antes),
           f"{len(restantes)} de {len(antes)} esperadas")
    st, _, _ = pedir(assinada)
    marcar("o objeto saiu do bucket", st in (403, 404), f"HTTP {st}")
    print()

    # ── 8. O bucket continua privado ───────────────────────────────────────────
    print("8. Bucket privado")
    partes = urlsplit(assinada)
    st, _, _ = pedir(urlunsplit((partes.scheme, partes.netloc, partes.path, "", "")))
    marcar("mesma URL sem assinatura e recusada", st in (401, 403), f"HTTP {st}")
    st, _, _ = pedir(f"{partes.scheme}://{partes.netloc}/")
    marcar("listagem do bucket recusada", st in (400, 401, 403), f"HTTP {st}")
    st, _, _ = pedir(f"{base}/visual-history/{perfil}")
    marcar("historico exige autenticacao", st == 401, f"HTTP {st}")
    print()

    ruins = [nome for nome, ok in placar if not ok]
    print("-" * 62)
    print(f"{len(placar) - len(ruins)} de {len(placar)} verificacoes passaram")
    if ruins:
        print("\nFalhou:")
        for nome in ruins:
            print(f"  - {nome}")
    return 1 if ruins else 0


if __name__ == "__main__":
    sys.exit(main())

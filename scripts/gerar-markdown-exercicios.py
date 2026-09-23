# -*- coding: utf-8 -*-
"""Gera o briefing de arte dos exercicios do FORGE, para encomendar as imagens novas.

Por que um script e nao um arquivo escrito a mao
------------------------------------------------
O catalogo tem 134 exercicios e muda. Um markdown digitado envelhece no dia em que
alguem adiciona um agachamento novo, e ninguem descobre: o arquivo continua ali,
parecendo certo. Rodando o script, o documento sempre reflete `exercises.json`.

O rodizio de modelo tambem e decidido aqui, e nao no olho de quem gera: alternando
dentro de cada grupo muscular, qualquer sessao de treino cai com homem e mulher
misturados. Se a escolha ficasse solta, o resultado provavel seria o de hoje, em que
as 134 imagens sao o mesmo homem.

Uso:
    python scripts/gerar-markdown-exercicios.py "<caminho do arquivo .md>"
"""
import io
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

from muscles import to_frontend  # noqa: E402

SAIDA = sys.argv[1] if len(sys.argv) > 1 else "FORGE-EXERCICIOS.md"

EQUIPAMENTO = {
    "barbell": "barra", "dumbbell": "halteres", "cable": "polia", "machine": "máquina",
    "smith_machine": "Smith", "bodyweight": "peso do corpo", "bench": "banco",
    "rack": "rack",
}
LATERALIDADE = {"bilateral": "bilateral", "unilateral": "unilateral"}
CATEGORIA = {"compound": "composto", "isolation": "isolado"}

# Os musculos que `to_frontend` ainda nao traduz. Aqui aparecem em portugues para o
# documento nao levar identificador interno para quem vai desenhar.
FALTANDO = {"erectors": "Eretores da espinha", "forearms": "Antebraços"}

# De cima para baixo no corpo, que e como se organiza uma sessao de fotos.
ORDEM = [
    "Peitoral superior", "Peitoral esternal", "Costas / espessura", "Dorsais / largura",
    "Trapézio", "Deltóide anterior", "Deltóide lateral", "Deltóide posterior",
    "Bíceps", "Tríceps", "Antebraços", "Abdômen", "Eretores da espinha",
    "Quadríceps", "Posteriores", "Glúteos", "Adutores", "Panturrilhas",
]


def musculo(interno):
    return FALTANDO.get(to_frontend(interno), to_frontend(interno))


def equipamentos(lista):
    return ", ".join(EQUIPAMENTO.get(e, e) for e in (lista or [])) or "nenhum"


def main():
    exercicios = json.load(io.open(RAIZ / "backend" / "exercises.json", encoding="utf-8"))
    catalogo = json.load(io.open(
        RAIZ / "frontend" / "src" / "features" / "exercisePhotoCatalog.json", encoding="utf-8"))
    arte = {c["id"]: os.path.basename(c["src"]) for c in catalogo}

    repetidas = defaultdict(list)
    for c in catalogo:
        repetidas[c["src"]].append(c["id"])
    compartilhadas = {src: ids for src, ids in repetidas.items() if len(ids) > 1}

    grupos = defaultdict(list)
    for e in exercicios:
        grupos[musculo(e["primary_muscle"])].append(e)
    ordenados = [g for g in ORDEM if g in grupos] + \
                [g for g in sorted(grupos) if g not in ORDEM]

    # O rodizio: alterna dentro do grupo e troca o pe a cada grupo, para que nenhum
    # grupo fique so de um lado e para que uma sessao qualquer venha misturada.
    modelo = {}
    for gi, grupo in enumerate(ordenados):
        for i, e in enumerate(sorted(grupos[grupo], key=lambda x: x["name"])):
            modelo[e["id"]] = "Mulher" if (i + gi) % 2 else "Homem"
    homens = sum(1 for v in modelo.values() if v == "Homem")

    linhas = []
    w = linhas.append

    w("# FORGE: briefing de arte dos exercícios")
    w("")
    w(f"**{len(exercicios)} exercícios.** Gerado de `backend/exercises.json`, que é a fonte")
    w("que o aplicativo usa de verdade.")
    w("")
    w("Este documento existe para que as 134 imagens saiam parecendo uma coleção só, e não")
    w("134 decisões separadas. A coerência entre elas vale mais do que o capricho de")
    w("qualquer uma: numa lista de oito, uma imagem fora do padrão salta mais do que oito")
    w("imagens medianas.")
    w("")

    # ── Onde as imagens aparecem ────────────────────────────────────────────────────
    w("## 1. Onde essas imagens aparecem, e em que tamanho")
    w("")
    w("Medido no CSS do aplicativo, não estimado:")
    w("")
    w("| onde | tamanho na tela |")
    w("|---|---|")
    w("| editor de programa | 48 x 48 px |")
    w("| lista da sessão do dia | **55 x 54 px** |")
    w("| biblioteca de treinos | 56 x 56 px |")
    w("| troca de exercício | 56 x 56 px |")
    w("| prévia do programa | 56 x 56 px |")
    w("| cabeçalho do exercício durante o treino | 64 x 64 px |")
    w("")
    w("São seis lugares e o maior tem **64 px**. A arte é entregue grande e o celular")
    w("reduz, então tudo é julgado num quadrado do tamanho de uma unha do polegar, em tela")
    w("escura, numa lista de 5 a 8 seguidas.")
    w("")
    w("O que sobrevive a essa redução é **a silhueta do corpo e o aparelho**. Rosto, textura")
    w("de parede, gente ao fundo e detalhe de roupa não sobrevivem, e ainda competem com o")
    w("nome do exercício, que está escrito bem ao lado.")
    w("")

    # ── As duas entregas ────────────────────────────────────────────────────────────
    w("## 2. Duas entregas, nesta ordem")
    w("")
    w("### Entrega 1: o ÍCONE (prioridade)")
    w("")
    w("É o que o aplicativo usa hoje, nos seis lugares acima. Substituir os 134 é o ganho")
    w("imediato e não depende de nada ser programado.")
    w("")
    w("| item | valor |")
    w("|---|---|")
    w("| gerar em | 1024 x 1024 (quadrado) |")
    w("| entregar em | **512 x 512, `.webp`**, até 80 KB |")
    w("| conteúdo | **um único momento** do exercício, sem seta, sem sequência |")
    w("| momento | o ponto mais reconhecível do movimento, normalmente o fim da contração |")
    w("| nome | `<id>-v2.webp` |")
    w("")
    w("### Entrega 2: a FICHA DE EXECUÇÃO")
    w("")
    w("Esta é nova. Hoje o FORGE não tem nenhum campo de execução por exercício: durante o")
    w("treino ele mostra nome, repetições, RIR e descanso, e nada sobre como fazer o")
    w("movimento. Quem não sabe executar sai do aplicativo no meio da série. A ficha é o que")
    w("tapa esse buraco, aberta em tela cheia ao tocar no exercício.")
    w("")
    w("| item | valor |")
    w("|---|---|")
    w("| gerar em | **1536 x 1024 (paisagem)** |")
    w("| entregar em | 1200 x 800, `.webp`, até 220 KB |")
    w("| conteúdo | **dois quadros** lado a lado: início e fim do movimento |")
    w("| seta | **uma só**, entre os dois quadros, indicando o sentido da fase de força |")
    w("| nome | `<id>-exec-v1.webp` |")
    w("")
    w("Dois quadros e não três: com três, cada corpo perde um terço da largura justamente na")
    w("tela em que a pessoa está olhando para aprender o movimento. Menos quadros, corpo")
    w("maior, execução mais clara.")
    w("")
    w("Paisagem e não quadrado: a ficha ocupa a largura da tela do celular. Em quadrado se")
    w("paga por altura que vai sobrar.")
    w("")
    w("Se só der para fazer uma das duas entregas, faça a **1**. O ícone vai para seis telas")
    w("que já existem; a ficha precisa de uma tela que ainda será construída.")
    w("")

    # ── A cena ──────────────────────────────────────────────────────────────────────
    w("## 3. A cena, igual nas 134")
    w("")
    w("O FORGE é escuro, com acento champanhe (`#e0b685`) e tipografia sóbria. As imagens")
    w("atuais são fotografias de academia em luz baixa e quente, e o caminho é esse mesmo,")
    w("melhor executado. Fotografia realista, não ilustração e não 3D.")
    w("")
    w("| elemento | como deve ser |")
    w("|---|---|")
    w("| fundo | academia escura, desfocada, entre `#0b0d0c` e `#151817` |")
    w("| luz | baixa e quente, vindo de lado, recortando o corpo do fundo |")
    w("| pessoas em cena | **uma só**, a que executa |")
    w("| roupa | preta ou grafite, lisa, sem marca, sem estampa, sem cor forte |")
    w("| físico | atlético e realista, não fisiculturista, não modelo de banco de imagem |")
    w("| enquadramento | corpo inteiro, ocupando cerca de 80% da altura do quadro |")
    w("| câmera | na altura do tronco, ângulo de 3/4 que deixa o movimento legível |")
    w("| aparelho | sempre visível e identificável, é metade da informação |")
    w("")
    w("### O que não pode aparecer")
    w("")
    w("- **Moldura, borda ou canto arredondado.** O aplicativo já desenha a moldura: borda")
    w("  de 1 px em `#554739`, canto de 9 px, com `object-fit: contain`. Arte com moldura")
    w("  própria vira moldura dentro de moldura. Entregue o quadro cheio, sangrado.")
    w("- **Texto, número, logo ou marca de água.** O nome do exercício já está ao lado, e")
    w("  texto some antes de tudo na redução para 55 px.")
    w("- **Seta no ícone.** Seta é da ficha de execução. No ícone, a 55 px, uma seta ocupa")
    w("  cerca de 1 px e vira um risco colorido sem sentido.")
    w("- **Fundo claro, branco ou recortado.** A tela do aplicativo é preta.")
    w("- **Rosto em close, expressão de esforço, outra pessoa observando, espelho.**")
    w("")

    # ── Modelo ──────────────────────────────────────────────────────────────────────
    w("## 4. Homem e mulher, alternados")
    w("")
    w("Hoje as 134 imagens são o mesmo modelo masculino, do primeiro ao último grupo")
    w("muscular. Uma atleta mulher usa o FORGE inteiro sem se ver uma vez.")
    w("")
    w("A coluna **Modelo** de cada tabela já resolve isso, e não é para ser sorteada na")
    w("hora: o rodízio alterna dentro de cada grupo muscular e troca o pé a cada grupo, de")
    w("modo que qualquer sessão de treino venha misturada. Ficam "
      f"**{homens} com modelo masculino** e **{len(modelo) - homens} com modelo feminino**.")
    w("")
    w("Tudo o mais fica igual entre os dois: mesma academia, mesma luz, mesma roupa preta")
    w("lisa, mesmo enquadramento. O que muda é quem executa, e só.")
    w("")

    # ── Nome dos arquivos ───────────────────────────────────────────────────────────
    w("## 5. Nome dos arquivos")
    w("")
    w("O ícone novo é `<id>-v2.webp`, e não `-v1`. O aplicativo referencia a imagem pelo")
    w("nome: trocar o conteúdo mantendo o nome deixa a imagem velha no cache do celular de")
    w("quem já usou o FORGE, e a pessoa continua vendo a arte antiga sem saber por quê.")
    w("")
    w("A coluna **Arte atual** de cada tabela mostra o arquivo que está no ar hoje.")
    w("")

    # ── Prompt ──────────────────────────────────────────────────────────────────────
    w("## 6. Prompt pronto")
    w("")
    w("Os campos entre chaves vêm da linha do exercício na tabela.")
    w("")
    w("### Ícone")
    w("")
    w("```")
    w("Fotografia realista de academia premium, luz baixa e quente vindo de lado,")
    w("fundo escuro e desfocado (#0b0d0c a #151817).")
    w("Uma única pessoa: {Modelo}, físico atlético e realista, roupa de treino preta")
    w("lisa, sem marca e sem estampa.")
    w("Exercício: {Exercício}. Equipamento visível e identificável: {Equipamento}.")
    w("Execução {Execução}.")
    w("Corpo inteiro, ocupando cerca de 80% da altura do quadro, centralizado,")
    w("câmera na altura do tronco, ângulo de 3/4 que deixa o movimento legível.")
    w("Momento: o ponto mais reconhecível do exercício, no fim da fase de contração.")
    w("Quadrado 1024x1024, sangrado até a borda.")
    w("Sem texto, sem número, sem seta, sem logo, sem moldura, sem borda,")
    w("sem canto arredondado, sem fundo branco, sem outra pessoa em cena.")
    w("```")
    w("")
    w("### Ficha de execução")
    w("")
    w("```")
    w("Mesma pessoa, mesma academia, mesma luz e mesma roupa da imagem anterior.")
    w("Composição em paisagem 1536x1024, dividida em dois quadros lado a lado:")
    w("  quadro da esquerda: posição inicial de {Exercício}")
    w("  quadro da direita: posição final de {Exercício}")
    w("Uma única seta fina entre os dois quadros, cor champanhe #e0b685,")
    w("indicando o sentido da fase de força.")
    w("Corpo inteiro nos dois quadros, mesmo enquadramento e mesma escala nos dois.")
    w("Equipamento visível: {Equipamento}.")
    w("Sem texto, sem número, sem logo, sem moldura, sem borda.")
    w("```")
    w("")

    # ── Avisos ──────────────────────────────────────────────────────────────────────
    if compartilhadas:
        w("## 7. Antes de começar")
        w("")
        for src, ids in compartilhadas.items():
            nomes = [next(e["name"] for e in exercicios if e["id"] == i) for i in ids]
            w(f"- `{os.path.basename(src)}` é usada por **{len(ids)}** exercícios: "
              + ", ".join(f"`{i}` ({n})" for i, n in zip(ids, nomes)) + ".")
            if len(set(nomes)) == 1:
                w("  Os dois têm o mesmo nome, o mesmo músculo, a mesma máquina e a mesma")
                w("  faixa de repetição: é o mesmo exercício cadastrado duas vezes. Gere uma")
                w("  arte só. Quem precisa de conserto é o catálogo, não a arte.")
        w("")

    # ── Tabelas ─────────────────────────────────────────────────────────────────────
    w("## 8. Os 134 exercícios")
    w("")
    w("| coluna | para que serve |")
    w("|---|---|")
    w("| **Exercício** | o nome que aparece ao lado da imagem no aplicativo |")
    w("| **Modelo** | quem executa, já alternado |")
    w("| **id** | o nome do arquivo sai daqui: `<id>-v2.webp` |")
    w("| **Equipamento** | o que precisa estar visível na cena |")
    w("| **Execução** | bilateral (os dois lados juntos) ou unilateral (um lado por vez) |")
    w("| **Tipo** | composto (vários músculos) ou isolado (um só) |")
    w("| **Também trabalha** | ajuda a escolher o ângulo que mostra o alvo principal |")
    w("| **Arte atual** | o arquivo que será substituído |")
    w("")
    w("---")
    w("")

    total = 0
    for grupo in ordenados:
        itens = sorted(grupos[grupo], key=lambda e: e["name"])
        total += len(itens)
        w(f"### {grupo}")
        w("")
        w(f"*{len(itens)} exercício{'s' if len(itens) > 1 else ''}*")
        w("")
        w("| Exercício | Modelo | id | Equipamento | Execução | Tipo | Também trabalha | Arte atual |")
        w("|---|---|---|---|---|---|---|---|")
        for e in itens:
            sec = ", ".join(musculo(m) for m in (e.get("secondary_muscles") or [])) or "nenhum"
            w(f"| **{e['name']}** | {modelo[e['id']]} | `{e['id']}` "
              f"| {equipamentos(e.get('equipment'))} "
              f"| {LATERALIDADE.get(e.get('laterality'), e.get('laterality') or 'nenhum')} "
              f"| {CATEGORIA.get(e.get('category'), e.get('category') or 'nenhum')} "
              f"| {sec} | `{arte.get(e['id'], 'SEM ARTE')}` |")
        w("")

    w("---")
    w("")
    w("## Conferência")
    w("")
    w(f"- exercícios no catálogo: **{len(exercicios)}**")
    w(f"- listados acima: **{total}**")
    w(f"- grupos musculares: **{len(grupos)}**")
    w(f"- modelo masculino: **{homens}** | modelo feminino: **{len(modelo) - homens}**")
    w(f"- arquivos de arte distintos hoje: **{len(set(arte.values()))}**")
    w("")
    w("Se os dois primeiros números forem diferentes, este documento está incompleto e não")
    w("deve ser usado para encomendar nada.")
    w("")

    io.open(SAIDA, "w", encoding="utf-8").write("\n".join(linhas))
    print(f"{len(exercicios)} exercicios, {len(grupos)} grupos, "
          f"{homens} homem / {len(modelo)-homens} mulher, {len(linhas)} linhas")


if __name__ == "__main__":
    main()

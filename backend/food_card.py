# -*- coding: utf-8 -*-
"""Forge Food Card: a lógica que decide o que cada alimento mostra no infográfico.

O que este módulo NÃO faz
-------------------------
Não calcula macro nenhum. Os números vêm de `food_snapshot`, que é o que o FORGE já grava
quando o atleta registra uma refeição:

    {"foods": [{"food_id", "name", "grams", "kcal", "protein_g", "carbs_g", "fat_g"}],
     "totals": {"kcal", "protein_g", "carbs_g", "fat_g"}}

Duplicar essa conta aqui criaria dois totais para a mesma comida, e dois totais diferentes
para a mesma comida destroem a confiança nos dois. O Food Card LÊ a refeição registrada.

O que este módulo decide
------------------------
Três coisas por alimento, todas determinísticas e todas editáveis depois pelo atleta:

  ÍCONE          de que categoria é o alimento
  MACRO PRINCIPAL qual macro o representa
  DESCRIÇÃO      uma frase de uma biblioteca fechada

A descrição é fechada de propósito. Deixar um modelo escrever "rico em antioxidantes que
combatem o envelhecimento" numa peça que o atleta publica no Instagram é alegação
nutricional inventada, com o nome do FORGE em cima. Quando não há frase segura para um
alimento, o card sai sem descrição — o que é diferente de inventar uma.
"""
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ── Macros ──────────────────────────────────────────────────────────────────────────

PROTEINA = "protein"
CARBOIDRATO = "carbs"
GORDURA = "fat"

MACROS = (PROTEINA, CARBOIDRATO, GORDURA)

CAMPO_DO_MACRO = {PROTEINA: "protein_g", CARBOIDRATO: "carbs_g", GORDURA: "fat_g"}
ROTULO_DO_MACRO = {PROTEINA: "PROTEÍNA", CARBOIDRATO: "CARBOIDRATOS", GORDURA: "GORDURA"}

# Quilocalorias por grama. É o que permite comparar macros na mesma moeda: 10 g de gordura
# pesam mais na refeição do que 15 g de carboidrato, e comparar só as gramas inverteria a
# resposta.
KCAL_POR_GRAMA = {PROTEINA: 4.0, CARBOIDRATO: 4.0, GORDURA: 9.0}

# ── Ícones ──────────────────────────────────────────────────────────────────────────

ICONE_GENERICO = "generic-food"

ICONES = ("beef", "chicken", "fish", "egg", "rice", "oats", "bread", "pasta", "potato",
          "sweet-potato", "pumpkin", "fruit", "vegetables", "dairy", "whey", "nuts",
          ICONE_GENERICO)

# Trechos de nome para categoria. A busca é por trecho porque o catálogo do FORGE mistura
# nomes curtos ("Ovo") com nomes de rótulo ("Whey Protein Concentrado — Growth"), e um
# mapa por id exato precisaria de uma linha por alimento dos milhares do catálogo.
#
# A ORDEM importa: "batata doce" precisa ser testada antes de "batata", senão ela cai no
# ícone da batata comum. Por isso é uma lista de pares, e não um dicionário.
_POR_NOME: List[Tuple[Tuple[str, ...], str]] = [
    (("batata doce", "batata-doce"), "sweet-potato"),
    (("moranga", "abóbora", "abobora", "cabotiá", "cabotia"), "pumpkin"),
    (("whey", "albumina", "caseína", "caseina", "proteína isolada"), "whey"),
    (("ovo", "clara de ovo", "codorna"), "egg"),
    (("frango", "peito de frango", "peru", "chester"), "chicken"),
    (("carne", "patinho", "alcatra", "acém", "acem", "costela", "picanha", "maminha",
      "coxão", "coxao", "músculo", "musculo", "bovina", "boi", "porco", "suína",
      "suina", "lombo", "bisteca"), "beef"),
    (("peixe", "tilápia", "tilapia", "salmão", "salmao", "atum", "sardinha", "merluza",
      "bacalhau", "camarão", "camarao"), "fish"),
    (("arroz",), "rice"),
    (("aveia", "granola", "farelo de aveia"), "oats"),
    (("pão", "pao", "torrada", "tapioca", "cuscuz"), "bread"),
    (("macarrão", "macarrao", "massa", "espaguete", "penne", "talharim"), "pasta"),
    (("batata", "mandioca", "aipim", "macaxeira", "inhame", "cará", "cara"), "potato"),
    (("leite", "iogurte", "queijo", "requeijão", "requeijao", "ricota", "cottage",
      "coalhada"), "dairy"),
    (("castanha", "amendoim", "amêndoa", "amendoa", "nozes", "pistache", "avelã",
      "avela", "pasta de amendoim"), "nuts"),
    (("banana", "maçã", "maca", "laranja", "mamão", "mamao", "abacaxi", "morango",
      "uva", "manga", "melancia", "pera", "kiwi", "abacate", "fruta"), "fruit"),
    (("brócolis", "brocolis", "couve", "alface", "espinafre", "tomate", "cenoura",
      "abobrinha", "berinjela", "pepino", "beterraba", "chuchu", "vagem", "legume",
      "salada", "verdura"), "vegetables"),
]


def icone_de(nome: str) -> str:
    """A categoria visual do alimento. Nunca falha: cai no genérico.

    Falta de ícone não pode impedir a criação do card — um alimento sem categoria
    conhecida ainda tem nome, quantidade e macro, que é o que a peça precisa mostrar.
    """
    texto = str(nome or "").strip().lower()
    for trechos, icone in _POR_NOME:
        if any(t in texto for t in trechos):
            return icone
    return ICONE_GENERICO


# ── Descrições ──────────────────────────────────────────────────────────────────────
#
# Biblioteca FECHADA. Cada chave é uma frase que um nutricionista assinaria, e nenhuma
# delas promete efeito, cura ou resultado. Quando o alimento não se encaixa em nenhuma,
# o card sai sem descrição, que é diferente de inventar uma.

DESCRICOES: Dict[str, str] = {
    "protein_source": "Fonte de proteína de alto valor biológico",
    "lean_protein": "Fonte de proteína com baixo teor de gordura",
    "complex_carb": "Fonte de carboidratos complexos e fibras",
    "simple_carb": "Fonte de carboidratos de rápida absorção",
    "fat_source": "Fonte de gorduras",
    "vegetable": "Fonte de fibras e micronutrientes",
    "dairy": "Fonte de proteína e cálcio",
}

# Do ícone para a descrição. É a mesma categorização, então derivar daqui evita uma
# segunda tabela de trechos de nome que poderia discordar da primeira.
_DESCRICAO_POR_ICONE = {
    "beef": "protein_source",
    "chicken": "lean_protein",
    "fish": "protein_source",
    "egg": "protein_source",
    "whey": "protein_source",
    "dairy": "dairy",
    "rice": "complex_carb",
    "oats": "complex_carb",
    "bread": "complex_carb",
    "pasta": "complex_carb",
    "potato": "complex_carb",
    "sweet-potato": "complex_carb",
    "pumpkin": "complex_carb",
    "fruit": "simple_carb",
    "vegetables": "vegetable",
    "nuts": "fat_source",
}


def descricao_de(icone: str) -> Optional[str]:
    """A CHAVE da descrição, ou None. O texto sai de `DESCRICOES`.

    Guardar a chave, e não a frase, permite corrigir o texto depois sem reescrever os
    Food Cards já salvos.
    """
    return _DESCRICAO_POR_ICONE.get(icone)


# ── Macro principal ─────────────────────────────────────────────────────────────────

# Categorias com resposta conhecida, que a conta de energia erraria.
#
# O caso que mostrou isto foi a carne moída da própria referência visual: 38 g de proteína
# contra 22 g de gordura são 152 kcal contra 198, ou seja, pela energia ela sairia como
# "fonte de gordura". Nenhum treinador, nenhum rótulo e nenhuma pessoa descreve carne
# moída assim — e a referência que define esta feature traz, em letra grande,
# CARNE MOÍDA / PROTEÍNA.
#
# O mesmo vale para todo corte gorduroso: costela, picanha, salmão. A conta de energia é
# a regra geral e continua valendo para o resto; estas categorias são a exceção declarada.
_MACRO_FIXO = {
    "beef": PROTEINA,
    "chicken": PROTEINA,
    "fish": PROTEINA,
    "egg": PROTEINA,
    "whey": PROTEINA,
    "nuts": GORDURA,
    "vegetables": CARBOIDRATO,
}


def macro_principal(alimento: Dict[str, Any], icone: Optional[str] = None) -> str:
    """O macro que representa este alimento.

    Regra: quando a categoria tem resposta conhecida, ela vence; senão, ganha o macro que
    mais contribui com ENERGIA, e não com gramas. Comparar gramas diria que 15 g de
    carboidrato pesam mais que 10 g de gordura, quando são 60 kcal contra 90.
    """
    icone = icone or icone_de(alimento.get("name"))
    if icone in _MACRO_FIXO:
        return _MACRO_FIXO[icone]

    energia = {m: float(alimento.get(CAMPO_DO_MACRO[m]) or 0) * KCAL_POR_GRAMA[m]
               for m in MACROS}
    if not any(energia.values()):
        return PROTEINA
    # `max` com chave explícita para o desempate ser estável: proteína, carboidrato,
    # gordura, na ordem de `MACROS`. Sem isso, dois macros empatados dariam resultados
    # diferentes conforme a ordem do dicionário.
    return max(MACROS, key=lambda m: (energia[m], -MACROS.index(m)))


# ── Posicionamento automático ───────────────────────────────────────────────────────
#
# Coordenadas NORMALIZADAS (0 a 1), e não pixels. É o que faz a mesma composição valer
# para a prévia no celular, a prévia no desktop e a exportação em 1080x1920.
#
# As áreas seguras evitam o logo (topo esquerdo) e o resumo (base). Os cards nascem nos
# cantos e o atleta ajusta depois; o âncora nasce puxado para o centro, que é onde a
# comida costuma estar numa foto de prato.

AREAS_SEGURAS = {
    "top-left": (0.06, 0.16),
    "top-right": (0.52, 0.16),
    "bottom-left": (0.06, 0.60),
    "bottom-right": (0.52, 0.60),
}

# Por quantidade de alimentos, quais cantos usar e em que ordem. A especificação define
# isto, e a ordem importa: com dois alimentos, cantos opostos deixam a foto respirar no
# meio, que é onde está o prato.
ORDEM_DOS_CANTOS = {
    1: ["top-left"],
    2: ["top-left", "bottom-right"],
    3: ["top-left", "bottom-left", "bottom-right"],
    4: ["top-left", "top-right", "bottom-left", "bottom-right"],
}

MAXIMO_DE_ITENS = 4

# Para onde o âncora aponta em cada canto.
#
# Duas correções, as duas medidas em peças exportadas:
#
#   A primeira versão punha o âncora a poucos pixels do próprio card, e o conector virava
#   um risco curto que não apontava nada.
#
#   A segunda mandou cada âncora para o lado OPOSTO ao card, e aí as linhas dos dois cards
#   de baixo se cruzaram no meio da peça. Duas linhas cruzadas numa arte de três elementos
#   é o tipo de coisa que denuncia que ninguém olhou o resultado.
#
# A regra que funciona: o âncora vai para o miolo da foto, que é onde a comida está, MAS
# fica do mesmo lado do card. Assim a linha atravessa imagem sem esbarrar na do vizinho.
_ANCORA_DO_CANTO = {
    "top-left": (0.44, 0.48),
    "top-right": (0.58, 0.50),
    "bottom-left": (0.42, 0.44),
    "bottom-right": (0.60, 0.46),
}


def posicionar(quantidade: int) -> List[Dict[str, float]]:
    """As posições iniciais de card e âncora, normalizadas."""
    quantidade = max(1, min(MAXIMO_DE_ITENS, int(quantidade or 1)))
    posicoes = []
    for canto in ORDEM_DOS_CANTOS[quantidade]:
        cx, cy = AREAS_SEGURAS[canto]
        ax, ay = _ANCORA_DO_CANTO[canto]
        posicoes.append({"cardX": cx, "cardY": cy, "anchorX": ax, "anchorY": ay})
    return posicoes


# ── Montagem dos itens ──────────────────────────────────────────────────────────────

def montar_itens(alimentos: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """De alimentos de uma refeição registrada para itens do Food Card.

    Os macros entram exatamente como foram gravados. Nada é recalculado.
    """
    escolhidos = list(alimentos)[:MAXIMO_DE_ITENS]
    posicoes = posicionar(len(escolhidos)) if escolhidos else []
    itens = []
    for alimento, posicao in zip(escolhidos, posicoes):
        icone = icone_de(alimento.get("name"))
        itens.append({
            "foodId": alimento.get("food_id"),
            "name": alimento.get("name") or "Alimento",
            "quantity": float(alimento.get("grams") or 0),
            "unit": "g",
            "calories": float(alimento.get("kcal") or 0),
            "protein": float(alimento.get("protein_g") or 0),
            "carbs": float(alimento.get("carbs_g") or 0),
            "fat": float(alimento.get("fat_g") or 0),
            "iconKey": icone,
            "descriptionKey": descricao_de(icone),
            "primaryMacro": macro_principal(alimento, icone),
            **posicao,
        })
    return itens


def resumo(totais: Dict[str, Any]) -> Dict[str, float]:
    """Os totais da refeição COMPLETA, mesmo quando só quatro alimentos viram card.

    A especificação é explícita: destacar quatro não pode fazer o rodapé mentir sobre o
    que a pessoa comeu.
    """
    return {
        "protein": round(float(totais.get("protein_g") or 0)),
        "carbs": round(float(totais.get("carbs_g") or 0)),
        "fat": round(float(totais.get("fat_g") or 0)),
        "calories": round(float(totais.get("kcal") or 0)),
    }

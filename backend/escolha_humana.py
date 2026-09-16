# -*- coding: utf-8 -*-
"""A pergunta que um treinador faz, no lugar de uma lista de macros.

Por que este modulo existe
--------------------------
O FORGE ja sabia montar a refeicao inteira sozinho, e sabia bem: `MEAL_COMBOS` guarda
combinacoes nomeadas ("Mingau FORGE", "Pre-treino sem fruta do metodo") e
`find_substitutes` ja calcula a porcao certa de cada alternativa simulando a refeicao
inteira — "150 g de frango" vira "128 g de patinho", e nao uma regra de tres.

O que faltava era PERGUNTAR. Toda essa capacidade estava atras de um botao de troca, item
por item, depois do plano pronto. A pessoa recebia um prato fechado e tinha de brigar com
ele.

O treinador descreveu o que ele queria como um Subway: primeiro voce escolhe o formato do
prato, depois voce escolhe a carne.

    "Pre-treino: ou farinha de arroz e whey, ou farinha de arroz e aveia, ou whey e aveia."
    "Pos-treino: escolha a sua carne. Quando a pessoa nao tem frango, ela tem um patinho."
    "Almoco: o que voce quer? Patinho, salmao, file suino."

Entao sao duas perguntas, e nao uma tela de numeros:

  1. QUAL COMBINACAO — as montagens prontas daquela refeicao, cada uma com a porcao ja
     calculada e as calorias fechadas.
  2. QUAL ALIMENTO DENTRO DELA — para cada espaco que aceita troca, as alternativas com a
     grama certa de cada uma.

Este modulo nao inventa comida nem matematica: ele so junta as duas capacidades que ja
existiam e devolve no formato de uma pergunta. Toda porcao vem do motor.
"""
from typing import Any, Dict, List, Optional

from nutrition_engine import (
    FOOD_INDEX,
    _infer_meal_type,
    _score_food,
    find_substitutes,
    get_meal_archetype_options,
    tolerancia_de_caloria,
)

# Como o FORGE chama cada refeicao quando fala com a pessoa. O tom importa: a tela existe
# justamente para deixar de soar como planilha.
PERGUNTA_DA_REFEICAO = {
    "breakfast": "O que você vai comer no café da manhã?",
    "pre_workout": "O que você vai comer antes de treinar?",
    "post_workout": "E depois do treino?",
    "lunch": "O que você quer no almoço?",
    "dinner": "E no jantar?",
    "snack": "O que você quer no lanche?",
    # Lanche da manha e prato salgado pequeno, e nao shake — entao a pergunta tambem muda.
    "morning_snack": "E no lanche da manhã?",
}

# O rotulo de cada espaco trocavel, na ordem em que faz sentido perguntar: a carne
# primeiro, porque e ela que a pessoa tem ou nao tem em casa.
ESPACOS_TROCAVEIS = [
    ("primary_protein", "Escolha sua proteína", "É ela que manda no prato."),
    ("primary_carb", "Escolha seu carboidrato", "O que vai junto."),
    ("legume", "Escolha sua leguminosa", "Feijão, lentilha, grão-de-bico."),
    ("vegetable", "Escolha seu legume", "Volume no prato, quase sem caloria."),
    ("fruit", "Escolha sua fruta", ""),
    ("fat_source", "Escolha sua gordura", "Entra em pouca quantidade."),
]

# Quantas alternativas pedir ao motor por espaco. O padrao de `find_substitutes` e tres, e
# tres esconde justamente o caso que o treinador citou: quem nao tem frango precisa ver o
# patinho, o suino e o ovo na mesma lista.
MAX_ALTERNATIVAS = 12


# A ordem em que um papel vale mais do que outro quando o alimento tem varios. O whey, por
# exemplo, declara ["recipe_component", "secondary_protein", "primary_protein"]: pegar o
# primeiro da lista fazia dele um "componente de receita", e a pergunta "escolha sua
# proteina" simplesmente sumia do pre-treino.
ORDEM_DOS_PAPEIS = [papel for papel, _, _ in ESPACOS_TROCAVEIS]


def _nome(food_id: str) -> str:
    return FOOD_INDEX.get(food_id, {}).get("name", food_id)


def _papel_do(food_id: str) -> Optional[str]:
    papeis = FOOD_INDEX.get(food_id, {}).get("roles") or []
    for papel in ORDEM_DOS_PAPEIS:
        if papel in papeis:
            return papel
    return papeis[0] if papeis else None


def _macros_do_item(food_id: str, gramas: float) -> Dict[str, float]:
    f = FOOD_INDEX.get(food_id) or {}
    base = max(1.0, float(f.get("grams") or 100))
    fator = float(gramas) / base
    return {
        "kcal": round(float(f.get("kcal") or 0) * fator, 1),
        "protein_g": round(float(f.get("protein_g") or 0) * fator, 1),
        "carbs_g": round(float(f.get("carbs_g") or 0) * fator, 1),
        "fat_g": round(float(f.get("fat_g") or 0) * fator, 1),
    }


def _somar(itens: List[Dict[str, Any]]) -> Dict[str, float]:
    total = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for it in itens:
        m = _macros_do_item(it["food_id"], it["gramas"])
        for k in total:
            total[k] += m[k]
    return {k: round(v) for k, v in total.items()}


def _itens_da_opcao(opcao: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Os alimentos de uma montagem, com a porcao que o motor calculou para ela."""
    itens = []
    for it in (opcao.get("meal") or {}).get("foods") or []:
        fid = it.get("food_id")
        if not fid:
            continue
        gramas = round(float(it.get("grams") or 0))
        itens.append({
            "food_id": fid,
            "nome": _nome(fid),
            "gramas": gramas,
            "papel": _papel_do(fid),
            **_macros_do_item(fid, gramas),
        })
    return itens


def _combinacao(opcao: Dict[str, Any]) -> Dict[str, Any]:
    itens = _itens_da_opcao(opcao)
    return {
        "id": opcao.get("archetype_id"),
        "titulo": opcao.get("label"),
        # O que a pessoa le antes de escolher: os alimentos, e nao o id da combinacao.
        "resumo": " + ".join(i["nome"] for i in itens),
        "do_metodo": bool(opcao.get("metodo")),
        "itens": itens,
        **_somar(itens),
    }


def _alternativas_do_espaco(item: Dict[str, Any], itens: List[Dict[str, Any]],
                            perfil: Dict[str, Any], goal: str,
                            tipo: str) -> List[Dict[str, Any]]:
    """As trocas possiveis para UM alimento da montagem, cada uma com a grama dela.

    A porcao nao e estimada aqui: `find_substitutes` simula a refeicao inteira com o
    substituto no lugar e devolve quantos gramas aquele alimento precisa ter para ocupar o
    mesmo papel. E por isso que 150 g de frango viram 128 g de patinho e 62 g de whey, em
    vez de 150 g de tudo.
    """
    encontrados = find_substitutes(
        item["food_id"], perfil, [i["food_id"] for i in itens],
        max_results=MAX_ALTERNATIVAS, orig_grams=item["gramas"], goal=goal,
        meal_type=tipo, validate_daily=False,
    )
    opcoes = [{
        "food_id": item["food_id"],
        "nome": item["nome"],
        "gramas": item["gramas"],
        "atual": True,
        **_macros_do_item(item["food_id"], item["gramas"]),
    }]
    alternativas = []
    for achado in encontrados:
        # find_substitutes devolve (id, gramas, observacao).
        fid, gramas = achado[0], round(float(achado[1]))
        if fid == item["food_id"] or gramas <= 0:
            continue
        alternativas.append({
            "food_id": fid,
            "nome": _nome(fid),
            "gramas": gramas,
            "atual": False,
            **_macros_do_item(fid, gramas),
        })

    # A ordem da lista e uma recomendacao silenciosa: o que estiver no topo e o que a
    # maioria vai escolher. Entao ela segue a pontuacao do metodo, que ja pesa o que serve
    # naquela refeicao, o que a pessoa gosta e o preco — frango e patinho na frente,
    # salmao no fim. O alimento atual fica sempre em primeiro, porque ele e o padrao.
    alternativas.sort(key=lambda o: -_score_food(FOOD_INDEX.get(o["food_id"], {}), tipo, perfil, goal))
    return opcoes + alternativas


def escolhas_da_refeicao(nome_da_refeicao: str, perfil: Dict[str, Any],
                         alvo: Dict[str, Any], goal: str = "maintenance",
                         combinacao_escolhida: Optional[str] = None,
                         usados: Optional[List[str]] = None) -> Dict[str, Any]:
    """As duas perguntas daquela refeicao, prontas para virar tela.

    `combinacao_escolhida` decide de qual montagem saem as trocas. Sem ela, vale a
    primeira — que e a mais bem pontuada e, quando existe, a do metodo do treinador.
    """
    tipo = _infer_meal_type(nome_da_refeicao)
    alvo_cal = float(alvo.get("kcal") or alvo.get("target_cal") or 0)
    alvo_prot = float(alvo.get("protein_g") or alvo.get("target_protein") or 0)
    alvo_gord = float(alvo.get("fat_g") or alvo.get("target_fat") or 0)

    opcoes = get_meal_archetype_options(
        nome_da_refeicao, alvo_cal, alvo_prot, alvo_gord, perfil,
        set(usados or []), goal=goal,
    )
    combinacoes = [_combinacao(o) for o in opcoes]
    combinacoes = [c for c in combinacoes if c["itens"]]

    escolhida = None
    if combinacao_escolhida:
        escolhida = next((c for c in combinacoes if c["id"] == combinacao_escolhida), None)
    if escolhida is None and combinacoes:
        escolhida = combinacoes[0]

    trocas = []
    if escolhida:
        por_papel = {i["papel"]: i for i in escolhida["itens"] if i.get("papel")}
        for papel, rotulo, explicacao in ESPACOS_TROCAVEIS:
            item = por_papel.get(papel)
            if not item:
                continue
            alternativas = _alternativas_do_espaco(
                item, escolhida["itens"], perfil, goal, tipo)
            # Um espaco com uma opcao so nao e uma escolha: nao vira pergunta na tela.
            if len(alternativas) < 2:
                continue
            trocas.append({
                "papel": papel,
                "rotulo": rotulo,
                "explicacao": explicacao,
                "atual": item["food_id"],
                "opcoes": alternativas,
            })

    return {
        "refeicao": nome_da_refeicao,
        "tipo": tipo,
        "pergunta": PERGUNTA_DA_REFEICAO.get(tipo, "O que você quer comer?"),
        "alvo": {
            "kcal": round(alvo_cal),
            "protein_g": round(alvo_prot),
            "fat_g": round(alvo_gord),
            # A margem existe na tela para a pessoa parar de perseguir o numero exato.
            # "Numa diferenca de 150 para mais ou para menos nao faz diferenca."
            "tolerancia": round(tolerancia_de_caloria(alvo_cal)),
        },
        "combinacoes": combinacoes,
        "escolhida": escolhida["id"] if escolhida else None,
        "trocas": trocas,
    }

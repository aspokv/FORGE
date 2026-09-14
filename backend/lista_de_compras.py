# -*- coding: utf-8 -*-
"""A lista de compras da semana, a partir do plano alimentar.

O plano do FORGE pesa o alimento NO PRATO, ja pronto: "250 g de arroz branco cozido". No
mercado se compra cru, e arroz cozido pesa quase tres vezes o cru porque absorveu agua. Uma
lista que mandasse comprar 1,75 kg de arroz faria a pessoa levar o triplo do que precisa — e
lista que erra por tres e pior que lista nenhuma.

Por isso o coracao deste modulo e a tabela de rendimento. Ela e aproximada por natureza (o
mesmo corte de frango perde mais ou menos agua conforme o fogo), e a tela diz isso. Mas
aproximada e util; o peso do prato aplicado a compra e simplesmente errado.

O que NAO existe aqui: preco. O FORGE nao sabe quanto custa clara de ovo na cidade de
ninguem, e numero inventado num app que a pessoa usa para decidir o que comer nao se paga.
"""
from typing import Any, Dict, List, Optional

# Quanto do peso CRU sobra depois de pronto. Peso de compra = peso do prato / rendimento.
#
# Grao seco absorve agua e mais que dobra; carne perde agua e encolhe; folha murcha muito.
# Espinafre e o extremo: quatro quilos de folha crua viram um quilo refogado, e quem confia
# no peso pronto compra um quarto do que precisa.
RENDIMENTO = {
    # Graos e massas secos: absorvem agua.
    "rice-white": 3.00,
    "rice-brown": 2.70,
    "pasta": 2.40,
    "pasta-whole": 2.40,
    "beans-black": 2.60,
    "beans-carioca": 2.60,
    "lentils": 2.50,
    "chickpeas": 2.40,
    # Carnes e peixes: perdem agua no calor.
    "chicken-breast": 0.75,
    "chicken-thigh": 0.75,
    "beef-grill": 0.73,
    "pork-loin": 0.75,
    "salmon": 0.80,
    # Raizes e tuberculos: perdem pouca agua, mas perdem casca.
    "potato": 0.85,
    "sweet-potato": 0.85,
    "cassava": 0.72,
    "pumpkin": 0.72,
    "beetroot": 0.80,
    # Legumes e folhas.
    "broccoli": 0.82,
    "zucchini": 0.85,
    "green-beans": 0.90,
    "eggplant": 0.75,
    "spinach": 0.25,
}

# Onde cada alimento fica no mercado. Ninguem compra na ordem das refeicoes; compra na ordem
# da loja, e uma lista fora dessa ordem faz a pessoa atravessar o mercado seis vezes.
CORREDOR = {
    "acougue": "Açougue e peixaria",
    "hortifruti": "Hortifrúti",
    "mercearia": "Mercearia",
    "laticinios": "Laticínios e ovos",
    "outros": "Outros",
}

SECAO_DO_ALIMENTO = {
    "chicken-breast": "acougue", "chicken-thigh": "acougue", "beef-grill": "acougue",
    "pork-loin": "acougue", "salmon": "acougue", "tilapia": "acougue", "shrimp": "acougue",
    "tuna-can": "mercearia", "sardine-can": "mercearia",
    "eggs-whole": "laticinios", "egg-whites": "laticinios", "milk-skim": "laticinios",
    "milk-whole": "laticinios", "yogurt-natural": "laticinios", "yogurt-greek": "laticinios",
    "cheese-cottage": "laticinios", "cheese-minas": "laticinios", "whey": "outros",
    "rice-white": "mercearia", "rice-brown": "mercearia", "pasta": "mercearia",
    "pasta-whole": "mercearia", "oats": "mercearia", "beans-black": "mercearia",
    "beans-carioca": "mercearia", "lentils": "mercearia", "chickpeas": "mercearia",
    "tapioca": "mercearia", "couscous": "mercearia", "bread-white": "mercearia",
    "bread-whole": "mercearia", "peanut-butter": "mercearia", "olive-oil": "mercearia",
    "brazil-nuts": "mercearia", "cashews": "mercearia", "peanuts": "mercearia",
    "almonds": "mercearia", "chia": "mercearia", "flaxseed": "mercearia", "honey": "mercearia",
}

# Alimento que se compra por unidade, nao por peso: "14 ovos" resolve, "805 g de ovo" nao.
PESO_DA_UNIDADE = {
    "eggs-whole": (50, "ovos"),
    "egg-whites": (33, "claras"),
    "tuna-can": (120, "latas"),
    "sardine-can": (85, "latas"),
    "banana": (100, "bananas"),
    "apple": (130, "maçãs"),
    "orange": (180, "laranjas"),
}

# Palavras no nome que denunciam a secao quando o id nao esta mapeado. Ordem importa: a
# primeira que casar vence, entao o especifico vem antes do generico.
#
# O casamento e por PALAVRA INTEIRA, e nao por pedaco de texto. Com substring, "ovo" casava
# dentro de "Alimento novo" e mandava um alimento desconhecido para a secao de laticinios —
# defeito que so apareceu porque o teste usou justamente um nome com "novo" dentro.
_PISTAS = [
    ("acougue", ("frango", "carne", "bovina", "bovino", "suína", "suino", "suíno", "peixe",
                 "tilápia", "tilapia", "salmão", "salmao", "filé", "file", "camarão", "camarao",
                 "peru", "patinho", "alcatra", "picanha", "lombo", "costela", "linguiça")),
    ("laticinios", ("leite", "iogurte", "queijo", "ovo", "ovos", "clara", "claras",
                    "requeijão", "requeijao", "ricota", "manteiga", "cottage")),
    ("hortifruti", ("banana", "maçã", "maca", "laranja", "mamão", "mamao", "morango", "abacaxi",
                    "melancia", "melão", "melao", "manga", "uva", "pera", "kiwi", "abacate",
                    "batata", "cenoura", "abobrinha", "brócolis", "brocolis", "couve", "alface",
                    "tomate", "cebola", "alho", "espinafre", "beterraba", "abóbora", "abobora",
                    "berinjela", "vagem", "mandioca", "inhame", "pepino", "pimentão", "pimentao")),
]


# O plano nomeia o alimento como ele chega ao prato ("Batata inglesa cozida"), e numa lista de
# compras isso confunde: a pessoa procura batata crua na banca. O preparo sai do nome, e a
# conversao de peso ja esta feita na coluna do lado.
_PREPAROS = (" cozida", " cozido", " grelhada", " grelhado", " assada", " assado",
             " refogada", " refogado", " frita", " frito", " crua", " cru")


def nome_de_compra(nome: str) -> str:
    limpo = str(nome or "")
    for preparo in _PREPAROS:
        if limpo.lower().endswith(preparo):
            return limpo[: -len(preparo)].strip()
    return limpo


def _palavras(texto: str) -> set:
    limpo = "".join(c if c.isalnum() else " " for c in str(texto or "").lower())
    return set(limpo.split())


def _secao(food_id: str, nome: str) -> str:
    if food_id in SECAO_DO_ALIMENTO:
        return SECAO_DO_ALIMENTO[food_id]
    palavras = _palavras(nome)
    for secao, pistas in _PISTAS:
        if any(pista in palavras for pista in pistas):
            return secao
    return "mercearia"


def _quantidade_legivel(gramas: float, food_id: str) -> Dict[str, Any]:
    """Como a quantidade aparece na etiqueta.

    Quando o alimento e vendido e contado por unidade, a UNIDADE vem na frente e o peso fica
    de apoio: ninguem pesa ovo na feira, conta. "16 ovos" e uma instrucao; "805 g de ovo" e
    uma conta que a pessoa tem de fazer no corredor, com o celular numa mao.

    Nos demais, o peso manda — nao existe "unidade" de arroz.
    """
    peso_texto = f"{gramas / 1000:.2f} kg".replace(".", ",") if gramas >= 1000 else f"{round(gramas)} g"
    if food_id in PESO_DA_UNIDADE:
        peso, rotulo = PESO_DA_UNIDADE[food_id]
        quantas = max(1, round(gramas / peso))
        return {"gramas": round(gramas), "texto": f"{quantas} {rotulo}",
                "apoio": peso_texto, "por_unidade": True}
    return {"gramas": round(gramas), "texto": peso_texto, "apoio": None, "por_unidade": False}


def montar_lista(plano: Dict[str, Any], dias: int = 7) -> Dict[str, Any]:
    """Soma o plano de um dia `dias` vezes e converte para peso de compra.

    O plano do FORGE e um template diario: as mesmas refeicoes todos os dias. Entao a semana
    e esse dia multiplicado, e se um dia o motor passar a variar o cardapio esta funcao
    acompanha sem mudanca — ela soma o que estiver no plano, nao o que supoe que esteja.
    """
    por_alimento: Dict[str, Dict[str, Any]] = {}
    for refeicao in (plano or {}).get("meals") or []:
        for item in refeicao.get("foods") or []:
            food_id = item.get("food_id")
            if not food_id:
                continue
            alimento = item.get("food") or {}
            gramas = float(item.get("grams") or 0) * dias
            if gramas <= 0:
                continue
            registro = por_alimento.setdefault(food_id, {
                "food_id": food_id,
                "nome": nome_de_compra(alimento.get("name") or food_id),
                "nome_no_plano": alimento.get("name") or food_id,
                "gramas_no_prato": 0.0,
            })
            registro["gramas_no_prato"] += gramas

    itens: List[Dict[str, Any]] = []
    for food_id, registro in por_alimento.items():
        rendimento = RENDIMENTO.get(food_id)
        prato = registro["gramas_no_prato"]
        compra = prato / rendimento if rendimento else prato
        itens.append({
            **registro,
            "gramas_no_prato": round(prato),
            "convertido": bool(rendimento),
            "rendimento": rendimento,
            "secao": _secao(food_id, registro["nome"]),
            "estado": estado_de_compra(registro["nome"]) if rendimento else None,
            "compra": _quantidade_legivel(compra, food_id),
        })

    # Dentro da secao, do maior para o menor: o que pesa mais e o que decide o carrinho.
    itens.sort(key=lambda i: -i["compra"]["gramas"])
    secoes = []
    for chave, rotulo in CORREDOR.items():
        do_corredor = [i for i in itens if i["secao"] == chave]
        if do_corredor:
            secoes.append({"chave": chave, "titulo": rotulo, "itens": do_corredor})

    return {"secoes": secoes, "total_de_itens": len(itens), "dias": dias,
            "convertidos": sum(1 for i in itens if i["convertido"])}


def peso_cru(food_id: str, gramas_prontas: float) -> Optional[int]:
    """Quantos gramas crus rendem `gramas_prontas` daquele alimento.

    O plano manda "250 g de arroz cozido" e a pessoa esta na cozinha com o pacote na mao,
    sem saber quanto medir. Sao 83 g. Esse calculo acontece TODO DIA, enquanto a compra
    acontece uma vez por semana — e por isso ele importa mais que a lista.

    Devolve None para alimento que nao muda de peso: dizer "120 g de banana = 120 g de
    banana crua" e ruido, e ruido repetido em toda linha vira poluicao.
    """
    rendimento = RENDIMENTO.get(food_id)
    if not rendimento:
        return None
    gramas = float(gramas_prontas or 0)
    if gramas <= 0:
        return None
    return round(gramas / rendimento)


def anotar_peso_cru(plano: Dict[str, Any]) -> Dict[str, Any]:
    """Acrescenta `raw_grams` em cada item do plano que muda de peso ao cozinhar.

    Feito na hora de servir, e nao dentro do motor, de proposito: isto e informacao de
    apresentacao. O motor continua calculando caloria e macro pelo peso pronto, que e como a
    tabela nutricional mede — mexer nele para uma etiqueta seria trocar a base do calculo.
    """
    if not plano:
        return plano
    for refeicao in plano.get("meals") or []:
        for item in refeicao.get("foods") or []:
            cru = peso_cru(item.get("food_id"), item.get("grams"))
            if cru:
                item["raw_grams"] = cru
    return plano


def estado_de_compra(nome: str) -> str:
    """"crus" ou "crua", conforme o nome do alimento.

    A palavra fica colada no numero na tela, e nao no rodape: quem conhece a propria dieta
    tem 1,75 kg de arroz na cabeca, e ver "583 g" solto parece erro do aplicativo. Rodape
    ninguem le; a palavra ao lado do numero nao tem como ser ignorada.
    """
    limpo = str(nome or "").strip().lower()
    primeira = limpo.split()[0] if limpo.split() else ""
    return "crua" if primeira.endswith("a") else "cru"

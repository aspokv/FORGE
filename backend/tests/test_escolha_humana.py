# -*- coding: utf-8 -*-
"""A pergunta do treinador, e nao a tela de macros.

Por que este arquivo existe
---------------------------
O treinador descreveu o que queria como um Subway: primeiro voce escolhe o formato do
prato, depois voce escolhe a carne.

    "Pre-treino: ou farinha de arroz e whey, ou farinha de arroz e aveia, ou whey e aveia."
    "Pos-treino: escolha a sua carne. Quando a pessoa nao tem frango, ela tem um patinho."
    "Almoco: o que voce quer? Patinho, salmao, file suino."
    "Se passar um pouquinho das calorias nao tem problema. 150 para mais ou para menos."

A capacidade ja existia inteira no motor — `MEAL_COMBOS` guarda as montagens nomeadas e
`find_substitutes` ja calcula a porcao de cada alternativa simulando a refeicao completa.
O que faltava era PERGUNTAR: tudo isso vivia atras de um botao de troca, item por item,
depois do plano pronto.

Estes testes prendem o formato da pergunta. Nao precisam de banco.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import nutrition_engine as ne  # noqa: E402
from escolha_humana import escolhas_da_refeicao  # noqa: E402

PERFIL = {"weight_kg": 80, "height_cm": 175, "age": 30, "sex": "male",
          "activity_level": "moderate", "training_days": 4, "meal_count": 5,
          "cooking_time": "medium", "preferred_foods": [], "disliked_foods": [],
          "avoid_foods": [], "allergies": [], "dietary_restrictions": []}

REFEICOES = [
    ("Café da manhã", {"kcal": 500, "protein_g": 35, "fat_g": 14}),
    ("Pré-treino", {"kcal": 400, "protein_g": 30, "fat_g": 8}),
    ("Pós-treino", {"kcal": 550, "protein_g": 40, "fat_g": 10}),
    ("Almoço", {"kcal": 650, "protein_g": 45, "fat_g": 18}),
    ("Lanche da tarde", {"kcal": 350, "protein_g": 25, "fat_g": 10}),
    ("Jantar", {"kcal": 600, "protein_g": 45, "fat_g": 18}),
]


def _resposta(nome, alvo, **kw):
    return escolhas_da_refeicao(nome, PERFIL, alvo, goal="maintenance", **kw)


# -- A pergunta -----------------------------------------------------------------------

@pytest.mark.parametrize("nome,alvo", REFEICOES)
def test_toda_refeicao_faz_uma_pergunta_em_portugues(nome, alvo):
    """O tom e o ponto: a tela existe para deixar de soar como planilha."""
    r = _resposta(nome, alvo)
    assert r["pergunta"].endswith("?")
    assert len(r["pergunta"]) > 10


@pytest.mark.parametrize("nome,alvo", REFEICOES)
def test_toda_refeicao_oferece_mais_de_uma_montagem(nome, alvo):
    """Uma opcao so nao e escolha. Se o motor devolvesse uma, a tela nao teria por que
    existir."""
    r = _resposta(nome, alvo)
    assert len(r["combinacoes"]) >= 2, f"{nome} ofereceu {len(r['combinacoes'])}"


# -- Primeira pergunta: qual montagem -------------------------------------------------

@pytest.mark.parametrize("nome,alvo", REFEICOES)
def test_toda_montagem_vem_com_porcao_e_caloria(nome, alvo):
    """Escolher sem ver a porcao e escolher no escuro. A grama vem do motor, sempre."""
    for c in _resposta(nome, alvo)["combinacoes"]:
        assert c["itens"], f"{c['titulo']} veio sem alimento"
        assert c["kcal"] > 0
        for item in c["itens"]:
            assert item["gramas"] > 0, f"{item['nome']} sem porcao"
            assert item["nome"] and item["nome"] != item["food_id"]


@pytest.mark.parametrize("nome,alvo", REFEICOES)
def test_a_montagem_se_apresenta_pelos_alimentos_e_nao_pelo_id(nome, alvo):
    """"Aveia em flocos + Whey" diz mais do que "forge_oats_whey_banana"."""
    for c in _resposta(nome, alvo)["combinacoes"]:
        assert " + " in c["resumo"] or len(c["itens"]) == 1
        assert "_" not in c["resumo"]


def test_o_pre_treino_oferece_as_duplas_do_metodo():
    """O pedido literal: "ou farinha de arroz e whey, ou farinha de arroz e aveia, ou whey
    e aveia"."""
    r = _resposta("Pré-treino", {"kcal": 400, "protein_g": 30, "fat_g": 8})
    conjuntos = [frozenset(i["food_id"] for i in c["itens"]) for c in r["combinacoes"]]
    duplas_do_metodo = [{"whey-protein", "oats"}, {"whey-protein", "rice-flour"}]
    assert any(frozenset(d) <= conj for d in duplas_do_metodo for conj in conjuntos), \
        "nenhuma dupla do metodo no pre-treino: %s" % (conjuntos,)


def test_a_montagem_do_metodo_vem_marcada_e_na_frente():
    """Quando existe uma do metodo, ela e a recomendacao — e recomendacao que aparece em
    quinto lugar nao e recomendacao."""
    r = _resposta("Pré-treino", {"kcal": 400, "protein_g": 30, "fat_g": 8})
    do_metodo = [i for i, c in enumerate(r["combinacoes"]) if c["do_metodo"]]
    assert do_metodo, "o pre-treino nao trouxe nenhuma montagem do metodo"
    assert do_metodo[0] == 0


# -- Segunda pergunta: qual alimento dentro dela --------------------------------------

@pytest.mark.parametrize("nome,alvo", [r for r in REFEICOES if r[0] in
                                       ("Almoço", "Jantar", "Pós-treino")])
def test_o_prato_principal_deixa_escolher_a_carne(nome, alvo):
    """"Escolha a sua carne. Quando a pessoa nao tem frango, ela tem um patinho"."""
    r = _resposta(nome, alvo)
    proteina = next((t for t in r["trocas"] if t["papel"] == "primary_protein"), None)
    assert proteina, f"{nome} nao perguntou pela proteina"
    ids = {o["food_id"] for o in proteina["opcoes"]}
    assert len(ids) >= 4, f"{nome} ofereceu so {ids}"
    assert {"beef-grill", "beef-ground"} & ids, f"nenhuma carne bovina em {ids}"


@pytest.mark.parametrize("nome,alvo", REFEICOES)
def test_toda_alternativa_traz_a_porcao_dela(nome, alvo):
    """E o pedido antigo do treinador, o mesmo de "40 gramas de whey, ou 150 de frango":
    a porcao de cada alternativa e a dela, e nao a do alimento que estava la."""
    for troca in _resposta(nome, alvo)["trocas"]:
        gramas = {o["food_id"]: o["gramas"] for o in troca["opcoes"]}
        assert all(g > 0 for g in gramas.values())
        # Alimentos de densidade diferente nao podem sair com a MESMA porcao.
        assert len(set(gramas.values())) > 1, \
            f"{troca['rotulo']}: todas as opcoes com a mesma grama {gramas}"


@pytest.mark.parametrize("nome,alvo", REFEICOES)
def test_o_alimento_atual_e_o_primeiro_e_vem_marcado(nome, alvo):
    """A tela precisa saber o que ja esta escolhido sem cruzar listas e arriscar
    discordar do servidor."""
    for troca in _resposta(nome, alvo)["trocas"]:
        assert troca["opcoes"][0]["atual"] is True
        assert troca["opcoes"][0]["food_id"] == troca["atual"]
        assert sum(1 for o in troca["opcoes"] if o["atual"]) == 1


@pytest.mark.parametrize("nome,alvo", REFEICOES)
def test_espaco_sem_alternativa_nao_vira_pergunta(nome, alvo):
    """Perguntar "escolha sua proteina" e oferecer uma so e perder o tempo da pessoa."""
    for troca in _resposta(nome, alvo)["trocas"]:
        assert len(troca["opcoes"]) >= 2


def test_a_lista_de_carne_comeca_pelo_que_o_metodo_prefere():
    """A ordem e recomendacao silenciosa: o topo e o que a maioria vai escolher. Frango e
    carne na frente, salmao e tilapia no fim — que e a regra de preco do treinador."""
    r = _resposta("Almoço", {"kcal": 650, "protein_g": 45, "fat_g": 18})
    proteina = next(t for t in r["trocas"] if t["papel"] == "primary_protein")
    ordem = [o["food_id"] for o in proteina["opcoes"]]
    for caro in ("tilapia", "salmon"):
        if caro in ordem and "chicken-breast" in ordem:
            assert ordem.index("chicken-breast") < ordem.index(caro)
        if caro in ordem and "beef-ground" in ordem:
            assert ordem.index("beef-ground") < ordem.index(caro)


def test_o_whey_e_reconhecido_como_proteina():
    """O whey declara ["recipe_component", "secondary_protein", "primary_protein"]. Ler o
    primeiro papel da lista fazia dele um "componente de receita", e a pergunta "escolha
    sua proteina" sumia do pre-treino inteiro."""
    from escolha_humana import _papel_do
    assert _papel_do("whey-protein") == "primary_protein"
    assert _papel_do("chicken-breast") == "primary_protein"
    assert _papel_do("olive-oil") == "fat_source"


# -- A margem ------------------------------------------------------------------------

@pytest.mark.parametrize("nome,alvo", REFEICOES)
def test_a_margem_viaja_junto_com_o_alvo(nome, alvo):
    """"Se passar um pouquinho nao tem problema." A margem so serve se estiver na tela: sem
    ela a pessoa persegue o numero exato, que e o oposto do que o treinador pediu."""
    r = _resposta(nome, alvo)
    assert r["alvo"]["tolerancia"] == round(ne.tolerancia_de_caloria(alvo["kcal"]))
    assert r["alvo"]["tolerancia"] >= 150


# -- Escolher uma montagem troca as perguntas de dentro -------------------------------

def test_escolher_outra_montagem_muda_as_trocas():
    r = _resposta("Almoço", {"kcal": 650, "protein_g": 45, "fat_g": 18})
    outra = next(c for c in r["combinacoes"] if c["id"] != r["escolhida"])
    r2 = _resposta("Almoço", {"kcal": 650, "protein_g": 45, "fat_g": 18},
                   combinacao_escolhida=outra["id"])
    assert r2["escolhida"] == outra["id"]
    assert {t["papel"] for t in r2["trocas"]} or True
    atuais = {t["papel"]: t["atual"] for t in r2["trocas"]}
    for papel, fid in atuais.items():
        assert fid in {i["food_id"] for i in outra["itens"]}, \
            f"a troca de {papel} nao saiu da montagem escolhida"


def test_montagem_inexistente_cai_na_primeira_em_vez_de_quebrar():
    r = _resposta("Almoço", {"kcal": 650, "protein_g": 45, "fat_g": 18},
                  combinacao_escolhida="nao_existe")
    assert r["escolhida"] is not None
    assert r["trocas"]


# -- Restricoes continuam valendo ------------------------------------------------------

def test_quem_nao_come_ovo_nunca_ve_ovo_na_escolha():
    """A tela nova nao pode ser um contorno das restricoes: ela oferece MAIS opcoes, e nao
    opcoes que a pessoa nao pode comer."""
    perfil = dict(PERFIL, allergies=["ovo"])
    r = escolhas_da_refeicao("Café da manhã", perfil,
                             {"kcal": 500, "protein_g": 35, "fat_g": 14},
                             goal="maintenance")
    ovos = {"eggs-whole", "egg-whites", "chicken-egg-omelet"}
    for c in r["combinacoes"]:
        assert not (ovos & {i["food_id"] for i in c["itens"]})
    for t in r["trocas"]:
        assert not (ovos & {o["food_id"] for o in t["opcoes"]})


def test_o_que_a_pessoa_nao_gosta_nao_e_oferecido():
    perfil = dict(PERFIL, disliked_foods=["tilapia", "salmon"])
    r = escolhas_da_refeicao("Almoço", perfil,
                             {"kcal": 650, "protein_g": 45, "fat_g": 18},
                             goal="maintenance")
    for t in r["trocas"]:
        ids = {o["food_id"] for o in t["opcoes"]}
        assert not ({"tilapia", "salmon"} & ids), f"{t['rotulo']} ofereceu {ids}"

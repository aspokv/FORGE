# -*- coding: utf-8 -*-
"""As receitas do FORGE.

O que estes testes protegem
---------------------------
A promessa da area de receitas nao e "ter receitas" — qualquer PDF tem. E que cada
ingrediente aponta para o catalogo do motor, e por isso:

  1. a caloria e CALCULADA, nunca digitada (o defeito mais comum em livro fitness e a
     receita anunciar 260 kcal e o prato ter 400);
  2. o FORGE consegue responder "isto cabe no meu lanche da tarde?", que e a unica pergunta
     que importa para quem esta seguindo um plano.

Se um `food_id` deixar de existir no catalogo, a receita passa a mentir em silencio: os
macros somem sem ninguem notar, porque o alimento some da conta. E o primeiro teste daqui.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import nutrition_engine as ne  # noqa: E402
import receitas as rc  # noqa: E402

TODAS = rc.RECEITAS
IDS_DE_CLASSE = {chave for chave, _, _, _ in rc.CLASSES}


# -- O elo com o catalogo -------------------------------------------------------------

@pytest.mark.parametrize("receita", TODAS, ids=lambda r: r["id"])
def test_todo_ingrediente_existe_no_catalogo(receita):
    """Um `food_id` errado nao quebra nada: ele some da soma, e a receita passa a mentir
    em silencio sobre as proprias calorias."""
    for item in receita["ingredientes"]:
        assert item["food_id"] in ne.FOOD_INDEX, \
            "%s usa %s, que nao existe no catalogo" % (receita["id"], item["food_id"])


@pytest.mark.parametrize("receita", TODAS, ids=lambda r: r["id"])
def test_toda_receita_tem_quantidade_em_gramas(receita):
    for item in receita["ingredientes"]:
        assert isinstance(item["gramas"], (int, float))
        assert item["gramas"] > 0, "%s: %s sem quantidade" % (receita["id"], item["food_id"])


def test_a_caloria_e_calculada_e_nao_digitada():
    """Nenhuma receita carrega kcal escrito a mao — o numero sai do catalogo."""
    for receita in TODAS:
        assert "kcal" not in receita, "%s tem caloria digitada" % receita["id"]
        assert "macros" not in receita


def test_a_conta_bate_com_o_catalogo():
    """Confere a soma de uma receita a mao, para o calculo nao poder derivar em silencio."""
    mingau = next(r for r in TODAS if r["id"] == "mingau-forge")
    esperado = 0.0
    for item in mingau["ingredientes"]:
        f = ne.FOOD_INDEX[item["food_id"]]
        esperado += f["kcal"] * item["gramas"] / f["grams"]
    assert rc.macros_da_receita(mingau)["kcal"] == round(esperado)


# -- Rendimento ------------------------------------------------------------------------

def test_o_macro_e_por_porcao_e_nao_da_panela():
    """As bolinhas somam a massa inteira e rendem quatro. Mostrar o total ao lado de uma
    sobremesa faria a pessoa achar que ela nao cabe — ou comer as quatro achando que era
    uma."""
    bolinha = next(r for r in TODAS if r["id"] == "bolinha-energetica")
    assert bolinha["rendimento"] == 4
    por_porcao = rc.macros_da_receita(bolinha)["kcal"]
    inteira = sum(ne.FOOD_INDEX[i["food_id"]]["kcal"] * i["gramas"]
                  / ne.FOOD_INDEX[i["food_id"]]["grams"]
                  for i in bolinha["ingredientes"])
    assert por_porcao == round(inteira / 4)


@pytest.mark.parametrize("receita", TODAS, ids=lambda r: r["id"])
def test_rendimento_e_sempre_um_numero_util(receita):
    assert int(receita.get("rendimento") or 1) >= 1


# -- As classes ------------------------------------------------------------------------

@pytest.mark.parametrize("receita", TODAS, ids=lambda r: r["id"])
def test_toda_receita_cai_numa_classe_conhecida(receita):
    assert receita["classe"] in IDS_DE_CLASSE


def test_toda_classe_da_tela_tem_receita():
    """Aba vazia e pior do que aba que nao existe."""
    for c in rc.classes_com_contagem():
        assert c["quantas"] > 0
        assert rc.listar(classe=c["chave"])


def test_as_classes_cobrem_o_dia_inteiro():
    """Cafe, lanche da manha, pre, pos, almoco/jantar, lanche da tarde e sobremesa. Uma
    area de receitas sem cafe da manha nao serve para o metodo."""
    presentes = {r["classe"] for r in TODAS}
    assert {"cafe_da_manha", "lanche_da_manha", "pre_treino", "pos_treino",
            "almoco_jantar", "lanche", "sobremesa"} <= presentes


def test_a_classe_aponta_para_um_tipo_de_refeicao_do_motor():
    """Sem isso, encaixar a receita no plano exigiria um tradutor no meio — e tradutor no
    meio e onde as duas telas passam a discordar."""
    for _chave, _rotulo, tipo, _frase in rc.CLASSES:
        assert tipo in ne.MEAL_TEMPLATES, "%s nao e tipo de refeicao do motor" % tipo


# -- Refeicao livre --------------------------------------------------------------------

def test_existe_refeicao_livre():
    livres = rc.listar(apenas_livres=True)
    assert len(livres) >= 4
    assert all(r["refeicao_livre"] for r in livres)


def test_a_refeicao_livre_usa_so_alimento_do_plano():
    """"As melhores receitas sem fugir muito do plano." Se a sobremesa trouxesse um
    ingrediente de fora, ela deixaria de caber na conta do dia — que e o ponto dela."""
    do_plano = set(ne.FOOD_INDEX)
    for r in rc.listar(apenas_livres=True):
        for item in r["ingredientes"]:
            assert item["food_id"] in do_plano


def test_a_refeicao_livre_cabe_num_lanche_comum():
    """Sobremesa que estoura o lanche nao e refeicao livre, e escapada."""
    for r in rc.listar(apenas_livres=True):
        encaixe = rc.cabe_na_refeicao(r["id"], 350)
        assert encaixe["cabe"], "%s passa %s kcal" % (r["nome"], encaixe["excedeu"])


# -- O encaixe -------------------------------------------------------------------------

def test_ficar_abaixo_do_alvo_nunca_reprova():
    """Uma sobremesa de 150 kcal cabe num lanche de 350 e ainda sobra espaco. Reprovar ali
    seria transformar boa noticia em bloqueio."""
    encaixe = rc.cabe_na_refeicao("maca-assada", 350)
    assert encaixe["cabe"] is True
    assert encaixe["sobra"] > 0
    assert encaixe["excedeu"] == 0


def test_passar_muito_do_alvo_reprova():
    encaixe = rc.cabe_na_refeicao("prato-completo", 300)
    assert encaixe["cabe"] is False
    assert encaixe["excedeu"] > 0
    assert encaixe["sobra"] == 0


def test_a_margem_e_a_mesma_do_resto_do_produto():
    """Se a receita usasse uma margem propria, esta tela e a do plano diriam coisas
    diferentes sobre o mesmo prato."""
    for alvo in (300, 500, 2000, 3600):
        assert rc.cabe_na_refeicao("mingau-forge", alvo)["margem"] == \
            round(ne.tolerancia_de_caloria(alvo))


def test_receita_inexistente_devolve_nada_em_vez_de_quebrar():
    assert rc.por_id("nao-existe") is None
    assert rc.cabe_na_refeicao("nao-existe", 400) is None


# -- O texto ---------------------------------------------------------------------------

@pytest.mark.parametrize("receita", TODAS, ids=lambda r: r["id"])
def test_toda_receita_tem_nome_resumo_e_preparo(receita):
    assert receita["nome"].strip()
    assert receita.get("resumo", "").strip()
    assert receita.get("preparo"), "%s sem modo de preparo" % receita["id"]
    assert all(passo.strip() for passo in receita["preparo"])


@pytest.mark.parametrize("receita", TODAS, ids=lambda r: r["id"])
def test_toda_receita_explica_por_que_esta_no_forge(receita):
    """O que separa esta area de uma lista de receitas: cada uma diz o que faz no metodo."""
    assert receita.get("por_que", "").strip()


def test_os_ids_sao_unicos():
    ids = [r["id"] for r in TODAS]
    assert len(ids) == len(set(ids))


def test_a_frase_da_classe_concorda_em_genero():
    """"Cabe no seu sobremesa" saiu na tela. Montar a frase com "no seu" mais o rotulo
    dava erro de portugues em toda receita doce — e receita doce e justamente a que a
    pessoa mais abre."""
    assert rc.FRASE_DA_CLASSE["sobremesa"] == "na sua sobremesa"
    assert rc.FRASE_DA_CLASSE["cafe_da_manha"] == "no seu café da manhã"
    # Toda classe tem frase, e nenhuma frase mistura artigo com genero errado.
    for chave, rotulo, _tipo, frase in rc.CLASSES:
        assert frase.startswith(("no seu ", "na sua ")), (chave, frase)
    assert rc.por_id("mousse-de-morango")["classe_frase"] == "na sua sobremesa"


def test_a_receita_completa_traz_o_nome_do_alimento_e_nao_so_o_id():
    """A tela nao pode ter de consultar o catalogo para escrever "Aveia em flocos"."""
    r = rc.por_id("mingau-forge")
    nomes = [i["nome"] for i in r["ingredientes"]]
    assert "Aveia em flocos" in nomes
    assert all(n and not n.islower() for n in nomes)

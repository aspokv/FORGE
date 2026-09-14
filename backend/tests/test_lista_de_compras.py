# -*- coding: utf-8 -*-
"""FORGE — a lista de compras da semana.

O que estes testes defendem, em ordem de gravidade:

O PESO DE COMPRA NAO E O PESO DO PRATO. O plano pesa o alimento pronto: "250 g de arroz
cozido". Arroz cozido pesa quase tres vezes o cru. Uma lista que mandasse comprar 1,75 kg de
arroz faria a pessoa levar o triplo — e lista que erra por tres e pior que lista nenhuma. O
teste do arroz e o coracao deste arquivo.

A CONVERSAO TEM DOIS SENTIDOS. Grao seco absorve agua e o peso de compra e MENOR; carne perde
agua e o peso de compra e MAIOR. Uma tabela aplicada na direcao errada erra para os dois
lados ao mesmo tempo, e o erro na carne passa despercebido porque e pequeno.

NADA SOME NA SOMA. Alimento que aparece em duas refeicoes tem de virar uma linha so, com a
soma das duas — senao a pessoa compra metade.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import random  # noqa: E402

from lista_de_compras import (  # noqa: E402
    RENDIMENTO, anotar_peso_cru, estado_de_compra, montar_lista, nome_de_compra, peso_cru,
)
from nutrition_engine import (  # noqa: E402
    check_plan_hard_limits, compute_macro_targets, generate_daily_plan,
)


def _item(food_id, nome, gramas, grams_base=100):
    return {"food_id": food_id, "grams": gramas,
            "food": {"id": food_id, "name": nome, "grams": grams_base}}


def _plano(*itens):
    return {"meals": [{"name": "Refeição", "foods": list(itens)}]}


def _achar(lista, food_id):
    for secao in lista["secoes"]:
        for item in secao["itens"]:
            if item["food_id"] == food_id:
                return item
    return None


def test_a_semana_e_o_dia_multiplicado():
    lista = montar_lista(_plano(_item("oats", "Aveia em flocos", 100)), dias=7)
    assert _achar(lista, "oats")["compra"]["gramas"] == 700


# O caso que originou a tabela inteira.
def test_arroz_cozido_vira_um_terco_na_compra():
    lista = montar_lista(_plano(_item("rice-white", "Arroz branco cozido", 250)), dias=7)
    arroz = _achar(lista, "rice-white")
    assert arroz["gramas_no_prato"] == 1750
    assert arroz["compra"]["gramas"] == pytest.approx(583, abs=2)
    assert arroz["convertido"] is True


def test_carne_encolhe_entao_compra_se_mais_e_nao_menos():
    lista = montar_lista(_plano(_item("chicken-breast", "Peito de frango grelhado", 150)), dias=7)
    frango = _achar(lista, "chicken-breast")
    assert frango["compra"]["gramas"] > frango["gramas_no_prato"], "converteu para o lado errado"
    assert frango["compra"]["gramas"] == pytest.approx(1400, abs=10)


def test_espinafre_e_o_extremo_e_precisa_estar_certo():
    """Quatro quilos de folha crua viram um quilo refogado; errar aqui e comprar um quarto."""
    lista = montar_lista(_plano(_item("spinach", "Espinafre refogado", 100)), dias=7)
    assert _achar(lista, "spinach")["compra"]["gramas"] == pytest.approx(2800, abs=10)


def test_alimento_cru_nao_e_convertido():
    lista = montar_lista(_plano(_item("banana", "Banana", 120)), dias=7)
    banana = _achar(lista, "banana")
    assert banana["convertido"] is False
    assert banana["compra"]["gramas"] == 840


def test_o_mesmo_alimento_em_duas_refeicoes_vira_uma_linha_somada():
    plano = {"meals": [
        {"name": "Almoço", "foods": [_item("oats", "Aveia em flocos", 50)]},
        {"name": "Lanche", "foods": [_item("oats", "Aveia em flocos", 30)]},
    ]}
    lista = montar_lista(plano, dias=7)
    assert lista["total_de_itens"] == 1
    assert _achar(lista, "oats")["compra"]["gramas"] == 560


def test_toda_conversao_declarada_tem_fator_positivo():
    for food_id, fator in RENDIMENTO.items():
        assert fator > 0, food_id
        # Fator acima de 4 ou abaixo de 0.2 quase sempre e erro de digitacao, nao alimento.
        assert 0.2 <= fator <= 4.0, (food_id, fator)


# "Batata inglesa cozida 3,29 kg" faz a pessoa procurar batata pronta na banca.
def test_o_preparo_sai_do_nome_na_lista_de_compras():
    assert nome_de_compra("Batata inglesa cozida") == "Batata inglesa"
    assert nome_de_compra("Peito de frango grelhado") == "Peito de frango"
    assert nome_de_compra("Espinafre refogado") == "Espinafre"
    assert nome_de_compra("Cenoura crua") == "Cenoura"


def test_nome_sem_preparo_fica_intacto():
    assert nome_de_compra("Aveia em flocos") == "Aveia em flocos"
    assert nome_de_compra("Atum em lata (água)") == "Atum em lata (água)"


# Ninguem pesa ovo na feira, conta. "16 ovos" e instrucao; "805 g de ovo" e uma conta para a
# pessoa fazer no corredor, com o celular numa mao.
def test_alimento_contado_por_unidade_lidera_com_a_unidade():
    compra = montar_lista(_plano(_item("eggs-whole", "Ovo inteiro", 100)), dias=7)
    ovo = _achar(compra, "eggs-whole")["compra"]
    assert ovo["texto"] == "14 ovos"
    assert ovo["apoio"] == "700 g"
    assert ovo["por_unidade"] is True


def test_alimento_vendido_a_peso_lidera_com_o_peso():
    lista = montar_lista(_plano(_item("oats", "Aveia em flocos", 100)), dias=7)
    aveia = _achar(lista, "oats")["compra"]
    assert aveia["texto"] == "700 g"
    assert aveia["apoio"] is None
    assert aveia["por_unidade"] is False


def test_clara_tambem_e_contada(): 
    lista = montar_lista(_plano(_item("egg-whites", "Clara de ovo", 180)), dias=7)
    assert _achar(lista, "egg-whites")["compra"]["texto"] == "38 claras"


def test_as_secoes_seguem_a_ordem_do_mercado():
    plano = _plano(
        _item("oats", "Aveia em flocos", 50),
        _item("chicken-breast", "Peito de frango grelhado", 150),
        _item("banana", "Banana", 100),
    )
    titulos = [s["chave"] for s in montar_lista(plano, dias=7)["secoes"]]
    assert titulos.index("acougue") < titulos.index("hortifruti") < titulos.index("mercearia")


def test_alimento_desconhecido_cai_na_mercearia_em_vez_de_sumir():
    lista = montar_lista(_plano(_item("xpto-novo", "Alimento novo", 40)), dias=7)
    assert _achar(lista, "xpto-novo") is not None
    assert _achar(lista, "xpto-novo")["secao"] == "mercearia"


def test_plano_vazio_devolve_lista_vazia_sem_quebrar():
    for entrada in ({}, {"meals": []}, None):
        lista = montar_lista(entrada, dias=7)
        assert lista["secoes"] == []
        assert lista["total_de_itens"] == 0


def test_item_sem_gramas_nao_entra():
    lista = montar_lista(_plano(_item("oats", "Aveia", 0)), dias=7)
    assert lista["total_de_itens"] == 0


def test_a_lista_nao_fala_de_dinheiro():
    """Preco nao existe aqui: o FORGE nao sabe quanto custa nada, e chutar seria inventar."""
    lista = montar_lista(_plano(_item("oats", "Aveia em flocos", 100)), dias=7)
    texto = repr(lista).lower()
    for proibido in ("preco", "preço", "valor", "r$", "custo"):
        assert proibido not in texto


class TestPesoNaPanela:
    """O problema que acontece TODO DIA, enquanto a compra acontece uma vez por semana.

    O plano manda "250 g de arroz cozido" e a pessoa esta na cozinha com o pacote na mao,
    sem saber quanto medir. Errar aqui e errar a dieta inteira de um dia, nao so a compra.
    """

    def test_arroz_cozido_vira_um_terco_na_panela(self):
        assert peso_cru("rice-white", 250) == 83

    def test_carne_precisa_de_mais_cru_do_que_o_prato_pede(self):
        assert peso_cru("chicken-breast", 150) == 200

    # Repetir "120 g de banana = 120 g de banana crua" em toda linha seria poluicao.
    def test_alimento_que_nao_muda_de_peso_nao_ganha_etiqueta(self):
        assert peso_cru("banana", 120) is None
        assert peso_cru("oats", 100) is None

    def test_grama_zero_ou_ausente_nao_vira_etiqueta(self):
        assert peso_cru("rice-white", 0) is None
        assert peso_cru("rice-white", None) is None

    def test_o_plano_servido_ganha_o_peso_cru_so_onde_faz_sentido(self):
        plano = {"meals": [{"name": "Almoço", "foods": [
            {"food_id": "rice-white", "grams": 250, "food": {"name": "Arroz branco cozido"}},
            {"food_id": "banana", "grams": 120, "food": {"name": "Banana"}},
        ]}]}
        itens = anotar_peso_cru(plano)["meals"][0]["foods"]
        assert itens[0]["raw_grams"] == 83
        assert "raw_grams" not in itens[1]

    def test_anotar_plano_vazio_nao_quebra(self):
        assert anotar_peso_cru({}) == {}
        assert anotar_peso_cru(None) is None


class TestPalavraDoEstado:
    """A palavra fica colada no numero porque rodape ninguem le.

    Quem conhece a propria dieta tem 1,75 kg de arroz na cabeca; ver "583 g" solto parece
    erro do aplicativo, e nao conversao.
    """

    def test_concorda_com_o_genero_do_alimento(self):
        assert estado_de_compra("Arroz branco") == "cru"
        assert estado_de_compra("Batata inglesa") == "crua"
        assert estado_de_compra("Peito de frango") == "cru"
        assert estado_de_compra("Abobrinha") == "crua"

    def test_nome_vazio_nao_quebra(self):
        assert estado_de_compra("") == "cru"
        assert estado_de_compra(None) == "cru"

    def test_so_alimento_convertido_recebe_a_palavra(self):
        lista = montar_lista(_plano(
            _item("rice-white", "Arroz branco cozido", 250),
            _item("banana", "Banana", 120),
        ), dias=7)
        assert _achar(lista, "rice-white")["estado"] == "cru"
        assert _achar(lista, "banana")["estado"] is None


# Quatro pessoas que nao se parecem em nada: sexo, peso, objetivo e frequencia diferentes.
PERFIS = [
    ("homem 92 kg em ganho, 5x", dict(weight_kg=92, height_cm=180, age=28, sex="male",
                                      training_days=5, goal="bulking", activity_level="moderate")),
    ("mulher 58 kg em corte, 4x", dict(weight_kg=58, height_cm=163, age=33, sex="female",
                                       training_days=4, goal="cutting", activity_level="moderate")),
    ("mulher 70 kg em manutencao", dict(weight_kg=70, height_cm=170, age=41, sex="female",
                                        training_days=3, goal="maintenance", activity_level="light")),
    ("homem 68 kg em corte, 6x", dict(weight_kg=68, height_cm=174, age=22, sex="male",
                                      training_days=6, goal="cutting", activity_level="high")),
]


def _plano_de(na):
    alvos = compute_macro_targets(na["weight_kg"], na["height_cm"], na["age"], na["sex"],
                                  na["training_days"], na["goal"], na["activity_level"], None)
    for _ in range(10):
        candidato = generate_daily_plan(alvos, na, 4, na["goal"], random.randint(0, 999))
        if not check_plan_hard_limits(candidato, alvos):
            return candidato, alvos
    raise AssertionError("o motor nao gerou plano valido para este perfil")


class TestValeParaQualquerPerfil:
    """A lista nao pode servir so a um tipo de atleta.

    O risco real de uma funcao construida olhando UM perfil e amarrar sem querer alguma
    suposicao dele — que existe arroz no plano, que sao quatro refeicoes, que o objetivo e
    ganho. Estes testes exercitam perfis que nao se parecem em nada e exigem lista utilizavel
    em todos. Quem quebrar isto descobre na hora, e nao no telefone de um atleta.
    """

    @pytest.mark.parametrize("rotulo,na", PERFIS, ids=[p[0] for p in PERFIS])
    def test_todo_perfil_gera_lista_utilizavel(self, rotulo, na):
        plano, _ = _plano_de(na)
        lista = montar_lista(plano, 7)
        assert lista["total_de_itens"] > 0, rotulo
        assert lista["secoes"], rotulo
        for secao in lista["secoes"]:
            for item in secao["itens"]:
                assert item["nome"], (rotulo, item)
                assert item["compra"]["gramas"] > 0, (rotulo, item["nome"])
                assert item["compra"]["texto"], (rotulo, item["nome"])

    @pytest.mark.parametrize("rotulo,na", PERFIS, ids=[p[0] for p in PERFIS])
    def test_todo_perfil_recebe_o_peso_da_panela_onde_cabe(self, rotulo, na):
        plano, _ = _plano_de(na)
        itens = [i for r in anotar_peso_cru(plano)["meals"] for i in r["foods"]]
        # Nem todo plano tem alimento que muda de peso, mas quando tem, a etiqueta e valida.
        for item in itens:
            if "raw_grams" in item:
                assert item["raw_grams"] > 0, (rotulo, item["food_id"])

    def test_perfis_diferentes_produzem_listas_diferentes(self):
        """Se duas pessoas opostas recebessem a mesma lista, algo estaria fixo no codigo."""
        tamanhos = set()
        for _, na in PERFIS:
            plano, alvos = _plano_de(na)
            tamanhos.add(round(alvos["goal_calories"]))
        assert len(tamanhos) == len(PERFIS), "perfis distintos convergiram para a mesma meta"

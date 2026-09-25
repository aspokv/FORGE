# -*- coding: utf-8 -*-
"""Colar a dieta tem que trazer a dieta INTEIRA.

O relato: um atleta colou a dieta que recebeu e ela "saiu pela metade". A reprodução com
o texto exato mostrou pior que isso — a dieta chegava com ZERO caloria:

* "Whey: 40 g" e "Banana: 120 g" sumiam. O parser só lia quantidade na frente
  ("40 g de whey"); com o número no fim, "whey: 40 g" inteiro virava o nome, não casava
  com nada, e a linha era descartada.
* Os que casavam ("Farinha de arroz: 60 g") chegavam SEM gramas, e sem gramas o item vale
  zero. Por isso o total do dia era 0 kcal.
* "Carne bovina/frango/peixe: 200 g" e "Legumes/verduras: à vontade" sumiam.
* A tabela "Substituições do carboidrato" virava dois itens a mais na ceia.

Estes testes usam o texto do atleta como veio, e prendem cada um desses formatos.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from nutrition_engine import FOOD_FAMILIES, FOOD_INDEX  # noqa: E402
from nutrition_import import (  # noqa: E402
    REVIEW_ESTIMATED_PORTION, REVIEW_FREE_PORTION, REVIEW_QUANTITY_MISSING, build_matcher,
    draft_to_plan, is_meal_header, parse_diet_text, validate_draft,
)

# O texto exatamente como o atleta colou: linhas em branco, travessão e seta incluídos.
DIETA_DO_ATLETA = """DIETA — 83 KG | RECOMPOSIÇÃO
Pós-treino

Whey: 40 g
Farinha de arroz: 60 g
Iogurte natural: 170 g
Banana: 120 g
Almoço

Carne bovina/frango/peixe: 200 g
Batata inglesa: 250 g
Legumes/verduras: à vontade
Lanche

Carne/frango: 150 g
Batata inglesa: 150 g
Jantar

Carne bovina/frango/peixe: 200 g
Batata inglesa: 200 g
Legumes/verduras: à vontade
Ceia

Iogurte natural: 200 g
Whey: 30 g
Substituições do carboidrato

250 g batata inglesa → 200 g batata-doce → 150 g aipim
200 g batata inglesa → 160 g batata-doce → 120 g aipim
"""

# (alimento, gramas) de cada refeição, na ordem do texto.
ESPERADO = {
    "Pós-treino": [("whey-protein", 40), ("rice-flour", 60), ("yogurt-natural", 170),
                   ("banana", 120)],
    "Almoço": [("beef-grill", 200), ("potato", 250), ("mixed-vegetables", 100)],
    "Lanche": [("beef-grill", 150), ("potato", 150)],
    "Jantar": [("beef-grill", 200), ("potato", 200), ("mixed-vegetables", 100)],
    "Ceia": [("yogurt-natural", 200), ("whey-protein", 30)],
}


@pytest.fixture(scope="module")
def dieta():
    return parse_diet_text(DIETA_DO_ATLETA, build_matcher(), "Dieta importada")


def _itens(d):
    return [i for m in d["meals"] for i in m["items"]]


class TestADietaDoAtletaChegaInteira:

    def test_todas_as_refeicoes_na_ordem(self, dieta):
        assert [m["name"] for m in dieta["meals"]] == list(ESPERADO)

    def test_cada_alimento_com_a_quantidade_que_estava_escrita(self, dieta):
        for meal in dieta["meals"]:
            lido = [(i["food_id"], i["grams"]) for i in meal["items"]]
            assert lido == ESPERADO[meal["name"]], meal["name"]

    def test_nenhuma_linha_foi_descartada(self, dieta):
        assert dieta["warnings"] == []
        assert dieta["stats"]["items"] == 14

    # O sintoma que o atleta viu: dieta com caloria de menos. Faixa larga de propósito —
    # o alvo é o absurdo (zero, metade), não o arredondamento do catálogo.
    def test_o_dia_soma_a_dieta_e_nao_uma_fracao_dela(self, dieta):
        assert 2000 < dieta["daily_totals"]["kcal"] < 2900
        assert dieta["daily_totals"]["protein_g"] > 200

    def test_o_titulo_vira_o_nome_da_dieta(self, dieta):
        assert dieta["name"] == "DIETA — 83 KG | RECOMPOSIÇÃO"
        assert "DIETA" not in [m["name"] for m in dieta["meals"]]

    def test_pode_ser_ativada_sem_pendencia_bloqueante(self, dieta):
        assert validate_draft(dieta) == []


class TestQuantidadeDepoisDoNome:

    @pytest.mark.parametrize("linha,alimento,gramas,estimado", [
        ("Whey: 40 g", "whey-protein", 40, False),
        ("Banana 120g", "banana", 120, False),
        ("Arroz branco - 150 g", "rice-white", 150, False),
        ("Iogurte natural (170 g)", "yogurt-natural", 170, False),
        ("Leite desnatado: 200 ml", "milk-skim", 200, False),
        ("Aveia: 2 colheres de sopa", "oats", 30, True),
        ("Ovos: 3", "eggs-whole", 150, True),
        # Medida caseira E peso: vale o peso, que foi o que a pessoa pesou.
        ("Whey: 1 scoop (30 g)", "whey-protein", 30, False),
        ("1 scoop de whey (35 g)", "whey-protein", 35, False),
    ])
    def test_formatos_de_quantidade_no_fim(self, linha, alimento, gramas, estimado):
        item = _itens(parse_diet_text("LANCHE\n" + linha))[0]
        assert (item["food_id"], item["grams"], item["estimated"]) == (alimento, gramas, estimado)

    # Com acento é como quase todo mundo escreve. Sem o acento no padrão, a medida caía
    # dentro do nome ("xícara de arroz") e a quantidade se perdia.
    @pytest.mark.parametrize("linha,alimento,gramas", [
        ("1 xícara de arroz branco", "rice-white", 120),
        ("1 filé de frango", "chicken-breast", 120),
        ("Arroz branco: 1 xícara", "rice-white", 120),
    ])
    def test_medida_caseira_com_acento(self, linha, alimento, gramas):
        item = _itens(parse_diet_text("ALMOÇO\n" + linha))[0]
        assert (item["food_id"], item["grams"]) == (alimento, gramas)
        assert REVIEW_ESTIMATED_PORTION in item["review_reasons"]

    def test_numero_solto_sem_separador_nao_vira_quantidade(self):
        """"Ômega 3" é nome, e não três unidades de ômega."""
        d = parse_diet_text("ALMOÇO\n150 g de arroz branco\nÔmega 3")
        assert [i["food_id"] for i in _itens(d)] == ["rice-white"]
        assert any("Ômega 3" in w for w in d["warnings"])

    @pytest.mark.parametrize("cabecalho", ["Café da manhã (07:00)", "Almoço - 12:30",
                                           "Refeição 1", "Lanche 16:00"])
    def test_horario_no_cabecalho_nao_vira_quantidade(self, cabecalho):
        d = parse_diet_text(cabecalho + "\n2 ovos")
        assert d["meals"][0]["name"] == cabecalho
        assert [i["food_id"] for i in _itens(d)] == ["eggs-whole"]

    @pytest.mark.parametrize("linha", ["WHEY: 40 G", "Café com leite: 200 ml", "Banana: 120 g"])
    def test_item_com_quantidade_no_fim_nao_e_cabecalho(self, linha):
        assert is_meal_header(linha) is False

    def test_dois_alimentos_com_quantidade_no_fim_na_mesma_linha(self):
        d = parse_diet_text("ALMOÇO\nArroz branco 100 g, feijão preto 80 g")
        assert [(i["food_id"], i["grams"]) for i in _itens(d)] == [
            ("rice-white", 100), ("beans-black", 80)]

    def test_virgula_decimal_nao_separa_item(self):
        item = _itens(parse_diet_text("ALMOÇO\nArroz branco: 1,5 kg"))[0]
        assert item["grams"] == 1500


class TestOpcoesNoMesmoItem:
    """"Carne bovina/frango/peixe: 200 g" é UM item com três opções, na mesma quantidade."""

    def test_a_primeira_opcao_vira_o_item_e_as_outras_ficam_guardadas(self):
        item = _itens(parse_diet_text("ALMOÇO\nCarne bovina/frango/peixe: 200 g"))[0]
        assert item["food_id"] == "beef-grill"
        assert item["grams"] == 200
        assert item["alternativas"] == ["chicken-breast", "tilapia"]
        assert item["needs_review"] is False

    def test_ou_tambem_separa_opcoes(self):
        item = _itens(parse_diet_text("JANTAR\nFrango ou peixe: 150 g"))[0]
        assert (item["food_id"], item["grams"], item["alternativas"]) == (
            "chicken-breast", 150, ["tilapia"])

    def test_opcoes_nao_viram_itens_separados(self):
        d = parse_diet_text("ALMOÇO\nCarne bovina, frango ou peixe: 200 g")
        assert len(_itens(d)) == 1

    def test_opcao_que_o_catalogo_nao_conhece_pede_um_olhar(self):
        item = _itens(parse_diet_text("ALMOÇO\nFrango/xyzzy: 150 g"))[0]
        assert item["food_id"] == "chicken-breast"
        assert item["needs_review"] is True

    def test_as_opcoes_chegam_ao_plano_com_nome(self, dieta):
        plano = draft_to_plan(dieta)
        carne = plano["meals"][1]["foods"][0]
        assert carne["food_id"] == "beef-grill"
        assert [a["food_id"] for a in carne["alternativas"]] == ["chicken-breast", "tilapia"]
        assert all(a["name"] for a in carne["alternativas"])


class TestOpcoesComQuantidadePropria:
    """"100 g de arroz ou 250 g de batata": opções com quantidades diferentes não são
    "na mesma quantidade" — são uma equivalência, e vão para a tabela de trocas."""

    @pytest.mark.parametrize("linha", ["100 g de arroz branco ou 250 g de batata inglesa",
                                       "Arroz branco 100 g / Batata inglesa 250 g"])
    def test_o_item_e_a_primeira_opcao_e_a_equivalencia_vira_troca(self, linha):
        d = parse_diet_text("ALMOÇO\n" + linha)
        assert [(i["food_id"], i["grams"], i["alternativas"]) for i in _itens(d)] == [
            ("rice-white", 100, [])]
        assert d["substituicoes"] == [{"titulo": "ALMOÇO", "opcoes": [
            {"food_id": "rice-white", "raw_name": d["substituicoes"][0]["opcoes"][0]["raw_name"],
             "grams": 100, "estimated": False, "match_confidence": "alias"},
            {"food_id": "potato", "raw_name": d["substituicoes"][0]["opcoes"][1]["raw_name"],
             "grams": 250, "estimated": False, "match_confidence": "alias"},
        ]}]

    def test_mais_separa_itens_mesmo_com_opcoes_no_segundo(self):
        """Sem o "+" separar primeiro, as opções engoliam o arroz."""
        d = parse_diet_text("ALMOÇO\nArroz branco 100 g + frango ou peixe 150 g")
        assert [(i["food_id"], i["grams"], i["alternativas"]) for i in _itens(d)] == [
            ("rice-white", 100, []), ("chicken-breast", 150, ["tilapia"])]

    def test_alimento_do_catalogo_com_mais_no_nome_continua_um_item(self):
        d = parse_diet_text("LANCHE\nCreme de arroz + whey: 80 g")
        assert [(i["food_id"], i["grams"]) for i in _itens(d)] == [("rice-cream-whey", 80)]

    def test_fracao_nao_e_separador_de_opcao(self):
        d = parse_diet_text("CAFÉ DA MANHÃ\n1/2 xícara de aveia")
        assert d["substituicoes"] == []


class TestAVontade:

    def test_verdura_a_vontade_conta_uma_porcao_de_referencia_e_avisa(self, dieta):
        legumes = dieta["meals"][1]["items"][2]
        assert legumes["food_id"] == "mixed-vegetables"
        assert legumes["a_vontade"] is True
        assert legumes["grams"] == FOOD_INDEX["mixed-vegetables"]["grams"]
        assert legumes["review_reasons"] == [REVIEW_FREE_PORTION]

    # O defeito de produção que já existia: "arroz à vontade" vale zero e tira a meta do
    # dia do lugar. Fora das verduras, "à vontade" continua pedindo o número.
    def test_fora_das_verduras_a_vontade_continua_pedindo_o_numero(self):
        d = parse_diet_text("ALMOÇO\nArroz branco: à vontade")
        item = _itens(d)[0]
        assert item["food_id"] == "rice-white"
        assert item["grams"] is None
        assert REVIEW_QUANTITY_MISSING in item["review_reasons"]
        assert validate_draft(d)

    def test_o_plano_sabe_que_e_a_vontade(self, dieta):
        plano = draft_to_plan(dieta)
        assert plano["meals"][1]["foods"][2].get("a_vontade") is True

    @pytest.mark.parametrize("linha", ["Legumes à vontade", "Verduras (à vontade)",
                                       "Legumes e verduras: a vontade", "Salada de legumes livre"])
    def test_jeitos_de_escrever(self, linha):
        item = _itens(parse_diet_text("JANTAR\n" + linha))[0]
        assert item["food_id"] == "mixed-vegetables"
        assert item["a_vontade"] is True


class TestTabelaDeTrocas:

    def test_as_trocas_nao_viram_comida_na_ceia(self, dieta):
        ceia = dieta["meals"][-1]
        assert [i["food_id"] for i in ceia["items"]] == ["yogurt-natural", "whey-protein"]

    def test_as_trocas_sao_lidas_com_alimento_e_gramas(self, dieta):
        trocas = dieta["substituicoes"]
        assert [t["titulo"] for t in trocas] == ["Substituições do carboidrato"] * 2
        assert [[(o["food_id"], o["grams"]) for o in t["opcoes"]] for t in trocas] == [
            [("potato", 250), ("sweet-potato", 200), ("cassava", 150)],
            [("potato", 200), ("sweet-potato", 160), ("cassava", 120)],
        ]

    def test_as_trocas_chegam_ao_plano_com_nome(self, dieta):
        plano = draft_to_plan(dieta)
        primeira = plano["substituicoes"][0]["opcoes"]
        assert [o["name"] for o in primeira] == [FOOD_INDEX[f]["name"] for f in
                                                 ("potato", "sweet-potato", "cassava")]

    def test_seta_fora_de_uma_secao_de_trocas_tambem_e_troca(self):
        d = parse_diet_text("ALMOÇO\n150 g de arroz branco\n100 g arroz branco -> 250 g batata inglesa")
        assert [i["food_id"] for i in _itens(d)] == ["rice-white"]
        assert len(d["substituicoes"]) == 1

    def test_uma_refeicao_depois_da_tabela_volta_a_receber_itens(self):
        d = parse_diet_text("Substituições\n100 g arroz branco = 250 g batata inglesa\n"
                            "Ceia\nIogurte natural: 170 g")
        assert d["meals"][0]["name"] == "Ceia"
        assert [i["food_id"] for i in _itens(d)] == ["yogurt-natural"]
        assert len(d["substituicoes"]) == 1


class TestRefeicaoComItensNaMesmaLinha:

    def test_cabecalho_e_itens_na_mesma_linha(self):
        d = parse_diet_text("Almoço: arroz branco 150 g, peito de frango 120 g")
        assert d["meals"][0]["name"] == "Almoço"
        assert [(i["food_id"], i["grams"]) for i in _itens(d)] == [
            ("rice-white", 150), ("chicken-breast", 120)]

    def test_o_primeiro_formato_continua_valendo(self):
        d = parse_diet_text("ALMOÇO\n150g de arroz branco\n120g de peito de frango")
        assert [(i["food_id"], i["grams"]) for i in _itens(d)] == [
            ("rice-white", 150), ("chicken-breast", 120)]


class TestLegumesEVerduras:
    """O alimento novo do catálogo, que existe para "Legumes/verduras: à vontade"."""

    def test_os_numeros_sao_a_media_das_verduras_do_catalogo(self):
        """Medido, e não chutado: se alguém corrigir uma verdura, este teste avisa que a
        média mudou."""
        outras = [f for f in FOOD_INDEX.values()
                  if f.get("category") == "VEGETABLE" and f["id"] != "mixed-vegetables"]
        mix = FOOD_INDEX["mixed-vegetables"]
        for campo, folga in (("kcal", 1), ("protein_g", 0.1), ("carbs_g", 0.1), ("fat_g", 0.1)):
            media = sum(float(f[campo]) for f in outras) / len(outras)
            assert mix[campo] == pytest.approx(media, abs=folga), campo

    def test_o_gerador_de_plano_nao_escolhe_este_alimento(self):
        """Ele serve a dieta colada. O plano gerado continua montado com verdura de verdade."""
        assert not any("mixed-vegetables" in ids for ids in FOOD_FAMILIES.values())

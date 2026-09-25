# -*- coding: utf-8 -*-
"""Periodização automática da dieta, sem servidor.

O pedido: "sigo a dieta por quatro semanas; em emagrecimento ele vai cortando o
carboidrato, em ganho de massa vai fazendo superávit". Estes testes prendem as regras que
tornam isso seguro: quem mexe é o carboidrato, os pisos não se atravessam, a balança pode
segurar o degrau, e o prato muda junto com a meta.
"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import periodizacao_automatica as pa  # noqa: E402
from food_diary import DIARY_FOODS  # noqa: E402
from nutrition_engine import FOOD_INDEX, build_food_item  # noqa: E402

BASE = {"kcal": 2416, "protein_g": 251.4, "carbs_g": 223.9, "fat_g": 57.5}


def _tabela(fase, semanas=4, ritmo="moderado", base=BASE, peso=83):
    return pa.montar_progressao(base, peso, fase, semanas, ritmo)["tabela"]


class TestAProgressao:

    def test_a_semana_1_e_a_dieta_como_ela_esta(self):
        primeira = _tabela(pa.CORTE)[0]
        assert (primeira["kcal"], primeira["carbs_g"]) == (2416, 223.9)

    def test_no_corte_so_o_carboidrato_desce(self):
        tabela = _tabela(pa.CORTE)
        assert [l["kcal"] for l in tabela] == sorted((l["kcal"] for l in tabela), reverse=True)
        assert {l["protein_g"] for l in tabela} == {251.4}
        assert {l["fat_g"] for l in tabela} == {57.5}

    def test_no_ganho_o_carboidrato_sobe(self):
        tabela = _tabela(pa.GANHO)
        assert tabela[-1]["kcal"] > tabela[0]["kcal"]
        assert tabela[-1]["carbs_g"] > tabela[0]["carbs_g"]
        assert {l["protein_g"] for l in tabela} == {251.4}

    @pytest.mark.parametrize("ritmo", [r for r in pa.RITMOS if r != pa.AGRESSIVO])
    def test_o_passo_tem_teto_como_o_do_conselho(self, ritmo):
        grande = {**BASE, "kcal": 5000, "carbs_g": 700}
        assert pa.passo_kcal(grande["kcal"], pa.CORTE, ritmo) <= pa.TETO_DO_PASSO[pa.CORTE]
        assert pa.passo_kcal(grande["kcal"], pa.GANHO, ritmo) <= pa.TETO_DO_PASSO[pa.GANHO]

    def test_ritmo_mais_forte_corta_mais(self):
        suave, forte = _tabela(pa.CORTE, 4, "suave"), _tabela(pa.CORTE, 4, "forte")
        assert forte[1]["kcal"] < suave[1]["kcal"]


class TestAgressivo:
    """O ritmo de atleta: carboidrato perto de zero no corte, superávit grande no ganho.
    Perto de zero, e nunca zero."""

    def test_passo_maior_com_teto_proprio(self):
        assert pa.passo_kcal(2416, pa.CORTE, pa.AGRESSIVO) > pa.passo_kcal(2416, pa.CORTE, "forte")
        assert pa.passo_kcal(8000, pa.CORTE, pa.AGRESSIVO) == pa.TETO_DO_PASSO_AGRESSIVO[pa.CORTE]
        assert pa.passo_kcal(8000, pa.GANHO, pa.AGRESSIVO) == pa.TETO_DO_PASSO_AGRESSIVO[pa.GANHO]

    @pytest.mark.parametrize("peso,piso", [(83, 42), (60, 40), (120, 60)])
    def test_piso_de_carbo_desce_mas_nunca_zera(self, peso, piso):
        assert pa.piso_de_carbo(peso, pa.AGRESSIVO) == piso
        tabela = _tabela(pa.CORTE, 12, pa.AGRESSIVO, peso=peso)
        assert min(l["carbs_g"] for l in tabela) == piso > 0

    def test_corte_agressivo_desce_bem_mais_que_o_moderado(self):
        agressivo = _tabela(pa.CORTE, 12, pa.AGRESSIVO)
        moderado = _tabela(pa.CORTE, 12, "moderado")
        assert agressivo[-1]["carbs_g"] < moderado[-1]["carbs_g"] / 2

    def test_ganho_agressivo_passa_do_teto_do_ganho_comum_mas_tem_teto(self):
        tabela = _tabela(pa.GANHO, 12, pa.AGRESSIVO)
        assert max(l["kcal"] for l in tabela) > round(BASE["kcal"] * 1.2)
        assert max(l["kcal"] for l in tabela) <= round(BASE["kcal"] * 1.35)

    def test_a_balanca_tolera_mais_no_agressivo_mas_segura(self):
        t = lambda kg: {"suficiente": True, "kg_por_semana": kg, "peso_atual": 83.0}
        assert pa.decidir_degrau(pa.CORTE, t(-1.0), "moderado")[0] == "segurar"      # 1,2%
        assert pa.decidir_degrau(pa.CORTE, t(-1.0), pa.AGRESSIVO)[0] == "avancar"
        assert pa.decidir_degrau(pa.CORTE, t(-1.5), pa.AGRESSIVO)[0] == "segurar"    # 1,8%
        assert pa.decidir_degrau(pa.GANHO, t(0.6), pa.AGRESSIVO)[0] == "avancar"
        assert pa.decidir_degrau(pa.GANHO, t(1.0), pa.AGRESSIVO)[0] == "segurar"


class TestSempreFicaUmCarboNoPrato:
    """A meta perto de zero não pode virar "5 g de batata": cada fonte fica com uma porção."""

    def _plano(self):
        return [{"name": "Almoço", "target_cal": 700, "foods": [
                    build_food_item("chicken-breast", 200), build_food_item("potato", 250)]},
                {"name": "Ceia", "target_cal": 300, "foods": [
                    build_food_item("yogurt-natural", 200), build_food_item("banana", 120)]}]

    def test_cortar_tudo_ainda_deixa_uma_porcao_de_cada_fonte(self):
        novas, _, _ = pa.ajustar_refeicoes(self._plano(), -500, FOOD_INDEX, DIARY_FOODS, build_food_item)
        gramas = {f["food_id"]: f["grams"] for r in novas for f in r["foods"]}
        assert gramas["potato"] == 25 and gramas["banana"] == 10   # 10% da porção, no mínimo 10 g

    def test_a_meta_nao_promete_menos_do_que_o_prato_entrega(self):
        piso = pa.carbo_minimo_do_prato(self._plano(), FOOD_INDEX, DIARY_FOODS)
        tabela = pa.montar_progressao(BASE, 83, pa.CORTE, 12, pa.AGRESSIVO, piso)["tabela"]
        assert min(l["carbs_g"] for l in tabela) >= piso
        # E o prato cortado ao máximo entrega o piso que a meta mostra.
        novas, _, _ = pa.ajustar_refeicoes(self._plano(), -500, FOOD_INDEX, DIARY_FOODS, build_food_item)
        entregue = sum(DIARY_FOODS[f["food_id"]]["carbs_g"] * f["grams"] / DIARY_FOODS[f["food_id"]].get("grams", 100)
                       for r in novas for f in r["foods"])
        assert entregue == pytest.approx(piso, abs=1)

    def test_o_ganho_nao_tem_minimo_de_porcao_no_caminho(self):
        novas, _, _ = pa.ajustar_refeicoes(self._plano(), 40, FOOD_INDEX, DIARY_FOODS, build_food_item)
        assert {f["food_id"]: f["grams"] for r in novas for f in r["foods"]}["potato"] > 250


class TestOsPisos:

    def test_carboidrato_nao_desce_abaixo_de_1_5_g_por_kg(self):
        tabela = _tabela(pa.CORTE, 12, "forte")
        piso = round(1.5 * 83)
        assert min(l["carbs_g"] for l in tabela) == piso
        assert any(l["travou"] and "piso" in l["travou"] for l in tabela)

    def test_superavit_nao_passa_de_20_por_cento(self):
        tabela = _tabela(pa.GANHO, 12, "forte")
        assert max(l["kcal"] for l in tabela) <= round(BASE["kcal"] * 1.2)

    def test_quem_ja_esta_no_piso_de_carbo_nao_comeca_corte(self):
        with pytest.raises(ValueError, match="mínimo seguro"):
            pa.montar_progressao({**BASE, "carbs_g": 120}, 83, pa.CORTE, 4, "moderado")

    @pytest.mark.parametrize("semanas,ritmo,fase", [(3, "moderado", "corte"), (4, "turbo", "corte"),
                                                    (4, "moderado", "bulk")])
    def test_pedido_invalido_explica(self, semanas, ritmo, fase):
        with pytest.raises(ValueError):
            pa.montar_progressao(BASE, 83, fase, semanas, ritmo)

    def test_sem_peso_nao_da_para_calcular_o_piso(self):
        with pytest.raises(ValueError, match="peso"):
            pa.montar_progressao(BASE, None, pa.CORTE, 4, "moderado")


class TestABalancaSeguraODegrau:

    def _tendencia(self, kg_por_semana, peso=83.0):
        return {"suficiente": True, "kg_por_semana": kg_por_semana, "peso_atual": peso}

    def test_corte_perdendo_rapido_demais_segura(self):
        decisao, motivo = pa.decidir_degrau(pa.CORTE, self._tendencia(-1.2))
        assert decisao == "segurar" and "músculo" in motivo

    def test_corte_no_ritmo_avanca(self):
        assert pa.decidir_degrau(pa.CORTE, self._tendencia(-0.5))[0] == "avancar"

    def test_ganho_subindo_rapido_demais_segura(self):
        decisao, motivo = pa.decidir_degrau(pa.GANHO, self._tendencia(0.6))
        assert decisao == "segurar" and "gordura" in motivo

    def test_sem_pesagem_segue_o_calendario_e_pede_a_de_sexta(self):
        decisao, motivo = pa.decidir_degrau(pa.CORTE, {"suficiente": False})
        assert decisao == "avancar" and "sexta" in motivo

    def test_semana_do_calendario(self):
        inicio = date(2026, 9, 1)
        assert [pa.semana_do_calendario(inicio, date(2026, 9, d)) for d in (1, 7, 8, 15, 29)] == [1, 1, 2, 3, 5]


class TestOPratoMudaJunto:

    def _plano(self):
        item = build_food_item
        return [
            {"name": "Almoço", "target_cal": 700, "foods": [
                item("chicken-breast", 200), item("potato", 250), item("broccoli", 100)]},
            {"name": "Lanche", "target_cal": 400, "foods": [
                item("banana", 120), item("whey-protein", 40),
                {**item("mixed-vegetables", 100), "a_vontade": True}]},
        ]

    def _carbo(self, refeicoes):
        total = 0.0
        for r in refeicoes:
            for f in r["foods"]:
                base = DIARY_FOODS[f["food_id"]]
                total += base["carbs_g"] * f["grams"] / base.get("grams", 100)
        return total

    def test_so_as_fontes_de_carboidrato_mudam(self):
        novas, _, _ = pa.ajustar_refeicoes(self._plano(), -40, FOOD_INDEX, DIARY_FOODS, build_food_item)
        gramas = {f["food_id"]: f["grams"] for r in novas for f in r["foods"]}
        assert gramas["chicken-breast"] == 200 and gramas["whey-protein"] == 40
        # Verdura segura a fome, e "à vontade" é referência: nenhuma das duas é cortada.
        assert gramas["broccoli"] == 100 and gramas["mixed-vegetables"] == 100
        assert gramas["potato"] < 250 and gramas["banana"] < 120

    def test_o_carbo_do_dia_chega_perto_do_pedido(self):
        antes = self._plano()
        novas, aplicado, _ = pa.ajustar_refeicoes(antes, -40, FOOD_INDEX, DIARY_FOODS, build_food_item)
        assert self._carbo(novas) - self._carbo(antes) == pytest.approx(aplicado, abs=0.5)
        assert aplicado == pytest.approx(-40, abs=6)   # arredondamento de 5 g

    def test_as_gramas_saem_de_5_em_5(self):
        novas, _, _ = pa.ajustar_refeicoes(self._plano(), -33, FOOD_INDEX, DIARY_FOODS, build_food_item)
        assert all(f["grams"] % 5 == 0 for r in novas for f in r["foods"])

    def test_a_mudanca_diz_o_que_mudou_no_prato(self):
        _, _, mudancas = pa.ajustar_refeicoes(self._plano(), 30, FOOD_INDEX, DIARY_FOODS, build_food_item)
        batata = next(m for m in mudancas if m["refeicao"] == "Almoço")
        assert batata["de"] == 250 and batata["para"] > 250

    def test_nao_muda_o_plano_de_entrada(self):
        antes = self._plano()
        pa.ajustar_refeicoes(antes, -40, FOOD_INDEX, DIARY_FOODS, build_food_item)
        assert antes[0]["foods"][1]["grams"] == 250

    def test_plano_sem_fonte_de_carbo_nao_quebra(self):
        so_proteina = [{"name": "A", "foods": [build_food_item("chicken-breast", 200)]}]
        novas, aplicado, mudancas = pa.ajustar_refeicoes(so_proteina, -40, FOOD_INDEX, DIARY_FOODS, build_food_item)
        assert (novas, aplicado, mudancas) == (so_proteina, 0.0, [])

# -*- coding: utf-8 -*-
"""FORGE — carboidrato concentrado no dia do ponto fraco.

Esta e a mudanca mais perigosa da alimentacao ate agora: ela nao acrescenta tela, ela
recalcula o que as pessoas comem. Por isso o teste mais importante deste arquivo nao e
nenhum caso bonito — e a invariante:

    A SEMANA SOMA EXATAMENTE O MESMO.

Se os dias prioritarios simplesmente ganhassem carboidrato a mais, quem esta em corte
entraria num superavit acidental sem nunca ter pedido. Esse e o pior tipo de defeito: o que
engorda a pessoa em silencio, semana apos semana, enquanto o aplicativo diz que esta tudo
certo. Todos os testes de soma aqui existem por causa disso.

O segundo grupo defende os caminhos em que NAO se deve ciclar. Sem ponto fraco marcado,
inventar um dia prioritario e decidir pela pessoa.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ciclagem_de_carboidrato import (  # noqa: E402
    MAXIMO_DO_DIA, MINIMO_DO_DIA, ciclar_por_sessao, ciclar_semana, classe_da_sessao,
    classificar_semana, dia_prioritario, onde_colocar,
)

ALVOS = {"carbs_g": 400.0, "protein_g": 180.0, "fat_g": 70.0, "goal_calories": 2950}

PEITO = {"focus": ["Peitoral esternal", "Peitoral superior", "Dorsais / largura"]}
PERNA = {"focus": ["Quadríceps", "Posteriores", "Glúteos"]}

# Segunda a domingo: treina seg, ter, qui, sex; descansa qua, sab, dom.
SEMANA = [PEITO, PERNA, None, PEITO, PERNA, None, None]


class TestOCruzamentoComOPontoFraco:
    """O perfil e a sessao usam o MESMO vocabulario — verificado no catalogo de musculos."""

    def test_a_sessao_que_treina_o_ponto_fraco_e_prioritaria(self):
        assert dia_prioritario(PEITO["focus"], ["Peitoral superior"]) is True

    def test_a_sessao_que_nao_treina_o_ponto_fraco_nao_e(self):
        assert dia_prioritario(PERNA["focus"], ["Peitoral superior"]) is False

    # No celular ninguem digita acento, e o dado gravado pode vir de versoes diferentes.
    def test_o_acento_nao_decide_nada(self):
        assert dia_prioritario(["Quadríceps"], ["Quadriceps"]) is True
        assert dia_prioritario(["Tríceps"], ["TRICEPS"]) is True

    def test_sem_ponto_fraco_nenhum_dia_e_prioritario(self):
        assert dia_prioritario(PEITO["focus"], []) is False
        assert dia_prioritario(PEITO["focus"], None) is False

    def test_classifica_os_sete_dias(self):
        assert classificar_semana(SEMANA, ["Peitoral superior"]) == [
            "prioritario", "treino", "descanso", "prioritario", "treino", "descanso", "descanso"]

    def test_semana_curta_completa_com_descanso(self):
        assert len(classificar_semana([PEITO], ["Peitoral superior"])) == 7


class TestAInvarianteQueTornaIssoSeguro:
    """A semana soma o mesmo. Sem isto, a ciclagem vira superavit acidental."""

    def test_o_carboidrato_da_semana_nao_muda(self):
        r = ciclar_semana(ALVOS, SEMANA, ["Peitoral superior"])
        assert r["semana"]["carbs_g"] == pytest.approx(400.0 * 7, abs=1.0)

    def test_a_proteina_nao_cicla(self):
        r = ciclar_semana(ALVOS, SEMANA, ["Peitoral superior"])
        assert {d["protein_g"] for d in r["dias"]} == {180.0}
        assert r["semana"]["protein_g"] == pytest.approx(180.0 * 7, abs=0.5)

    def test_a_gordura_tambem_fica_fixa(self):
        r = ciclar_semana(ALVOS, SEMANA, ["Peitoral superior"])
        assert {d["fat_g"] for d in r["dias"]} == {70.0}

    def test_a_caloria_da_semana_nao_muda(self):
        r = ciclar_semana(ALVOS, SEMANA, ["Peitoral superior"])
        semana_base = (180.0 * 4 + 400.0 * 4 + 70.0 * 9) * 7
        assert r["semana"]["goal_calories"] == pytest.approx(semana_base, rel=0.005)

    @pytest.mark.parametrize("semana,rotulo", [
        ([PEITO] * 7, "sete dias de treino, todos prioritarios"),
        ([PEITO, PERNA, PEITO, PERNA, PEITO, PERNA, None], "seis treinos"),
        ([PEITO, None, None, None, None, None, None], "um treino so"),
        ([PEITO, PERNA, None, None, None, None, None], "dois treinos"),
    ], ids=lambda x: x if isinstance(x, str) else "")
    def test_a_soma_fecha_em_qualquer_formato_de_semana(self, semana, rotulo):
        r = ciclar_semana(ALVOS, semana, ["Peitoral superior"])
        if r is None:
            return  # semana uniforme nao cicla, e isso e coberto em outro teste
        assert r["semana"]["carbs_g"] == pytest.approx(400.0 * 7, abs=1.5), rotulo


class TestONaoCiclarTambemEUmaDecisao:
    """Quando nao ha o que ciclar, a resposta e None e a tela usa a meta unica de sempre."""

    def test_sem_ponto_fraco_marcado_nao_cicla(self):
        assert ciclar_semana(ALVOS, SEMANA, []) is None
        assert ciclar_semana(ALVOS, SEMANA, None) is None

    def test_ponto_fraco_que_a_semana_nao_treina_nao_cicla(self):
        assert ciclar_semana(ALVOS, SEMANA, ["Panturrilhas"]) is None

    def test_semana_sem_treino_nenhum_nao_cicla(self):
        assert ciclar_semana(ALVOS, [None] * 7, ["Peitoral superior"]) is None

    # Sete dias iguais nao tem o que concentrar: mover numero ali seria ruido.
    def test_semana_toda_prioritaria_nao_cicla(self):
        assert ciclar_semana(ALVOS, [PEITO] * 7, ["Peitoral superior"]) is None

    def test_desligado_por_escolha_nao_cicla(self):
        assert ciclar_semana(ALVOS, SEMANA, ["Peitoral superior"], ativo=False) is None

    def test_meta_sem_carboidrato_nao_cicla(self):
        vazio = {**ALVOS, "carbs_g": 0}
        assert ciclar_semana(vazio, SEMANA, ["Peitoral superior"]) is None


class TestOsLimitesProtegemOsDiasFracos:
    """Sem limite, uma semana com um unico treino levaria quase todo o carboidrato para ele."""

    def test_nenhum_dia_fica_abaixo_do_piso(self):
        for semana in ([PEITO, None, None, None, None, None, None], SEMANA):
            r = ciclar_semana(ALVOS, semana, ["Peitoral superior"])
            if r:
                menor = min(d["carbs_g"] for d in r["dias"]) / 400.0
                assert menor >= MINIMO_DO_DIA - 0.02, semana

    def test_nenhum_dia_passa_do_teto(self):
        for semana in ([PEITO, None, None, None, None, None, None], SEMANA):
            r = ciclar_semana(ALVOS, semana, ["Peitoral superior"])
            if r:
                maior = max(d["carbs_g"] for d in r["dias"]) / 400.0
                assert maior <= MAXIMO_DO_DIA + 0.02, semana


class TestOQueAPessoaVe:
    def test_o_dia_do_ponto_fraco_recebe_mais_que_o_descanso(self):
        r = ciclar_semana(ALVOS, SEMANA, ["Peitoral superior"])
        por_classe = {}
        for d in r["dias"]:
            por_classe.setdefault(d["classe"], d["carbs_g"])
        assert por_classe["prioritario"] > por_classe["treino"] > por_classe["descanso"]

    def test_a_caloria_do_dia_acompanha_o_carboidrato_do_dia(self):
        """Caloria fixa com carboidrato variavel seria duas verdades na mesma tela."""
        r = ciclar_semana(ALVOS, SEMANA, ["Peitoral superior"])
        for d in r["dias"]:
            esperado = d["protein_g"] * 4 + d["carbs_g"] * 4 + d["fat_g"] * 9
            assert d["goal_calories"] == pytest.approx(esperado, abs=1)

    def test_os_sete_dias_vem_nomeados_e_em_ordem(self):
        r = ciclar_semana(ALVOS, SEMANA, ["Peitoral superior"])
        assert [d["dia"] for d in r["dias"]][:3] == ["segunda", "terça", "quarta"]
        assert [d["indice"] for d in r["dias"]] == list(range(7))


# Os programas que o MOTOR gera se chamam "Upper 1", "Lower 1" — sem dia da semana no nome.
SESSOES = [
    {"label": "Upper 1", "focus": ["Peitoral esternal", "Peitoral superior", "Dorsais / largura"]},
    {"label": "Lower 1", "focus": ["Quadríceps", "Posteriores", "Glúteos"]},
    {"label": "Upper 2", "focus": ["Peitoral esternal", "Peitoral superior", "Dorsais / largura"]},
    {"label": "Lower 2", "focus": ["Quadríceps", "Posteriores", "Glúteos"]},
]


class TestCiclarSemAgendaDeCalendario:
    """A ciclagem que vale para todo atleta, e nao so para quem colou treino com dia no nome.

    Descoberta que mudou o desenho: o mapa "segunda = peito" so existe quando o rotulo da
    sessao comeca com o dia da semana. Nos programas que o motor gera isso nao acontece — o
    FORGE avanca o ponteiro conforme a pessoa conclui o treino. Entao a pergunta certa e
    "que sessao vem agora", e nao "que dia da semana e hoje".
    """

    def test_a_semana_continua_somando_o_mesmo(self):
        r = ciclar_por_sessao({"carbs_g": 400.0, "protein_g": 180.0, "fat_g": 70.0,
                               "goal_calories": 2950}, SESSOES, 4, ["Peitoral superior"])
        assert r["semana"]["carbs_g"] == pytest.approx(r["semana"]["carbs_g_plano"], abs=2.0)

    @pytest.mark.parametrize("treinos", [2, 3, 4, 5, 6])
    def test_a_soma_fecha_com_qualquer_frequencia(self, treinos):
        r = ciclar_por_sessao(ALVOS, SESSOES, treinos, ["Peitoral superior"])
        assert r is not None, treinos
        assert r["semana"]["carbs_g"] == pytest.approx(r["semana"]["carbs_g_plano"], rel=0.02), treinos

    def test_o_dia_do_ponto_fraco_recebe_mais(self):
        c = ciclar_por_sessao(ALVOS, SESSOES, 4, ["Peitoral superior"])["por_classe"]
        assert c["prioritario"]["carbs_g"] > c["treino"]["carbs_g"] > c["descanso"]["carbs_g"]

    def test_sem_ponto_fraco_nao_cicla(self):
        assert ciclar_por_sessao(ALVOS, SESSOES, 4, []) is None

    def test_ponto_fraco_que_nenhuma_sessao_treina_nao_cicla(self):
        assert ciclar_por_sessao(ALVOS, SESSOES, 4, ["Panturrilhas"]) is None

    def test_sem_sessao_nenhuma_nao_cicla(self):
        assert ciclar_por_sessao(ALVOS, [], 4, ["Peitoral superior"]) is None

    # Se toda sessao treina o ponto fraco e nao ha descanso, nao ha de onde tirar.
    def test_semana_sem_folga_nem_variacao_nao_cicla(self):
        todas = [SESSOES[0]] * 7
        assert ciclar_por_sessao(ALVOS, todas, 7, ["Peitoral superior"]) is None

    def test_proteina_e_gordura_nao_mudam_entre_as_classes(self):
        c = ciclar_por_sessao(ALVOS, SESSOES, 4, ["Peitoral superior"])["por_classe"]
        assert len({v["protein_g"] for v in c.values()}) == 1
        assert len({v["fat_g"] for v in c.values()}) == 1

    def test_nenhuma_classe_estoura_os_limites(self):
        for treinos in range(1, 8):
            r = ciclar_por_sessao(ALVOS, SESSOES, treinos, ["Peitoral superior"])
            if not r:
                continue
            for classe in r["por_classe"].values():
                fator = classe["carbs_g"] / ALVOS["carbs_g"]
                assert MINIMO_DO_DIA - 0.02 <= fator <= MAXIMO_DO_DIA + 0.02, (treinos, classe)


class TestAClasseDeHoje:
    def test_sessao_do_ponto_fraco_e_prioritaria(self):
        assert classe_da_sessao(SESSOES[0], ["Peitoral superior"]) == "prioritario"

    def test_outra_sessao_e_treino(self):
        assert classe_da_sessao(SESSOES[1], ["Peitoral superior"]) == "treino"

    def test_sem_sessao_e_descanso(self):
        assert classe_da_sessao(None, ["Peitoral superior"]) == "descanso"


REFEICOES = [
    {"name": "Café da manhã", "foods": [
        {"food_id": "oats", "grams": 60, "food": {"name": "Aveia em flocos"}}]},
    {"name": "Almoço", "foods": [
        {"food_id": "rice-white", "grams": 250, "food": {"name": "Arroz branco cozido"}},
        {"food_id": "potato", "grams": 200, "food": {"name": "Batata inglesa cozida"}}]},
]


class TestOndeColocarOCarboidrato:
    """Dizer o alvo sem dizer o movimento deixa a pessoa parada.

    Ela sabe que hoje sao 582 g e nao sabe o que fazer com isso. A traducao para gramas de
    comida e o que transforma numero em acao.
    """

    def test_aponta_a_refeicao_com_mais_carboidrato(self):
        r = onde_colocar(140, REFEICOES)
        assert r["refeicao"] == "Almoço"
        assert "Arroz" in r["alimento"]

    def test_traduz_a_diferenca_em_gramas_de_comida(self):
        # 140 g de carboidrato em arroz cozido, que tem 28,1 g por 100 g -> cerca de 498 g.
        assert onde_colocar(140, REFEICOES)["gramas"] == pytest.approx(498, abs=5)

    def test_diferenca_negativa_manda_tirar(self):
        assert onde_colocar(-140, REFEICOES)["acao"] == "tire"
        assert onde_colocar(140, REFEICOES)["acao"] == "some"

    # Mandar comer arroz para quem montou o plano com tapioca seria conselho de outro app.
    def test_a_fonte_sai_do_plano_da_pessoa(self):
        so_tapioca = [{"name": "Lanche", "foods": [
            {"food_id": "tapioca", "grams": 100, "food": {"name": "Tapioca"}}]}]
        assert "Tapioca" in onde_colocar(60, so_tapioca)["alimento"]

    def test_plano_sem_fonte_conhecida_nao_inventa_conselho(self):
        sem_carbo = [{"name": "Jantar", "foods": [
            {"food_id": "chicken-breast", "grams": 200, "food": {"name": "Peito de frango"}}]}]
        assert onde_colocar(140, sem_carbo) is None

    def test_diferenca_irrelevante_nao_vira_conselho(self):
        assert onde_colocar(1, REFEICOES) is None
        assert onde_colocar(0, REFEICOES) is None

    def test_sem_refeicao_nao_quebra(self):
        assert onde_colocar(140, []) is None
        assert onde_colocar(140, None) is None

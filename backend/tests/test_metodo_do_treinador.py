# -*- coding: utf-8 -*-
"""FORGE — o metodo do treinador, extraido dos protocolos reais.

O que estes testes defendem nao e codigo, e FIDELIDADE. O metodo foi lido em 65 protocolos
que o treinador montou a mao; se alguem mexer numa fracao sem entender, o plano gerado deixa
de parecer com o que ele entrega aos alunos, e ninguem percebe — o numero continua fechando.

Por isso os testes prendem as afirmacoes que vieram escritas nos documentos:

  - no dia low o pos-treino vai SEM amido ("Sem batata aqui", literal no protocolo);
  - a gordura do dia low fica em um horario so;
  - o carboidrato do dia high volta para o pos-treino e para o almoco;
  - toda fonte tem alternativa dentro do mesmo papel.

E a invariante de sempre: a distribuicao SOMA o carboidrato do dia, nunca cria nem perde.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from food_diary import DIARY_FOODS  # noqa: E402
from metodo_do_treinador import (  # noqa: E402
    DISTRIBUICAO, ORDEM_DO_DIA, PAPEIS, PROTOCOLOS, REGRAS,
    carbo_por_refeicao, ciclo_do_protocolo, protocolo, regra,
)


class TestAArquiteturaDeRefeicoes:
    """As refeicoes sao nomeadas pela FUNCAO, e nao pela hora do relogio."""

    def test_o_dia_tem_a_ordem_do_metodo(self):
        assert ORDEM_DO_DIA[0] == "pre_treino"
        assert ORDEM_DO_DIA[1] == "pos_treino"
        assert ORDEM_DO_DIA[-1] == "ceia"

    def test_todo_papel_da_ordem_existe(self):
        for papel in ORDEM_DO_DIA:
            assert papel in PAPEIS, papel

    # Quem treina as 6h e quem treina as 19h recebem a mesma estrutura.
    def test_nenhum_papel_se_chama_pela_hora(self):
        for chave in PAPEIS:
            assert "manha" not in chave and "noite" not in chave

    def test_todo_papel_explica_o_porque(self):
        for chave, papel in PAPEIS.items():
            assert papel.get("porque"), chave
            assert len(papel["porque"]) > 30, chave

    # Plano que nao aceita troca e plano que a pessoa abandona.
    def test_todo_papel_com_proteina_oferece_alternativa(self):
        for chave, papel in PAPEIS.items():
            fontes = papel.get("fontes_proteina")
            if fontes:
                assert len(fontes) >= 2, chave

    def test_toda_fonte_citada_existe_no_catalogo(self):
        faltando = []
        for chave, papel in PAPEIS.items():
            for campo in ("fontes_carbo", "fontes_proteina", "fontes_gordura", "acompanha"):
                for fid in papel.get(campo) or []:
                    if fid not in DIARY_FOODS:
                        faltando.append((chave, campo, fid))
        assert not faltando, f"fontes fora do catalogo: {faltando}"


class TestOFormatoDoDiaLow:
    """O dia low nao e so 'menos carboidrato' — ele muda de formato."""

    # "Sem batata aqui", escrito assim no protocolo.
    def test_o_pos_treino_do_dia_low_vai_sem_amido(self):
        assert DISTRIBUICAO["low"]["pos_treino"] == 0.0

    def test_o_almoco_do_dia_low_tambem_vai_sem_amido(self):
        assert DISTRIBUICAO["low"]["almoco"] == 0.0

    def test_o_que_sobra_no_low_cerca_o_treino_e_a_tarde(self):
        low = DISTRIBUICAO["low"]
        assert low["pre_treino"] > 0
        assert low["lanche"] > 0
        assert low["lanche_final"] > 0

    def test_no_dia_high_o_amido_volta_para_as_duas(self):
        alto = DISTRIBUICAO["high"]
        assert alto["pos_treino"] > 0
        assert alto["almoco"] > 0


class TestADistribuicaoSomaODia:
    """Mudar uma fracao nao pode fazer o dia ganhar ou perder carboidrato em silencio."""

    @pytest.mark.parametrize("tipo", ["low", "high", "ganho"])
    def test_a_soma_fecha_no_carboidrato_do_dia(self, tipo):
        divisao = carbo_por_refeicao(400, tipo)
        assert sum(divisao.values()) == pytest.approx(400, abs=1.0), tipo

    @pytest.mark.parametrize("tipo", ["low", "high", "ganho"])
    def test_nenhuma_refeicao_recebe_carboidrato_negativo(self, tipo):
        assert all(v >= 0 for v in carbo_por_refeicao(400, tipo).values()), tipo

    def test_tipo_desconhecido_cai_no_high_em_vez_de_quebrar(self):
        assert sum(carbo_por_refeicao(400, "xpto").values()) == pytest.approx(400, abs=1.0)

    def test_dia_sem_carboidrato_nao_quebra(self):
        assert sum(carbo_por_refeicao(0, "low").values()) == 0


class TestOsProtocolosDeCiclagem:
    """Os nomes sao do treinador, tirados dos proprios arquivos dele."""

    def test_os_protocolos_que_ele_usa_estao_todos_aqui(self):
        for chave in ("3low1high", "4low1high", "6low1high", "saturacao"):
            assert chave in PROTOCOLOS, chave

    def test_o_ciclo_tres_por_um_tem_quatro_dias(self):
        assert ciclo_do_protocolo("3low1high") == ["low", "low", "low", "high"]

    def test_o_seis_por_um_e_mais_restritivo_que_o_tres_por_um(self):
        assert ciclo_do_protocolo("6low1high").count("low") > ciclo_do_protocolo("3low1high").count("low")

    def test_todo_protocolo_diz_para_quem_serve(self):
        for chave, p in PROTOCOLOS.items():
            assert p.get("para_quem"), chave

    def test_protocolo_inexistente_devolve_vazio_em_vez_de_quebrar(self):
        assert ciclo_do_protocolo("nao-existe") == []
        assert protocolo("nao-existe") is None


class TestAsRegrasComRazao:
    """A razao importa tanto quanto a regra: e ela que faz o atleta obedecer."""

    def test_toda_regra_traz_o_porque(self):
        for r in REGRAS:
            assert r.get("porque"), r["chave"]
            assert len(r["porque"]) > 25, r["chave"]

    def test_as_regras_que_vieram_escritas_nos_protocolos_estao_aqui(self):
        for chave in ("pesagem", "gordura_low", "sem_amido_pos_low", "folhas_livres",
                      "canela", "batata_volume", "agua", "substituicao"):
            assert regra(chave) is not None, chave

    # A pesagem pronta e a base da conversao de compra e de panela que ja esta no ar.
    def test_a_regra_da_pesagem_diz_que_e_pronto(self):
        assert "pronto" in regra("pesagem")["regra"].lower()

    def test_regra_inexistente_devolve_nulo(self):
        assert regra("nao-existe") is None


def test_nenhum_dado_de_aluno_entrou_no_codigo():
    """O que foi extraido e a estrutura. Nome, foto e medida de aluno ficaram fora."""
    fonte = (Path(__file__).parent.parent / "metodo_do_treinador.py").read_text(encoding="utf-8")
    proibidos = ["Debora", "Tamy", "Joice", "Nicolau", "Gabriel", "Andrea", "Mariana", "Erika"]
    encontrados = [p for p in proibidos if p.lower() in fonte.lower()]
    assert not encontrados, f"nome de aluno no codigo: {encontrados}"

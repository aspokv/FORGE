# -*- coding: utf-8 -*-
"""Treinar no dia de descanso, e descansar no dia que seria de treino.

Por que isto existe
-------------------
Um atleta ia viajar no fim de semana e quis adiantar o treino de sábado para a quinta, que
na agenda dele é descanso. Não havia como: dia de descanso é renderizado sem sessão, sem
lista de exercícios e sem botão de iniciar, e o único caminho oferecido era a Biblioteca —
que SUBSTITUI a sessão ativa, ou seja, mexe no programa para resolver uma semana atípica.

O que estes testes prendem é que a troca resolve a semana sem virar um segundo programa:
ela é datada, vence sozinha, e o programa continua sendo a verdade por baixo.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import troca_de_dia  # noqa: E402
from workout_calendar import calendar_selection  # noqa: E402

# Quinta não tem sessão: é o descanso da semana. Sábado tem.
SESSOES = [
    {"day": 1, "label": "Segunda · Upper A", "exercises": []},
    {"day": 2, "label": "Terça · Full Body A", "exercises": []},
    {"day": 3, "label": "Quarta · Upper B", "exercises": []},
    {"day": 4, "label": "Sexta · Upper C", "exercises": []},
    {"day": 5, "label": "Sábado · Full Body B", "exercises": []},
    {"day": 6, "label": "Domingo · Upper D", "exercises": []},
]
QUINTA = date(2026, 9, 24)
SEXTA = date(2026, 9, 25)
SABADO = date(2026, 9, 26)
DOMINGO = date(2026, 9, 27)
TROCA = [{"treinar_em": "2026-09-24", "descansar_em": "2026-09-26"}]


def _rotulo(dia, trocas=None):
    r = calendar_selection(SESSOES, dia, trocas=trocas)
    return r["today"]["label"] if r["today"] else None


class TestOCasoQueOriginouTudo:
    """Viajo no fim de semana: quero treinar hoje, quinta, e descansar no sábado."""

    def test_sem_troca_a_quinta_e_descanso(self):
        assert _rotulo(QUINTA) is None

    def test_com_a_troca_a_quinta_recebe_o_treino_do_sabado(self):
        assert _rotulo(QUINTA, TROCA) == "Sábado · Full Body B"

    # A outra ponta. Sem ela a pessoa treinaria DUAS vezes a mesma sessão na semana, e o
    # volume da semana sairia errado sem ninguém perceber.
    def test_e_o_sabado_vira_descanso(self):
        assert _rotulo(SABADO, TROCA) is None

    @pytest.mark.parametrize("dia,esperado", [
        (SEXTA, "Sexta · Upper C"),
        (DOMINGO, "Domingo · Upper D"),
    ])
    def test_os_outros_dias_nao_se_mexem(self, dia, esperado):
        assert _rotulo(dia, TROCA) == esperado


class TestOProgramaContinuaSendoAVerdade:

    def test_sem_trocas_o_calendario_e_o_de_sempre(self):
        """O caminho sem troca não pode mudar de comportamento por causa desta feature."""
        for dia in (QUINTA, SEXTA, SABADO, DOMINGO):
            assert _rotulo(dia, None) == _rotulo(dia, [])

    # Uma troca só vale para as duas datas dela. A quinta da semana seguinte continua sendo
    # descanso — senão a exceção viraria um programa paralelo, divergindo do que o atleta
    # acha que segue.
    def test_a_troca_nao_se_repete_na_semana_seguinte(self):
        assert _rotulo(QUINTA + timedelta(days=7), TROCA) is None

    def test_troca_inteiramente_no_passado_e_descartada(self):
        antiga = [{"treinar_em": "2026-09-10", "descansar_em": "2026-09-12"}]
        assert troca_de_dia.normalizar(antiga, QUINTA) == []

    # Enquanto o dia de descanso não chegou, a troca precisa continuar valendo: é ela que
    # impede o treino de aparecer duas vezes.
    def test_troca_com_uma_ponta_no_futuro_sobrevive(self):
        assert len(troca_de_dia.normalizar(TROCA, SEXTA)) == 1
        assert _rotulo(SABADO, TROCA) is None


class TestOQueNaoPodeAcontecer:

    @pytest.mark.parametrize("entrada", [
        None, [], [{}], ["texto"], [{"treinar_em": "nao-e-data", "descansar_em": "2026-09-26"}],
        [{"treinar_em": "2026-09-24"}], [{"descansar_em": "2026-09-26"}],
        [{"treinar_em": "2026-09-24", "descansar_em": "2026-09-24"}],
    ])
    def test_troca_malformada_nao_derruba_o_programa(self, entrada):
        """O treino do dia vale mais que a exceção: dado ruim é ignorado, não explode."""
        assert troca_de_dia.normalizar(entrada, QUINTA) == []
        assert _rotulo(QUINTA, entrada) is None   # segue sendo descanso, sem erro

    def test_a_mesma_troca_duas_vezes_conta_uma(self):
        assert len(troca_de_dia.normalizar(TROCA + TROCA, QUINTA)) == 1

    @pytest.mark.parametrize("treino,descanso,pedaco", [
        ("2026-09-20", "2026-09-26", "já passou"),
        ("2026-09-24", "2026-09-20", "já passou"),
        ("2026-09-24", "2026-09-24", "dia diferente"),
        ("nao-e-data", "2026-09-26", "datas válidas"),
        ("2026-10-20", "2026-09-26", "dias à frente"),
    ])
    def test_pedido_invalido_explica_o_que_fazer(self, treino, descanso, pedaco):
        with pytest.raises(ValueError) as erro:
            troca_de_dia.validar(treino, descanso, QUINTA)
        assert pedaco in str(erro.value)

    def test_o_alcance_e_de_uma_semana(self):
        """Mover para fora da semana não é mover: é mudar o programa por outro caminho."""
        assert troca_de_dia.ALCANCE_EM_DIAS == 7
        troca_de_dia.validar(QUINTA + timedelta(days=7), SABADO, QUINTA)
        with pytest.raises(ValueError):
            troca_de_dia.validar(QUINTA + timedelta(days=8), SABADO, QUINTA)


class TestProgramaSemDiaDaSemana:
    """PPL gerado pelo motor não fixa dia: não tem descanso fixo e não há o que trocar."""

    SEM_ROTULO = [{"day": 1, "label": "Push", "exercises": []},
                  {"day": 2, "label": "Pull", "exercises": []}]

    def test_calendario_continua_nulo_com_ou_sem_troca(self):
        assert calendar_selection(self.SEM_ROTULO, QUINTA) is None
        assert calendar_selection(self.SEM_ROTULO, QUINTA, trocas=TROCA) is None

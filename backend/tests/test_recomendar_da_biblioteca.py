# -*- coding: utf-8 -*-
"""FORGE — escolher, na biblioteca, o programa que melhor serve a este atleta.

Antes, quem trocava a prioridade e estava num programa da biblioteca ouvia "escolha outro
programa na Biblioteca" — 23 programas para decidir sozinha, justamente no momento em que
ela acabou de dizer o que quer. O FORGE sabe os dias, o perfil e a regiao: ele tem de
apontar QUAL.

O que estes testes defendem:

  - programa que a pessoa NAO consegue cumprir nunca e oferecido (dias demais, sexo errado,
    volume avancado para quem nao declarou experiencia);
  - a prioridade realmente decide entre dois programas viaveis;
  - e a recomendacao vem com o porque, porque recomendacao sem motivo e palpite com nome.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from recomendar_da_biblioteca import (DIFERENCA_MAXIMA_DE_DIAS, avaliar,  # noqa: E402
                                      dias_do_programa, recomendar)
from training_programs import TRAINING_PROGRAMS  # noqa: E402


def perfil(**extra):
    base = {"days": 4, "sex": "Masculino", "experience": "Avançado", "priorities": []}
    base.update(extra)
    return base


class TestQuemNaoServeNaoEOferecido:

    def test_programa_com_dias_demais_e_eliminado(self):
        for programa in TRAINING_PROGRAMS:
            nota = avaliar(programa, perfil(days=3))
            if nota:
                assert abs(nota["dias"] - 3) <= DIFERENCA_MAXIMA_DE_DIAS, nota["nome"]

    def test_programa_de_um_sexo_nao_vai_para_o_outro(self):
        femininos = [p for p in TRAINING_PROGRAMS
                     if str(p.get("audience_type", "")).lower() == "female"]
        assert femininos, "o catalogo precisa ter programa feminino para este teste valer"
        for programa in femininos:
            assert avaliar(programa, perfil(sex="Masculino", days=dias_do_programa(programa))) is None

    # Volume avancado nao e "mais treino": e um programa que assume uma capacidade de
    # recuperar que nem todo mundo tem.
    def test_volume_avancado_nao_vai_para_quem_nao_declarou_experiencia(self):
        pesados = [p for p in TRAINING_PROGRAMS if p.get("safety") in ("expert", "advanced")]
        for programa in pesados:
            assert avaliar(programa, perfil(experience="Recreativo",
                                            days=dias_do_programa(programa))) is None

    def test_ninguem_fica_sem_nenhuma_opcao(self):
        for dias in (3, 4, 5, 6):
            r = recomendar(perfil(days=dias))
            assert r["melhor"], f"nenhum programa para {dias} dias"


class TestAPrioridadeDecide:

    def test_trocar_a_prioridade_troca_a_recomendacao(self):
        a = recomendar(perfil(days=5, sex="Feminino", priorities=["Glúteos"]))["melhor"]
        b = recomendar(perfil(days=5, sex="Feminino", priorities=["Dorsais / largura"]))["melhor"]
        assert a and b
        assert a["id"] != b["id"], f"mesma escolha para prioridades opostas: {a['nome']}"

    def test_o_escolhido_cobre_mais_a_prioridade_que_as_alternativas(self):
        r = recomendar(perfil(days=5, sex="Feminino", priorities=["Glúteos", "Posteriores"]))
        melhor, *outros = r["recomendados"]
        assert melhor["cobertura"] > 0, "o escolhido nao cobre a prioridade"
        for outro in outros:
            assert melhor["nota"] >= outro["nota"]

    # Fracao e nao total absoluto: um programa de seis dias tem mais series em qualquer
    # musculo, e comparar o numero cru escolheria sempre o mais longo.
    def test_a_cobertura_e_fracao_e_nao_volume_bruto(self):
        r = recomendar(perfil(days=6, priorities=["Bíceps"]))
        for opcao in r["recomendados"]:
            assert 0.0 <= opcao["cobertura"] <= 1.0, opcao


class TestARecomendacaoSeExplica:

    def test_vem_com_o_porque(self):
        r = recomendar(perfil(days=5, priorities=["Peitoral superior"]))
        assert r["porque"]
        assert "sessões por semana" in r["porque"]

    def test_o_porque_cita_a_prioridade_quando_ela_existe(self):
        r = recomendar(perfil(days=5, priorities=["Peitoral superior"]))
        assert "Peitoral superior" in r["porque"]

    def test_sem_prioridade_o_porque_nao_inventa_uma(self):
        r = recomendar(perfil(days=4, priorities=[]))
        assert "prioridades" not in r["porque"]

    def test_devolve_alternativas_e_nao_so_a_primeira(self):
        r = recomendar(perfil(days=5, priorities=["Bíceps"]), quantos=3)
        assert len(r["recomendados"]) >= 2

    def test_a_ordem_e_da_melhor_para_a_pior(self):
        notas = [o["nota"] for o in recomendar(perfil(days=5, priorities=["Bíceps"]))["recomendados"]]
        assert notas == sorted(notas, reverse=True)


class TestOCatalogoEstaSaudavel:
    """Se um programa cadastrado tiver dado quebrado, e melhor saber aqui."""

    @pytest.mark.parametrize("programa", TRAINING_PROGRAMS, ids=lambda p: p["id"])
    def test_todo_programa_tem_sessoes_na_primeira_fase(self, programa):
        assert dias_do_programa(programa) > 0, programa["name"]

    @pytest.mark.parametrize("programa", TRAINING_PROGRAMS, ids=lambda p: p["id"])
    def test_todo_exercicio_do_programa_existe_no_catalogo(self, programa):
        from recomendar_da_biblioteca import _EXERCICIOS
        faltando = [item.get("exercise_id")
                    for fase in programa.get("phases", [])
                    for sessao in fase.get("sessions", [])
                    for item in sessao.get("exercises", [])
                    if item.get("exercise_id") not in _EXERCICIOS]
        assert not faltando, f"{programa['name']}: {sorted(set(faltando))}"

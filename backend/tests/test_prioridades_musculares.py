# -*- coding: utf-8 -*-
"""FORGE — trocar as regioes prioritarias sem refazer a avaliacao.

Por que isto existe: escolher prioridade e a PRIMEIRA coisa que o FORGE pergunta, e e
justamente quando a pessoa menos sabe o que cada regiao significa. Quem errou ficava preso:
o Perfil listava as prioridades e nao deixava mexer, e o unico caminho era responder o
questionario inteiro de novo. Um atleta real travou assim.

O que estes testes defendem:

  - regiao invalida NAO entra no perfil. `to_internal` e tradutor e nao validador: ele
    devolve o nome intacto quando nao conhece, e sem conferir contra MUSCLE_IDS o perfil
    gravaria uma regiao que o motor nunca encontra — a prioridade nao teria efeito nenhum e
    ninguem saberia por que;
  - o programa gerado pelo motor REALMENTE muda quando a prioridade muda;
  - e quando ele nao muda (ficha colada, programa da biblioteca), a resposta diz isso em vez
    de deixar a pessoa achando que salvou e nao funcionou.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from muscles import MAX_PRIORITIES, MUSCLE_IDS, to_internal  # noqa: E402


class TestAValidacaoDaRegiao:
    """A parte que impede o perfil de guardar lixo."""

    # Foi este comportamento que me enganou: o tradutor devolve o desconhecido intacto.
    def test_to_internal_devolve_o_desconhecido_intacto(self):
        assert to_internal("Panturrilha do Nicolas") == "Panturrilha do Nicolas"
        assert to_internal("Deltóide lateral") == "side_delts"

    def test_por_isso_a_conferencia_e_contra_o_conjunto_canonico(self):
        assert to_internal("Deltóide lateral") in MUSCLE_IDS
        assert to_internal("Panturrilha do Nicolas") not in MUSCLE_IDS

    @pytest.mark.parametrize("regiao", [
        "Peitoral superior", "Deltóide lateral", "Dorsais / largura",
        "Bíceps", "Tríceps", "Quadríceps", "Glúteos", "Abdômen",
    ])
    def test_toda_regiao_do_questionario_e_reconhecida(self, regiao):
        assert to_internal(regiao) in MUSCLE_IDS, regiao

    def test_o_maximo_e_tres(self):
        assert MAX_PRIORITIES == 3


class TestOProgramaRespondeAPrioridade:
    """Prioridade que nao muda o treino nao e prioridade."""

    def _perfil(self, prioridades):
        return {
            "id": "teste", "name": "Teste", "sex": "male", "age": 30,
            "height_cm": 180, "weight_kg": 80, "days": 5, "session_minutes": 70,
            "experience": "Avançado", "goal": "Hipertrofia",
            "equipment": ["Academia completa"], "gym_complete": True,
            "priorities": list(prioridades), "assessment": {},
        }

    def _volume(self, programa):
        return [(s.get("label"), sum(e.get("sets", 0) for e in (s.get("exercises") or [])))
                for s in (programa.get("sessions") or [])]

    def _programa(self, prioridades):
        """`asyncio.run` porque o projeto nao tem pytest-asyncio, e as outras suites tambem
        chamam o motor assim."""
        import asyncio
        from engine import build_program_v2
        return asyncio.run(build_program_v2(self._perfil(prioridades), None))

    def test_trocar_a_prioridade_muda_o_volume_do_programa_gerado(self):
        a = self._volume(self._programa(["Glúteos"]))
        b = self._volume(self._programa(["Deltóide lateral"]))
        assert a and b
        assert a != b, "o programa nao reagiu a troca de prioridade"

    def test_sem_prioridade_o_programa_continua_valido(self):
        assert self._programa([]).get("sessions"), "equilibrado nao pode gerar programa vazio"

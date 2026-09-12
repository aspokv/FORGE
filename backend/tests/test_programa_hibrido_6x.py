# -*- coding: utf-8 -*-
"""
O hibrido 6x da biblioteca, e a regra que vale para qualquer ficha que entre nela.

O teste que mais importa aqui e o do CATALOGO. Um `exercise_id` inventado nao quebra import
nem derruba teste nenhum: ele atravessa o backend inteiro em silencio e so aparece na tela
do atleta, no meio da sessao, como um item sem foto e sem nome proprio. E o tipo de defeito
que chega ao cliente porque nada no caminho reclamou.

Os demais testes prendem o que a ficha do proprietario definiu: a rotacao das enfases, os
RIR por tipo de exercicio e os descansos.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")
os.environ.setdefault("FORGE_JWT_SECRET", "teste")

from engine import EXERCISES  # noqa: E402
from training_programs import TRAINING_PROGRAMS  # noqa: E402

ID = "hibrido-6x-peitoral-dorsal"


@pytest.fixture(scope="module")
def programa():
    achados = [p for p in TRAINING_PROGRAMS if p["id"] == ID]
    assert len(achados) == 1, f"esperado exatamente um {ID}, achei {len(achados)}"
    return achados[0]


@pytest.fixture(scope="module")
def sessoes(programa):
    return programa["phases"][0]["sessions"]


def _ids_do_catalogo():
    itens = EXERCISES if isinstance(EXERCISES, list) else list(EXERCISES.values())
    return {e["id"] for e in itens}


# ── A trava que importa ──────────────────────────────────────────────────────────────

def test_todo_exercicio_existe_no_catalogo(sessoes):
    catalogo = _ids_do_catalogo()
    fora = sorted({e["exercise_id"] for s in sessoes for e in s["exercises"]
                   if e["exercise_id"] not in catalogo})
    assert not fora, f"exercícios que não existem no catálogo: {fora}"


def test_nenhuma_ficha_da_biblioteca_aponta_para_exercicio_inexistente():
    """Vale para TODAS as fichas, nao so para esta: o defeito e igual em qualquer uma."""
    catalogo = _ids_do_catalogo()
    fora = set()
    for p in TRAINING_PROGRAMS:
        for fase in p.get("phases", []):
            for s in fase.get("sessions", []):
                for e in s.get("exercises", []):
                    if e.get("exercise_id") not in catalogo:
                        fora.add((p["id"], e.get("exercise_id")))
    assert not fora, f"fichas apontando para exercício inexistente: {sorted(fora)}"


# ── A forma da ficha ─────────────────────────────────────────────────────────────────

def test_seis_sessoes_de_sete_exercicios(sessoes):
    assert len(sessoes) == 6
    for s in sessoes:
        assert len(s["exercises"]) == 7, f"{s['label']} tem {len(s['exercises'])}"


def test_a_rotacao_das_enfases_esta_preservada(sessoes):
    """
    E a razao de a ficha existir: peitoral superior, medio e inferior em dias diferentes,
    costas por largura, espessura e extensao do ombro. Perder a ordem descaracteriza tudo.
    """
    esperado = ["Peito superior", "Dorsal largura", "Peito médio",
                "Costas espessura", "Peito inferior", "Dorsal e posterior"]
    for s, trecho in zip(sessoes, esperado):
        assert trecho in s["label"], f"{s['label']} não contém {trecho!r}"


def test_quadriceps_e_posterior_alternam_dia_a_dia(sessoes):
    quadriceps = [i for i, s in enumerate(sessoes) if "Quadríceps" in s["focus"]]
    posterior = [i for i, s in enumerate(sessoes) if "Posterior de coxa" in s["focus"]]
    assert quadriceps == [0, 2, 4], quadriceps
    assert posterior == [1, 3, 5], posterior


# ── As regras de execucao que o proprietario definiu ─────────────────────────────────

def test_composto_e_isolador_tem_RIR_e_descanso_proprios(sessoes):
    """A ficha separa os dois: composto 1-2 RIR e 2 a 3 min; isolador 1 RIR e 60 a 120 s."""
    vistos = {(e["rir"], e["rest"]) for s in sessoes for e in s["exercises"]}
    assert vistos == {("1–2", "150 s"), ("1", "90 s")}, vistos


def test_todo_isolador_avisa_do_zero_RIR_na_ultima_serie(sessoes):
    isoladores = [e for s in sessoes for e in s["exercises"] if e["rir"] == "1"]
    assert isoladores, "nenhum isolador encontrado"
    for e in isoladores:
        assert "0 RIR na última série" in e["note"], e["exercise_id"]


def test_a_regra_de_progressao_chega_ao_atleta(sessoes):
    """
    A nota do primeiro exercicio e o campo que sobrevive ao salvamento de programa
    personalizado. Se a progressao sair dali, ela some ao aplicar a ficha.
    """
    assert "2,5% a 5%" in sessoes[0]["exercises"][0]["note"]


def test_a_ficha_se_apresenta_como_avancada_e_sem_genero(programa):
    assert programa["level"] == "Avançado"
    assert programa["audience_type"] == "unisex"
    assert programa["category"] == "abcdef"

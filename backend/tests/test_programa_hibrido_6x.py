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


# ── Versao 2: upper / lower ──────────────────────────────────────────────────────────

ID_V2 = "hibrido-6x-upper-lower"


@pytest.fixture(scope="module")
def sessoes_v2():
    achados = [p for p in TRAINING_PROGRAMS if p["id"] == ID_V2]
    assert len(achados) == 1
    return achados[0]["phases"][0]["sessions"]


def test_v2_alterna_upper_e_lower(sessoes_v2):
    """A estrutura E a ficha: perder a alternancia vira outro programa."""
    tipos = ["Upper A", "Lower A", "Upper B", "Lower B", "Upper C", "Lower C"]
    for s, esperado in zip(sessoes_v2, tipos):
        assert esperado in s["label"], f"{s['label']} não é {esperado}"


def test_v2_usa_a_regra_de_isolador_da_propria_ficha(sessoes_v2):
    """
    A V2 escreve "0-1 RIR na ultima serie", e nao "1 RIR podendo chegar a 0" como a V1.
    O campo segue a ficha que esta sendo transcrita, nao a versao anterior.
    """
    vistos = {(e["rir"], e["rest"]) for s in sessoes_v2 for e in s["exercises"]}
    assert vistos == {("1–2", "150 s"), ("0–1", "90 s")}, vistos


def test_v2_tem_quarenta_exercicios(sessoes_v2):
    assert sum(len(s["exercises"]) for s in sessoes_v2) == 40


# ── Versao 3: full body rotativo, com trabalho leve ──────────────────────────────────

ID_V3 = "hibrido-6x-full-body"


@pytest.fixture(scope="module")
def sessoes_v3():
    achados = [p for p in TRAINING_PROGRAMS if p["id"] == ID_V3]
    assert len(achados) == 1
    return achados[0]["phases"][0]["sessions"]


def test_v3_tem_exatamente_um_estimulo_leve_por_sessao(sessoes_v3):
    """
    O leve e a ideia central da V3: o grupo que nao e da vez entra com duas series so, para
    somar volume sem somar fadiga. Duas leves num dia, ou nenhuma, descaracteriza a ficha.
    """
    for s in sessoes_v3:
        leves = [e for e in s["exercises"] if e["rir"] == "2–3"]
        assert len(leves) == 1, f"{s['label']} tem {len(leves)} estímulos leves"
        assert leves[0]["sets"] == 2, f"{s['label']}: o leve tem {leves[0]['sets']} séries"


def test_v3_manda_explicitamente_nao_ir_a_falha_no_leve(sessoes_v3):
    """Sem essa ordem escrita, o leve vira mais uma serie pesada e a ficha perde a funcao."""
    for s in sessoes_v3:
        leve = next(e for e in s["exercises"] if e["rir"] == "2–3")
        assert "Não levar à falha" in leve["note"], s["label"]


def test_v3_alterna_o_leve_entre_peito_e_costas(sessoes_v3):
    """
    Segunda, quarta e sexta sao dias de peito pesado, entao o leve e de costas; terca,
    quinta e sabado invertem. E essa alternancia que mantem a frequencia dos dois grupos.
    """
    costas = {"lat-pulldown", "cable-row", "cable-straight-arm-pulldown"}
    peito = {"pec-deck", "cable-fly", "cable-incline-fly"}
    esperado = [costas, peito, costas, peito, costas, peito]
    for s, grupo in zip(sessoes_v3, esperado):
        leve = next(e for e in s["exercises"] if e["rir"] == "2–3")
        assert leve["exercise_id"] in grupo, f"{s['label']}: leve é {leve['exercise_id']}"


def test_v3_tem_seis_exercicios_por_sessao(sessoes_v3):
    for s in sessoes_v3:
        assert len(s["exercises"]) == 6, f"{s['label']} tem {len(s['exercises'])}"


# ── As tres convivem ─────────────────────────────────────────────────────────────────

def test_as_tres_versoes_existem_e_nao_colidem():
    ids = [p["id"] for p in TRAINING_PROGRAMS]
    for pid in (ID, ID_V2, ID_V3):
        assert ids.count(pid) == 1, f"{pid} aparece {ids.count(pid)} vezes"


def test_as_tres_tem_nomes_distintos_na_biblioteca():
    """Nome repetido na lista deixa o atleta sem saber qual esta escolhendo."""
    nomes = [p["name"] for p in TRAINING_PROGRAMS if p["id"] in (ID, ID_V2, ID_V3)]
    assert len(set(nomes)) == 3, nomes

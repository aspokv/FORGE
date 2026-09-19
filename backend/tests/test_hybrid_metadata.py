# -*- coding: utf-8 -*-
"""Metadado do Hybrid: região, demanda de bíceps e estresse articular.

O que esta suíte protege
------------------------
A especificação do Hybrid pede três campos novos em cada exercício. Cadastrá-los nos 134
duplicaria informação que o catálogo já tem sob outro nome, e duas fontes que podem
divergir é como um catálogo ganha um defeito silencioso: alguém edita `movement_pattern`,
esquece `region`, e a partir daí o motor e a tela discordam sobre o mesmo exercício.

Então os testes cobram duas coisas dos 134 de uma vez:

  1. Toda pergunta tem resposta. Nenhum exercício pode cair fora da classificação, porque
     um exercício sem região nunca entra numa rotação de vetor e some da prescrição sem
     ninguém perceber.

  2. A resposta é a que um treinador daria. Puxada é largura, remada é espessura, agachamento
     é joelho, stiff é quadril. Isso está escrito caso a caso, e não por amostragem.

Roda com `--noconftest`: nada aqui toca banco, rede ou relógio.
"""
import io
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from hybrid_metadata import (  # noqa: E402
    ADUTORES, ALTA, BAIXA, CLAVICULAR, COSTAL, ESPESSURA, ESTERNAL, FLEXAO_DE_JOELHO,
    JOELHO, LARGURA, MEDIA, PANTURRILHA, QUADRIL, REGIAO_EXPLICITA, TRAPEZIO,
    demanda_de_biceps, estresse_articular, metadados_de, regiao_de,
)

EXERCICIOS = json.load(io.open(Path(__file__).parent.parent / "exercises.json",
                               encoding="utf-8"))
POR_ID = {e["id"]: e for e in EXERCICIOS}

REGIOES_CONHECIDAS = {
    CLAVICULAR, ESTERNAL, COSTAL, LARGURA, ESPESSURA, TRAPEZIO,
    JOELHO, QUADRIL, FLEXAO_DE_JOELHO, PANTURRILHA, ADUTORES,
}


def ex(eid):
    assert eid in POR_ID, f"{eid} não está no catálogo — o teste é que está errado"
    return POR_ID[eid]


# ── Cobertura: ninguém pode cair fora ───────────────────────────────────────────────

def test_todo_exercicio_do_catalogo_tem_regiao():
    """Um exercício sem região nunca entra numa rotação de vetor: ele some da prescrição
    sem levantar erro nenhum."""
    sem = [e["id"] for e in EXERCICIOS if not regiao_de(e)]
    assert sem == [], f"sem região: {sem}"


def test_todo_exercicio_tem_demanda_de_biceps_e_estresse_articular():
    validos = {ALTA, MEDIA, BAIXA}
    for e in EXERCICIOS:
        m = metadados_de(e)
        assert m["biceps_demand"] in validos, f"{e['id']}: {m['biceps_demand']}"
        assert m["joint_stress"] in validos, f"{e['id']}: {m['joint_stress']}"


def test_os_grupos_grandes_usam_as_regioes_do_hybrid_e_nao_o_nome_do_musculo():
    """Peito, costas e pernas são os três grupos que o Hybrid rotaciona por região. Se um
    deles devolvesse o próprio músculo, a rotação viraria a divisão de sempre."""
    grandes = {"upper_chest", "mid_chest", "lats", "upper_back", "traps",
               "quads", "hamstrings", "glutes", "adductors", "calves"}
    for e in EXERCICIOS:
        if e["primary_muscle"] in grandes:
            assert regiao_de(e) in REGIOES_CONHECIDAS, \
                f"{e['id']} ({e['primary_muscle']}) caiu em {regiao_de(e)}"


# ── Peitoral: os três vetores ───────────────────────────────────────────────────────

@pytest.mark.parametrize("eid,esperado", [
    ("bb-incline-press", CLAVICULAR),
    ("db-incline-press", CLAVICULAR),
    ("cable-incline-fly", CLAVICULAR),
    ("bb-bench-press", ESTERNAL),
    ("pec-deck", ESTERNAL),
    ("db-fly", ESTERNAL),
])
def test_peitoral_clavicular_e_esternal_saem_do_musculo(eid, esperado):
    assert regiao_de(ex(eid)) == esperado


@pytest.mark.parametrize("eid", sorted(REGIAO_EXPLICITA))
def test_o_costal_existe_e_e_exatamente_a_excecao_declarada(eid):
    """Os três de peitoral inferior estão todos como `mid_chest`, e `bb-decline-press`
    divide `horizontal_press` com o supino reto: não há par (músculo, padrão) que os
    separe. É o único caso do catálogo que a derivação não fecha."""
    exercicio = ex(eid)
    assert exercicio["primary_muscle"] == "mid_chest"
    assert regiao_de(exercicio) == COSTAL


def test_o_supino_reto_e_o_declinado_sao_indistinguiveis_sem_a_excecao():
    """Prova de que a exceção não é preguiça: os dois compartilham músculo E padrão."""
    reto, declinado = ex("bb-bench-press"), ex("bb-decline-press")
    assert reto["primary_muscle"] == declinado["primary_muscle"]
    assert reto["movement_pattern"] == declinado["movement_pattern"]
    assert regiao_de(reto) != regiao_de(declinado)


# ── Costas: largura, espessura, trapézio ────────────────────────────────────────────

@pytest.mark.parametrize("eid,esperado", [
    ("pullup", LARGURA),
    ("cable-pulldown", LARGURA),
    ("neutral-pulldown", LARGURA),
    ("db-pullover", LARGURA),                     # extensão de ombro é largura
    ("cable-straight-arm-pulldown", LARGURA),
    ("bb-row", ESPESSURA),
    ("cable-row", ESPESSURA),
    ("db-row", ESPESSURA),
    ("db-shrug", TRAPEZIO),
    ("smith-shrug", TRAPEZIO),
])
def test_costas_separam_largura_de_espessura(eid, esperado):
    assert regiao_de(ex(eid)) == esperado


def test_o_pullover_conta_como_largura_e_nao_como_espessura():
    """A especificação coloca `shoulderExtension` junto de `verticalPull` em WIDTH. É a
    decisão que impede o pullover de ser oferecido como se fosse remada."""
    assert regiao_de(ex("db-pullover")) == regiao_de(ex("pullup"))


# ── Pernas ──────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("eid,esperado", [
    ("bb-squat", JOELHO),
    ("leg-press", JOELHO),
    ("leg-extension", JOELHO),
    ("rdl", QUADRIL),
    ("hip-thrust", QUADRIL),
    ("conventional-deadlift", QUADRIL),
    ("lying-leg-curl", FLEXAO_DE_JOELHO),
    ("seated-calf", PANTURRILHA),
    ("machine-standing-calf", PANTURRILHA),
])
def test_pernas_separam_joelho_de_quadril(eid, esperado):
    assert regiao_de(ex(eid)) == esperado


def test_stiff_e_agachamento_nunca_caem_na_mesma_regiao():
    """Se caíssem, o Hybrid poderia prescrever os dois como se fossem o mesmo estímulo e
    chamar isso de rotação."""
    assert regiao_de(ex("rdl")) != regiao_de(ex("bb-squat"))


# ── Demanda de bíceps: a restrição de tendão ────────────────────────────────────────

def test_a_pegada_e_lida_do_id_quando_ela_esta_la():
    """Os ids do FORGE já carregam `supinated-` e `neutral-`. Onde o id diz, ele manda."""
    assert demanda_de_biceps(ex("supinated-pulldown")) == ALTA
    assert demanda_de_biceps(ex("supinated-bb-row")) == ALTA
    assert demanda_de_biceps(ex("neutral-pullup")) == BAIXA
    assert demanda_de_biceps(ex("neutral-pulldown")) == BAIXA


def test_rosca_com_o_biceps_alongado_sob_carga_e_demanda_ALTA():
    """É a posição que dói em quem tem o tendão distal sensível, e é exatamente o que a
    restrição `bicepsTendonSensitivity` precisa penalizar."""
    for eid in ("incline-db-curl", "bayesian-curl", "spider-curl"):
        assert demanda_de_biceps(ex(eid)) == ALTA, eid


def test_a_pegada_tambem_e_lida_do_NOME_quando_o_id_nao_diz():
    """`cable-row` é "Remada baixa triângulo na polia": pegada neutra, e o id não conta.

    Ler só o id deixava as oito remadas do catálogo em demanda média ou alta, e aí ligar a
    restrição de tendão apagaria o vetor de espessura inteiro em vez de trocar um
    exercício. Foi o teste de cobertura logo abaixo que mostrou isso.
    """
    assert demanda_de_biceps(ex("cable-row")) == BAIXA
    assert "neutral" not in ex("cable-row")["id"]


def test_martelo_e_corda_sao_a_saida_confortavel():
    """Antebraço neutro tira o tendão da posição que incomoda. Quando a restrição está
    ligada, é para cá que a seleção deve migrar."""
    for eid in ("db-hammer-curl", "cable-hammer-curl"):
        assert demanda_de_biceps(ex(eid)) == BAIXA, eid


def test_agachamento_nao_cobra_biceps():
    assert demanda_de_biceps(ex("bb-squat")) == BAIXA


def test_existe_alternativa_de_costas_para_quem_tem_o_tendao_sensivel():
    """A restrição é penalidade, e não lista de proibição — mas ela só é honesta se
    sobrar o que prescrever. Se todas as costas fossem demanda ALTA, penalizar seria o
    mesmo que apagar o grupo."""
    costas = [e for e in EXERCICIOS if e["primary_muscle"] in ("lats", "upper_back")]
    confortaveis = [e["id"] for e in costas if demanda_de_biceps(e) == BAIXA]
    assert len(confortaveis) >= 3, f"só {len(confortaveis)} opções: {confortaveis}"
    # E elas precisam cobrir os DOIS vetores, senão a restrição apagaria largura ou
    # espessura em vez de apagar um exercício.
    regioes = {regiao_de(POR_ID[i]) for i in confortaveis}
    assert {LARGURA, ESPESSURA} <= regioes, f"cobre só {regioes}"


# ── Estresse articular ──────────────────────────────────────────────────────────────

def test_maquina_e_cabo_cobram_menos_articulacao_que_peso_livre_pesado():
    assert estresse_articular(ex("leg-press")) == BAIXA
    assert estresse_articular(ex("conventional-deadlift")) in (ALTA, MEDIA)
    assert estresse_articular(ex("pec-deck")) == BAIXA


def test_terra_convencional_e_o_teto_de_estresse_articular():
    """Se o movimento mais sistêmico do catálogo não for ALTA, a escala não separa nada."""
    assert estresse_articular(ex("conventional-deadlift")) == ALTA


# ── O catálogo inteiro, em números ──────────────────────────────────────────────────

def test_a_distribuicao_de_regioes_nao_tem_buraco():
    """Uma região com zero exercícios é uma arquitetura que não pode ser montada: o
    Hybrid pediria `costal` num dia e receberia lista vazia."""
    contagem = Counter(regiao_de(e) for e in EXERCICIOS)
    for regiao in (CLAVICULAR, ESTERNAL, COSTAL, LARGURA, ESPESSURA,
                   JOELHO, QUADRIL, FLEXAO_DE_JOELHO, PANTURRILHA):
        assert contagem[regiao] >= 2, f"{regiao} tem só {contagem[regiao]} exercício(s)"

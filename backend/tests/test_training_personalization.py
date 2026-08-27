"""Perfil (feminino/masculino) e regioes prioritarias na geracao do treino.

Duas regras que o produto exige e que precisam valer ao mesmo tempo:

  1. o perfil da um PONTO DE PARTIDA quando o atleta ainda nao declarou prioridade;
  2. a prioridade declarada tem peso MAIOR que o perfil — nada de proibir mulher de
     priorizar peito nem homem de priorizar gluteos.

Testes puros: nao precisam de banco nem de servidor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from engine import VOLUME_TIERS, calculate_weekly_volume
from muscles import (
    DEFAULT_EMPHASIS_BY_SEX, MAX_PRIORITIES, get_profile_priorities_internal,
    get_ranked_priorities, normalize_sex,
)

BASE = {"days": 4, "experience": "Intermediário", "assessment": {}}


def perfil(**kw):
    return {**BASE, **kw}


def series(p):
    return {m: d["target_sets"] for m, d in calculate_weekly_volume(p, "ppl", 4).items()}


def tier(p, muscle):
    return calculate_weekly_volume(p, "ppl", 4)[muscle]["tier"]


# ── o perfil como ponto de partida ───────────────────────────────────────────────────

@pytest.mark.parametrize("valor", ["Feminino", "feminino", "female", "F", "mulher"])
def test_perfil_feminino_e_reconhecido(valor):
    assert normalize_sex(valor) == "female"


@pytest.mark.parametrize("valor", ["Masculino", "male", "M", "homem"])
def test_perfil_masculino_e_reconhecido(valor):
    assert normalize_sex(valor) == "male"


def test_perfil_feminino_muda_a_geracao():
    p = perfil(sex="Feminino")
    principal, _ = get_ranked_priorities(p)
    assert principal == DEFAULT_EMPHASIS_BY_SEX["female"][0] == "glutes"
    assert series(p)["glutes"] > series(perfil())["glutes"]


def test_perfil_masculino_muda_a_geracao():
    p = perfil(sex="Masculino")
    principal, _ = get_ranked_priorities(p)
    assert principal == DEFAULT_EMPHASIS_BY_SEX["male"][0]
    assert series(p)[principal] > series(perfil())[principal]


def test_os_dois_perfis_geram_treinos_diferentes():
    assert series(perfil(sex="Feminino")) != series(perfil(sex="Masculino"))


# ── a prioridade declarada vence o perfil ────────────────────────────────────────────

def test_homem_pode_priorizar_gluteos():
    p = perfil(sex="Masculino", priorities=["Glúteos"])
    assert get_ranked_priorities(p)[0] == "glutes"
    assert tier(p, "glutes") == "priority"
    assert series(p)["glutes"] == VOLUME_TIERS["priority"]["target_sets"]


def test_mulher_pode_priorizar_peito_e_bracos():
    p = perfil(sex="Feminino", priorities=["Peitoral esternal", "Bíceps"])
    principal, secundarias = get_ranked_priorities(p)
    assert principal == "mid_chest"
    assert "biceps" in secundarias
    # o ponto de partida feminino nao pode se impor sobre a escolha declarada
    assert tier(p, "glutes") != "priority"


def test_prioridade_declarada_substitui_o_ponto_de_partida():
    p = perfil(sex="Feminino", priorities=["Trapézio"])
    assert get_profile_priorities_internal(p) == ["traps"]


# ── ranking e teto ───────────────────────────────────────────────────────────────────

def test_a_primeira_da_lista_e_a_principal():
    p = perfil(priorities=["Bíceps", "Glúteos", "Panturrilhas"])
    principal, secundarias = get_ranked_priorities(p)
    assert principal == "biceps"
    assert secundarias == ["glutes", "calves"]


def test_principal_recebe_mais_volume_que_secundaria():
    p = perfil(priorities=["Bíceps", "Glúteos"])
    s = series(p)
    assert s["biceps"] > s["glutes"] > series(perfil())["glutes"]
    assert tier(p, "biceps") == "priority"
    assert tier(p, "glutes") == "priority_secondary"


def test_prioridades_sao_limitadas():
    muitas = ["Glúteos", "Bíceps", "Tríceps", "Quadríceps", "Panturrilhas",
              "Abdômen", "Trapézio", "Adutores", "Oblíquos"]
    p = perfil(priorities=muitas)
    assert len(get_profile_priorities_internal(p)) == MAX_PRIORITIES
    with_emphasis = [m for m, s in series(p).items() if s > VOLUME_TIERS["normal"]["target_sets"]]
    assert len(with_emphasis) == MAX_PRIORITIES


def test_duplicatas_nao_consomem_o_teto():
    p = perfil(priorities=["Glúteos", "Glúteos", "Bíceps"])
    assert get_profile_priorities_internal(p) == ["glutes", "biceps"]


def test_prioridade_nao_abandona_o_resto_do_corpo():
    """Enfase nao pode zerar ninguem: o restante fica no tier normal, nao em nada."""
    s = series(perfil(priorities=["Glúteos"]))
    assert all(v >= VOLUME_TIERS["maintenance"]["target_sets"] for v in s.values())


# ── compatibilidade com usuario existente ────────────────────────────────────────────

def test_perfil_antigo_sem_sexo_e_sem_prioridade_nao_muda():
    p = perfil()
    assert get_ranked_priorities(p) == (None, [])
    assert get_profile_priorities_internal(p) == []
    assert set(series(p).values()) <= {VOLUME_TIERS["normal"]["target_sets"],
                                       VOLUME_TIERS["maintenance"]["target_sets"]}


def test_sexo_invalido_nao_quebra_a_geracao():
    p = perfil(sex="prefiro nao dizer")
    assert normalize_sex(p["sex"]) is None
    assert get_ranked_priorities(p) == (None, [])


def test_prioridade_legada_por_nome_de_frontend_continua_valendo():
    """A avaliacao antiga grava o nome em portugues, nao o id interno."""
    assert get_profile_priorities_internal(perfil(priorities=["Dorsais / largura"])) == ["lats"]

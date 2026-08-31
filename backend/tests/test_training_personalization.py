"""Training personalization: explicit priorities own the emphasis.

Sex may exist in the profile, but it must not silently create an aesthetic goal.
Declared priorities always drive specialization and remain capped/recoverable.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from engine import VOLUME_TIERS, calculate_weekly_volume
from muscles import (
    MAX_PRIORITIES, get_profile_priorities_internal,
    get_ranked_priorities, normalize_sex,
)

BASE = {"days": 4, "experience": "Intermediário", "assessment": {}}


def perfil(**kw):
    return {**BASE, **kw}


def series(p):
    return {m: d["target_sets"] for m, d in calculate_weekly_volume(p, "ppl", 4).items()}


def tier(p, muscle):
    return calculate_weekly_volume(p, "ppl", 4)[muscle]["tier"]


@pytest.mark.parametrize("valor", ["Feminino", "feminino", "female", "F", "mulher"])
def test_perfil_feminino_e_reconhecido(valor):
    assert normalize_sex(valor) == "female"


@pytest.mark.parametrize("valor", ["Masculino", "male", "M", "homem"])
def test_perfil_masculino_e_reconhecido(valor):
    assert normalize_sex(valor) == "male"


def test_sexo_sozinho_nao_inventa_prioridade():
    assert get_ranked_priorities(perfil(sex="Feminino")) == (None, [])
    assert get_ranked_priorities(perfil(sex="Masculino")) == (None, [])
    assert series(perfil(sex="Feminino")) == series(perfil(sex="Masculino"))


def test_qualquer_perfil_pode_priorizar_gluteos():
    for sex in ("Masculino", "Feminino", None):
        p = perfil(sex=sex, priorities=["Glúteos"])
        assert get_ranked_priorities(p)[0] == "glutes"
        assert tier(p, "glutes") == "priority"


def test_qualquer_perfil_pode_priorizar_peito_e_bracos():
    for sex in ("Masculino", "Feminino", None):
        p = perfil(sex=sex, priorities=["Peitoral esternal", "Bíceps"])
        principal, secundarias = get_ranked_priorities(p)
        assert principal == "mid_chest"
        assert "biceps" in secundarias


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
    s = series(perfil(priorities=["Glúteos"]))
    assert all(v >= VOLUME_TIERS["maintenance"]["target_sets"] for v in s.values())


def test_perfil_antigo_sem_sexo_e_sem_prioridade_nao_muda():
    p = perfil()
    assert get_ranked_priorities(p) == (None, [])
    assert get_profile_priorities_internal(p) == []
    assert set(series(p).values()) <= {
        VOLUME_TIERS["normal"]["target_sets"],
        VOLUME_TIERS["maintenance"]["target_sets"],
    }


def test_sexo_invalido_nao_quebra_a_geracao():
    p = perfil(sex="prefiro nao dizer")
    assert normalize_sex(p["sex"]) is None
    assert get_ranked_priorities(p) == (None, [])


def test_prioridade_legada_por_nome_de_frontend_continua_valendo():
    assert get_profile_priorities_internal(perfil(priorities=["Dorsais / largura"])) == ["lats"]


def test_sem_avaliacao_individual_ninguem_e_rebaixado_para_manutencao():
    tiers = {m: d["tier"] for m, d in calculate_weekly_volume(perfil(), "ppl", 4).items()}
    assert "maintenance" not in tiers.values()
    assert set(tiers.values()) == {"normal"}


def test_avaliacao_ausente_nao_vira_musculo_fraco():
    sem = series(perfil())
    assert all(v == VOLUME_TIERS["normal"]["target_sets"] for v in sem.values())


def test_prioridades_sozinhas_bastam_para_personalizar():
    p = perfil(priorities=["Glúteos", "Quadríceps"])
    s = series(p)
    assert s["glutes"] > s["quads"] > s["hamstrings"]
    assert tier(p, "glutes") == "priority"
    assert tier(p, "quads") == "priority_secondary"


def test_avaliacao_legada_continua_rebaixando_quem_o_atleta_marcou_como_forte():
    p = perfil(assessment={"Bíceps": {"development": "muito forte", "priority": "normal"}})
    assert tier(p, "biceps") == "maintenance"


def test_prioridade_declarada_vence_a_avaliacao_legada():
    p = perfil(
        priorities=["Glúteos"],
        assessment={"Glúteos": {"development": "muito forte", "priority": "baixa"}},
    )
    assert tier(p, "glutes") == "priority"


def test_tres_prioridades_nao_recebem_todas_o_tratamento_maximo():
    p = perfil(priorities=["Glúteos", "Quadríceps", "Bíceps"])
    s = series(p)
    assert s["glutes"] > s["quads"] == s["biceps"]
    niveis = [tier(p, m) for m in ("glutes", "quads", "biceps")]
    assert niveis == ["priority", "priority_secondary", "priority_secondary"]


def test_volume_prioritario_respeita_o_teto_do_motor():
    p = perfil(priorities=["Glúteos", "Quadríceps", "Bíceps"])
    for _, d in calculate_weekly_volume(p, "ppl", 4).items():
        assert d["target_sets"] <= d["max_sets"] <= VOLUME_TIERS["priority"]["max_sets"]

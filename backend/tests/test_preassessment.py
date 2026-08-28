"""Pre-avaliacao: catalogo, validacao e previa deterministica.

Sem rede, sem banco e sem IA — o modulo e funcao pura, e o teste existe justamente para
provar isso: mesma entrada, mesma saida, sempre.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import preassessment as pa  # noqa: E402
from billing_plans import (  # noqa: E402
    CAPACIDADES_ELITE, CAPACIDADES_ESSENCIAL, CAPACIDADES_PRO, plano,
)

BASE = {
    "sex": "female",
    "experience": "Intermediário",
    "goal": "Hipertrofia",
    "days": 4,
    "priorities": ["Glúteos", "Posteriores"],
}
COM_ALIMENTACAO = {**BASE, "body_goal": "fat_loss", "goal_intensity": "moderado"}


def _previa(respostas, caps, code):
    return pa.montar_previa(pa.normalizar(respostas, caps), caps, plano(code))


# ── Catalogo por plano ───────────────────────────────────────────────────────────────

def test_o_essencial_nao_recebe_perguntas_de_alimentacao():
    """Perguntar e depois nao entregar seria pior do que nao perguntar."""
    c = pa.catalogo(CAPACIDADES_ESSENCIAL)
    assert c["includes_nutrition"] is False
    assert c["body_goals"] == []


def test_pro_e_elite_recebem_as_perguntas_de_alimentacao():
    for caps in (CAPACIDADES_PRO, CAPACIDADES_ELITE):
        c = pa.catalogo(caps)
        assert c["includes_nutrition"] is True
        assert {g["id"] for g in c["body_goals"]} == {"muscle_gain", "fat_loss", "maintenance"}


def test_o_ritmo_agressivo_aparece_bloqueado_no_pro_e_livre_no_elite():
    def agressivos(caps):
        c = pa.catalogo(caps)
        return {i["locked"] for g in c["body_goals"] for i in g["intensities"]
                if i["id"] == "agressivo"}

    assert agressivos(CAPACIDADES_PRO) == {True}
    assert agressivos(CAPACIDADES_ELITE) == {False}


def test_o_catalogo_traz_o_que_a_tela_precisa_para_montar_as_perguntas():
    c = pa.catalogo(CAPACIDADES_PRO)
    assert {s["id"] for s in c["sexes"]} == {"female", "male"}
    assert len(c["experiences"]) == 3
    assert c["days"] == [2, 3, 4, 5, 6]
    assert len(c["regions"]) == 18
    assert c["max_priorities"] == 3


# ── Validacao no servidor ────────────────────────────────────────────────────────────

def test_respostas_completas_sao_aceitas():
    doc = pa.normalizar(COM_ALIMENTACAO, CAPACIDADES_PRO)
    assert doc["sex"] == "female"
    assert doc["days"] == 4
    assert doc["priorities"] == ["Glúteos", "Posteriores"]
    assert doc["body_goal"] == "fat_loss"
    assert doc["goal_intensity"] == "moderado"


@pytest.mark.parametrize("campo,valor", [
    ("sex", "outro"),
    ("experience", "Semideus"),
    ("goal", "Crossfit"),
    ("days", 9),
    ("days", "muitos"),
    ("days", None),
])
def test_resposta_fora_do_catalogo_e_recusada(campo, valor):
    with pytest.raises(pa.RespostaInvalida) as e:
        pa.normalizar({**BASE, campo: valor}, CAPACIDADES_ESSENCIAL)
    assert e.value.campo == campo


def test_o_ritmo_agressivo_e_recusado_para_quem_nao_tem_o_plano():
    """A tela mostra bloqueado; o servidor recusa. As duas coisas precisam existir."""
    with pytest.raises(pa.RespostaInvalida) as e:
        pa.normalizar({**COM_ALIMENTACAO, "goal_intensity": "agressivo"}, CAPACIDADES_PRO)
    assert e.value.campo == "goal_intensity"
    assert "Elite" in e.value.mensagem


def test_o_elite_aceita_o_ritmo_agressivo():
    doc = pa.normalizar({**COM_ALIMENTACAO, "goal_intensity": "agressivo"}, CAPACIDADES_ELITE)
    assert doc["goal_intensity"] == "agressivo"


def test_o_essencial_ignora_resposta_de_alimentacao_enviada_a_forca():
    """Mandar body_goal sem ter a capacidade nao cria plano alimentar nenhum."""
    doc = pa.normalizar({**COM_ALIMENTACAO, "goal_intensity": "agressivo"},
                        CAPACIDADES_ESSENCIAL)
    assert "body_goal" not in doc
    assert "goal_intensity" not in doc


def test_sem_prioridade_e_uma_resposta_valida():
    doc = pa.normalizar({**BASE, "priorities": []}, CAPACIDADES_ESSENCIAL)
    assert doc["priorities"] == []


def test_prioridade_inexistente_e_descartada_em_silencio():
    doc = pa.normalizar({**BASE, "priorities": ["Glúteos", "Cauda"]}, CAPACIDADES_ESSENCIAL)
    assert doc["priorities"] == ["Glúteos"]


def test_prioridade_repetida_nao_ocupa_duas_vagas():
    doc = pa.normalizar({**BASE, "priorities": ["Glúteos", "Glúteos", "Bíceps"]},
                        CAPACIDADES_ESSENCIAL)
    assert doc["priorities"] == ["Glúteos", "Bíceps"]


def test_mais_de_tres_prioridades_e_recusado():
    with pytest.raises(pa.RespostaInvalida) as e:
        pa.normalizar({**BASE, "priorities": ["Glúteos", "Bíceps", "Tríceps", "Abdômen"]},
                      CAPACIDADES_ESSENCIAL)
    assert e.value.campo == "priorities"


def test_a_ordem_das_prioridades_define_principal_e_secundaria():
    doc = pa.normalizar({**BASE, "priorities": ["Bíceps", "Glúteos"]}, CAPACIDADES_ESSENCIAL)
    previa = pa.montar_previa(doc, CAPACIDADES_ESSENCIAL, plano("essential"))
    papeis = {r["region"]: r["role"] for r in previa["focus"]["regions"]}
    assert papeis["Bíceps"] == "Principal"
    assert papeis["Glúteos"] == "Secundária"


# ── Previa ───────────────────────────────────────────────────────────────────────────

def test_a_previa_e_deterministica():
    """Mesma entrada, mesma saida. Sem IA, sem rede, sem aleatoriedade."""
    a = _previa(COM_ALIMENTACAO, CAPACIDADES_PRO, "pro")
    b = _previa(COM_ALIMENTACAO, CAPACIDADES_PRO, "pro")
    assert a == b


def test_a_previa_usa_a_mesma_regra_de_split_do_motor():
    """Se a previa dissesse Upper/Lower e o motor entregasse PPL, a venda teria sido
    feita com uma informacao que o produto nao cumpre."""
    from engine import determine_split
    for dias in pa.DIAS_DISPONIVEIS:
        for experiencia in ("Iniciante", "Intermediário", "Avançado"):
            doc = pa.normalizar({**BASE, "days": dias, "experience": experiencia},
                                CAPACIDADES_ESSENCIAL)
            previa = pa.montar_previa(doc, CAPACIDADES_ESSENCIAL, plano("essential"))
            assert previa["training"]["split"] == determine_split(
                dias, experiencia, doc["goal"])
            assert len(previa["training"]["sessions"]) == dias


def test_a_previa_nao_entrega_exercicio_nenhum():
    """O ponto do bloqueio: estrutura sim, conteudo nao."""
    previa = _previa(COM_ALIMENTACAO, CAPACIDADES_ELITE, "elite")
    assert previa["locked"] is True
    for sessao in previa["training"]["sessions"]:
        assert sessao["locked"] is True
        assert "exercises" not in sessao
        assert set(sessao) == {"label", "regions", "locked"}


def test_a_previa_nao_entrega_dieta():
    previa = _previa(COM_ALIMENTACAO, CAPACIDADES_PRO, "pro")
    n = previa["nutrition"]
    assert n["included"] is True
    assert n["locked"] is True
    assert "meals" not in n
    assert "kcal" not in n


def test_as_regioes_da_sessao_saem_em_portugues():
    previa = _previa(BASE, CAPACIDADES_ESSENCIAL, "essential")
    todas = {r for s in previa["training"]["sessions"] for r in s["regions"]}
    assert todas
    assert todas <= {"Peitoral", "Costas", "Ombros", "Braços", "Pernas", "Core"}


def test_o_essencial_nao_promete_alimentacao():
    previa = _previa(BASE, CAPACIDADES_ESSENCIAL, "essential")
    n = previa["nutrition"]
    assert n["included"] is False
    assert "protocol" not in n
    assert "Pro" in n["note"] and "Elite" in n["note"]


def test_a_previa_do_pro_mostra_o_protocolo_escolhido():
    previa = _previa(COM_ALIMENTACAO, CAPACIDADES_PRO, "pro")
    p = previa["nutrition"]["protocol"]
    assert p["intensity"] == "moderado"
    assert p["delta_pct"] < 0, "emagrecimento e deficit"
    assert p["protein_g_per_kg"] > 0


def test_ganho_de_massa_aparece_como_superavit():
    previa = _previa({**BASE, "body_goal": "muscle_gain", "goal_intensity": "moderado"},
                     CAPACIDADES_PRO, "pro")
    assert previa["nutrition"]["protocol"]["delta_pct"] > 0


def test_manutencao_nao_tem_ritmo():
    previa = _previa({**BASE, "body_goal": "maintenance"}, CAPACIDADES_PRO, "pro")
    assert previa["nutrition"]["protocol"] is None
    assert previa["nutrition"]["included"] is True


def test_sem_prioridade_a_previa_sugere_a_enfase_do_perfil():
    feminino = _previa({**BASE, "priorities": [], "sex": "female"},
                       CAPACIDADES_ESSENCIAL, "essential")["focus"]
    masculino = _previa({**BASE, "priorities": [], "sex": "male"},
                        CAPACIDADES_ESSENCIAL, "essential")["focus"]
    assert feminino["declared"] is False
    assert masculino["declared"] is False
    assert feminino["regions"] != masculino["regions"]
    assert all(r["role"] == "Sugerida" for r in feminino["regions"])


def test_a_previa_diz_de_qual_plano_esta_falando():
    previa = _previa(BASE, CAPACIDADES_PRO, "pro")
    assert previa["plan_code"] == "pro"
    assert previa["plan_name"] == "FORGE PRO"
    assert previa["cta"] == "Ativar meu plano e liberar o FORGE"
    assert previa["headline"]


def test_os_tres_planos_produzem_previas_diferentes():
    e = _previa(BASE, CAPACIDADES_ESSENCIAL, "essential")
    p = _previa(COM_ALIMENTACAO, CAPACIDADES_PRO, "pro")
    assert e["nutrition"]["included"] is False
    assert p["nutrition"]["included"] is True
    # o treino e o mesmo: o plano muda o que acompanha, nao a estrutura do treino
    assert e["training"] == p["training"]

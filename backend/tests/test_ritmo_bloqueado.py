"""O ritmo que o plano nao inclui aparece BLOQUEADO, e nao escolhivel.

Por que este arquivo existe
---------------------------
A tela de troca de objetivo oferecia o card "Agressivo/Atleta" como qualquer outro. A
pessoa escolhia, clicava em salvar, esperava, e so entao levava um 402: "seu plano atual
nao inclui este recurso". Oferecer e depois recusar e pior do que nao oferecer.

O catalogo do questionario (`preassessment`) ja resolvia isso com `locked` desde sempre.
A rota `/nutrition/goal-catalog`, que alimenta as OUTRAS duas telas onde o ritmo e
escolhido, nao. Estes testes prendem as duas pontas: a oferta so mostra como escolhivel
o que a gravacao aceita.

Nao precisam de banco: medem a funcao que monta as opcoes.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_database")

import billing_plans as bp  # noqa: E402
import nutrition_routes as nr  # noqa: E402

CONJUNTOS = ["cutting_intensity", "bulking_intensity"]


def _por_id(conjunto, permite):
    return {o["id"]: o for o in nr._opcoes_de_intensidade(conjunto, permite)}


def test_sem_a_capacidade_o_ritmo_avancado_vem_bloqueado():
    for conjunto in CONJUNTOS:
        opcoes = _por_id(conjunto, False)
        avancados = [o for o in opcoes.values() if o["advanced"]]
        assert avancados, f"{conjunto} nao tem ritmo avancado para bloquear"
        assert all(o["locked"] for o in avancados)


def test_com_a_capacidade_nada_fica_bloqueado():
    for conjunto in CONJUNTOS:
        assert not any(o["locked"] for o in _por_id(conjunto, True).values())


def test_ritmo_comum_nunca_e_bloqueado():
    """Bloquear o Moderado deixaria a conta sem NENHUM ritmo escolhivel."""
    for conjunto in CONJUNTOS:
        comuns = [o for o in _por_id(conjunto, False).values() if not o["advanced"]]
        assert comuns
        assert not any(o["locked"] for o in comuns)


def test_bloqueado_continua_na_lista_em_vez_de_sumir():
    """Esconder faria parecer que o FORGE nao tem o recurso, quando quem nao tem e o
    plano. A opcao fica visivel, marcada — e e assim que ela vira caminho de upgrade."""
    for conjunto in CONJUNTOS:
        assert set(_por_id(conjunto, False)) == set(_por_id(conjunto, True))


def test_toda_opcao_diz_se_esta_bloqueada():
    """A tela nao pode ter que adivinhar: `locked` existe em todas, nunca ausente."""
    for conjunto in CONJUNTOS:
        for permite in (True, False):
            for o in _por_id(conjunto, permite).values():
                assert isinstance(o["locked"], bool)


def test_o_padrao_e_liberar():
    """Quem chama sem informar capacidade nao pode bloquear ninguem por engano."""
    for conjunto in CONJUNTOS:
        assert not any(o["locked"] for o in nr._opcoes_de_intensidade(conjunto))


def test_o_ritmo_padrao_do_objetivo_nunca_e_um_ritmo_bloqueavel():
    """Se o padrao fosse o avancado, a conta sem a capacidade abriria a tela ja num
    estado que ela nao pode salvar."""
    for conjunto in CONJUNTOS:
        padrao = nr.FORGE_COACH_METHODOLOGY[f"{conjunto}_default"]
        assert _por_id(conjunto, False)[padrao]["locked"] is False


def test_quem_entrega_o_agressivo_hoje_e_o_pro():
    """Prende a decisao atual: a capacidade desceu do Elite para o Pro. O Essencial
    continua sem ela, entao ela segue paga — so que um degrau abaixo."""
    assert bp.plano_minimo_com(bp.PROTOCOLOS_AGRESSIVOS)["code"] == "pro"
    assert bp.PROTOCOLOS_AGRESSIVOS not in bp.capacidades_do_plano("essential")

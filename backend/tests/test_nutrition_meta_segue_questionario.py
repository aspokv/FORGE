# -*- coding: utf-8 -*-
"""
Corrigir o questionario nao mudava a meta do plano ja gravado.

O caso real: uma atleta teve a altura gravada em metros, recebeu uma meta de 427 kcal,
voltou ao questionario e corrigiu para 1,65 m — e continuou vendo 427. O numero nao vinha
do dado novo: vinha de um plano antigo, que ninguem tocou. Salvar a avaliacao gravava o
perfil e ia embora.

Agora a META do plano acompanha o questionario. As REFEICOES ficam: a pessoa escolheu
aquilo, e apagar o plano dela porque mudou de peso seria pior que o defeito. A tela passa
a mostrar a verdade — o que ela precisa contra o que o plano entrega.
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nutrition_engine import compute_macro_targets  # noqa: E402
import nutrition_routes  # noqa: E402


class _Colecao:
    """Mongo de mentira, pequeno o bastante para o teste ser sobre a REGRA."""

    def __init__(self, doc=None):
        self.doc = doc
        self.ultimo_set = None

    async def find_one(self, *_args, **_kwargs):
        return self.doc

    async def update_one(self, _filtro, update, **_kwargs):
        self.ultimo_set = update.get("$set")
        if self.doc is not None:
            for chave, valor in (update.get("$set") or {}).items():
                if chave == "plan.targets":
                    self.doc.setdefault("plan", {})["targets"] = valor


class _Db:
    def __init__(self, plano=None):
        self.nutrition_plans = _Colecao(plano)


QUESTIONARIO_CERTO = {
    "weight_kg": 65, "height_cm": 165, "age": 28, "sex": "female",
    "training_days": 5, "goal": "fat_loss", "intensity": "moderado",
    "activity_level": "moderate",
}

def _plano_com_meta_velha():
    """
    O plano que a atleta tinha: meta gravada quando a altura estava em metros.

    Uma FUNCAO, e nao uma constante: `dict(CONSTANTE)` e copia rasa, entao o `plan`
    aninhado seria o mesmo objeto em todos os testes — um mutaria o valor que o outro
    espera, e a suite passaria ou falharia conforme a ordem de execucao.
    """
    return {
        "plan": {
            "meals": [{"name": "Cafe da manha", "foods": []}],
            "targets": {"goal_calories": 427.0, "protein_g": 143.0,
                        "carbs_g": 0.0, "fat_g": 52.0},
        }
    }


def _rodar(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_a_meta_do_plano_acompanha_o_questionario_corrigido():
    db = _Db(_plano_com_meta_velha())
    atualizou = _rodar(nutrition_routes._atualizar_meta_do_plano(db, "atleta-1", QUESTIONARIO_CERTO))

    assert atualizou is True
    nova = db.nutrition_plans.doc["plan"]["targets"]
    esperada = compute_macro_targets(65, 165, 28, "female", 5, "fat_loss", "moderate", "moderado")

    assert nova["goal_calories"] == esperada["goal_calories"]
    assert nova["goal_calories"] > 1000, "a meta de 427 kcal sobreviveu a correcao"
    assert nova["carbs_g"] > 0, "o carboidrato continuou zerado"


def test_as_refeicoes_nao_sao_tocadas():
    """Mudar de peso nao pode apagar o plano que a pessoa montou."""
    db = _Db(_plano_com_meta_velha())
    _rodar(nutrition_routes._atualizar_meta_do_plano(db, "atleta-1", QUESTIONARIO_CERTO))
    assert db.nutrition_plans.doc["plan"]["meals"] == [{"name": "Cafe da manha", "foods": []}]
    # A escrita e cirurgica: so o campo da meta.
    assert list(db.nutrition_plans.ultimo_set.keys()) == ["plan.targets"]


def test_sem_plano_gravado_nao_ha_o_que_atualizar():
    db = _Db(None)
    assert _rodar(nutrition_routes._atualizar_meta_do_plano(db, "atleta-1", QUESTIONARIO_CERTO)) is False


@pytest.mark.parametrize("faltando", ["weight_kg", "height_cm", "age", "training_days"])
def test_questionario_incompleto_nao_recalcula_nem_quebra(faltando):
    """
    Salvar a avaliacao nao pode falhar por causa deste recalculo. O onboarding de treino
    semeia um questionario parcial, e ele precisa passar.
    """
    parcial = {k: v for k, v in QUESTIONARIO_CERTO.items() if k != faltando}
    db = _Db(_plano_com_meta_velha())
    assert _rodar(nutrition_routes._atualizar_meta_do_plano(db, "atleta-1", parcial)) is False
    # A meta antiga continua la, intocada — nao viramos zero nem None.
    assert db.nutrition_plans.doc["plan"]["targets"]["goal_calories"] == 427.0


def test_dado_impossivel_nao_derruba_o_salvamento():
    torto = {**QUESTIONARIO_CERTO, "weight_kg": "muito"}
    db = _Db(_plano_com_meta_velha())
    assert _rodar(nutrition_routes._atualizar_meta_do_plano(db, "atleta-1", torto)) is False


def test_altura_em_metros_no_questionario_ainda_produz_meta_sa():
    """
    Cinto e suspensorio: mesmo que um perfil antigo tenha a altura em metros, o recalculo
    passa por `compute_macro_targets`, que normaliza.
    """
    em_metros = {**QUESTIONARIO_CERTO, "height_cm": 1.65}
    db = _Db(_plano_com_meta_velha())
    assert _rodar(nutrition_routes._atualizar_meta_do_plano(db, "atleta-1", em_metros)) is True
    assert db.nutrition_plans.doc["plan"]["targets"]["goal_calories"] > 1000

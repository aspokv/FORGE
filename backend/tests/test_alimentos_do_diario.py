# -*- coding: utf-8 -*-
"""FORGE — o catalogo de alimentos do diario.

O atleta reclamou que nao achava albumina para registrar. A busca ja somava catalogo local e
Open Food Facts, mas o catalogo local tinha 107 itens e, quando o provedor mundial nao
responde para um termo em portugues, sobra tela vazia. Alimento que nao entra no diario nao
existe para o motor de nutricao, entao catalogo curto e buraco de dados.

O que estes testes defendem:

  - nenhum id novo pisa num id antigo — `food_snapshot` resolve cada registro salvo pelo id,
    e sombrear um id mudaria retroativamente o que a pessoa registrou mes passado;
  - nenhum alimento aparece duas vezes com nomes iguais, que e como a busca fica com cara de
    quebrada (o mesmo arroz com dois valores diferentes);
  - os macros fecham com a caloria declarada, o que pega erro de digitacao numa tabela de
    quase duzentas linhas;
  - o que o atleta pediu realmente aparece na busca.
"""
import sys
import unicodedata
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from alimentos_do_diario import ALIMENTOS_EXTRA, APELIDOS_EXTRA  # noqa: E402
from food_diary import DIARY_FOODS, MACROS  # noqa: E402
from nutrition_engine import FOOD_INDEX  # noqa: E402


def _normalizar(texto):
    sem_acento = unicodedata.normalize("NFD", str(texto).lower()).encode("ascii", "ignore").decode()
    return " ".join("".join(c for c in sem_acento if c.isalnum() or c.isspace()).split())


def _busca(termo):
    """A mesma leitura da tela: casa no nome ou em qualquer apelido, sem acento."""
    alvo = _normalizar(termo)
    return [f for f in DIARY_FOODS.values()
            if alvo in _normalizar(f["name"])
            or any(alvo in _normalizar(a) for a in f.get("aliases") or [])]


def test_o_catalogo_cresceu_de_verdade():
    assert len(ALIMENTOS_EXTRA) >= 150, "a ampliacao encolheu"
    assert len(DIARY_FOODS) >= 280


# `food_snapshot` resolve pelo id: sombrear um id antigo reescreveria historico.
def test_nenhum_id_novo_pisa_num_id_antigo():
    assert not set(ALIMENTOS_EXTRA) & set(FOOD_INDEX)


def test_todo_alimento_do_gerador_de_plano_continua_no_diario():
    faltando = [fid for fid in FOOD_INDEX if fid not in DIARY_FOODS]
    assert not faltando, f"sumiram do diario: {faltando[:5]}"


def test_nenhum_alimento_aparece_duas_vezes():
    vistos = {}
    for food in DIARY_FOODS.values():
        chave = _normalizar(food["name"])
        assert chave not in vistos, f"'{food['name']}' duplica {vistos.get(chave)}"
        vistos[chave] = food["id"]


def test_toda_linha_tem_a_forma_que_o_diario_espera():
    for food in ALIMENTOS_EXTRA.values():
        assert food["id"] and food["name"], food
        assert food["grams"] > 0, food["id"]
        for macro in MACROS:
            valor = food[macro]
            assert isinstance(valor, (int, float)) and valor >= 0, (food["id"], macro, valor)
        assert food["source"], food["id"]
        assert isinstance(food["aliases"], list)


"""
Alcool carrega 7 kcal/g e nao entra em proteina, carboidrato nem gordura, entao bebida
alcoolica nunca fecha a conta. Fibra e o outro caso: conta como carboidrato na tabela mas
nao e toda metabolizada, e por isso limao e champignon declaram menos caloria do que a soma.
Isentar e honesto; afrouxar a tolerancia para todos esconderia erro de digitacao de verdade.
"""
_COM_ALCOOL = {"diary-drink-wine-red", "diary-drink-cachaca"}
# Canela e o extremo da fibra: 80 g de carboidrato por 100 g, dos quais uns 53 g nao sao
# metabolizados. A conta 4/4/9 nunca fecharia, e fecha-la seria mentir sobre a caloria.
_RICOS_EM_FIBRA = {"diary-fruit-lemon", "diary-veg-mushroom", "diary-supp-pretreino",
                   "diary-cond-cinnamon"}


@pytest.mark.parametrize("food", sorted(ALIMENTOS_EXTRA.values(), key=lambda f: f["id"]), ids=lambda f: f["id"])
def test_os_macros_fecham_com_a_caloria_declarada(food):
    if food["id"] in _COM_ALCOOL or food["id"] in _RICOS_EM_FIBRA:
        pytest.skip("álcool ou fibra não fecham pela conta 4/4/9")
    calculado = 4 * food["protein_g"] + 4 * food["carbs_g"] + 9 * food["fat_g"]
    declarado = food["kcal"]
    if calculado == 0 and declarado == 0:
        return
    assert calculado > 0, f"{food['id']} declara {declarado} kcal sem macro nenhum"
    desvio = abs(declarado - calculado) / calculado
    assert desvio <= 0.22 or abs(declarado - calculado) <= 12, (
        f"{food['id']}: {declarado} kcal declarado contra {calculado:.0f} calculado")


def test_nenhum_macro_absurdo_por_100g():
    for food in ALIMENTOS_EXTRA.values():
        if food["grams"] != 100:
            continue
        for macro in ("protein_g", "carbs_g", "fat_g"):
            assert food[macro] <= 100, (food["id"], macro)
        assert food["kcal"] <= 900, food["id"]


# A reclamacao que originou tudo isto.
def test_albumina_aparece_na_busca():
    achados = _busca("albumina")
    assert len(achados) >= 3, "albumina continua invisivel no diario"
    assert any(f["protein_g"] >= 70 for f in achados), "nenhuma albumina com proteina de albumina"


@pytest.mark.parametrize("termo", [
    "banana", "morango", "abacaxi", "mamao", "melancia", "goiaba", "maracuja", "pitaya",
    "brocolis", "couve", "abobrinha", "cenoura", "beterraba", "quiabo",
    "arroz", "feijao", "macarrao", "batata doce", "tapioca", "cuscuz", "aveia", "quinoa",
    "ovo", "clara", "tilapia", "atum", "sardinha", "patinho", "picanha", "figado",
    "iogurte", "requeijao", "ricota", "parmesao", "manteiga",
    "castanha", "amendoim", "chia", "linhaca", "pasta de amendoim",
    "creatina", "caseina", "colageno", "maltodextrina", "hipercalorico", "barra de proteina",
    "agua de coco", "cafe", "leite de coco",
    "feijoada", "strogonoff", "coxinha", "tapioca com queijo", "marmita",
    "maionese", "mel", "cacau",
])
def test_o_que_a_pessoa_digita_encontra_alimento(termo):
    assert _busca(termo), f"'{termo}' nao devolve nada no diario"


def test_apelidos_extras_caem_em_alimentos_que_existem():
    for fid in APELIDOS_EXTRA:
        assert fid in DIARY_FOODS, f"{fid} nao existe no catalogo"


def test_apelido_extra_realmente_faz_a_busca_achar():
    # "feijao" sem acento e o caso comum: ninguem digita acento no celular.
    assert any(f["id"] == "beans-carioca" for f in _busca("feijao"))
    assert any(f["id"] == "yogurt-greek" for f in _busca("grego"))


def test_suplemento_e_medido_pela_dose_do_rotulo():
    """Registrar "100 g de creatina" nao existe na vida real; a porcao tem de ser a do rotulo."""
    creatina = DIARY_FOODS["diary-supp-creatine"]
    assert creatina["grams"] == 3
    barra = DIARY_FOODS["diary-supp-protein-bar"]
    assert barra["grams"] == 45


def test_a_fonte_nunca_promete_precisao_que_nao_tem():
    for food in ALIMENTOS_EXTRA.values():
        fonte = food["source"].lower()
        assert "confirme" in fonte or "porção" in fonte or "porcao" in fonte or "valor" in fonte, food["id"]

# -*- coding: utf-8 -*-
"""O prato que o motor monta tem de ser o prato que o treinador prescreve.

Por que este arquivo existe
---------------------------
Um aluno gerou a dieta dele e recebeu isto, cinco refeicoes, todos os dias:

    Cafe da manha    Clara de ovo, Ovo inteiro, BATATA DOCE, Laranja, Pasta de amendoim
    Lanche da manha  Whey, Aveia, Mamao, AZEITE DE OLIVA
    Almoco           FILE DE TILAPIA, Batata inglesa, Tomate, CASTANHA DO PARA
    Lanche da tarde  Atum, Farinha de arroz, Manga
    Jantar           Peito de frango, Arroz branco, Abobora, Amendoim torrado

Quatro defeitos, e nenhum deles era de macro — as contas fechavam. Eram defeitos de
COMPOSICAO, que e o que a pessoa realmente ve:

1. Batata doce no cafe da manha. O slot de carboidrato do cafe era o unico do arquivo sem
   familia, entao ele varria a categoria inteira — inclusive o que o proprio catalogo
   marca como `lunch`/`dinner`.
2. Azeite de oliva dentro de um shake de whey com aveia e mamao. `_infer_meal_type`
   classificava "Lanche da manha" como CAFE DA MANHA (casava "manha" antes de "lanche"),
   e o acrescimo de gordura escolhia por densidade — o azeite e sempre o primeiro da fila.
3. Tilapia no almoco todo dia. Nao existia nocao de preco: tilapia e salmao competiam de
   igual para igual com frango e ovo, e ganhavam.
4. Castanha do Para no almoco. Mesma causa do 2.

O motor tem escrito nele, em caixa alta, "MACROS AJUSTAM A REFEICAO, MACROS NAO INVENTAM A
REFEICAO". Era exatamente o contrario que acontecia.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import nutrition_engine as ne  # noqa: E402

PERFIL = {"weight_kg": 80, "height_cm": 175, "age": 30, "sex": "male",
          "activity_level": "moderate", "training_days": 4, "meal_count": 5,
          "cooking_time": "medium", "preferred_foods": [], "disliked_foods": []}
ALVOS = {"goal_calories": 2400, "protein_g": 170, "carbs_g": 270, "fat_g": 70}

DIAS = [0, 1, 2, 3, 4, 5, 6]


def _planos():
    for semente in DIAS:
        plano = ne.generate_daily_plan(ALVOS, PERFIL, meal_count=5,
                                       goal="maintenance", variety_seed=semente)
        yield semente, (plano["meals"] if isinstance(plano, dict) else plano)


def _ids(refeicao):
    return [it["food_id"] for it in refeicao.get("foods", [])]


def _por_tipo(refeicoes, tipo):
    return [m for m in refeicoes if ne._infer_meal_type(m.get("name") or "") == tipo]


# -- 1. O nome da refeicao decide o template ------------------------------------------

@pytest.mark.parametrize("nome,esperado", [
    ("Café da manhã", "breakfast"),
    ("Café da manhã / Pré-treino", "breakfast"),   # o layout de seis refeicoes
    # Tipo proprio: o metodo separa o lanche da manha (prato salgado pequeno) do lanche da
    # tarde (o shake). Antes os dois caiam no mesmo template e o das nove saia com atum,
    # farinha de arroz e laranja.
    ("Lanche da manhã", "morning_snack"),
    ("Lanche da tarde", "snack"),
    ("Lanche pré-treino", "pre_workout"),          # treino vence lanche
    ("Pré-treino", "pre_workout"),
    ("Pós-treino", "post_workout"),
    ("Ceia", "snack"),
    ("Almoço", "lunch"),
    ("Jantar", "dinner"),
])
def test_o_nome_cai_no_template_certo(nome, esperado):
    assert ne._infer_meal_type(nome) == esperado


def test_lanche_da_manha_nao_e_cafe_da_manha():
    """O defeito exato. Um lanche classificado como cafe recebe a pontuacao de cafe, e e
    por isso que o azeite (que pontua para almoco e jantar) chegava perto de um shake."""
    assert ne._infer_meal_type("Lanche da manhã") != "breakfast"


# -- 2. Cada alimento na refeicao a que ele pertence -----------------------------------

def test_nenhum_alimento_aparece_fora_da_refeicao_dele():
    """A regra geral, valendo para o plano inteiro: se o alimento declara em quais
    refeicoes entra, ele so aparece numa delas."""
    fora = []
    for semente, refeicoes in _planos():
        for m in refeicoes:
            mt = ne._infer_meal_type(m.get("name") or "")
            for fid in _ids(m):
                if not ne._pertence_a_refeicao(fid, mt):
                    fora.append((semente, m.get("name"), ne.FOOD_INDEX[fid]["name"]))
    assert not fora, "alimento fora da refeicao dele: %s" % (fora[:6],)


def test_azeite_nunca_entra_num_lanche():
    """O caso que o aluno viu: azeite de oliva com whey, aveia e mamao."""
    for _, refeicoes in _planos():
        for m in _por_tipo(refeicoes, "snack"):
            assert "olive-oil" not in _ids(m), "azeite em %s" % m.get("name")


def test_castanha_do_para_nunca_entra_no_almoco_nem_no_jantar():
    for _, refeicoes in _planos():
        for tipo in ("lunch", "dinner"):
            for m in _por_tipo(refeicoes, tipo):
                assert "brazil-nuts" not in _ids(m)


# -- 3. Cafe da manha e cafe da manha --------------------------------------------------

CARBOS_DE_PRATO_FEITO = {"sweet-potato", "cassava", "pasta", "pasta-whole", "rice-brown"}


def test_o_cafe_da_manha_nao_tem_carboidrato_de_prato_feito():
    """Batata doce, mandioca e macarrao no cafe da manha. O slot era o unico sem familia."""
    for _, refeicoes in _planos():
        for m in _por_tipo(refeicoes, "breakfast"):
            achados = CARBOS_DE_PRATO_FEITO & set(_ids(m))
            assert not achados, "%s no cafe da manha" % (achados,)


def test_o_carboidrato_do_cafe_vem_da_familia_do_cafe():
    familia = set(ne.FOOD_FAMILIES["BREAKFAST_CARB"])
    for _, refeicoes in _planos():
        for m in _por_tipo(refeicoes, "breakfast"):
            carbs = [f for f in _ids(m)
                     if ne.FOOD_INDEX[f].get("category") == "CARBOHYDRATE"]
            for c in carbs:
                assert c in familia, "%s nao e carboidrato de cafe da manha" % c


def test_o_cafe_da_manha_tem_proteina_do_metodo():
    """Ovo, clara, whey ou omelete. E o que o treinador prescreve de manha."""
    familia = set(ne.FOOD_FAMILIES["BREAKFAST_PROTEIN"])
    for _, refeicoes in _planos():
        for m in _por_tipo(refeicoes, "breakfast"):
            assert familia & set(_ids(m)), "cafe sem proteina do metodo: %s" % (_ids(m),)


# -- 4. Preco: o plano so vale se a pessoa consegue comprar ----------------------------

CAROS = {"tilapia", "salmon", "brazil-nuts"}


def test_o_caro_nao_aparece_sozinho_no_lugar_do_comum():
    """Tilapia saia no almoco de TODO dia, e frango so no jantar. O criterio nao e banir:
    e nao deixar o caro ganhar do comum por acidente de pontuacao."""
    for semente, refeicoes in _planos():
        usados = {f for m in refeicoes for f in _ids(m)}
        assert not (CAROS & usados), "dia %s trouxe %s" % (semente, CAROS & usados)


def test_o_preferido_da_pessoa_vence_a_penalidade_de_preco():
    """Preco desempata, nao proibe. Quem pediu tilapia continua recebendo tilapia."""
    perfil = dict(PERFIL, preferred_foods=["tilapia"])
    nota_pedida = ne._score_food(ne.FOOD_INDEX["tilapia"], "lunch", perfil)
    nota_padrao = ne._score_food(ne.FOOD_INDEX["tilapia"], "lunch", PERFIL)
    assert nota_pedida > nota_padrao
    assert nota_pedida > ne._score_food(ne.FOOD_INDEX["chicken-breast"], "lunch", PERFIL)


def test_todo_alimento_tem_preco():
    """Sem o campo, o alimento passaria como barato por omissao — e o mais caro do
    catalogo entraria no plano de quem nao pode pagar."""
    for f in ne.FOODS:
        assert f.get("custo") in (1, 2, 3), "%s sem custo valido" % f["id"]


# -- 5. O que o treinador manda no prato principal -------------------------------------

def test_almoco_e_jantar_trazem_frango_ovo_ou_carne():
    """A regra do treinador, no prato principal: ou e peito de frango, ou e carne."""
    do_metodo = {"chicken-breast", "chicken-thigh", "beef-grill", "beef-ground",
                 "eggs-whole", "egg-whites", "chicken-egg-omelet", "pork-loin"}
    for semente, refeicoes in _planos():
        for tipo in ("lunch", "dinner"):
            for m in _por_tipo(refeicoes, tipo):
                assert do_metodo & set(_ids(m)), \
                    "dia %s, %s: %s" % (semente, m.get("name"), _ids(m))


# -- 6. Variedade nunca vale mais do que pertencer -------------------------------------

def test_variedade_nao_empurra_alimento_para_a_refeicao_errada():
    """A regra antiga preferia o que ainda nao tinha sido usado hoje. Numa familia de
    cinco gorduras isso mandava amendoim torrado (de lanche) para o jantar, so porque o
    azeite ja tinha ido para o almoco. Repetir o azeite e o certo."""
    for _, refeicoes in _planos():
        for m in _por_tipo(refeicoes, "dinner"):
            assert "peanuts" not in _ids(m), "amendoim torrado no jantar"


def test_a_gordura_pode_repetir_entre_refeicoes_do_dia():
    """Repetir o azeite e permitido — e o que qualquer cozinha faz.

    Este teste pedia a repeticao no almoco E no jantar. Depois que a gordura passou a
    entrar SO quando a refeicao ainda precisa dela, um jantar de acem (18 g de gordura
    sozinho) deixou de receber azeite, e a repeticao passou a acontecer entre outras
    refeicoes. O que importa nao e QUAIS duas: e que repetir seja possivel, porque a
    alternativa e o absurdo de por amendoim torrado no jantar so por ser novo.
    """
    repetiu = False
    for _, refeicoes in _planos():
        vezes = sum(1 for m in refeicoes if "olive-oil" in _ids(m))
        if vezes >= 2:
            repetiu = True
    assert repetiu, "o azeite nunca repetiu: a excecao nao esta valendo"


def test_a_gordura_so_entra_quando_a_refeicao_ainda_precisa():
    """Um prato que ja tem 18 g de gordura na propria carne nao leva azeite por cima. Era
    assim que o dia fechava 21% acima do alvo de gordura."""
    for _, refeicoes in _planos():
        for m in refeicoes:
            gordura_da_comida = sum(
                ne._food_macros(it["food_id"], it["grams"])[3]
                for it in m.get("foods", [])
                if "fat_source" not in ne.FOOD_INDEX[it["food_id"]].get("roles", []))
            tem_gordura_avulsa = any(
                "fat_source" in ne.FOOD_INDEX[it["food_id"]].get("roles", [])
                for it in m.get("foods", []))
            alvo = m.get("target_fat") or 0
            if tem_gordura_avulsa and alvo:
                assert gordura_da_comida < alvo * 1.6, (
                    "%s ja tinha %.0f g de gordura e ainda recebeu tempero"
                    % (m.get("name"), gordura_da_comida))

# -*- coding: utf-8 -*-
"""FORGE — montar a refeicao escolhendo alimento por alimento.

O que estes testes defendem e uma promessa feita ao atleta: "voce escolhe o que vai comer".
Promessa dessa natureza quebra de tres jeitos, e os tres estao cobertos aqui:

  - oferecer um alimento que ele NAO PODE comer (alergia, restricao, alimento evitado);
  - oferecer um espaco vazio que ele nao tem como preencher, travando o fluxo;
  - deixar montar um prato incoerente sem avisar.

O que NAO e testado aqui de proposito: a grama de cada alimento. Quem decide porcao e
`calculate_meal_portions`, que ja tem suite propria. Este modulo so diz o que CABE.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from montagem_por_alimento import (ORDEM, ROTULOS, espacos_da_refeicao,  # noqa: E402
                                   falta_escolher)
from nutrition_engine import FOOD_INDEX  # noqa: E402

SEM_RESTRICAO = {"avoid_foods": [], "allergies": [], "dietary_restrictions": []}

REFEICOES = ["Café da manhã", "Almoço", "Jantar", "Pré-treino", "Pós-treino", "Lanche da tarde"]


class TestOsEspacosDaRefeicao:

    @pytest.mark.parametrize("refeicao", REFEICOES)
    def test_toda_refeicao_tem_pelo_menos_um_espaco_obrigatorio(self, refeicao):
        espacos = espacos_da_refeicao(refeicao, SEM_RESTRICAO)
        assert any(e["obrigatorio"] for e in espacos), refeicao

    # Espaco vazio e obrigatorio trava a pessoa sem ela entender por que o botao nao liga.
    @pytest.mark.parametrize("refeicao", REFEICOES)
    def test_nenhum_espaco_chega_a_tela_sem_opcao(self, refeicao):
        for espaco in espacos_da_refeicao(refeicao, SEM_RESTRICAO):
            assert espaco["alimentos"], f"{refeicao}/{espaco['rotulo']} sem opcao"

    @pytest.mark.parametrize("refeicao", REFEICOES)
    def test_todo_espaco_tem_rotulo_que_uma_pessoa_le(self, refeicao):
        for espaco in espacos_da_refeicao(refeicao, SEM_RESTRICAO):
            assert espaco["rotulo"] != espaco["papel"], espaco["papel"]
            assert espaco["rotulo"] in [r[0] for r in ROTULOS.values()]

    def test_a_proteina_vem_antes_do_carboidrato(self):
        """A proteina ancora o prato e e o que mais pesa na conta: escolher ela primeiro faz
        o resto se ajustar. Na ordem inversa, o carboidrato toma a caloria e a proteina fica
        espremida contra o limite de porcao."""
        papeis = [e["papel"] for e in espacos_da_refeicao("Almoço", SEM_RESTRICAO)]
        assert papeis.index("primary_protein") < papeis.index("primary_carb")

    def test_a_ordem_da_tela_segue_a_ordem_declarada(self):
        papeis = [e["papel"] for e in espacos_da_refeicao("Café da manhã", SEM_RESTRICAO)]
        assert papeis == [p for p in ORDEM if p in papeis]

    def test_nome_de_refeicao_desconhecido_nao_quebra(self):
        espacos = espacos_da_refeicao("Refeição do Nicolas", SEM_RESTRICAO)
        assert espacos and any(e["obrigatorio"] for e in espacos)


class TestOQueAPessoaNaoPodeComerNaoAparece:
    """A promessa mais seria da tela. Um alimento proibido oferecido aqui e a pessoa
    escolhendo com confianca aquilo que ela nao pode comer."""

    def test_alimento_evitado_some_de_todos_os_espacos(self):
        perfil = {**SEM_RESTRICAO, "avoid_foods": ["chicken-breast"]}
        for espaco in espacos_da_refeicao("Almoço", perfil):
            assert all(a["food_id"] != "chicken-breast" for a in espaco["alimentos"])

    def test_restricao_vegetariana_tira_a_carne(self):
        perfil = {**SEM_RESTRICAO, "dietary_restrictions": ["vegetarian"]}
        ids = {a["food_id"] for e in espacos_da_refeicao("Almoço", perfil) for a in e["alimentos"]}
        assert "beef-grill" not in ids
        assert "chicken-breast" not in ids

    def test_sem_lactose_tira_o_whey(self):
        perfil = {**SEM_RESTRICAO, "dietary_restrictions": ["lactose_free"]}
        ids = {a["food_id"] for e in espacos_da_refeicao("Lanche da tarde", perfil)
               for a in e["alimentos"]}
        assert "whey-protein" not in ids

    # Protocolo agressivo: o teto de densidade de carboidrato ja existia no motor e tinha de
    # valer aqui tambem, senao a tela ofereceria arroz para quem esta em low-carb de verdade.
    def test_o_teto_de_carboidrato_do_protocolo_vale_na_lista(self):
        perfil = {**SEM_RESTRICAO, "_max_food_carb_g_per_100g": 12.0}
        ids = {a["food_id"] for e in espacos_da_refeicao("Almoço", perfil) for a in e["alimentos"]}
        assert "rice-white" not in ids
        assert ids, "o teto nao pode esvaziar a refeicao inteira"


class TestOAlimentoEscolhidoNaoApareceDuasVezes:
    """"Proteina" e "Proteina extra" oferecem os mesmos alimentos. Sem cuidado, a pessoa ve
    o ovo que acabou de escolher disponivel de novo no espaco seguinte e monta um prato com
    ovo duas vezes sem perceber."""

    def test_o_escolhido_some_dos_outros_espacos(self):
        espacos = espacos_da_refeicao("Café da manhã", SEM_RESTRICAO, ["eggs-whole"])
        dono = [e for e in espacos if e["escolhido"] == "eggs-whole"]
        assert len(dono) == 1
        for espaco in espacos:
            if espaco is dono[0]:
                continue
            assert all(a["food_id"] != "eggs-whole" for a in espaco["alimentos"]), espaco["rotulo"]

    def test_o_escolhido_continua_visivel_no_proprio_espaco(self):
        """Some dos outros, mas nao do seu: sem isso a pessoa nao teria como desmarcar."""
        espacos = espacos_da_refeicao("Almoço", SEM_RESTRICAO, ["rice-white"])
        dono = next(e for e in espacos if e["escolhido"] == "rice-white")
        assert any(a["food_id"] == "rice-white" for a in dono["alimentos"])


class TestOQueFaltaEscolher:
    def test_diz_o_que_falta_pelo_rotulo_e_nao_pelo_papel(self):
        espacos = espacos_da_refeicao("Almoço", SEM_RESTRICAO)
        falta = falta_escolher(espacos)
        assert "Proteína" in falta
        assert "primary_protein" not in falta

    def test_espaco_opcional_nunca_entra_no_que_falta(self):
        espacos = espacos_da_refeicao("Almoço", SEM_RESTRICAO)
        opcionais = {e["rotulo"] for e in espacos if not e["obrigatorio"]}
        assert not (opcionais & set(falta_escolher(espacos)))

    def test_com_todos_os_obrigatorios_escolhidos_nao_falta_nada(self):
        espacos = espacos_da_refeicao("Almoço", SEM_RESTRICAO)
        escolhas = [e["alimentos"][0]["food_id"] for e in espacos if e["obrigatorio"]]
        assert falta_escolher(espacos_da_refeicao("Almoço", SEM_RESTRICAO, escolhas)) == []


class TestOCartaoDoAlimento:
    def test_o_dado_e_por_100g_e_nao_por_porcao(self):
        """A porcao so existe depois que o conjunto todo esta escolhido, porque ela e
        distribuida entre os alimentos. Mostrar grama aqui seria um numero que muda sozinho
        na tela seguinte."""
        espaco = espacos_da_refeicao("Almoço", SEM_RESTRICAO)[0]
        for alimento in espaco["alimentos"]:
            assert "kcal_por_100g" in alimento
            assert "grams" not in alimento

    def test_o_alimento_do_metodo_vem_marcado_e_primeiro(self):
        espacos = espacos_da_refeicao("Almoço", SEM_RESTRICAO)
        proteina = next(e for e in espacos if e["papel"] == "primary_protein")
        assert proteina["alimentos"][0]["metodo"] is True
        marcados = [a["metodo"] for a in proteina["alimentos"]]
        assert marcados == sorted(marcados, reverse=True), "os do metodo tem de vir juntos no topo"

    def test_todo_alimento_oferecido_existe_no_catalogo_do_motor(self):
        for refeicao in REFEICOES:
            for espaco in espacos_da_refeicao(refeicao, SEM_RESTRICAO):
                for alimento in espaco["alimentos"]:
                    assert alimento["food_id"] in FOOD_INDEX, alimento["food_id"]

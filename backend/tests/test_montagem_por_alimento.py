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


class TestABuscaLivre:
    """Para quem ja sabe o que vai comer e nao quer rolar cinco espacos.

    O que estes testes defendem: a busca acha o que a pessoa DIGITOU, e nao o que ela
    deveria ter digitado. Erro de digitacao na cozinha e a regra, nao a excecao — foi
    exatamente isso que o atleta reclamou quando "abulmina" nao achava a albumina dele.
    """

    def _buscar(self, q, perfil=None, limite=20):
        from montagem_por_alimento import buscar_para_montagem
        return buscar_para_montagem(q, perfil or SEM_RESTRICAO, limite)

    def test_acha_pelo_nome_exato(self):
        nomes = [a["name"] for a in self._buscar("arroz")]
        assert any("Arroz" in n for n in nomes), nomes

    # O caso real: letras trocadas de lugar.
    @pytest.mark.parametrize("digitado", ["abulmina", "abumina", "albumia"])
    def test_acha_albumina_mesmo_com_erro_de_digitacao(self, digitado):
        nomes = [a["name"].lower() for a in self._buscar(digitado)]
        assert any("albumina" in n for n in nomes), f"{digitado} -> {nomes}"

    def test_acha_com_duas_palavras_e_erro_numa_delas(self):
        nomes = [a["name"].lower() for a in self._buscar("batatta doce")]
        assert any("batata" in n and "doce" in n for n in nomes), nomes

    # "batata doce" nao pode trazer toda batata do catalogo so porque a primeira palavra
    # bateu: quem digita duas palavras esta estreitando a busca, e nao alargando.
    def test_as_duas_palavras_precisam_casar(self):
        nomes = [a["name"].lower() for a in self._buscar("batata doce")]
        assert nomes and all("doce" in n for n in nomes), nomes

    def test_texto_sem_sentido_nao_devolve_nada(self):
        assert self._buscar("xyzabc") == []

    def test_uma_letra_nao_devolve_nada(self):
        assert self._buscar("a") == []

    def test_diz_quais_o_motor_sabe_dimensionar(self):
        from nutrition_engine import FOOD_INDEX
        for achado in self._buscar("arroz"):
            assert achado["dimensionavel"] == (achado["food_id"] in FOOD_INDEX)

    # O alimento que o motor dimensiona vem primeiro: ele entra na refeicao sem a pessoa ter
    # de pesar nada, entao e o caminho mais curto quando existe.
    def test_o_que_o_motor_dimensiona_vem_antes(self):
        achados = self._buscar("whey")
        dimensionaveis = [a["dimensionavel"] for a in achados]
        assert True in dimensionaveis
        primeiro_manual = dimensionaveis.index(False) if False in dimensionaveis else len(dimensionaveis)
        assert all(dimensionaveis[:primeiro_manual]), achados

    # Nao adianta esconder o leite na lista por funcao e entregar ele na busca.
    def test_a_restricao_vale_na_busca_tambem(self):
        perfil = {**SEM_RESTRICAO, "dietary_restrictions": ["vegetarian"]}
        ids = {a["food_id"] for a in self._buscar("frango", perfil)}
        assert "chicken-breast" not in ids

    def test_alimento_evitado_nao_aparece_na_busca(self):
        perfil = {**SEM_RESTRICAO, "avoid_foods": ["rice-white"]}
        ids = {a["food_id"] for a in self._buscar("arroz", perfil)}
        assert "rice-white" not in ids

    def test_todo_achado_traz_o_macro_por_100g(self):
        for achado in self._buscar("frango"):
            for campo in ("kcal_por_100g", "protein_por_100g", "carb_por_100g", "fat_por_100g"):
                assert campo in achado, achado["name"]

    def test_o_limite_e_respeitado(self):
        assert len(self._buscar("a" * 2 + "rroz", limite=2)) <= 2

    # O catalogo tem o mesmo alimento duas vezes em dois casos conhecidos: batata-doce e
    # castanha-do-para, uma vez no motor e outra so no diario. Na busca isso aparecia como
    # duas linhas iguais e a pessoa nao tinha como saber qual escolher.
    @pytest.mark.parametrize("consulta,palavra", [
        ("batata doce", "batata"),
        ("castanha do para", "castanha"),
    ])
    def test_o_mesmo_alimento_nao_aparece_duas_vezes(self, consulta, palavra):
        nomes = [a["name"].lower() for a in self._buscar(consulta)]
        repetidos = [n for n in nomes if palavra in n]
        assert len(repetidos) <= 1, repetidos

    # Desduplicar nao pode juntar alimentos que sao de fato diferentes.
    def test_alimentos_parecidos_e_diferentes_continuam_separados(self):
        nomes = {a["name"] for a in self._buscar("arroz")}
        assert "Arroz branco cozido" in nomes
        assert "Arroz integral cozido" in nomes

    # Entre os dois registros, fica o que o motor sabe dimensionar: o outro obrigaria a
    # pessoa a pesar um alimento que o FORGE ja sabe calcular.
    def test_entre_os_duplicados_fica_o_que_o_motor_dimensiona(self):
        achados = self._buscar("batata doce")
        assert achados and achados[0]["dimensionavel"] is True


class TestAContaDoDia:
    """A tolerancia que importa e a do DIA, e nao a da refeicao.

    Quem tem 2.000 kcal para bater nao se importa se o cafe da manha passou 80: importa se o
    dia fecha. E ele fecha sozinho, porque as refeicoes seguintes passam a mirar o que sobrou
    (`redistribute_remaining_targets`, que ja existia).

    A margem nao foi inventada para esta tela: e `calorie_tolerance_pct`, que vive no metodo
    do FORGE e vale 5%. Em 2.000 kcal da os 100 para cima ou para baixo que o atleta pediu.
    """

    def _dia(self, alvo, refeicoes, travadas, idx, kcal_desta):
        from nutrition_routes import _dia_do_rascunho
        draft = {
            "targets": {"goal_calories": alvo},
            "meals": [{"foods": [{"food_id": "rice-white", "grams": 200}] if t else []}
                      for t in travadas],
            "locked": list(travadas),
        }
        for i, t in enumerate(travadas):
            if t and i != idx:
                draft["meals"][i]["foods"] = [{"food_id": "rice-white", "grams": 100}]
        return _dia_do_rascunho(draft, idx, {"kcal": kcal_desta})

    def test_a_margem_sai_do_metodo_e_nao_de_um_numero_solto(self):
        from nutrition_engine import FORGE_COACH_METHODOLOGY
        dia = self._dia(2000, 5, [False] * 5, 0, 500)
        assert dia["tolerancia"] == round(2000 * FORGE_COACH_METHODOLOGY["calorie_tolerance_pct"])
        assert dia["tolerancia"] == 100, "2.000 kcal com 5% tem de dar exatamente 100"

    # Julgar um dia pela metade diria "voce esta 1.500 kcal abaixo" para quem acabou de
    # escolher o cafe da manha.
    def test_o_dia_so_e_julgado_quando_esta_completo(self):
        parcial = self._dia(2000, 5, [False, False, False, False, False], 0, 500)
        assert parcial["fechado"] is False
        assert parcial["refeicoes_faltando"] == 4

    def test_com_todas_travadas_o_dia_fecha(self):
        fechado = self._dia(2000, 5, [True] * 5, 0, 500)
        assert fechado["fechado"] is True
        assert fechado["refeicoes_faltando"] == 0

    def test_a_refeicao_sendo_montada_nao_conta_duas_vezes(self):
        """Ela entra pelo total da previa, e nao pelo que esta gravado no rascunho."""
        dia = self._dia(2000, 5, [True] * 5, 0, 500)
        # 4 refeicoes travadas de 100 g de arroz + os 500 da previa. Se a refeicao 0
        # contasse duas vezes, o total passaria disso.
        assert dia["ja_escolhido"] < 500 + 4 * 200

    @pytest.mark.parametrize("consumido,dentro", [
        (2000, True), (2100, True), (1900, True), (2101, False), (1899, False),
    ])
    def test_a_margem_aceita_cem_para_cada_lado(self, consumido, dentro):
        dia = self._dia(2000, 1, [True], 0, consumido)
        assert dia["dentro_da_tolerancia"] is dentro, f"{consumido} kcal"

    def test_alvo_zerado_nao_quebra(self):
        dia = self._dia(0, 3, [False] * 3, 0, 0)
        assert dia["alvo"] == 0 and dia["tolerancia"] == 0


class TestAPorcaoNaLista:
    """A lista tem de dizer QUANTO, e nao caloria por 100 g.

    Eu tinha escrito o contrario no codigo, com o argumento de que a porcao so existe depois
    do conjunto todo escolhido. O argumento estava certo e a conclusao errada: a lista passou
    a oferecer "Whey — 400 kcal /100g", e ninguem come 100 g de whey. O atleta reclamou
    disso com essas palavras.
    """

    ALVO = {"cal": 760, "protein": 50, "fat": 20, "goal": "muscle_gain"}

    def test_cada_alimento_traz_a_porcao_que_ele_teria(self):
        espacos = espacos_da_refeicao("Café da manhã", SEM_RESTRICAO, None, self.ALVO)
        for espaco in espacos:
            for alimento in espaco["alimentos"]:
                assert alimento.get("porcao_g"), f"{espaco['rotulo']}/{alimento['name']}"

    # O numero que motivou a reclamacao.
    def test_a_porcao_do_whey_e_de_gente_e_nao_de_100g(self):
        espacos = espacos_da_refeicao("Café da manhã", SEM_RESTRICAO, None, self.ALVO)
        proteina = next(e for e in espacos if e["papel"] == "primary_protein")
        whey = next(a for a in proteina["alimentos"] if a["food_id"] == "whey-protein")
        assert whey["porcao_g"] <= 60, whey["porcao_g"]

    def test_nenhuma_porcao_passa_do_teto_do_alimento(self):
        from nutrition_engine import _portion_limit
        for refeicao in ("Café da manhã", "Almoço", "Jantar"):
            espacos = espacos_da_refeicao(refeicao, SEM_RESTRICAO, None, self.ALVO)
            for espaco in espacos:
                for alimento in espaco["alimentos"]:
                    teto = _portion_limit(FOOD_INDEX[alimento["food_id"]], "hard_max")
                    assert alimento["porcao_g"] <= teto + 1, f"{alimento['name']}"

    # Sem alvo a lista continua funcionando: a porcao some, a caloria por 100 g fica.
    def test_sem_alvo_a_lista_nao_quebra(self):
        espacos = espacos_da_refeicao("Almoço", SEM_RESTRICAO)
        assert espacos
        for alimento in espacos[0]["alimentos"]:
            assert "kcal_por_100g" in alimento
            assert "porcao_g" not in alimento


class TestOQueCombinaVemPrimeiro:
    """Ninguem bate whey com batata inglesa.

    A afinidade nao e lista escrita a mao: sai de MEAL_COMBOS. Se "Mingau FORGE" junta
    PORRIDGE_CARB com FAST_PROTEIN, entao aveia e farinha de arroz andam com whey.
    """

    ALVO = {"cal": 760, "protein": 50, "fat": 20, "goal": "muscle_gain"}

    def _carbos(self, escolhidos):
        espacos = espacos_da_refeicao("Café da manhã", SEM_RESTRICAO, escolhidos, self.ALVO)
        return next(e for e in espacos if e["papel"] == "primary_carb")["alimentos"]

    def test_escolhido_o_whey_o_topo_e_carbo_que_combina_e_do_metodo(self):
        """Nao prende os DOIS ids exatos: com a lista aberta entrou tambem o creme de arroz
        com whey, que combina e e do metodo — resultado melhor, e o teste e que estava
        estreito. O que importa e a propriedade: o topo combina com o que foi escolhido."""
        topo = self._carbos(["whey-protein"])[:3]
        assert all(a["combina"] and a["metodo"] for a in topo), [a["name"] for a in topo]
        ids = {a["food_id"] for a in topo}
        assert {"oats", "rice-flour"} <= ids, ids

    def test_o_arroz_branco_nao_vem_na_frente_do_whey(self):
        nomes = [a["food_id"] for a in self._carbos(["whey-protein"])]
        assert nomes.index("rice-white") > nomes.index("oats")

    def test_o_que_combina_vem_marcado(self):
        for alimento in self._carbos(["whey-protein"]):
            if alimento["food_id"] in ("oats", "rice-flour"):
                assert alimento["combina"] is True, alimento["name"]

    # Sem nada escolhido nao existe com o que combinar, e marcar tudo seria ruido.
    def test_sem_escolha_nada_e_marcado_como_combina(self):
        assert not any(a["combina"] for a in self._carbos([]))


class TestOProtocoloAgressivoTambemTemEscolha:
    """O atleta no teto de carboidrato via SEMPRE o mesmo prato.

    O protocolo agressivo poe um teto de densidade (12 g de carboidrato por 100 g) que
    reprova praticamente todo carboidrato do catalogo — sobra a beterraba. Como quase toda
    combinacao exige um carboidrato, ele ficava com UMA opcao no almoco, uma no jantar, uma
    no pre e uma no pos. Ele reclamou que "continua tudo igual", e estava certo.

    Estes testes prendem o piso: ninguem, em nenhum protocolo, recebe uma unica opcao.
    """

    TETO = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
            "preferred_foods": [], "disliked_foods": [], "weight_kg": 70,
            "_max_food_carb_g_per_100g": 12.0}

    def _opcoes(self, refeicao, semente=1):
        from nutrition_engine import get_meal_archetype_options
        return get_meal_archetype_options(refeicao, 542, 40, 15, self.TETO, set(),
                                          "fat_loss", None, 0, None, 5, semente)

    @pytest.mark.parametrize("refeicao", REFEICOES)
    def test_toda_refeicao_oferece_pelo_menos_duas_opcoes(self, refeicao):
        opcoes = self._opcoes(refeicao)
        assert len(opcoes) >= 2, f"{refeicao}: {[o['label'] for o in opcoes]}"

    # "Padrao" e o template de emergencia. Ele existe para ninguem ficar sem nada, e ver ele
    # significa que combinacao nenhuma sobreviveu — era o caso do pre e do pos-treino.
    @pytest.mark.parametrize("refeicao", REFEICOES)
    def test_nenhuma_refeicao_cai_no_template_de_emergencia(self, refeicao):
        rotulos = [o["label"] for o in self._opcoes(refeicao)]
        assert "Padrão" not in rotulos, f"{refeicao} caiu no fallback: {rotulos}"

    def test_o_teto_continua_valendo_nas_opcoes_oferecidas(self):
        """Dar mais escolha nao pode furar o protocolo: nenhum alimento denso passa."""
        from nutrition_engine import FOOD_INDEX, food_carb_density
        for refeicao in REFEICOES:
            for opcao in self._opcoes(refeicao):
                for item in opcao["meal"]["foods"]:
                    densidade = food_carb_density(FOOD_INDEX[item["food_id"]])
                    assert densidade <= 12.0, (
                        f"{refeicao}/{opcao['label']}: {item['food']['name']} tem "
                        f"{densidade:.1f} g de carbo por 100 g")

    def test_mostrar_outras_opcoes_muda_de_verdade_tambem_no_teto(self):
        vistos = set()
        for semente in range(1, 6):
            assinatura = tuple(sorted(
                tuple(sorted(i["food_id"] for i in o["meal"]["foods"]))
                for o in self._opcoes("Almoço", semente)))
            vistos.add(assinatura)
        assert len(vistos) >= 3, f"so {len(vistos)} resultados distintos em 5 toques"


class TestAListaMostraTudoQueServe:
    """O atleta pediu: "liste todas as proteinas que existem, tudo de carboidrato que existe".

    Antes a lista usava a familia curada quando ela existia, e o almoco mostrava 9 das 14
    proteinas do catalogo. A familia curada serve para o motor ESCOLHER sozinho, e nao para
    limitar quem esta escolhendo a mao. Ela nao sumiu: virou ORDEM.
    """

    ALVO = {"cal": 800, "protein": 55, "fat": 22, "goal": "muscle_gain"}

    def _espaco(self, refeicao, papel, perfil=None):
        espacos = espacos_da_refeicao(refeicao, perfil or SEM_RESTRICAO, None, self.ALVO)
        return next(e for e in espacos if e["papel"] == papel)

    def test_a_proteina_do_almoco_lista_o_catalogo_inteiro(self):
        from nutrition_engine import FOOD_INDEX
        do_catalogo = {f["id"] for f in FOOD_INDEX.values()
                       if "primary_protein" in (f.get("roles") or [])}
        oferecidos = {a["food_id"] for a in self._espaco("Almoço", "primary_protein")["alimentos"]}
        assert do_catalogo <= oferecidos, sorted(do_catalogo - oferecidos)

    def test_o_carboidrato_do_almoco_lista_o_catalogo_inteiro(self):
        from nutrition_engine import FOOD_INDEX
        do_catalogo = {f["id"] for f in FOOD_INDEX.values()
                       if "primary_carb" in (f.get("roles") or [])}
        oferecidos = {a["food_id"] for a in self._espaco("Almoço", "primary_carb")["alimentos"]}
        assert do_catalogo <= oferecidos, sorted(do_catalogo - oferecidos)

    # Abrir a lista nao pode abrir a porta para o que a pessoa nao pode comer.
    def test_abrir_a_lista_nao_furou_a_restricao(self):
        perfil = {**SEM_RESTRICAO, "dietary_restrictions": ["vegetarian"]}
        ids = {a["food_id"] for a in self._espaco("Almoço", "primary_protein", perfil)["alimentos"]}
        assert "chicken-breast" not in ids and "beef-grill" not in ids

    def test_abrir_a_lista_nao_furou_o_teto_do_protocolo(self):
        from nutrition_engine import FOOD_INDEX, food_carb_density
        perfil = {**SEM_RESTRICAO, "_max_food_carb_g_per_100g": 12.0}
        for alimento in self._espaco("Almoço", "primary_carb", perfil)["alimentos"]:
            assert food_carb_density(FOOD_INDEX[alimento["food_id"]]) <= 12.0, alimento["name"]

    # A familia curada virou ordem: o que o metodo aponta continua vindo primeiro.
    def test_o_que_o_metodo_aponta_continua_no_topo(self):
        alimentos = self._espaco("Almoço", "primary_protein")["alimentos"]
        assert alimentos[0]["metodo"] is True, alimentos[0]["name"]


class TestOsAlvosDeMacroDaRefeicao:
    def _alvos(self, cal, prot, gord):
        from nutrition_routes import _alvos_de_macro
        return _alvos_de_macro({"target_cal": cal, "target_protein": prot, "target_fat": gord})

    # O carboidrato e o macro RESIDUAL: o que sobra da caloria depois de proteina e gordura.
    def test_o_carboidrato_fecha_a_caloria_da_refeicao(self):
        alvos = self._alvos(542, 40, 15)
        somado = alvos["protein_g"] * 4 + alvos["carbs_g"] * 4 + alvos["fat_g"] * 9
        assert abs(somado - 542) <= 4, somado

    def test_nenhum_macro_fica_negativo(self):
        """Gordura alta demais para a caloria da refeicao nao pode gerar carbo negativo."""
        alvos = self._alvos(200, 40, 30)
        assert alvos["carbs_g"] >= 0

    def test_refeicao_sem_alvo_nao_quebra(self):
        assert self._alvos(0, 0, 0) == {"protein_g": 0, "carbs_g": 0, "fat_g": 0}

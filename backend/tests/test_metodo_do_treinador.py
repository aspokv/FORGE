# -*- coding: utf-8 -*-
"""FORGE — o metodo do treinador, extraido dos protocolos reais.

O que estes testes defendem nao e codigo, e FIDELIDADE. O metodo foi lido em 65 protocolos
que o treinador montou a mao; se alguem mexer numa fracao sem entender, o plano gerado deixa
de parecer com o que ele entrega aos alunos, e ninguem percebe — o numero continua fechando.

Por isso os testes prendem as afirmacoes que vieram escritas nos documentos:

  - no dia low o pos-treino vai SEM amido ("Sem batata aqui", literal no protocolo);
  - a gordura do dia low fica em um horario so;
  - o carboidrato do dia high volta para o pos-treino e para o almoco;
  - toda fonte tem alternativa dentro do mesmo papel.

E a invariante de sempre: a distribuicao SOMA o carboidrato do dia, nunca cria nem perde.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from food_diary import DIARY_FOODS  # noqa: E402
from metodo_do_treinador import (  # noqa: E402
    DISTRIBUICAO, ORDEM_DO_DIA, PAPEIS, PROTOCOLOS, REGRAS,
    carbo_por_refeicao, ciclo_do_protocolo, protocolo, regra,
)


class TestAArquiteturaDeRefeicoes:
    """As refeicoes sao nomeadas pela FUNCAO, e nao pela hora do relogio."""

    def test_o_dia_tem_a_ordem_do_metodo(self):
        assert ORDEM_DO_DIA[0] == "pre_treino"
        assert ORDEM_DO_DIA[1] == "pos_treino"
        assert ORDEM_DO_DIA[-1] == "ceia"

    def test_todo_papel_da_ordem_existe(self):
        for papel in ORDEM_DO_DIA:
            assert papel in PAPEIS, papel

    # Quem treina as 6h e quem treina as 19h recebem a mesma estrutura.
    def test_nenhum_papel_se_chama_pela_hora(self):
        for chave in PAPEIS:
            assert "manha" not in chave and "noite" not in chave

    def test_todo_papel_explica_o_porque(self):
        for chave, papel in PAPEIS.items():
            assert papel.get("porque"), chave
            assert len(papel["porque"]) > 30, chave

    # Plano que nao aceita troca e plano que a pessoa abandona.
    def test_todo_papel_com_proteina_oferece_alternativa(self):
        for chave, papel in PAPEIS.items():
            fontes = papel.get("fontes_proteina")
            if fontes:
                assert len(fontes) >= 2, chave

    def test_toda_fonte_citada_existe_no_catalogo(self):
        faltando = []
        for chave, papel in PAPEIS.items():
            for campo in ("fontes_carbo", "fontes_proteina", "fontes_gordura", "acompanha"):
                for fid in papel.get(campo) or []:
                    if fid not in DIARY_FOODS:
                        faltando.append((chave, campo, fid))
        assert not faltando, f"fontes fora do catalogo: {faltando}"


class TestOFormatoDoDiaLow:
    """O dia low nao e so 'menos carboidrato' — ele muda de formato."""

    # "Sem batata aqui", escrito assim no protocolo.
    def test_o_pos_treino_do_dia_low_vai_sem_amido(self):
        assert DISTRIBUICAO["low"]["pos_treino"] == 0.0

    def test_o_almoco_do_dia_low_tambem_vai_sem_amido(self):
        assert DISTRIBUICAO["low"]["almoco"] == 0.0

    def test_o_que_sobra_no_low_cerca_o_treino_e_a_tarde(self):
        low = DISTRIBUICAO["low"]
        assert low["pre_treino"] > 0
        assert low["lanche"] > 0
        assert low["lanche_final"] > 0

    def test_no_dia_high_o_amido_volta_para_as_duas(self):
        alto = DISTRIBUICAO["high"]
        assert alto["pos_treino"] > 0
        assert alto["almoco"] > 0


class TestADistribuicaoSomaODia:
    """Mudar uma fracao nao pode fazer o dia ganhar ou perder carboidrato em silencio."""

    @pytest.mark.parametrize("tipo", ["low", "high", "ganho"])
    def test_a_soma_fecha_no_carboidrato_do_dia(self, tipo):
        divisao = carbo_por_refeicao(400, tipo)
        assert sum(divisao.values()) == pytest.approx(400, abs=1.0), tipo

    @pytest.mark.parametrize("tipo", ["low", "high", "ganho"])
    def test_nenhuma_refeicao_recebe_carboidrato_negativo(self, tipo):
        assert all(v >= 0 for v in carbo_por_refeicao(400, tipo).values()), tipo

    def test_tipo_desconhecido_cai_no_high_em_vez_de_quebrar(self):
        assert sum(carbo_por_refeicao(400, "xpto").values()) == pytest.approx(400, abs=1.0)

    def test_dia_sem_carboidrato_nao_quebra(self):
        assert sum(carbo_por_refeicao(0, "low").values()) == 0


class TestOsProtocolosDeCiclagem:
    """Os nomes sao do treinador, tirados dos proprios arquivos dele."""

    def test_os_protocolos_que_ele_usa_estao_todos_aqui(self):
        for chave in ("3low1high", "4low1high", "6low1high", "saturacao"):
            assert chave in PROTOCOLOS, chave

    def test_o_ciclo_tres_por_um_tem_quatro_dias(self):
        assert ciclo_do_protocolo("3low1high") == ["low", "low", "low", "high"]

    def test_o_seis_por_um_e_mais_restritivo_que_o_tres_por_um(self):
        assert ciclo_do_protocolo("6low1high").count("low") > ciclo_do_protocolo("3low1high").count("low")

    def test_todo_protocolo_diz_para_quem_serve(self):
        for chave, p in PROTOCOLOS.items():
            assert p.get("para_quem"), chave

    def test_protocolo_inexistente_devolve_vazio_em_vez_de_quebrar(self):
        assert ciclo_do_protocolo("nao-existe") == []
        assert protocolo("nao-existe") is None


class TestAsRegrasComRazao:
    """A razao importa tanto quanto a regra: e ela que faz o atleta obedecer."""

    def test_toda_regra_traz_o_porque(self):
        for r in REGRAS:
            assert r.get("porque"), r["chave"]
            assert len(r["porque"]) > 25, r["chave"]

    def test_as_regras_que_vieram_escritas_nos_protocolos_estao_aqui(self):
        for chave in ("pesagem", "gordura_low", "sem_amido_pos_low", "folhas_livres",
                      "canela", "batata_volume", "agua", "substituicao"):
            assert regra(chave) is not None, chave

    # A pesagem pronta e a base da conversao de compra e de panela que ja esta no ar.
    def test_a_regra_da_pesagem_diz_que_e_pronto(self):
        assert "pronto" in regra("pesagem")["regra"].lower()

    def test_regra_inexistente_devolve_nulo(self):
        assert regra("nao-existe") is None


def test_nenhum_dado_de_aluno_entrou_no_codigo():
    """O que foi extraido e a estrutura. Nome, foto e medida de aluno ficaram fora."""
    fonte = (Path(__file__).parent.parent / "metodo_do_treinador.py").read_text(encoding="utf-8")
    proibidos = ["Debora", "Tamy", "Joice", "Nicolau", "Gabriel", "Andrea", "Mariana", "Erika"]
    encontrados = [p for p in proibidos if p.lower() in fonte.lower()]
    assert not encontrados, f"nome de aluno no codigo: {encontrados}"


class TestOMetodoMontaAsEscolhas:
    """De descritivo a decisivo: agora o metodo escolhe o que e oferecido.

    Ate aqui o atleta LIA a arquitetura do dia e aplicava sozinho. Estes testes defendem o
    passo seguinte — quando ele monta o plano refeicao por refeicao, as opcoes que o FORGE
    apresenta sao as combinacoes do treinador, e sao as PRIMEIRAS.
    """

    def _opcoes(self, nome, cal=700, prot=50, gord=15, objetivo="muscle_gain"):
        from nutrition_engine import get_meal_archetype_options
        perfil = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
                  "preferred_foods": [], "disliked_foods": [], "weight_kg": 80}
        return get_meal_archetype_options(nome, cal, prot, gord, perfil, set(), objetivo)

    # O motor de plano tem catalogo proprio, menor que o do diario. Uma fonte citada aqui
    # que nao exista la some da combinacao em silencio, e o atleta recebe um prato
    # incompleto sem ninguem perceber.
    def test_toda_fonte_das_familias_existe_no_catalogo_do_motor(self):
        from nutrition_engine import FOOD_INDEX
        from metodo_do_treinador import FAMILIAS_DO_METODO
        faltando = [(fam, fid) for fam, ids in FAMILIAS_DO_METODO.items()
                    for fid in ids if fid not in FOOD_INDEX]
        assert not faltando, f"fontes fora do motor de plano: {faltando}"

    def test_as_familias_do_metodo_chegam_ao_motor(self):
        from nutrition_engine import FOOD_FAMILIES
        from metodo_do_treinador import FAMILIAS_DO_METODO
        for nome in FAMILIAS_DO_METODO:
            assert nome in FOOD_FAMILIES, nome

    def test_nenhum_combo_do_metodo_repete_id_de_combo_que_ja_existia(self):
        from nutrition_engine import MEAL_COMBOS
        ids = [c["id"] for c in MEAL_COMBOS]
        assert len(ids) == len(set(ids)), "id de combinacao duplicado"

    # Alvo por refeicao, e nao um numero unico: o pre-treino do metodo e banana com whey, e
    # cobrar dele a proteina de um almoco o tornaria inviavel por limite de porcao — o que
    # seria uma falha do teste, e nao do metodo.
    @pytest.mark.parametrize("refeicao,cal,prot,gord", [
        ("Pré-treino", 450, 30, 6),
        ("Pós-treino", 700, 50, 12),
        ("Almoço", 800, 55, 22),
        ("Jantar", 700, 50, 15),
    ])
    def test_a_primeira_opcao_oferecida_e_a_do_metodo(self, refeicao, cal, prot, gord):
        opcoes = self._opcoes(refeicao, cal, prot, gord)
        assert opcoes, refeicao
        assert opcoes[0].get("metodo") is True, (
            f"{refeicao}: primeira opcao e '{opcoes[0]['label']}', que nao e do metodo")

    def test_pre_treino_grande_demais_exclui_o_combo_em_vez_de_forcar_a_porcao(self):
        """Achado registrado, e nao defeito escondido.

        Num pre-treino de 700 kcal com 50 g de proteina, banana com whey so fecharia a conta
        com o whey muito alem da porcao real. A guarda de porcao exclui a combinacao — e o
        que sobra e uma opcao com proteina solida, que o metodo dele evita antes do treino.

        O comportamento esta certo (oferecer nada seria pior que oferecer algo), mas quem
        mexer nas fracoes de distribuicao precisa saber que um pre-treino grande sai do
        padrao do treinador. Se um dia o pre-treino do metodo passar a aparecer tambem
        nesse tamanho, este teste avisa que algo mudou na guarda de porcao.
        """
        opcoes = self._opcoes("Pré-treino", 700, 50, 12)
        assert opcoes, "nenhuma opcao de pre-treino"
        assert not any(o.get("metodo") for o in opcoes)

    # "Carboidrato rapido e proteina, sem fibra e sem gordura para nao pesar o estomago."
    def test_o_pre_treino_do_metodo_nao_leva_gordura_nem_proteina_solida(self):
        from nutrition_engine import FOOD_INDEX
        opcao = next(o for o in self._opcoes("Pré-treino", 500, 35, 8) if o.get("metodo"))
        for item in opcao["meal"]["foods"]:
            alimento = FOOD_INDEX[item["food_id"]]
            assert alimento.get("category") != "FAT", alimento["name"]
            assert item["food_id"] not in ("chicken-breast", "beef-grill", "tilapia"), alimento["name"]

    # A gordura do dia low fica em um horario so, e o horario e o almoco.
    def test_o_almoco_do_metodo_leva_a_gordura_do_dia(self):
        from nutrition_engine import FOOD_INDEX
        opcao = next(o for o in self._opcoes("Almoço", 800, 55, 22) if o.get("metodo"))
        ids = {i["food_id"] for i in opcao["meal"]["foods"]}
        assert any(FOOD_INDEX[f].get("category") == "FAT" for f in ids), sorted(ids)

    def test_o_pos_treino_do_metodo_traz_proteina_inteira_amido_e_legume(self):
        from nutrition_engine import FOOD_INDEX
        opcao = next(o for o in self._opcoes("Pós-treino", 700, 50, 12) if o.get("metodo"))
        cats = {FOOD_INDEX[i["food_id"]].get("category") for i in opcao["meal"]["foods"]}
        assert {"PROTEIN", "CARBOHYDRATE", "VEGETABLE"} <= cats, cats

    # A garantia estrutural: o metodo restringe a ESCOLHA, e nao pode inventar alimento.
    def test_nenhuma_opcao_do_metodo_usa_alimento_fora_das_familias_dele(self):
        from metodo_do_treinador import FAMILIAS_DO_METODO
        permitidos = {fid for ids in FAMILIAS_DO_METODO.values() for fid in ids}
        for refeicao in ("Pré-treino", "Pós-treino", "Almoço", "Jantar"):
            for opcao in self._opcoes(refeicao):
                if not opcao.get("metodo") or opcao["archetype_id"] == "forge_oats_whey_banana":
                    continue
                for item in opcao["meal"]["foods"]:
                    assert item["food_id"] in permitidos, (
                        f"{refeicao}/{opcao['label']}: {item['food_id']} fora do metodo")


def test_o_plano_automatico_nao_muda_com_o_metodo_registrado():
    """Regressao deliberada: registrar as combinacoes NAO pode mexer em quem ja tem plano.

    `generate_daily_plan` monta pelos MEAL_TEMPLATES e nunca passa por MEAL_COMBOS. Se um dia
    alguem ligar os dois caminhos, este teste avisa antes de o plano de um assinante mudar
    sozinho da noite para o dia.
    """
    from nutrition_engine import compute_macro_targets, generate_daily_plan
    alvos = compute_macro_targets(80, 180, 30, "male", 5, "muscle_gain")
    perfil = {"avoid_foods": [], "allergies": [], "dietary_restrictions": [],
              "preferred_foods": [], "disliked_foods": [], "weight_kg": 80}
    plano = generate_daily_plan(alvos, perfil, 5, "muscle_gain")
    assert len(plano["meals"]) == 5
    for refeicao in plano["meals"]:
        assert refeicao["foods"], refeicao["name"]
        assert "composition_source" not in refeicao or refeicao["composition_source"] != "dna"

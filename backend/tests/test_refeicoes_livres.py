# -*- coding: utf-8 -*-
"""Refeições do jeito do atleta: a parte que não precisa de servidor.

O pedido: "quero excluir café da manhã e almoço, adicionar de novo e botar o que eu quero".
Estes testes prendem as três regras que fazem isso ser livre arbítrio de verdade, e não
uma sugestão que o motor desfaz:

* a refeição montada guarda exatamente os alimentos e as gramas escolhidos;
* o que a pessoa montou não é redimensionado por nenhum fluxo automático;
* os registros de hoje andam junto com a refeição quando ela muda de lugar.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import refeicoes_livres as rl  # noqa: E402
from food_diary import DIARY_FOODS  # noqa: E402
from nutrition_engine import FOOD_INDEX, build_food_item  # noqa: E402

SO_DO_DIARIO = next(fid for fid in DIARY_FOODS if fid not in FOOD_INDEX)


def _montar(itens):
    return rl.montar_itens(itens, FOOD_INDEX, DIARY_FOODS, build_food_item)


class TestARefeicaoMontada:

    def test_guarda_os_alimentos_e_as_gramas_escolhidos(self):
        alimentos = _montar([("eggs-whole", 150), ("oats", 40)])
        assert [(a["food_id"], a["grams"]) for a in alimentos] == [("eggs-whole", 150), ("oats", 40)]

    def test_alimento_do_motor_sai_igual_ao_do_plano_gerado(self):
        """Mesmo formato, para "2 ovos" e o resto da exibição continuarem funcionando."""
        assert _montar([("eggs-whole", 100)])[0] == build_food_item("eggs-whole", 100)

    # 234 dos alimentos do catálogo só existem no diário. Sem o nome do diário junto, a
    # tela mostraria uma linha sem nome.
    def test_alimento_so_do_diario_entra_com_nome_e_marcado_como_manual(self):
        item = _montar([(SO_DO_DIARIO, 80)])[0]
        assert item["manual"] is True
        assert item["food"]["name"] == DIARY_FOODS[SO_DO_DIARIO]["name"]

    def test_alimento_inexistente_explica_o_que_fazer(self):
        with pytest.raises(ValueError, match="Busque de novo"):
            _montar([("nao-existe-no-catalogo", 100)])

    def test_o_alvo_da_refeicao_e_o_que_ela_entrega(self):
        alimentos = _montar([("rice-white", 150), ("chicken-breast", 120), (SO_DO_DIARIO, 50)])
        refeicao = rl.refeicao_livre("  Almoço de domingo  ", alimentos, DIARY_FOODS)
        totais = rl.macros_dos_itens(alimentos, DIARY_FOODS)
        assert refeicao["name"] == "Almoço de domingo"
        assert refeicao["target_cal"] == round(totais["kcal"])
        assert refeicao["livre"] is True


class TestOsNumerosDoDia:

    # A soma do motor só conhece os alimentos dele. Um item manual contaria zero e o dia
    # pareceria menor que o prato.
    def test_item_manual_entra_na_conta(self):
        so_manual = rl.macros_dos_itens(_montar([(SO_DO_DIARIO, 100)]), DIARY_FOODS)
        base = DIARY_FOODS[SO_DO_DIARIO]
        esperado = float(base["kcal"]) * 100 / float(base.get("grams") or 100)
        assert so_manual["kcal"] == pytest.approx(esperado, abs=0.1)
        assert so_manual["kcal"] > 0

    @pytest.mark.parametrize("fid", ["chicken-breast", "rice-white", "eggs-whole", "mixed-vegetables"])
    def test_o_catalogo_do_diario_e_o_do_motor_concordam(self, fid):
        """A conta usa o catálogo do diário também para alimento do motor: os dois precisam
        dizer o mesmo, senão o total do plano mudaria só por passar por esta tela."""
        for m in ("kcal", "protein_g", "carbs_g", "fat_g"):
            assert float(DIARY_FOODS[fid][m]) == pytest.approx(float(FOOD_INDEX[fid][m])), (fid, m)

    def test_total_do_plano_e_a_soma_das_refeicoes(self):
        a = rl.refeicao_livre("A", _montar([("rice-white", 100)]), DIARY_FOODS)
        b = rl.refeicao_livre("B", _montar([("chicken-breast", 100)]), DIARY_FOODS)
        total = rl.totais_do_plano([a, b], DIARY_FOODS)
        assert total["kcal"] == pytest.approx(
            rl.macros_dos_itens(a["foods"], DIARY_FOODS)["kcal"]
            + rl.macros_dos_itens(b["foods"], DIARY_FOODS)["kcal"], abs=0.2)


class TestOQueAPessoaMontouNinguemRedimensiona:

    def test_refeicao_livre_e_livre(self):
        assert rl.e_livre({"livre": True, "foods": []})

    def test_refeicao_com_item_pesado_pela_pessoa_tambem(self):
        """A montagem por refeição grava itens manuais sem a marca de livre: o número ali
        também foi decidido por alguém."""
        assert rl.e_livre({"foods": [{"food_id": SO_DO_DIARIO, "grams": 80, "manual": True}]})

    def test_refeicao_gerada_pelo_motor_continua_ajustavel(self):
        assert not rl.e_livre({"foods": [build_food_item("rice-white", 120)]})


class TestOsRegistrosDeHojeAcompanhamARefeicao:

    def test_excluir_a_primeira_sobe_as_outras(self):
        assert rl.mapa_ao_excluir(0, 4) == {0: None, 1: 0, 2: 1, 3: 2}

    def test_excluir_a_ultima_so_apaga_o_registro_dela(self):
        assert rl.mapa_ao_excluir(3, 4) == {3: None}

    def test_inserir_no_comeco_desce_todas(self):
        assert rl.mapa_ao_inserir(0, 3) == {0: 1, 1: 2, 2: 3}

    def test_inserir_no_fim_nao_move_nada(self):
        assert rl.mapa_ao_inserir(3, 3) == {}

    @pytest.mark.parametrize("mapa,quantas", [
        (rl.mapa_ao_excluir(1, 6), 6), (rl.mapa_ao_inserir(0, 5), 5),
        (rl.mapa_ao_excluir(0, 2), 2), (rl.mapa_ao_inserir(2, 5), 5)])
    def test_nenhum_movimento_pisa_num_registro_que_ainda_nao_saiu(self, mapa, quantas):
        """Simula um registro por refeição que existe e aplica os movimentos na ordem
        proposta: nenhum pode cair numa vaga ainda ocupada."""
        ocupado = {i: f"registro-{i}" for i in range(quantas)}
        for antigo, novo in rl.ordem_dos_movimentos(mapa):
            if novo is None:
                ocupado.pop(antigo, None)
                continue
            assert novo not in ocupado or novo == antigo, f"{antigo}->{novo} sobrescreveu"
            ocupado[novo] = ocupado.pop(antigo)
        esperados = {novo: f"registro-{antigo}" for antigo, novo in mapa.items() if novo is not None}
        for novo, registro in esperados.items():
            assert ocupado[novo] == registro

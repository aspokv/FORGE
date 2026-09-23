# -*- coding: utf-8 -*-
"""Forge Food Card: ícone, macro principal, descrição e posicionamento.

O que esta suíte protege
------------------------
Uma peça que o atleta publica no Instagram com o nome do FORGE em cima. Dois riscos, e o
segundo é o que importa:

  1. **O card sai errado.** Ícone de carne num prato de arroz, macro principal trocado.
     Feio, e o atleta percebe na hora.

  2. **O card sai MENTINDO.** Um número recalculado que não bate com a refeição
     registrada, ou uma frase de alegação nutricional inventada. Isso o atleta não
     percebe, e é o que leva o nome dele junto.

Por isso os testes de macro comparam com a refeição de origem em vez de conferir
aritmética, e os de descrição cobram que a biblioteca seja FECHADA — nenhuma frase pode
prometer efeito, cura ou resultado.

Roda com `--noconftest`: nada aqui toca banco, rede ou relógio.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from food_card import (  # noqa: E402
    CARBOIDRATO, DESCRICOES, GORDURA, ICONE_GENERICO, ICONES, MAXIMO_DE_ITENS, PROTEINA,
    descricao_de, icone_de, macro_principal, montar_itens, posicionar, resumo,
)


def alimento(nome, gramas=100, kcal=0, p=0, c=0, g=0, fid=None):
    """Um alimento no formato que `food_snapshot` grava."""
    return {"food_id": fid or nome.lower().replace(" ", "-"), "name": nome,
            "grams": gramas, "kcal": kcal, "protein_g": p, "carbs_g": c, "fat_g": g}


# ── Ícones ──────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nome,esperado", [
    ("Carne moída bovina", "beef"),
    ("Patinho moído cru", "beef"),
    ("Peito de frango grelhado", "chicken"),
    ("Tilápia assada", "fish"),
    ("Ovos de codorna cozidos", "egg"),
    ("Arroz branco cozido", "rice"),
    ("Aveia em flocos", "oats"),
    ("Pão francês", "bread"),
    ("Macarrão integral", "pasta"),
    ("Moranga cozida", "pumpkin"),
    ("Whey Protein Concentrado — Growth Supplements", "whey"),
    ("Iogurte natural desnatado", "dairy"),
    ("Castanha de caju", "nuts"),
    ("Banana prata", "fruit"),
    ("Brócolis cozido no vapor", "vegetables"),
])
def test_o_icone_sai_do_nome_do_alimento(nome, esperado):
    assert icone_de(nome) == esperado


def test_batata_doce_nao_cai_no_icone_da_batata_comum():
    """A ordem da tabela é o que decide isto: "batata doce" precisa ser testada antes de
    "batata", senão o trecho mais curto captura os dois."""
    assert icone_de("Batata doce cozida") == "sweet-potato"
    assert icone_de("Batata inglesa cozida") == "potato"


@pytest.mark.parametrize("nome", ["Suplemento X", "", None, "Preparado caseiro do vô"])
def test_alimento_desconhecido_nao_impede_o_card(nome):
    """Falta de ícone não pode bloquear a criação: o alimento ainda tem nome, quantidade
    e macro, que é o que a peça precisa mostrar."""
    assert icone_de(nome) == ICONE_GENERICO


def test_todo_icone_derivado_existe_na_biblioteca():
    for nome in ("Carne", "Arroz", "Ovo", "Coisa nenhuma", "Whey", "Abacate"):
        assert icone_de(nome) in ICONES


# ── Macro principal ─────────────────────────────────────────────────────────────────

def test_o_macro_principal_compara_ENERGIA_e_nao_gramas():
    """15 g de carboidrato são 60 kcal; 10 g de gordura são 90. Comparar gramas inverteria
    a resposta e chamaria de "fonte de carboidrato" um alimento que é gordura."""
    azeitona = alimento("Azeitona preta", kcal=120, p=1, c=15, g=10)
    assert macro_principal(azeitona) == GORDURA


def test_carne_e_proteina_mesmo_quando_a_gordura_pesa_mais_em_energia():
    """A carne moída da própria referência visual: 38 g de proteína contra 22 g de
    gordura são 152 kcal contra 198. Pela conta de energia ela sairia "fonte de gordura",
    e a referência que define esta feature traz CARNE MOÍDA / PROTEÍNA em letra grande.

    Vale para todo corte gorduroso: costela, picanha, salmão.
    """
    assert macro_principal(alimento("Carne moída", 180, 350, 38, 0, 22)) == PROTEINA
    assert macro_principal(alimento("Costela bovina assada", 150, 540, 43, 0, 41)) == PROTEINA
    assert macro_principal(alimento("Salmão grelhado", 150, 310, 31, 0, 20)) == PROTEINA


def test_arroz_e_carboidrato():
    assert macro_principal(alimento("Arroz branco", 150, 195, 4, 42, 0.5)) == CARBOIDRATO


def test_o_ovo_e_proteina_mesmo_com_a_gordura_pesando_mais():
    """Um ovo tem quase tanta gordura quanto proteína e, pela conta de energia, sairia
    "gordura" — que não é como ninguém descreve um ovo numa refeição."""
    ovo = alimento("Ovos de codorna", 40, 63, 5.2, 0.2, 4.6)
    assert macro_principal(ovo) == PROTEINA


def test_alimento_sem_macro_nenhum_nao_quebra():
    assert macro_principal(alimento("Água", 300)) in (PROTEINA, CARBOIDRATO, GORDURA)


def test_o_desempate_e_estavel():
    """Dois macros empatados não podem dar respostas diferentes entre execuções."""
    empatado = alimento("Empate", 100, 80, 10, 10, 0)
    assert {macro_principal(empatado) for _ in range(20)} == {PROTEINA}


# ── Descrições ──────────────────────────────────────────────────────────────────────

def test_nenhuma_descricao_promete_efeito_cura_ou_resultado():
    """A frase vai numa peça pública com o nome do FORGE. "Fonte de proteína" é um fato
    de composição; "acelera o metabolismo" é alegação, e não sai daqui."""
    proibido = ("acelera", "queima", "emagrece", "cura", "previne", "combate", "detox",
                "desintoxica", "turbina", "potencializa", "milagr", "garante",
                "elimina", "reduz a gordura", "aumenta a imunidade")
    for chave, frase in DESCRICOES.items():
        texto = frase.lower()
        for termo in proibido:
            assert termo not in texto, f"{chave}: '{frase}' contém '{termo}'"


def test_toda_descricao_e_uma_frase_curta_e_apresentavel():
    for chave, frase in DESCRICOES.items():
        assert frase and frase[0].isupper(), chave
        assert len(frase) <= 60, f"{chave}: {len(frase)} caracteres não cabem no card"
        assert not frase.endswith("."), f"{chave}: o card não usa ponto final"


def test_alimento_sem_descricao_segura_sai_SEM_descricao():
    """Diferente de inventar uma. É a regra que impede o card de encher espaço com texto
    que ninguém verificou."""
    assert descricao_de(ICONE_GENERICO) is None


def test_toda_chave_de_descricao_derivada_existe_na_biblioteca():
    for nome in ("Carne", "Arroz", "Ovo", "Brócolis", "Castanha", "Banana", "Iogurte"):
        chave = descricao_de(icone_de(nome))
        if chave is not None:
            assert chave in DESCRICOES, f"{nome} aponta para {chave}, que não existe"


# ── Posicionamento ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_as_posicoes_sao_normalizadas(quantos):
    """0 a 1, e não pixels. É o que faz a mesma composição valer para a prévia no celular,
    a prévia no desktop e a exportação em 1080x1920."""
    for p in posicionar(quantos):
        for campo in ("cardX", "cardY", "anchorX", "anchorY"):
            assert 0.0 <= p[campo] <= 1.0, f"{campo}={p[campo]}"


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_nenhum_card_nasce_em_cima_de_outro(quantos):
    cantos = [(p["cardX"], p["cardY"]) for p in posicionar(quantos)]
    assert len(set(cantos)) == quantos


def test_nenhum_card_nasce_em_cima_do_logo_nem_do_resumo():
    """O logo fica no topo esquerdo e o resumo na base. Um card nascendo ali cobriria a
    identidade ou os totais, que são as duas coisas que a peça sempre mostra."""
    for quantos in (1, 2, 3, 4):
        for p in posicionar(quantos):
            # O logo ocupa aproximadamente os 14% de cima.
            assert p["cardY"] >= 0.14, f"card em cima do logo: {p}"
            # O resumo ocupa aproximadamente os 12% de baixo.
            assert p["cardY"] <= 0.82, f"card em cima do resumo: {p}"


def test_com_dois_alimentos_os_cards_ficam_em_cantos_opostos():
    """Deixa a foto respirar no meio, que é onde está o prato."""
    a, b = posicionar(2)
    assert a["cardX"] < 0.5 < b["cardX"]
    assert a["cardY"] < b["cardY"]


# ── Montagem a partir de uma refeição registrada ────────────────────────────────────

REFEICAO = [
    alimento("Carne moída", 180, 350, 38, 0, 22),
    alimento("Moranga cozida", 150, 60, 1.5, 15, 0.3),
    alimento("Ovos de codorna", 40, 63, 5.2, 0.2, 4.6),
    alimento("Azeite de oliva", 5, 45, 0, 0, 5),
    alimento("Arroz branco", 100, 130, 2.7, 28, 0.3),
]


def test_os_macros_do_card_sao_OS_MESMOS_da_refeicao_registrada():
    """O teste que importa. Recalcular aqui criaria dois totais para a mesma comida, e o
    atleta veria um número no diário e outro na peça que ele publica."""
    itens = montar_itens(REFEICAO)
    for item, origem in zip(itens, REFEICAO):
        assert item["calories"] == origem["kcal"]
        assert item["protein"] == origem["protein_g"]
        assert item["carbs"] == origem["carbs_g"]
        assert item["fat"] == origem["fat_g"]
        assert item["quantity"] == origem["grams"]


def test_a_montagem_para_em_quatro_alimentos():
    assert len(montar_itens(REFEICAO)) == MAXIMO_DE_ITENS


def test_todo_item_montado_tem_o_que_o_card_desenha():
    for item in montar_itens(REFEICAO):
        for campo in ("foodId", "name", "quantity", "unit", "calories", "protein",
                      "carbs", "fat", "iconKey", "primaryMacro",
                      "cardX", "cardY", "anchorX", "anchorY"):
            assert campo in item, f"falta {campo}"
        assert item["iconKey"] in ICONES
        assert item["primaryMacro"] in (PROTEINA, CARBOIDRATO, GORDURA)


def test_refeicao_vazia_nao_quebra():
    assert montar_itens([]) == []


def test_o_resumo_usa_o_total_da_refeicao_COMPLETA():
    """Destacar quatro alimentos não pode fazer o rodapé mentir sobre o que a pessoa
    comeu. A especificação é explícita sobre isto."""
    totais = {"kcal": 648, "protein_g": 47.4, "carbs_g": 43.2, "fat_g": 32.2}
    assert resumo(totais) == {"protein": 47, "carbs": 43, "fat": 32, "calories": 648}


def test_o_resumo_sobrevive_a_total_faltando():
    assert resumo({}) == {"protein": 0, "carbs": 0, "fat": 0, "calories": 0}


def test_as_linhas_dos_cards_de_baixo_nao_se_cruzam():
    """Medido numa peça exportada: com os âncoras do lado oposto ao card, as duas linhas
    de baixo se cruzavam no meio da arte. Duas linhas cruzadas num infográfico de três
    elementos é o tipo de coisa que denuncia que ninguém olhou o resultado.

    O âncora vai para o miolo da foto, mas fica do MESMO lado do card.
    """
    esquerda, direita = posicionar(4)[2], posicionar(4)[3]
    assert esquerda["cardX"] < direita["cardX"], "os cantos trocaram de lado"
    # Cada um aponta para dentro, sem passar do outro.
    assert esquerda["anchorX"] < direita["anchorX"], (
        f"as linhas se cruzam: {esquerda['anchorX']} >= {direita['anchorX']}")


def test_todo_ancora_fica_do_mesmo_lado_do_seu_card():
    for quantos in (1, 2, 3, 4):
        for p in posicionar(quantos):
            esquerdo = p["cardX"] < 0.5
            assert (p["anchorX"] < 0.5) == esquerdo or abs(p["anchorX"] - 0.5) < 0.12, (
                f"âncora atravessou para o outro lado: {p}")


def test_todo_ancora_aponta_para_o_miolo_da_foto():
    """Longe o suficiente do próprio card para a linha existir, e dentro da área onde a
    comida costuma estar numa foto de prato."""
    for quantos in (1, 2, 3, 4):
        for p in posicionar(quantos):
            distancia = ((p["anchorX"] - p["cardX"]) ** 2
                         + (p["anchorY"] - p["cardY"]) ** 2) ** 0.5
            assert distancia > 0.15, f"linha curta demais: {p}"
            assert 0.3 < p["anchorY"] < 0.7, f"âncora fora do miolo: {p}"

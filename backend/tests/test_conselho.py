# -*- coding: utf-8 -*-
"""O Conselho: a semana medida vira UMA decisao.

O que esta suite protege nao e a aritmetica, que e facil. E a ORDEM das perguntas, que e o
produto inteiro:

    da para ler?  ->  o plano foi seguido?  ->  o treino esta de pe?  ->  so entao, comida

Um aplicativo que pula direto para a comida corta a caloria de quem nao seguiu o plano e
de quem esta com o treino caindo, que sao exatamente as duas pessoas para quem cortar
comida e a pior coisa a fazer. Os testes com nome `nao_corta_comida_*` sao os que impedem
o motor de virar isso.

Roda com `--noconftest`: nada aqui toca banco, rede ou relogio.
"""
from datetime import date as CalendarDate, timedelta

import pytest

from conselho import (
    ACERTOU, AJUSTAR_ADERENCIA, AJUSTAR_CALORIA, ALAVANCAS, DIAS_MINIMOS_DE_REGISTRO,
    ERROU, MANTER, NAO_VERIFICAVEL, PISO_KCAL, PROTEGER_O_TREINO, SEGURAR_A_PERDA,
    SEM_LEITURA, TETO_DO_PASSO_KCAL, aderencia_alimentar, conferir_previsao, decidir,
    falhas_recorrentes, observar, passo_calorico, prontidao_por_dia_da_semana, retrospecto,
    tendencia_de_peso, queda_de_volume, volume_por_semana,
)

HOJE = CalendarDate(2026, 3, 15)
MUSCULOS = {"squat": "quads", "bench": "chest", "row": "back", "curl": "biceps"}


def dia(n):
    """`n` dias ANTES de hoje, em texto, que e como tudo chega do banco."""
    return (HOJE - timedelta(days=n)).isoformat()


def pesagens(peso_inicial, kg_por_semana, dias=21, passo=3):
    """Uma pesagem a cada `passo` dias, numa reta perfeita."""
    saida = []
    for n in range(dias, -1, -passo):
        avancado = (dias - n) / 7.0
        saida.append({"date": dia(n), "weight_kg": round(peso_inicial + kg_por_semana * avancado, 2)})
    return saida


def consumo(dias_registrados, kcal, janela=7):
    return [{"date": dia(n), "kcal": kcal} for n in range(janela - 1, janela - 1 - dias_registrados, -1)]


EXERCICIOS = ("squat", "bench", "row", "curl")


def treino(volumes, carga=100.0, reps=8):
    """Uma semana por entrada, da mais ANTIGA para a mais recente.

    Cada semana cai num UNICO dia, sete dias depois da anterior. Espalhar as series por
    varios dias parecia mais realista e estragava os dois agrupamentos de uma vez: dias
    vizinhos caem em semanas ISO diferentes quando cruzam um domingo, e o mesmo exercicio
    repetido em varios dias da semana quebra a cadeia de sessoes que `falhas_recorrentes`
    percorre. Um dia por semana mantem o dado sintetico dizendo exatamente o que ele
    pretende dizer.
    """
    saida = []
    n = len(volumes)
    for i, total in enumerate(volumes):
        data = dia(7 * (n - 1 - i))
        for j in range(total):
            saida.append({"exercise_id": EXERCICIOS[j % 4], "created_at": data,
                          "weight": carga, "reps": reps})
    return saida


def series_estaveis(semanas=4, por_semana=20, carga=100.0, reps=8):
    """Treino constante: mesma carga, mesmas repeticoes, mesmo volume toda semana."""
    return treino([por_semana] * semanas, carga=carga, reps=reps)


def agachamento_caindo(reps_por_semana, carga=140.0):
    """O mesmo exercicio, uma sessao por semana, perdendo repeticao com a carga parada.

    Usa carga MAIOR que a do treino de fundo de proposito: `falhas_recorrentes` compara a
    melhor serie de cada sessao, entao estas series e que mandam na leitura do agachamento
    sem eu precisar remover o exercicio do treino de fundo.
    """
    n = len(reps_por_semana)
    return [{"exercise_id": "squat", "created_at": dia(7 * (n - 1 - i)),
             "weight": carga, "reps": r} for i, r in enumerate(reps_por_semana)]


def checkins(por_dia_da_semana):
    """`por_dia_da_semana`: {weekday -> energia}. Estresse e dor ficam fixos."""
    saida = []
    for n in range(28):
        data = HOJE - timedelta(days=n)
        energia = por_dia_da_semana.get(data.weekday())
        if energia is None:
            continue
        saida.append({"local_date": data.isoformat(), "energy": energia,
                      "stress": 2, "soreness": 2})
    return saida


def estado(objetivo="fat_loss", dias_registrados=7, kcal=2000, alvo=2000,
           peso_inicial=90.0, kg_por_semana=-0.45, series=None, checks=None):
    return observar(
        objetivo=objetivo,
        dias_de_consumo=consumo(dias_registrados, kcal),
        janela_dias=7, alvo_kcal=alvo,
        pesagens=pesagens(peso_inicial, kg_por_semana),
        series=series if series is not None else series_estaveis(),
        musculo_por_exercicio=MUSCULOS,
        checkins=checks if checks is not None else [])


# ── A leitura do peso ───────────────────────────────────────────────────────────────

def test_a_inclinacao_do_peso_e_lida_por_reta_e_nao_por_diferenca():
    leitura = tendencia_de_peso(pesagens(90.0, -0.5))
    assert leitura["suficiente"] is True
    assert leitura["kg_por_semana"] == pytest.approx(-0.5, abs=0.02)


def test_um_dia_de_sal_no_fim_nao_vira_uma_semana_de_ganho():
    """O caso que motiva a reta: a ultima pesagem e a pior fonte de verdade que existe."""
    limpo = pesagens(90.0, -0.5)
    sujo = [dict(p) for p in limpo]
    sujo[-1]["weight_kg"] += 1.2  # agua de um dia

    reta = tendencia_de_peso(sujo)["kg_por_semana"]
    diferenca_ingenua = (sujo[-1]["weight_kg"] - sujo[-2]["weight_kg"]) / 3 * 7

    assert diferenca_ingenua > 0            # a conta ingenua acusa GANHO
    assert reta < 0                         # a reta continua vendo a perda
    assert reta == pytest.approx(-0.35, abs=0.15)


def test_duas_pesagens_no_mesmo_dia_contam_uma():
    com_duplicata = pesagens(90.0, -0.5) + [{"date": dia(0), "weight_kg": 999.0}]
    assert tendencia_de_peso(com_duplicata)["peso_atual"] == 999.0
    assert tendencia_de_peso(com_duplicata)["pesagens"] == tendencia_de_peso(pesagens(90.0, -0.5))["pesagens"]


@pytest.mark.parametrize("registros,motivo", [
    ([], "sem pesagem"),
    ([{"date": dia(2), "weight_kg": 90}, {"date": dia(1), "weight_kg": 90}], "pelo menos"),
    ([{"date": dia(2), "weight_kg": 90}, {"date": dia(1), "weight_kg": 90},
      {"date": dia(0), "weight_kg": 90}], "cobrem"),
])
def test_peso_sem_amostra_diz_que_nao_sabe(registros, motivo):
    leitura = tendencia_de_peso(registros)
    assert leitura["suficiente"] is False
    assert motivo in leitura["motivo"]


def test_peso_ignora_lixo_sem_quebrar():
    sujo = pesagens(90.0, -0.5) + [{"date": None, "weight_kg": 80},
                                   {"date": dia(1), "weight_kg": "oitenta"},
                                   {"date": "ontem", "weight_kg": 80}]
    assert tendencia_de_peso(sujo)["suficiente"] is True


# ── A leitura da comida ─────────────────────────────────────────────────────────────

def test_dia_sem_registro_nao_e_dia_de_jejum():
    """Tres dias perfeitos nao sao uma semana perfeita: sao tres dias e quatro pontos cegos."""
    leitura = aderencia_alimentar(consumo(3, 2000), 7, 2000)
    assert leitura["kcal_media"] == 2000          # o que foi registrado bateu a meta
    assert leitura["desvio"] == 0.0
    assert leitura["registro"] == pytest.approx(3 / 7, abs=0.001)
    assert leitura["suficiente"] is False         # e mesmo assim nao da para ler a semana
    assert str(DIAS_MINIMOS_DE_REGISTRO) in leitura["motivo"]


def test_a_media_nao_e_diluida_pelos_dias_que_faltam():
    """Se os dias ausentes entrassem como zero, a media cairia e o motor cortaria comida
    de quem so esqueceu de anotar."""
    leitura = aderencia_alimentar(consumo(4, 2000), 7, 2000)
    assert leitura["kcal_media"] == 2000
    assert leitura["desvio"] == 0.0


def test_sem_meta_calorica_nao_existe_desvio():
    leitura = aderencia_alimentar(consumo(7, 2000), 7, None)
    assert leitura["desvio"] is None
    assert leitura["suficiente"] is False


# ── A leitura do treino ─────────────────────────────────────────────────────────────

def test_volume_e_agrupado_por_semana_e_por_musculo():
    semanas = volume_por_semana(series_estaveis(semanas=3, por_semana=20), MUSCULOS)
    assert len(semanas) == 3
    qualquer = semanas[sorted(semanas)[-1]]
    assert qualquer["total"] == 20
    assert qualquer["series"]["quads"] == 5
    assert qualquer["tonelagem"] == 20 * 100 * 8


def test_queda_de_volume_compara_com_a_base_e_nao_com_a_semana_anterior():
    leitura = queda_de_volume(volume_por_semana(treino([20, 20, 20, 10]), MUSCULOS))
    assert leitura["suficiente"] is True
    assert leitura["variacao"] < -0.15


def test_uma_semana_so_nao_da_leitura_de_volume():
    leitura = queda_de_volume(volume_por_semana(series_estaveis(semanas=1), MUSCULOS))
    assert leitura["suficiente"] is False


def test_perder_repeticao_com_a_mesma_carga_e_falha():
    series = [
        {"exercise_id": "squat", "created_at": dia(21), "weight": 100, "reps": 10},
        {"exercise_id": "squat", "created_at": dia(14), "weight": 100, "reps": 9},
        {"exercise_id": "squat", "created_at": dia(7), "weight": 100, "reps": 8},
    ]
    achados = falhas_recorrentes(series)
    assert achados[0]["exercise_id"] == "squat"
    assert achados[0]["sessoes_seguidas"] == 2
    assert achados[0]["reps_antes"] == 10
    assert achados[0]["reps"] == 8


def test_perder_repeticao_por_ter_SUBIDO_a_carga_nao_e_falha():
    """Fazer 8 com 110 depois de 10 com 100 e progressao, e o motor nao pode chamar isso
    de queda. Se chamasse, ele puniria exatamente quem esta evoluindo."""
    series = [
        {"exercise_id": "squat", "created_at": dia(21), "weight": 100, "reps": 10},
        {"exercise_id": "squat", "created_at": dia(14), "weight": 110, "reps": 8},
        {"exercise_id": "squat", "created_at": dia(7), "weight": 120, "reps": 6},
    ]
    assert falhas_recorrentes(series) == []


def test_uma_sessao_ruim_isolada_nao_vira_assunto():
    series = [
        {"exercise_id": "squat", "created_at": dia(21), "weight": 100, "reps": 10},
        {"exercise_id": "squat", "created_at": dia(14), "weight": 100, "reps": 8},
        {"exercise_id": "squat", "created_at": dia(7), "weight": 100, "reps": 10},
    ]
    assert falhas_recorrentes(series) == []


# ── A leitura da prontidao ──────────────────────────────────────────────────────────

def test_a_prontidao_separa_o_pior_dia_da_semana():
    leitura = prontidao_por_dia_da_semana(checkins({0: 5, 1: 2, 3: 5}))
    assert leitura["suficiente"] is True
    assert leitura["pior_dia"] == "terça"
    assert leitura["pior_pontuacao"] < leitura["melhor_pontuacao"]


def test_um_check_in_solto_num_dia_nao_define_aquele_dia():
    poucos = [{"local_date": dia(1), "energy": 1, "stress": 5, "soreness": 5}]
    assert prontidao_por_dia_da_semana(poucos)["suficiente"] is False


def test_a_prontidao_do_conselho_usa_a_formula_do_motor_de_treino():
    """Duas formulas de prontidao no mesmo aplicativo seriam duas verdades sobre o mesmo
    atleta. Este teste quebra se alguem mexer numa das duas sem mexer na outra."""
    from engine import classificar_recuperacao

    _, esperado = classificar_recuperacao(3, 2, 2)
    leitura = prontidao_por_dia_da_semana(checkins({1: 3}))
    assert leitura["por_dia"]["terça"] == pytest.approx(esperado, abs=0.001)


# ── A arbitragem: a ordem das perguntas ─────────────────────────────────────────────

def test_toda_decisao_devolve_exatamente_uma_alavanca():
    """A trava numero um: mexer em comida e treino na mesma semana destroi a leitura da
    semana seguinte, porque todo resultado passa a ter duas explicacoes."""
    casos = [
        estado(dias_registrados=0),
        estado(dias_registrados=2),
        estado(kcal=2600),
        estado(series=treino([20, 20, 20, 8])),
        estado(kg_por_semana=-1.6),
        estado(kg_por_semana=0.0),
        estado(),
    ]
    for caso in casos:
        decisao = decidir(caso)
        assert decisao["alavanca"] in ALAVANCAS
        assert isinstance(decisao["motivo"], str) and decisao["motivo"]


def test_sem_registro_nenhum_o_motor_diz_que_nao_sabe():
    decisao = decidir(estado(dias_registrados=0))
    assert decisao["alavanca"] == SEM_LEITURA
    assert decisao["mudanca"] is None


def test_nao_corta_comida_de_quem_nao_registrou_a_semana():
    """O erro classico: a pessoa registrou 2 de 7 dias, o peso nao andou, e o aplicativo
    corta caloria. O plano nunca chegou a ser testado."""
    decisao = decidir(estado(dias_registrados=2, kg_por_semana=0.0))
    assert decisao["alavanca"] == AJUSTAR_ADERENCIA
    assert decisao["mudanca"] is None


def test_nao_corta_comida_de_quem_comeu_fora_do_alvo():
    """Comeu 30% acima do alvo e nao emagreceu. Mudar a meta so mudaria o numero de onde a
    pessoa escorrega."""
    decisao = decidir(estado(kcal=2600, alvo=2000, kg_por_semana=0.0))
    assert decisao["alavanca"] == AJUSTAR_ADERENCIA
    assert decisao["mudanca"] is None


def test_nao_corta_comida_com_o_treino_caindo():
    """A frase que separa o FORGE de um contador de calorias."""
    decisao = decidir(estado(kg_por_semana=0.0, series=treino([20, 20, 20, 8])))
    assert decisao["alavanca"] == PROTEGER_O_TREINO
    assert decisao["mudanca"]["tipo"] != "kcal"


def test_falha_repetida_mais_dia_ruim_vira_mudanca_de_agenda():
    """A mudanca mais barata que existe, e a que ninguem faz sozinho."""
    series = series_estaveis() + agachamento_caindo([10, 10, 8, 6])
    decisao = decidir(estado(kg_por_semana=0.0, series=series,
                             checks=checkins({0: 5, 1: 2, 3: 5})))
    assert decisao["alavanca"] == PROTEGER_O_TREINO
    assert decisao["mudanca"]["tipo"] == "agenda"
    assert decisao["mudanca"]["de"] == "terça"
    assert "terça" in decisao["motivo"]


def test_perder_rapido_demais_devolve_caloria_em_vez_de_tirar():
    decisao = decidir(estado(peso_inicial=90.0, kg_por_semana=-1.6))
    assert decisao["alavanca"] == SEGURAR_A_PERDA
    assert decisao["mudanca"]["tipo"] == "kcal"
    assert decisao["mudanca"]["delta"] > 0


def test_com_tudo_em_ordem_e_o_peso_travado_o_corte_finalmente_acontece():
    decisao = decidir(estado(kg_por_semana=0.0))
    assert decisao["alavanca"] == AJUSTAR_CALORIA
    assert decisao["mudanca"]["tipo"] == "kcal"
    assert decisao["mudanca"]["delta"] < 0
    assert decisao["previsao"]["tipo"] == "ritmo_de_peso"


def test_ganhando_rapido_demais_o_motor_CORTA_mesmo_estando_em_bulking():
    """Regressao do erro real: escolher o sentido pelo OBJETIVO mandava SOMAR caloria para
    quem ja subia rapido demais, que e a receita de transformar bulking em engorda."""
    decisao = decidir(estado(objetivo="muscle_gain", peso_inicial=80.0, kg_por_semana=1.2))
    assert decisao["alavanca"] == AJUSTAR_CALORIA
    assert decisao["mudanca"]["delta"] < 0


def test_nao_ganhando_em_bulking_o_motor_soma():
    decisao = decidir(estado(objetivo="muscle_gain", peso_inicial=80.0, kg_por_semana=0.0))
    assert decisao["alavanca"] == AJUSTAR_CALORIA
    assert decisao["mudanca"]["delta"] > 0


def test_manutencao_derivando_para_cima_e_cortada():
    decisao = decidir(estado(objetivo="maintenance", peso_inicial=80.0, kg_por_semana=0.5))
    assert decisao["alavanca"] == AJUSTAR_CALORIA
    assert decisao["mudanca"]["delta"] < 0


def test_quando_esta_funcionando_o_motor_nao_inventa_mudanca():
    """A coisa mais dificil que um motor automatico faz e nao mexer."""
    decisao = decidir(estado(kg_por_semana=-0.45))
    assert decisao["alavanca"] == MANTER
    assert decisao["mudanca"] is None


def test_comida_e_treino_lidos_mas_sem_balanca_nao_viram_corte():
    leitura = estado()
    leitura["peso"] = {"suficiente": False, "motivo": "poucas pesagens"}
    decisao = decidir(leitura)
    assert decisao["alavanca"] == SEM_LEITURA
    assert decisao["mudanca"] is None


# ── As travas do ajuste calorico ────────────────────────────────────────────────────

def test_o_passo_calorico_tem_teto_absoluto():
    assert abs(passo_calorico(4000, -1)) == TETO_DO_PASSO_KCAL
    assert abs(passo_calorico(1500, -1)) == 120


def test_o_ajuste_nunca_leva_a_meta_abaixo_do_piso():
    decisao = decidir(estado(kcal=1250, alvo=1250, kg_por_semana=0.0))
    if decisao["mudanca"]:
        assert decisao["mudanca"]["para"] >= PISO_KCAL


def test_a_mudanca_calorica_declara_o_que_nao_toca():
    decisao = decidir(estado(kg_por_semana=0.0))
    assert "proteína" in decisao["mudanca"]["trava"]


# ── O placar: o motor responde pela propria previsao ────────────────────────────────

def test_a_previsao_de_ritmo_pode_dar_ERRADO():
    """Um conselho que nunca pode estar errado nao e um conselho."""
    previsao = decidir(estado(kg_por_semana=0.0))["previsao"]
    semana_seguinte = estado(kg_por_semana=0.0)
    assert conferir_previsao(previsao, semana_seguinte)["resultado"] == ERROU


def test_a_previsao_de_ritmo_acerta_quando_o_peso_anda():
    previsao = decidir(estado(kg_por_semana=0.0))["previsao"]
    semana_seguinte = estado(kg_por_semana=-0.45)
    assert conferir_previsao(previsao, semana_seguinte)["resultado"] == ACERTOU


def test_quem_parou_de_registrar_nao_conta_como_acerto_nem_como_erro():
    """Contar isso como acerto premiaria o silencio; como erro, puniria o motor por uma
    coisa que nao foi ele que fez."""
    previsao = {"tipo": "ritmo_de_peso", "minimo": -0.01, "maximo": -0.003}
    mudo = estado()
    mudo["peso"] = {"suficiente": False}
    assert conferir_previsao(previsao, mudo)["resultado"] == NAO_VERIFICAVEL


def test_a_previsao_de_registro_e_conferida_pelo_numero_de_dias():
    previsao = {"tipo": "registros_minimos", "valor": 6}
    assert conferir_previsao(previsao, estado(dias_registrados=7))["resultado"] == ACERTOU
    assert conferir_previsao(previsao, estado(dias_registrados=4))["resultado"] == ERROU


def test_a_previsao_de_exercicio_e_conferida_pela_falha_ter_sumido():
    previsao = {"tipo": "exercicio_fechado", "exercise_id": "squat", "reps": 10}
    ainda_caindo = estado(series=series_estaveis() + agachamento_caindo([10, 10, 8, 6]))
    assert conferir_previsao(previsao, ainda_caindo)["resultado"] == ERROU
    assert conferir_previsao(previsao, estado())["resultado"] == ACERTOU


def test_sem_previsao_anterior_nao_ha_placar():
    assert conferir_previsao(None, estado())["resultado"] == NAO_VERIFICAVEL


def test_o_retrospecto_ignora_o_que_nao_deu_para_julgar():
    placar = retrospecto([{"resultado": ACERTOU}, {"resultado": ACERTOU},
                          {"resultado": ERROU}, {"resultado": NAO_VERIFICAVEL}])
    assert placar["julgadas"] == 3
    assert placar["taxa"] == pytest.approx(2 / 3, abs=0.001)
    assert placar["nao_verificaveis"] == 1


def test_o_retrospecto_de_quem_nunca_foi_julgado_nao_inventa_taxa():
    assert retrospecto([])["taxa"] is None


# ── O portugues que o atleta le ─────────────────────────────────────────────────────

def test_nenhuma_frase_gerada_traz_numero_com_ponto_decimal():
    """"0.28 kg" no meio de uma frase em portugues denuncia texto montado por maquina.

    Isto so apareceu quando rodei o motor contra dado de verdade, e por isso a varredura
    cobre TODAS as alavancas: o defeito estava em duas frases e nao nas outras quatro.
    """
    import re
    ponto_decimal = re.compile(r"\d\.\d")
    casos = [
        estado(dias_registrados=0), estado(dias_registrados=2), estado(kcal=2600),
        estado(series=treino([20, 20, 20, 8])), estado(kg_por_semana=-1.6),
        estado(kg_por_semana=0.0), estado(),
        estado(objetivo="muscle_gain", peso_inicial=80.0, kg_por_semana=0.0),
        estado(objetivo="maintenance", peso_inicial=80.0, kg_por_semana=0.5),
    ]
    for caso in casos:
        decisao = decidir(caso)
        textos = [decisao["titulo"], decisao["motivo"]]
        if decisao.get("previsao"):
            textos.append(decisao["previsao"].get("frase") or "")
        for texto in textos:
            assert not ponto_decimal.search(texto), f"ponto decimal em: {texto!r}"


def test_quem_comeu_na_meta_le_que_comeu_na_meta():
    """"comeu a 0% da meta" nao quer dizer nada. Zero por cento de DESVIO e estar na meta."""
    decisao = decidir(estado(kcal=2000, alvo=2000, kg_por_semana=0.0))
    assert "dentro da meta" in decisao["motivo"]
    assert "0%" not in decisao["motivo"]


def test_quem_comeu_fora_da_meta_le_para_que_lado():
    leitura = estado(kcal=2200, alvo=2000, kg_por_semana=0.0)
    # 10% exatos ainda e aderencia; 2200 contra 2000 sao 10%, entao o desvio passa reto.
    # Aqui interessa a frase do ramo calorico, que so acontece com desvio pequeno.
    decisao = decidir(estado(kcal=2060, alvo=2000, kg_por_semana=0.0))
    assert "3% acima da meta" in decisao["motivo"]


def test_o_formatador_escreve_numero_em_portugues():
    from conselho import numero
    assert numero(0.28) == "0,28"
    assert numero(-0.45, 2, sinal=True) == "-0,45"
    assert numero(0.45, 2, sinal=True) == "+0,45"


def test_a_frase_usa_o_NOME_do_exercicio_e_nao_o_identificador():
    """"Voce perdeu repeticao em squat" e identificador vazando para a tela."""
    leitura = estado(kg_por_semana=0.0,
                     series=series_estaveis() + agachamento_caindo([10, 10, 8, 6]))
    leitura["nomes"] = {"squat": "Agachamento livre"}
    decisao = decidir(leitura)
    assert "Agachamento livre" in decisao["motivo"]
    assert "squat" not in decisao["motivo"]
    # A previsao continua guardando o IDENTIFICADOR, que e o que da para conferir depois.
    assert decisao["previsao"]["exercise_id"] == "squat"


def test_sem_nome_conhecido_a_frase_cai_no_identificador_em_vez_de_quebrar():
    leitura = estado(kg_por_semana=0.0,
                     series=series_estaveis() + agachamento_caindo([10, 10, 8, 6]))
    decisao = decidir(leitura)
    assert "squat" in decisao["motivo"]


def test_nenhuma_frase_gerada_sai_sem_acento():
    """A mesma varredura do ponto decimal, para o portugues.

    "o corte e seu" nao e portugues, e o defeito e invisivel em teste que so olha a
    alavanca. Estas sao as formas sem acento que apareceram de verdade no texto.
    """
    sem_acento = ["voce", "Voce", "nao ", "Nao ", "repeticoes", "sessoes", "prontidao",
                  "musculo", "execucao", "balanca", "tendencia", "ninguem", "entao",
                  "exercicio", "proteina", "dificil", "mudanca", "calorica"]
    casos = [
        estado(dias_registrados=0), estado(dias_registrados=2), estado(kcal=2600),
        estado(series=treino([20, 20, 20, 8])), estado(kg_por_semana=-1.6),
        estado(kg_por_semana=0.0), estado(),
        estado(kg_por_semana=0.0, series=series_estaveis() + agachamento_caindo([10, 10, 8, 6]),
               checks=checkins({0: 5, 1: 2, 3: 5})),
        estado(kg_por_semana=0.0, series=series_estaveis() + agachamento_caindo([10, 10, 8, 6])),
    ]
    for caso in casos:
        decisao = decidir(caso)
        textos = [decisao["titulo"], decisao["motivo"]]
        if decisao.get("previsao"):
            textos.append(decisao["previsao"].get("frase") or "")
        if decisao.get("mudanca"):
            textos.append(decisao["mudanca"].get("trava") or "")
        for texto in textos:
            for forma in sem_acento:
                assert forma not in texto, f"{forma!r} sem acento em: {texto!r}"


# ── O placar do metodo ──────────────────────────────────────────────────────────────

def _semana(alavanca="caloria", objetivo="fat_loss", resultado=None, visivel=True,
            aplicada=None):
    return {"decisao": {"alavanca": alavanca, "objetivo": objetivo},
            "conferido": {"resultado": resultado} if resultado else None,
            "visivel": visivel,
            "aplicada": {"status": aplicada} if aplicada else None}


def test_com_amostra_pequena_o_placar_diz_que_ainda_nao_sabe():
    """Uma taxa tirada de duas semanas convenceria alguem a mudar uma regra com base em
    ruido. O numero aparece, mas acompanhado de "nao da para concluir"."""
    placar = retrospecto([])  # nao usado aqui, so garante o import vivo
    assert placar is not None

    from conselho import placar_do_metodo, MINIMO_PARA_CONCLUIR
    p = placar_do_metodo([_semana(resultado=ACERTOU), _semana(resultado=ACERTOU)])
    assert p["taxa"] == 1.0
    assert p["amostra_suficiente"] is False
    assert p["minimo_para_concluir"] == MINIMO_PARA_CONCLUIR


def test_com_amostra_suficiente_o_placar_conclui():
    from conselho import placar_do_metodo, MINIMO_PARA_CONCLUIR
    semanas = ([_semana(resultado=ACERTOU)] * 24) + ([_semana(resultado=ERROU)] * 8)
    p = placar_do_metodo(semanas)
    assert p["julgadas"] == 32 >= MINIMO_PARA_CONCLUIR
    assert p["amostra_suficiente"] is True
    assert p["taxa"] == 0.75


def test_a_semana_sem_veredito_conta_mas_nao_julga():
    """Quem parou de registrar nao vira acerto nem erro: premiar o silencio seria pior."""
    from conselho import placar_do_metodo
    p = placar_do_metodo([_semana(resultado=ACERTOU), _semana(resultado=None)])
    assert p["semanas"] == 2
    assert p["julgadas"] == 1


def test_o_placar_separa_quem_VIU_de_quem_nunca_viu():
    """Quem nunca viu o conselho nunca pode te-lo aplicado: esse grupo mede o que
    acontece sem intervencao, e e a unica comparacao honesta que existe."""
    from conselho import placar_do_metodo
    p = placar_do_metodo([_semana(visivel=True), _semana(visivel=False),
                          _semana(visivel=False)])
    assert p["vistas"] == 1
    assert p["nao_vistas"] == 2


def test_o_placar_separa_por_alavanca_e_por_objetivo():
    """Uma taxa unica esconde o que interessa: a regra que erra pode ser uma so."""
    from conselho import placar_do_metodo
    p = placar_do_metodo([
        _semana(alavanca=AJUSTAR_CALORIA, objetivo="fat_loss", resultado=ACERTOU),
        _semana(alavanca=AJUSTAR_CALORIA, objetivo="muscle_gain", resultado=ERROU),
        _semana(alavanca=MANTER, objetivo="fat_loss", resultado=ACERTOU),
    ])
    assert p["por_alavanca"][AJUSTAR_CALORIA]["semanas"] == 2
    assert p["por_alavanca"][MANTER]["taxa"] == 1.0
    assert p["por_objetivo"]["muscle_gain"]["taxa"] == 0.0


def test_o_placar_conta_quantas_foram_aplicadas():
    from conselho import placar_do_metodo
    p = placar_do_metodo([_semana(aplicada="aplicada"), _semana(aplicada="recusada"),
                          _semana()])
    assert p["aplicadas"] == 1


def test_o_placar_de_base_vazia_nao_inventa_taxa():
    from conselho import placar_do_metodo
    p = placar_do_metodo([])
    assert p["semanas"] == 0
    assert p["taxa"] is None
    assert p["amostra_suficiente"] is False

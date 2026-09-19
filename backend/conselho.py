# -*- coding: utf-8 -*-
"""FORGE — o Conselho: o resultado medido decide a semana seguinte.

Por que existe
--------------
O FORGE tinha dois motores muito bons que nunca se falavam, e isso da para provar sem
opiniao:

  - `nutrition_periodization.py` cortava caloria por CALENDARIO. A progressao era linear,
    desenhada no inicio, e nunca perguntava o que tinha acontecido.
  - `grep set_logs|workout_log` em `nutrition_engine.py`, `nutrition_periodization.py` e
    `nutrition_routes.py` dava ZERO. A alimentacao nao lia uma linha de treino, e o treino
    nao sabia que a pessoa estava em deficit.
  - `nutrition_weight_logs` era lido em um lugar util, `server.py`, para montar o grafico
    da tela de Evolucao. O dado mais caro que o aplicativo coleta, o resultado real, so
    virava desenho.

A decisao que define um treinador de verdade nao e nenhuma das duas sozinhas: e a
ARBITRAGEM entre elas. Travou o peso, corta comida, corta volume ou bota cardio? Quem so
enxerga a comida sempre responde "corta comida". Quem so enxerga o treino nunca responde.
Este modulo e o lugar onde as duas leituras se encontram e UMA decisao sai.

A regra
-------
No mesmo espirito de `MACROS AJUSTAM A REFEICAO, MACROS NAO INVENTAM A REFEICAO`:

    O RESULTADO AJUSTA O PLANO. O RESULTADO NAO INVENTA O PLANO.

Em codigo isso vira quatro travas, e elas sao o motivo de este arquivo ser burro de
proposito:

  1. UMA alavanca por semana. `decidir` devolve uma, nunca duas. Mexer em comida e treino
     na mesma semana destroi a leitura da semana seguinte: qualquer resultado passa a ter
     duas explicacoes e o motor nunca mais aprende nada.
  2. Sem leitura, sem palpite. Semana com pouco registro devolve `SEM_LEITURA` dizendo o
     que falta. Um corte automatico errado custa mais confianca do que dez acertos
     constroem.
  3. Dia sem registro nao e dia de jejum. A mesma disciplina que `/adherence-week` ja tem:
     quem esqueceu de anotar nao comeu zero, e tratar os dois como iguais faria o motor
     acusar um deficit que nunca existiu e cortar comida em cima de uma ficcao.
  4. Toda decisao carrega uma PREVISAO falsificavel, e na semana seguinte o motor e
     cobrado por ela. Um conselho que nunca pode estar errado nao e um conselho.

Nada aqui toca banco, rede ou relogio do sistema por conta propria: entra dado, sai
decisao. E por isso que a suite roda com `--noconftest` e cobre os casos de borda que
seriam caros de montar contra um Mongo de verdade.
"""
from __future__ import annotations

from datetime import date as CalendarDate, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cardio import cardio_step, frase_de_cardio
from engine import classificar_recuperacao

# ── Alavancas ───────────────────────────────────────────────────────────────────────
#
# A ORDEM destas constantes e a ordem em que `decidir` pergunta, e ela e a propria
# filosofia de treinamento. Ler comida antes de treino, por exemplo, faria o motor cortar
# caloria de quem so precisava dormir melhor.

SEM_LEITURA = "sem_leitura"
AJUSTAR_ADERENCIA = "aderencia"
PROTEGER_O_TREINO = "treino"
SEGURAR_A_PERDA = "perda_rapida"
AJUSTAR_CALORIA = "caloria"
# Cardio nao e credito de comida. E a alavanca de quando o resultado pede mais
# deficit e a comida ja esta no piso, e a de quando a perda esta rapida demais e a
# comida ja esta baixa. Os dois casos estao escritos em `cardio.py`.
AJUSTAR_CARDIO = "cardio"
MANTER = "manter"

ALAVANCAS = (SEM_LEITURA, AJUSTAR_ADERENCIA, PROTEGER_O_TREINO, AJUSTAR_CARDIO,
             SEGURAR_A_PERDA, AJUSTAR_CALORIA, MANTER)

# ── Limiares ────────────────────────────────────────────────────────────────────────

# Menos que isto na semana e uma amostra, nao uma semana.
DIAS_MINIMOS_DE_REGISTRO = 4
# Abaixo disto o plano nao foi testado, entao nao ha o que ajustar nele.
REGISTRO_MINIMO = 0.80
# Dez por cento fora do alvo ainda e seguir o plano. O mesmo espirito da tolerancia de
# 150 kcal do motor de nutricao: precisao de laboratorio nao e aderencia.
DESVIO_CALORICO_TOLERADO = 0.10
# Queda de volume que deixa de ser flutuacao e vira tendencia.
QUEDA_DE_VOLUME = 0.15
# Sessoes seguidas falhando o mesmo exercicio antes de isso virar assunto.
SESSOES_FALHAS = 2
# Perda semanal acima disto, em fracao do peso corporal, custa musculo.
PERDA_RAPIDA = 0.01
# Passo calorico de um ajuste, em fracao do alvo, e o teto absoluto dele.
PASSO_CALORICO = 0.08
TETO_DO_PASSO_KCAL = 250.0
# Piso de seguranca: nenhum ajuste automatico leva a meta abaixo disto.
PISO_KCAL = 1200.0
# Pesagens e dias minimos para a tendencia de peso valer alguma coisa.
MINIMO_DE_PESAGENS = 3
MINIMO_DE_DIAS_DE_PESO = 10
JANELA_DE_PESO_DIAS = 21

# Ritmo esperado por objetivo, em fracao do peso corporal por semana. O primeiro numero e
# o minimo que conta como "esta andando"; o segundo, o maximo saudavel.
RITMO_ESPERADO = {
    "fat_loss": (-0.010, -0.003),
    "muscle_gain": (0.001, 0.005),
    "maintenance": (-0.003, 0.003),
}

DIAS_DA_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado",
                  "domingo")


# ── Numero em portugues ─────────────────────────────────────────────────────────────

def numero(valor: float, casas: int = 2, sinal: bool = False) -> str:
    """Decimal com virgula, que e como se escreve peso no Brasil.

    Parece detalhe e nao e: o Conselho escreve frases que o atleta le, e "0.28 kg" no
    meio de uma frase em portugues denuncia que o texto foi montado por maquina. So
    apareceu quando rodei o motor contra dado de verdade.
    """
    texto = f"{valor:+.{casas}f}" if sinal else f"{valor:.{casas}f}"
    return texto.replace(".", ",")


# ── Leitura de datas ────────────────────────────────────────────────────────────────

def _dia(valor: Any) -> Optional[CalendarDate]:
    """Aceita `YYYY-MM-DD` ou um ISO completo com hora, e devolve None sem reclamar.

    Os registros chegam de tres origens com formatos diferentes: `local_date` do check-in,
    `date` do peso e da aderencia, e `created_at` em ISO completo das series.
    """
    if not valor:
        return None
    try:
        return CalendarDate.fromisoformat(str(valor)[:10])
    except (ValueError, TypeError):
        return None


# ── Observacao: o peso ──────────────────────────────────────────────────────────────

def tendencia_de_peso(registros: Sequence[Dict[str, Any]],
                      janela_dias: int = JANELA_DE_PESO_DIAS) -> Dict[str, Any]:
    """A inclinacao do peso em kg por semana, por minimos quadrados.

    Comparar a pesagem de hoje com a da semana passada e ler agua, nao gordura: um prato
    de macarrao e um dia de sal movem mais o numero do que uma semana inteira de deficit
    honesto. A reta sobre a janela inteira usa TODAS as pesagens e nao se importa com qual
    delas caiu num dia ruim.

    A janela de 21 dias tambem responde "travou ha quanto tempo?" de graca: uma reta plana
    em tres semanas ja e um travamento de duas semanas ou mais, sem precisar guardar
    historico de decisao nenhuma para descobrir isso.
    """
    pontos: List[Tuple[CalendarDate, float]] = []
    for registro in registros or []:
        data = _dia(registro.get("date"))
        peso = registro.get("weight_kg")
        if data is None or peso is None:
            continue
        try:
            pontos.append((data, float(peso)))
        except (TypeError, ValueError):
            continue

    if not pontos:
        return {"suficiente": False, "motivo": "sem pesagem registrada", "pesagens": 0}

    pontos.sort(key=lambda p: p[0])
    fim = pontos[-1][0]
    inicio = fim - timedelta(days=janela_dias - 1)
    dentro = [p for p in pontos if p[0] >= inicio]

    # Duas pesagens no mesmo dia viram uma: a ultima. Pesar de manha e a noite nao sao
    # duas medidas da mesma coisa, e a reta nao deve aprender o ciclo do dia.
    por_dia: Dict[CalendarDate, float] = {}
    for data, peso in dentro:
        por_dia[data] = peso
    dentro = sorted(por_dia.items())

    peso_atual = dentro[-1][1] if dentro else pontos[-1][1]
    if len(dentro) < MINIMO_DE_PESAGENS:
        return {"suficiente": False, "pesagens": len(dentro), "peso_atual": peso_atual,
                "motivo": f"preciso de pelo menos {MINIMO_DE_PESAGENS} pesagens na janela"}

    dias_cobertos = (dentro[-1][0] - dentro[0][0]).days + 1
    if dias_cobertos < MINIMO_DE_DIAS_DE_PESO:
        return {"suficiente": False, "pesagens": len(dentro), "peso_atual": peso_atual,
                "dias_cobertos": dias_cobertos,
                "motivo": f"as pesagens cobrem {dias_cobertos} dias, e eu preciso de "
                          f"{MINIMO_DE_DIAS_DE_PESO}"}

    base = dentro[0][0]
    xs = [float((data - base).days) for data, _ in dentro]
    ys = [peso for _, peso in dentro]
    media_x = sum(xs) / len(xs)
    media_y = sum(ys) / len(ys)
    variancia = sum((x - media_x) ** 2 for x in xs)
    if variancia == 0:
        return {"suficiente": False, "pesagens": len(dentro), "peso_atual": peso_atual,
                "motivo": "todas as pesagens são do mesmo dia"}
    covariancia = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
    por_dia_kg = covariancia / variancia

    return {"suficiente": True,
            "kg_por_semana": round(por_dia_kg * 7, 3),
            "pesagens": len(dentro),
            "dias_cobertos": dias_cobertos,
            "peso_atual": round(peso_atual, 2),
            "peso_medio": round(media_y, 2)}


# ── Observacao: a comida ────────────────────────────────────────────────────────────

def aderencia_alimentar(dias: Sequence[Dict[str, Any]], janela_dias: int,
                        alvo_kcal: Optional[float]) -> Dict[str, Any]:
    """Quanto da semana foi registrado, e quao perto do alvo foi o que se registrou.

    Sao DOIS numeros e nao um, porque eles respondem perguntas diferentes e confundi-los e
    o erro classico: `registro` diz se da para ler a semana, `desvio` diz se o plano foi
    seguido nos dias em que houve leitura. Uma pessoa que registrou tres dias perfeitos
    nao teve uma semana perfeita; teve tres dias e quatro pontos cegos.

    `dias` so traz dia COM registro, exatamente como `/adherence-week` devolve.
    """
    validos = []
    for dia in dias or []:
        kcal = dia.get("kcal")
        if kcal is None:
            continue
        try:
            kcal = float(kcal)
        except (TypeError, ValueError):
            continue
        if kcal <= 0:
            continue
        validos.append(kcal)

    janela = max(1, int(janela_dias or 1))
    registrados = len(validos)
    leitura = {
        "dias_registrados": registrados,
        "janela_dias": janela,
        "registro": round(registrados / janela, 3),
        "alvo_kcal": round(float(alvo_kcal), 0) if alvo_kcal else None,
    }
    if not validos:
        leitura.update({"suficiente": False, "kcal_media": None, "desvio": None,
                        "motivo": "nenhum dia com consumo registrado"})
        return leitura

    media = sum(validos) / len(validos)
    leitura["kcal_media"] = round(media, 0)
    if not alvo_kcal:
        leitura.update({"suficiente": False, "desvio": None,
                        "motivo": "o plano não tem meta calórica"})
        return leitura

    leitura["desvio"] = round((media - float(alvo_kcal)) / float(alvo_kcal), 3)
    leitura["suficiente"] = registrados >= DIAS_MINIMOS_DE_REGISTRO
    if not leitura["suficiente"]:
        leitura["motivo"] = (f"{registrados} de {janela} dias registrados, e eu preciso de "
                             f"{DIAS_MINIMOS_DE_REGISTRO}")
    return leitura


# ── Observacao: o treino ────────────────────────────────────────────────────────────

def _chave_da_semana(data: CalendarDate) -> str:
    ano, semana, _ = data.isocalendar()
    return f"{ano}-S{semana:02d}"


def volume_por_semana(series: Sequence[Dict[str, Any]],
                      musculo_por_exercicio: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Series e tonelagem por musculo, agrupadas por semana ISO.

    Tonelagem (carga x repeticoes) entra ao lado da contagem de series porque as duas
    mentem sozinhas: tres series pesadas e tres series leves contam igual na primeira, e a
    segunda sobe quando alguem troca agachamento por leg press sem ter ficado mais forte.
    Juntas, elas mostram quando o volume caiu de verdade.
    """
    semanas: Dict[str, Dict[str, Any]] = {}
    for serie in series or []:
        data = _dia(serie.get("created_at") or serie.get("date"))
        if data is None:
            continue
        musculo = musculo_por_exercicio.get(str(serie.get("exercise_id")))
        if not musculo:
            continue
        try:
            carga = float(serie.get("weight") or 0)
            reps = int(serie.get("reps") or 0)
        except (TypeError, ValueError):
            continue
        chave = _chave_da_semana(data)
        semana = semanas.setdefault(chave, {"series": {}, "tonelagem": 0.0, "total": 0})
        semana["series"][musculo] = semana["series"].get(musculo, 0) + 1
        semana["tonelagem"] += carga * reps
        semana["total"] += 1
    for semana in semanas.values():
        semana["tonelagem"] = round(semana["tonelagem"], 1)
    return semanas


def queda_de_volume(semanas: Dict[str, Dict[str, Any]],
                    semanas_de_base: int = 3) -> Dict[str, Any]:
    """A semana corrente contra a media das anteriores, no total e por musculo.

    Uma semana so nao diz nada: todo mundo tem semana ruim. A base de tres semanas e o que
    separa "semana ruim" de "voce esta encolhendo ha um mes".
    """
    if len(semanas) < 2:
        return {"suficiente": False, "motivo": "preciso de pelo menos duas semanas de treino"}

    ordenadas = sorted(semanas)
    atual = semanas[ordenadas[-1]]
    base_chaves = ordenadas[-(semanas_de_base + 1):-1]
    base = [semanas[c] for c in base_chaves]
    media_series = sum(s["total"] for s in base) / len(base)
    media_tonelagem = sum(s["tonelagem"] for s in base) / len(base)

    por_musculo = {}
    for musculo in {m for s in base for m in s["series"]} | set(atual["series"]):
        media = sum(s["series"].get(musculo, 0) for s in base) / len(base)
        agora = atual["series"].get(musculo, 0)
        if media > 0:
            por_musculo[musculo] = round((agora - media) / media, 3)

    piores = sorted(por_musculo.items(), key=lambda kv: kv[1])
    return {
        "suficiente": True,
        "semana": ordenadas[-1],
        "series_agora": atual["total"],
        "series_base": round(media_series, 1),
        "variacao": round((atual["total"] - media_series) / media_series, 3) if media_series else None,
        "tonelagem_agora": atual["tonelagem"],
        "tonelagem_base": round(media_tonelagem, 1),
        "variacao_tonelagem": (round((atual["tonelagem"] - media_tonelagem) / media_tonelagem, 3)
                               if media_tonelagem else None),
        "por_musculo": por_musculo,
        "pior_musculo": piores[0][0] if piores and piores[0][1] < 0 else None,
        "pior_queda": piores[0][1] if piores and piores[0][1] < 0 else None,
    }


def falhas_recorrentes(series: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Exercicios em que a pessoa vem perdendo repeticao com a MESMA carga ou menos.

    Este e o sinal que o atleta nao ve sozinho, porque ele acontece devagar e sempre tem
    uma desculpa local: dormiu mal, chegou atrasado, o banco estava ocupado. Repetido tres
    semanas seguidas no mesmo exercicio, deixou de ser desculpa e virou dado.

    Comparar so a melhor serie de cada sessao e proposital. O numero de series varia com a
    prescricao e com o tempo disponivel; a melhor serie e a coisa mais estavel que uma
    sessao produz.
    """
    por_exercicio: Dict[str, Dict[CalendarDate, Dict[str, float]]] = {}
    for serie in series or []:
        data = _dia(serie.get("created_at") or serie.get("date"))
        exercicio = serie.get("exercise_id")
        if data is None or not exercicio:
            continue
        try:
            carga = float(serie.get("weight") or 0)
            reps = int(serie.get("reps") or 0)
        except (TypeError, ValueError):
            continue
        if reps <= 0:
            continue
        sessoes = por_exercicio.setdefault(str(exercicio), {})
        melhor = sessoes.get(data)
        # "Melhor" e a serie de maior carga; empatou na carga, a de mais repeticoes.
        if melhor is None or (carga, reps) > (melhor["carga"], melhor["reps"]):
            sessoes[data] = {"carga": carga, "reps": reps}

    achados = []
    for exercicio, sessoes in por_exercicio.items():
        ordenadas = [sessoes[d] for d in sorted(sessoes)]
        if len(ordenadas) < SESSOES_FALHAS + 1:
            continue
        seguidas = 0
        for anterior, atual in zip(ordenadas, ordenadas[1:]):
            caiu = (atual["carga"] <= anterior["carga"] and atual["reps"] < anterior["reps"])
            seguidas = seguidas + 1 if caiu else 0
        if seguidas >= SESSOES_FALHAS:
            achados.append({"exercise_id": exercicio, "sessoes_seguidas": seguidas,
                            "carga": ordenadas[-1]["carga"], "reps": ordenadas[-1]["reps"],
                            "reps_antes": ordenadas[-1 - seguidas]["reps"]})
    achados.sort(key=lambda a: (-a["sessoes_seguidas"], a["exercise_id"]))
    return achados


def prontidao_por_dia_da_semana(checkins: Sequence[Dict[str, Any]],
                                minimo_por_dia: int = 2) -> Dict[str, Any]:
    """A prontidao media de cada dia da semana, pela formula do proprio motor de treino.

    A pergunta que isto responde nao aparece em nenhum grafico: nao e "voce esta cansado?",
    e "voce esta cansado NAS TERCAS". Um treino pesado marcado no pior dia da semana da
    pessoa parece fraqueza de perna e e so agenda.

    `classificar_recuperacao` vem de `engine.py` de proposito. Duas formulas de prontidao
    no mesmo aplicativo seriam duas verdades sobre o mesmo atleta.
    """
    por_dia: Dict[int, List[float]] = {}
    for checkin in checkins or []:
        data = _dia(checkin.get("local_date") or checkin.get("created_at"))
        if data is None:
            continue
        try:
            energia = float(checkin.get("energy", 4))
            estresse = float(checkin.get("stress", 2))
            dor = float(checkin.get("soreness", 2))
        except (TypeError, ValueError):
            continue
        _, pontuacao = classificar_recuperacao(energia, estresse, dor)
        por_dia.setdefault(data.weekday(), []).append(pontuacao)

    medias = {DIAS_DA_SEMANA[d]: round(sum(v) / len(v), 2)
              for d, v in por_dia.items() if len(v) >= minimo_por_dia}
    if not medias:
        return {"suficiente": False, "motivo": "poucos check-ins para separar por dia",
                "por_dia": {}}
    pior = min(medias.items(), key=lambda kv: kv[1])
    melhor = max(medias.items(), key=lambda kv: kv[1])
    return {"suficiente": True, "por_dia": medias,
            "pior_dia": pior[0], "pior_pontuacao": pior[1],
            "melhor_dia": melhor[0], "melhor_pontuacao": melhor[1],
            "amostras": {DIAS_DA_SEMANA[d]: len(v) for d, v in por_dia.items()}}


def observar(*, objetivo: Optional[str], dias_de_consumo: Sequence[Dict[str, Any]],
             janela_dias: int, alvo_kcal: Optional[float],
             pesagens: Sequence[Dict[str, Any]], series: Sequence[Dict[str, Any]],
             musculo_por_exercicio: Dict[str, str],
             checkins: Sequence[Dict[str, Any]],
             nome_por_exercicio: Optional[Dict[str, str]] = None,
             cardio: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """As linhas cruas do banco viram UMA leitura do atleta.

    Existe para a rota e a suite percorrerem o mesmo caminho. Se o teste montasse o estado
    a mao, ele provaria que o arbitro funciona sobre um dicionario inventado, e nao sobre o
    que o Mongo realmente devolve, que e o unico lugar onde isso importa.
    """
    return {
        "objetivo": objetivo,
        "comida": aderencia_alimentar(dias_de_consumo, janela_dias, alvo_kcal),
        "peso": tendencia_de_peso(pesagens),
        "volume": queda_de_volume(volume_por_semana(series, musculo_por_exercicio)),
        "falhas": falhas_recorrentes(series),
        "prontidao": prontidao_por_dia_da_semana(checkins),
        # Ja vem lido de `cardio.leitura_de_cardio`, pelo MESMO caminho da tela, para os
        # dois lados nunca mostrarem totais diferentes da mesma semana.
        "cardio": dict(cardio or {}),
        "treino_lido": bool(series),
        # O atleta le "Agachamento", e nao "squat". O identificador serve ao banco; o
        # nome serve a frase, e vazar identificador para a tela e a marca de um texto
        # que ninguem leu antes de publicar.
        "nomes": dict(nome_por_exercicio or {}),
    }


# ── A arbitragem ────────────────────────────────────────────────────────────────────

def _ritmo(objetivo: Optional[str]) -> Tuple[float, float]:
    return RITMO_ESPERADO.get(str(objetivo or "").lower(), RITMO_ESPERADO["maintenance"])


def passo_calorico(alvo_atual: float, sentido: int) -> float:
    """O tamanho de um ajuste, limitado por fracao E por teto absoluto.

    Sem o teto, uma meta de 4000 kcal levaria um corte de 320 numa tacada, que e mais do
    que um treinador faz de uma vez. Sem a fracao, 100 kcal seria irrelevante para essa
    mesma pessoa e brutal para quem come 1400.
    """
    passo = min(alvo_atual * PASSO_CALORICO, TETO_DO_PASSO_KCAL)
    return round(sentido * max(50.0, passo), 0)


def decidir(estado: Dict[str, Any]) -> Dict[str, Any]:
    """A semana inteira em UMA alavanca, com motivo, mudanca e previsao.

    A ordem das perguntas e a decisao de produto mais importante deste arquivo:

      1. Da para ler a semana?            senao, SEM_LEITURA
      2. O plano chegou a ser seguido?    senao, ADERENCIA (e nao se toca no plano)
      3. O treino esta de pe?             senao, TREINO (e nao se corta comida)
      4. Esta perdendo rapido demais?     entao, SEGURAR
      5. O resultado andou?               senao, CALORIA
      6. Nada disso                       entao, MANTER

    Os passos 2 e 3 sao o produto inteiro. Um aplicativo que pula direto para o 5 corta a
    comida de quem nao seguiu o plano e de quem esta com o treino caindo, que sao
    exatamente as duas pessoas para quem cortar comida e a pior coisa a fazer.
    """
    objetivo = str(estado.get("objetivo") or "maintenance").lower()
    comida = estado.get("comida") or {}
    peso = estado.get("peso") or {}
    volume = estado.get("volume") or {}
    falhas = estado.get("falhas") or []
    prontidao = estado.get("prontidao") or {}
    cardio = estado.get("cardio") or {}
    alvo_kcal = comida.get("alvo_kcal")
    peso_atual = peso.get("peso_atual")

    def conselho(alavanca, titulo, motivo, mudanca=None, previsao=None, confianca="media"):
        return {"alavanca": alavanca, "titulo": titulo, "motivo": motivo,
                "mudanca": mudanca, "previsao": previsao, "confianca": confianca,
                "objetivo": objetivo}

    # 1. Da para ler a semana?
    if not comida.get("dias_registrados"):
        faltas = [comida.get("motivo") or "nenhum dia com consumo registrado"]
        if not peso.get("suficiente"):
            faltas.append(peso.get("motivo") or "pesagens insuficientes")
        return conselho(
            SEM_LEITURA, "Essa semana eu não sei",
            "Não vou adivinhar. " + _frase_de_faltas(faltas),
            previsao={"tipo": "registros_minimos", "valor": DIAS_MINIMOS_DE_REGISTRO,
                      "prazo_dias": 7,
                      "frase": f"você registra pelo menos {DIAS_MINIMOS_DE_REGISTRO} dias"},
            confianca="alta")

    # 2. O plano chegou a ser seguido?
    registro = comida.get("registro") or 0
    desvio = comida.get("desvio")
    if registro < REGISTRO_MINIMO:
        registrados = comida.get("dias_registrados", 0)
        janela = comida.get("janela_dias", 7)
        return conselho(
            AJUSTAR_ADERENCIA, "Não vou mexer no seu plano",
            f"Você registrou {registrados} de {janela} dias. O plano não foi testado "
            f"ainda, então mudar ele agora seria corrigir uma conta que ninguém fez. "
            f"Essa semana o alvo é registrar, não emagrecer.",
            previsao={"tipo": "registros_minimos", "valor": max(6, int(janela * 0.85)),
                      "prazo_dias": 7,
                      "frase": f"você registra pelo menos {max(6, int(janela * 0.85))} dias"},
            confianca="alta")

    if desvio is not None and abs(desvio) > DESVIO_CALORICO_TOLERADO:
        direcao = "acima" if desvio > 0 else "abaixo"
        return conselho(
            AJUSTAR_ADERENCIA, "O plano está certo, a execução que escorregou",
            f"Você comeu {abs(round(desvio * 100))}% {direcao} da sua meta nos dias que "
            f"registrou, média de {int(comida.get('kcal_media') or 0)} kcal contra "
            f"{int(alvo_kcal or 0)} kcal. Mudar a meta agora só mudaria o número de onde "
            f"você escorrega. Vamos fechar uma semana no alvo e aí eu mexo.",
            previsao={"tipo": "desvio_maximo", "valor": DESVIO_CALORICO_TOLERADO,
                      "prazo_dias": 7,
                      "frase": f"sua média fica a menos de "
                               f"{int(DESVIO_CALORICO_TOLERADO * 100)}% do alvo"},
            confianca="alta")

    # 3. O treino esta de pe?
    caiu = volume.get("suficiente") and (volume.get("variacao") or 0) <= -QUEDA_DE_VOLUME
    if caiu or falhas:
        return _conselho_de_treino(conselho, volume, falhas, prontidao, caiu,
                                   estado.get("nomes") or {})

    # 4. Esta perdendo rapido demais?
    if peso.get("suficiente") and peso_atual:
        fracao = (peso.get("kg_por_semana") or 0) / peso_atual
        if fracao < -PERDA_RAPIDA:
            corte_de_cardio = (cardio_step(cardio.get("minutos_por_semana") or 0, -1)
                               if cardio.get("faz_cardio") else None)
            if corte_de_cardio:
                return conselho(
                    AJUSTAR_CARDIO, "Tira cardio antes de botar comida",
                    f"Sua tendência é de {numero(abs(peso.get('kg_por_semana')))} kg por "
                    f"semana, {numero(abs(fracao * 100), 1)}% do seu peso, e acima de "
                    f"{int(PERDA_RAPIDA * 100)}% por semana a conta começa a sair de "
                    f"músculo. Como {frase_de_cardio(cardio)}, o excesso de déficit tem "
                    f"de onde sair sem você comer mais: é o cardio que desce primeiro.",
                    mudanca=corte_de_cardio,
                    previsao={"tipo": "ritmo_de_peso", "minimo": -PERDA_RAPIDA,
                              "maximo": 0.0, "prazo_dias": 14,
                              "frase": "sua queda volta para menos de "
                                       f"{int(PERDA_RAPIDA * 100)}% por semana"},
                    confianca="media")
            delta = passo_calorico(float(alvo_kcal), +1) if alvo_kcal else None
            return conselho(
                SEGURAR_A_PERDA, "Você está descendo rápido demais",
                f"Sua tendência é de {numero(abs(peso.get('kg_por_semana')))} kg por semana, "
                f"{numero(abs(fracao * 100), 1)}% do seu peso. Acima de "
                f"{int(PERDA_RAPIDA * 100)}% por semana a conta começa a sair de músculo, "
                f"e músculo perdido em corte não volta no próximo bulking de graça.",
                mudanca=_mudanca_calorica(alvo_kcal, delta),
                previsao={"tipo": "ritmo_de_peso", "minimo": -PERDA_RAPIDA, "maximo": 0.0,
                          "prazo_dias": 14,
                          "frase": "sua queda volta para menos de "
                                   f"{int(PERDA_RAPIDA * 100)}% por semana"},
                confianca="alta")

    # 5. O resultado andou?
    if not peso.get("suficiente"):
        return conselho(
            SEM_LEITURA, "Falta o resultado para eu decidir",
            "Sua comida e seu treino estão lidos. O que falta é a balança: "
            + (peso.get("motivo") or "poucas pesagens"),
            previsao={"tipo": "pesagens_minimas", "valor": MINIMO_DE_PESAGENS,
                      "prazo_dias": 7,
                      "frase": f"você registra pelo menos {MINIMO_DE_PESAGENS} pesagens"},
            confianca="alta")

    minimo, maximo = _ritmo(objetivo)
    fracao = (peso.get("kg_por_semana") or 0) / peso_atual if peso_atual else 0

    # A regra e a mesma para os tres objetivos, e e por isso que ela esta certa: peso anda
    # para cima com caloria. Abaixo da faixa, soma; acima da faixa, corta.
    #
    # Escolher o sentido pelo OBJETIVO, e nao pela posicao na faixa, era um erro de verdade:
    # mandava SOMAR caloria para quem estava em ganho e ja subindo rapido demais, que e a
    # receita de transformar bulking em engorda. O objetivo diz onde e a faixa; quem diz
    # para que lado ir e o lado da faixa em que a pessoa esta.
    if fracao < minimo:
        sentido = +1
    elif fracao > maximo:
        sentido = -1
    else:
        sentido = 0

    if sentido:
        delta = passo_calorico(float(alvo_kcal), sentido) if alvo_kcal else None
        mudanca = _mudanca_calorica(alvo_kcal, delta)

        # A comida ja esta no piso e ainda falta deficit. Cortar mais nao e uma opcao, e
        # sem isto o motor devolveria um veredito sem nenhuma mudanca junto.
        if sentido < 0 and mudanca is None:
            somar_cardio = cardio_step(cardio.get("minutos_por_semana") or 0, +1)
            if somar_cardio:
                return conselho(
                    AJUSTAR_CARDIO, "A comida não desce mais. O cardio sobe",
                    f"Leitura limpa: você registrou "
                    f"{comida.get('dias_registrados')} de {comida.get('janela_dias')} "
                    f"dias, o treino não caiu, e mesmo assim o peso não andou. O corte "
                    f"seria o caminho, só que sua meta já está em "
                    f"{int(alvo_kcal or 0)} kcal e abaixo de {int(PISO_KCAL)} eu não "
                    f"desço. Como {frase_de_cardio(cardio)}, o déficit desta semana vem "
                    f"do movimento, e não do prato.",
                    mudanca=somar_cardio,
                    previsao=_previsao_de_ritmo(objetivo, peso_atual),
                    confianca="media")

        titulo = "Agora sim, o corte é seu" if sentido < 0 else "Agora sim, vamos somar"
        kg = peso.get("kg_por_semana") or 0
        andou = ("seu peso não saiu do lugar" if abs(kg) < 0.05
                 else f"seu peso foi a {numero(kg, 2, sinal=True)} kg por semana")
        fora = abs(round((desvio or 0) * 100))
        comeu = ("comeu dentro da meta" if fora <= 2
                 else f"ficou {fora}% {'acima' if (desvio or 0) > 0 else 'abaixo'} da meta")
        return conselho(
            AJUSTAR_CALORIA, titulo,
            f"Leitura limpa: você registrou {comida.get('dias_registrados')} de "
            f"{comida.get('janela_dias')} dias, {comeu} e seu treino não caiu. "
            f"Mesmo assim {andou} em {peso.get('dias_cobertos')} dias, fora da faixa do "
            f"seu objetivo. Não foi você, foi a conta. Ela que muda.",
            mudanca=mudanca,
            previsao=_previsao_de_ritmo(objetivo, peso_atual),
            confianca="alta")

    # 6. Nada disso.
    return conselho(
        MANTER, "Não mexe. Está funcionando",
        f"Você registrou {comida.get('dias_registrados')} de "
        f"{comida.get('janela_dias')} dias, comeu dentro da meta, o treino não caiu e o "
        f"peso anda a {numero(peso.get('kg_por_semana') or 0, 2, sinal=True)} kg por semana, "
        f"que é o ritmo certo para o seu objetivo. A coisa mais difícil de fazer aqui é "
        f"não inventar mudança.",
        previsao=_previsao_de_ritmo(objetivo, peso_atual),
        confianca="alta")


def _frase_de_faltas(faltas: Sequence[str]) -> str:
    if len(faltas) == 1:
        return f"Para ler sua semana me falta uma coisa: {faltas[0]}."
    lista = "; ".join(faltas)
    return f"Para ler sua semana me faltam duas coisas: {lista}."


def _mudanca_calorica(alvo_kcal: Optional[float], delta: Optional[float]) -> Optional[Dict[str, Any]]:
    """A mudanca proposta, ja limitada pelo piso de seguranca.

    Proteina nao entra aqui de proposito: ela e fixa em gramas, como em
    `nutrition_periodization`, e um motor automatico nao tem autoridade para mexer nela.
    """
    if not alvo_kcal or not delta:
        return None
    novo = float(alvo_kcal) + float(delta)
    if novo < PISO_KCAL:
        novo = PISO_KCAL
        delta = round(novo - float(alvo_kcal), 0)
        if delta == 0:
            return None
    return {"tipo": "kcal", "de": round(float(alvo_kcal), 0), "para": round(novo, 0),
            "delta": round(float(delta), 0),
            "trava": "proteína fixa em gramas e piso de gordura preservado"}


def _previsao_de_ritmo(objetivo: str, peso_atual: Optional[float]) -> Optional[Dict[str, Any]]:
    if not peso_atual:
        return None
    minimo, maximo = _ritmo(objetivo)
    kg_min, kg_max = round(minimo * peso_atual, 2), round(maximo * peso_atual, 2)
    if objetivo == "fat_loss":
        frase = (f"seu peso cai entre {numero(abs(kg_max))} e "
                 f"{numero(abs(kg_min))} kg por semana")
    elif objetivo == "muscle_gain":
        frase = f"seu peso sobe entre {numero(kg_min)} e {numero(kg_max)} kg por semana"
    else:
        frase = (f"seu peso fica entre {numero(kg_min, 2, sinal=True)} e "
                 f"{numero(kg_max, 2, sinal=True)} kg por semana")
    return {"tipo": "ritmo_de_peso", "minimo": minimo, "maximo": maximo,
            "prazo_dias": 14, "frase": frase}


def _conselho_de_treino(conselho, volume, falhas, prontidao, caiu,
                        nomes: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """O ramo que existe para NAO cortar comida.

    Aqui mora a frase que separa o FORGE de um contador de calorias: cortar comida com o
    treino caindo e acelerar com o freio puxado. O motor prefere devolver treino a tirar
    comida, e quando a prontidao aponta um dia especifico ele mexe na AGENDA, que e a
    mudanca mais barata que existe e a que ninguem faz sozinho.
    """
    pior_dia = prontidao.get("pior_dia") if prontidao.get("suficiente") else None
    alvo = falhas[0] if falhas else None
    nomes = nomes or {}
    exercicio = nomes.get(alvo["exercise_id"], alvo["exercise_id"]) if alvo else None

    if alvo and pior_dia:
        melhor = prontidao.get("melhor_dia")
        return conselho(
            PROTEGER_O_TREINO, "Não é perna fraca, é agenda",
            f"Você perdeu repetição em {exercicio} em "
            f"{alvo['sessoes_seguidas']} sessões seguidas, de {alvo['reps_antes']} para "
            f"{alvo['reps']} repetições com {alvo['carga']:.0f} kg. E a sua "
            f"{pior_dia} tem a pior prontidão da semana "
            f"({numero(prontidao.get('pior_pontuacao') or 0, 1)} contra "
            f"{numero(prontidao.get('melhor_pontuacao') or 0, 1)} na {melhor}). "
            f"Não vou cortar sua comida por causa disso.",
            mudanca={"tipo": "agenda", "de": pior_dia, "para": melhor,
                     "exercicio": alvo["exercise_id"],
                     "trava": "mesmo volume, só muda o dia"},
            previsao={"tipo": "exercicio_fechado", "exercise_id": alvo["exercise_id"],
                      "reps": alvo["reps_antes"], "prazo_dias": 10,
                      "frase": f"você volta a fazer {alvo['reps_antes']} repetições em "
                               f"{exercicio}"},
            confianca="media")

    if alvo:
        return conselho(
            PROTEGER_O_TREINO, "Seu treino está pedindo socorro, não sua dieta",
            f"Você perdeu repetição em {exercicio} em "
            f"{alvo['sessoes_seguidas']} sessões seguidas, de {alvo['reps_antes']} para "
            f"{alvo['reps']} repetições com a mesma carga ou menos. Isso não se resolve "
            f"comendo menos. Vamos tirar a carga desse exercício por uma semana e voltar "
            f"por cima.",
            mudanca={"tipo": "descarga", "exercicio": alvo["exercise_id"],
                     "percentual": -10,
                     "trava": "uma semana, e a carga volta sozinha depois"},
            previsao={"tipo": "exercicio_fechado", "exercise_id": alvo["exercise_id"],
                      "reps": alvo["reps_antes"], "prazo_dias": 10,
                      "frase": f"você volta a fazer {alvo['reps_antes']} repetições em "
                               f"{exercicio}"},
            confianca="media")

    pior_musculo = volume.get("pior_musculo")
    queda = abs(round((volume.get("variacao") or 0) * 100))
    detalhe = ""
    if pior_musculo and volume.get("pior_queda") is not None:
        detalhe = (f" A maior queda foi em {pior_musculo}, "
                   f"{abs(round(volume['pior_queda'] * 100))}% abaixo da sua base.")
    return conselho(
        PROTEGER_O_TREINO, "Seu volume caiu antes do seu peso",
        f"Você fez {volume.get('series_agora')} séries essa semana contra "
        f"{round(volume.get('series_base') or 0)} de média nas anteriores, "
        f"{queda}% a menos.{detalhe} "
        f"Enquanto o treino estiver descendo, mexer na comida só troca o motivo do "
        f"resultado não aparecer.",
        mudanca={"tipo": "volume", "musculo": pior_musculo,
                 "series_alvo": round(volume.get("series_base") or 0),
                 "trava": "voltar à base, não passar dela"},
        previsao={"tipo": "volume_restaurado",
                  "valor": round(volume.get("series_base") or 0), "prazo_dias": 7,
                  "frase": f"você volta a {round(volume.get('series_base') or 0)} séries na semana"},
        confianca="media")


# ── O placar: o motor responde pela propria previsao ────────────────────────────────

ACERTOU = "acertou"
ERROU = "errou"
NAO_VERIFICAVEL = "nao_verificavel"


def conferir_previsao(previsao: Optional[Dict[str, Any]],
                      estado: Dict[str, Any]) -> Dict[str, Any]:
    """A previsao da semana passada contra o que realmente aconteceu.

    Esta funcao e a diferenca entre um aplicativo que te manda fazer coisas e alguem que
    arrisca a reputacao junto com voce. Ela tem que poder devolver ERROU, senao o placar
    e decoracao.

    `NAO_VERIFICAVEL` nao e empate por educacao: e o caso honesto de quem parou de
    registrar. Contar isso como acerto seria premiar o silencio, e contar como erro seria
    punir o motor por uma coisa que nao foi ele que fez.
    """
    if not previsao:
        return {"resultado": NAO_VERIFICAVEL, "motivo": "sem previsao anterior"}

    tipo = previsao.get("tipo")
    comida = estado.get("comida") or {}
    peso = estado.get("peso") or {}
    volume = estado.get("volume") or {}
    falhas = {f["exercise_id"]: f for f in (estado.get("falhas") or [])}

    if tipo == "registros_minimos":
        medido = comida.get("dias_registrados")
        if medido is None:
            return {"resultado": NAO_VERIFICAVEL, "motivo": "sem registro de consumo"}
        return _placar(medido >= previsao.get("valor", 0), medido, previsao)

    if tipo == "pesagens_minimas":
        medido = peso.get("pesagens", 0)
        return _placar(medido >= previsao.get("valor", 0), medido, previsao)

    if tipo == "desvio_maximo":
        medido = comida.get("desvio")
        if medido is None or not comida.get("suficiente"):
            return {"resultado": NAO_VERIFICAVEL, "motivo": "semana sem leitura de consumo"}
        return _placar(abs(medido) <= previsao.get("valor", 0), round(medido, 3), previsao)

    if tipo == "ritmo_de_peso":
        if not peso.get("suficiente") or not peso.get("peso_atual"):
            return {"resultado": NAO_VERIFICAVEL, "motivo": "pesagens insuficientes"}
        fracao = (peso.get("kg_por_semana") or 0) / peso["peso_atual"]
        minimo = previsao.get("minimo")
        maximo = previsao.get("maximo")
        dentro = (minimo is None or fracao >= minimo) and (maximo is None or fracao <= maximo)
        return _placar(dentro, round(fracao, 4), previsao)

    if tipo == "exercicio_fechado":
        exercicio = previsao.get("exercise_id")
        ainda_falha = exercicio in falhas
        if not estado.get("treino_lido", True):
            return {"resultado": NAO_VERIFICAVEL, "motivo": "sem series registradas"}
        return _placar(not ainda_falha, "sem queda" if not ainda_falha else "ainda caindo",
                       previsao)

    if tipo == "volume_restaurado":
        if not volume.get("suficiente"):
            return {"resultado": NAO_VERIFICAVEL, "motivo": "sem semanas de treino suficientes"}
        medido = volume.get("series_agora", 0)
        return _placar(medido >= previsao.get("valor", 0), medido, previsao)

    return {"resultado": NAO_VERIFICAVEL, "motivo": f"previsao de tipo desconhecido: {tipo}"}


def _placar(acertou: bool, medido: Any, previsao: Dict[str, Any]) -> Dict[str, Any]:
    return {"resultado": ACERTOU if acertou else ERROU, "medido": medido,
            "previsto": previsao.get("frase") or previsao.get("valor")}


def retrospecto(conferidas: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """O placar corrido do motor, para a pessoa poder desconfiar dele com numero."""
    acertos = sum(1 for c in conferidas if c.get("resultado") == ACERTOU)
    erros = sum(1 for c in conferidas if c.get("resultado") == ERROU)
    julgadas = acertos + erros
    return {"acertos": acertos, "erros": erros, "julgadas": julgadas,
            "nao_verificaveis": len(conferidas) - julgadas,
            "taxa": round(acertos / julgadas, 3) if julgadas else None}


# ── O placar do metodo ──────────────────────────────────────────────────────────────

# Abaixo disto nao se conclui nada. O numero existe para a tela poder dizer "ainda nao
# sei" em vez de mostrar uma taxa de 100% tirada de duas semanas.
MINIMO_PARA_CONCLUIR = 30


def placar_do_metodo(semanas: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Quantas vezes cada alavanca do motor acertou a propria previsao.

    Cada semana gravada e um experimento: condicao antes, intervencao, aposta, resultado.
    Agregadas, elas respondem a pergunta que nunca foi feita ao FORGE: os limiares que
    decidem tudo (`PASSO_CALORICO` de 8%, `QUEDA_DE_VOLUME` de 15%, as faixas de
    `RITMO_ESPERADO`) estao certos? Hoje sao julgamento. Aqui eles passam a ter medida.

    A funcao NAO propoe correcao, e isso e deliberado enquanto a amostra e pequena: uma
    taxa calculada sobre cinco semanas convenceria alguem a mudar uma regra com base em
    ruido. Ela conta, separa por alavanca e por objetivo, e diz quando ainda nao da para
    concluir.

    `visivel` entra na conta porque quem NUNCA VIU o conselho nunca pode te-lo aplicado:
    esse grupo mede o que acontece sem intervencao, que e a unica base de comparacao
    honesta para o grupo que aplicou.
    """
    total = len(semanas)
    por_alavanca: Dict[str, Dict[str, Any]] = {}
    por_objetivo: Dict[str, Dict[str, Any]] = {}
    aplicadas = vistas = 0

    for semana in semanas:
        decisao = semana.get("decisao") or {}
        alavanca = decisao.get("alavanca") or "desconhecida"
        objetivo = decisao.get("objetivo") or "desconhecido"
        conferido = semana.get("conferido") or {}
        resultado = conferido.get("resultado")
        if semana.get("visivel"):
            vistas += 1
        if (semana.get("aplicada") or {}).get("status") == "aplicada":
            aplicadas += 1

        for mapa, chave in ((por_alavanca, alavanca), (por_objetivo, objetivo)):
            linha = mapa.setdefault(chave, {"semanas": 0, "acertos": 0, "erros": 0})
            linha["semanas"] += 1
            if resultado == ACERTOU:
                linha["acertos"] += 1
            elif resultado == ERROU:
                linha["erros"] += 1

    def fechar(mapa):
        for linha in mapa.values():
            julgadas = linha["acertos"] + linha["erros"]
            linha["julgadas"] = julgadas
            linha["taxa"] = round(linha["acertos"] / julgadas, 3) if julgadas else None
            # A tela precisa saber a diferenca entre "errou muito" e "ainda nao sei".
            linha["amostra_suficiente"] = julgadas >= MINIMO_PARA_CONCLUIR
        return mapa

    julgadas = sum(l["acertos"] + l["erros"] for l in por_alavanca.values())
    acertos = sum(l["acertos"] for l in por_alavanca.values())
    return {
        "semanas": total,
        "vistas": vistas,
        "nao_vistas": total - vistas,
        "aplicadas": aplicadas,
        "julgadas": julgadas,
        "acertos": acertos,
        "taxa": round(acertos / julgadas, 3) if julgadas else None,
        "amostra_suficiente": julgadas >= MINIMO_PARA_CONCLUIR,
        "minimo_para_concluir": MINIMO_PARA_CONCLUIR,
        "por_alavanca": fechar(por_alavanca),
        "por_objetivo": fechar(por_objetivo),
    }

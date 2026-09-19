"""Small, isolated cardio completion model for the FORGE workout finisher."""
from datetime import date as CalendarDate
from typing import Optional

from pydantic import BaseModel, Field


CARDIO_KINDS = {"moderate", "recovery", "free"}


class CardioLogIn(BaseModel):
    client_token: str = Field(..., min_length=8, max_length=80)
    kind: str = Field(default="moderate", max_length=24)
    modality: str = Field(..., min_length=2, max_length=40)
    # Era `le=120`, o teto do finalizador de treino. A aba de cardio registra a sessao
    # inteira, e uma pedalada de duas horas e meia nao e dedo errado.
    minutes: int = Field(..., ge=1, le=360)
    # Passou a ser opcional: no finalizador a pessoa escolhe o RPE numa lista, mas quem
    # registra a sessao depois nem sempre lembra o esforco, e exigir o campo faria ela
    # chutar um numero que depois entra no historico como se fosse medida.
    rpe: Optional[int] = Field(default=None, ge=1, le=10)
    session_day: Optional[int] = Field(default=None, ge=1, le=31)
    session_label: str = Field(default="", max_length=120)
    completed: bool = True
    # O que o painel da esteira mostrou. O nome carrega a procedencia de proposito, e o
    # campo e opcional porque quem corre na rua nao tem painel nenhum para ler: exigir o
    # numero transformaria "registrei minha corrida" em "inventei uma caloria".
    kcal_reported: Optional[int] = Field(default=None, ge=0, le=3000)
    # O dia em que o cardio aconteceu. Sem isto, tudo caia no dia em que foi digitado e a
    # media semanal mentiria para quem registra a semana toda no domingo.
    date: Optional[CalendarDate] = None
    note: str = Field(default="", max_length=280)


def cardio_doc(payload: CardioLogIn, profile_id: str, created_at: str) -> dict:
    kind = payload.kind if payload.kind in CARDIO_KINDS else "free"
    return {
        "date": (payload.date or CalendarDate.fromisoformat(created_at[:10])).isoformat(),
        "kcal_reported": payload.kcal_reported,
        "note": (payload.note or "").strip(),
        "profile_id": profile_id,
        "user_id": profile_id,
        "client_token": payload.client_token.strip(),
        "kind": kind,
        "modality": payload.modality.strip(),
        "minutes": payload.minutes,
        "rpe": payload.rpe,
        "session_day": payload.session_day,
        "session_label": payload.session_label.strip(),
        "completed": bool(payload.completed),
        "created_at": created_at,
    }


# ── Ler o cardio de uma janela ──────────────────────────────────────────────────────
#
# O numero que a maquina mostra
# -----------------------------
# A esteira diz "412 kcal". Esse numero e otimista por duas razoes conhecidas: ele e
# BRUTO, ou seja, inclui o que a pessoa gastaria sentada no mesmo tempo, e sai de uma
# formula generica que nao sabe o peso real nem a composicao de quem esta em cima dela.
# Erros de 20% a 30% para cima sao a regra, nao a excecao.
#
# Por isso o campo se chama `kcal_reported` e nunca e corrigido sozinho: corrigir exigiria
# um fator inventado. O numero que nao mente e a balanca, e quem le a balanca e o Conselho.
#
# O que o cardio E, no motor
# --------------------------
# Nao e credito de comida. O alvo calorico ja nasce de um TDEE que multiplica o BMR por um
# fator de atividade (1,1 a 1,55) mais um acrescimo pelos dias de treino: boa parte do
# gasto de cardio ja esta contada ali. Somar de novo o que o painel mostrou conta o mesmo
# gasto duas vezes, com um numero ja inflado.
#
# O cardio entra como ALAVANCA, em dois momentos: quando o resultado pede mais deficit e a
# comida ja esta no piso, e quando a perda esta rapida demais e a comida ja esta baixa.

# As modalidades que a tela oferece, na ordem. `modality` continua aceitando texto livre
# para nao invalidar o que ja foi gravado pelo finalizador de treino.
MODALITIES = ["Caminhada", "Esteira", "Bike", "Elíptico", "Escada", "Remo", "Corrida"]

# Abaixo disto a semana nao conta como "faz cardio": uma caminhada de 15 minutos num
# domingo nao e um habito que da para ajustar.
MINIMO_PARA_CONTAR = 30

# Acima disto, mandar fazer mais cardio para de ser conselho e vira desgaste: o custo de
# recuperacao come o treino, que e justamente o que o motor existe para proteger.
TETO_SEMANAL = 240

# Uma sessao a mais de 20 minutos e uma mudanca que da para cumprir e que ainda aparece na
# balanca em duas semanas.
PASSO_MINUTOS = 20


def cardio_reading(rows, janela_dias: int, hoje: CalendarDate = None) -> dict:
    """O cardio da janela virado em uma leitura por semana.

    Sao DOIS numeros de semana, e a diferenca importa:

      `minutos_na_semana`    o que foi feito na semana corrente. E o que a tela mostra
                             grande, porque e o que a pessoa reconhece: registrar 42
                             minutos e ler "10 min / semana" na mesma tela parece que o
                             aplicativo perdeu a sessao. Medido no navegador.

      `minutos_por_semana`   a media da janela inteira. E o que o Conselho usa, porque
                             uma semana solta nao e um habito, e o motor decide sobre
                             habito. Fica na linha de resumo, escrito como media.

    `kcal_reported` carrega a procedencia no proprio nome: quem ler este dicionario depois
    precisa saber que aquele numero veio do painel da maquina, e nao de uma medicao.
    """
    janela_dias = max(1, int(janela_dias or 1))
    hoje = hoje or CalendarDate.today()
    semana_atual = hoje.isocalendar()[:2]
    minutos = sum(int(r.get("minutes") or 0) for r in rows)
    kcal = sum(int(r.get("kcal_reported") or 0) for r in rows)
    por_semana = round(minutos / (janela_dias / 7.0))
    modalidades = []
    na_semana = 0
    for r in rows:
        m = (r.get("modality") or "").strip()
        if m and m not in modalidades:
            modalidades.append(m)
        try:
            dia = CalendarDate.fromisoformat(str(r.get("date") or "")[:10])
        except ValueError:
            continue
        if dia.isocalendar()[:2] == semana_atual:
            na_semana += int(r.get("minutes") or 0)
    return {
        "sessoes": len(rows),
        "minutos": minutos,
        "kcal_reported": kcal,
        "minutos_na_semana": na_semana,
        "minutos_por_semana": por_semana,
        "janela_dias": janela_dias,
        "modalidades": modalidades,
        # "faz cardio" e pergunta de habito, e por isso olha a media semanal.
        "faz_cardio": por_semana >= MINIMO_PARA_CONTAR,
        "cabe_mais": por_semana < TETO_SEMANAL,
    }


def cardio_step(minutos_por_semana, sentido: int):
    """A mudanca de cardio proposta, ja limitada pelo teto e pelo chao.

    Devolve None quando nao ha mudanca honesta a propor: somando, quando a pessoa ja esta
    no teto de desgaste; cortando, quando ela praticamente nao faz cardio e nao ha o que
    tirar.
    """
    atual = max(0, int(minutos_por_semana or 0))
    if sentido > 0:
        if atual >= TETO_SEMANAL:
            return None
        novo = min(TETO_SEMANAL, atual + PASSO_MINUTOS)
    elif sentido < 0:
        if atual < MINIMO_PARA_CONTAR:
            return None
        novo = max(0, atual - PASSO_MINUTOS)
    else:
        return None
    if novo == atual:
        return None
    return {"tipo": "cardio", "de": atual, "para": novo, "delta": novo - atual,
            "trava": "sem mexer na comida"}


def frase_de_cardio(leitura) -> str:
    """Como o cardio da semana e dito para o atleta, em uma frase."""
    leitura = leitura or {}
    if not leitura.get("sessoes"):
        return "você não registrou cardio"
    sessoes = leitura["sessoes"]
    plural = "sessões" if sessoes > 1 else "sessão"
    return (f"você registrou {sessoes} {plural} de cardio, "
            f"{leitura['minutos']} minutos no total")

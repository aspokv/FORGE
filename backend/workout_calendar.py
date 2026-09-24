"""Calendar selection only for fully labelled, unambiguous weekly programs."""
import re
import unicodedata
from contextvars import ContextVar

import troca_de_dia
from datetime import datetime, timedelta, timezone

# Browser offset (UTC minus local); legacy clients use Brasilia time.
browser_offset = ContextVar("forge_calendar_offset", default=180)
DAYS = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3,
        "sexta": 4, "sabado": 5, "domingo": 6}

def calendar_today():
    return datetime.now(timezone(timedelta(minutes=-browser_offset.get()))).date()

def weekly_sessions(sessions):
    mapped = {}
    for session in sessions:
        label = unicodedata.normalize("NFD", str(session.get("label") or "").lower())
        label = "".join(c for c in label if not unicodedata.combining(c))
        match = re.match(r"^\s*(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?(?=\s|[·:—–-]|$)", label)
        if not match or DAYS[match[1]] in mapped:
            return None
        mapped[DAYS[match[1]]] = session
    return mapped or None

def calendar_selection(sessions, today=None, after_today=False, trocas=None):
    """Que sessao e a de hoje, e qual e a proxima.

    `trocas` sao excecoes DATADAS: "o treino do dia X acontece no dia Y". Sem elas, o
    caminho e o de sempre — a agenda semanal, dia da semana por dia da semana. Com elas, a
    janela dos proximos dias e montada por DATA, porque troca fala de data e nao de dia da
    semana: quinta que vira treino e quinta desta semana, nao toda quinta.
    """
    mapped = weekly_sessions(sessions)
    if mapped is None:
        return None
    today = today or calendar_today()
    weekday = today.weekday()

    limpas = troca_de_dia.normalizar(trocas, today) if trocas else []
    if not limpas:
        current = mapped.get(weekday)
        offset = next(n for n in range(1 if after_today else 0, 8)
                      if (weekday + n) % 7 in mapped)
        return {"today": current, "next": mapped[(weekday + offset) % 7],
                "next_date": (today + timedelta(days=offset)).isoformat(),
                "weekdays": {str(s["day"]): w for w, s in mapped.items()}}

    # A janela vai para TRAS tambem, e isso nao e detalhe.
    #
    # Uma troca sobrevive enquanto qualquer uma das duas datas nao passou. Entao no dia em
    # que o atleta DESCANSA, a data em que ele ja treinou e passado — e se a janela
    # comecasse em hoje, a troca ficaria com uma ponta de fora e nao seria aplicada: o
    # sabado que ele adiantou para quinta voltaria a aparecer como treino no sabado.
    #
    # Cobrir o alcance para os dois lados garante que as duas pontas de qualquer troca viva
    # estao dentro da janela.
    dias = troca_de_dia.ALCANCE_EM_DIAS + 1
    janela = {(today + timedelta(days=n)).isoformat(): mapped.get((weekday + n) % 7)
              for n in range(-troca_de_dia.ALCANCE_EM_DIAS, dias + 1)}
    ajustada = troca_de_dia.aplicar(janela, limpas, today)

    current = ajustada[today.isoformat()]
    proximo_n = next((n for n in range(1 if after_today else 0, dias + 1)
                      if ajustada[(today + timedelta(days=n)).isoformat()]), None)
    if proximo_n is None:
        # Janela inteira sem treino: cai na agenda do programa, para `next` nunca vir vazio.
        offset = next(n for n in range(1 if after_today else 0, 8)
                      if (weekday + n) % 7 in mapped)
        proximo, proxima_data = mapped[(weekday + offset) % 7], today + timedelta(days=offset)
    else:
        proximo = ajustada[(today + timedelta(days=proximo_n)).isoformat()]
        proxima_data = today + timedelta(days=proximo_n)

    return {"today": current, "next": proximo,
            "next_date": proxima_data.isoformat(),
            "weekdays": {str(s["day"]): w for w, s in mapped.items()},
            "trocas": limpas}

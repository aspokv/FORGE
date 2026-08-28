"""Pre-avaliacao do funil publico: perguntas curtas e previa deterministica.

Roda ANTES do pagamento, entao vale a pena dizer o que ela deliberadamente nao faz:

  - nao chama IA e nao chama nada pela rede. Tudo aqui e funcao pura sobre as respostas
    e sobre as regras que o motor ja usa (`determine_split`, `get_day_targets`,
    `FORGE_COACH_METHODOLOGY`). Duas pessoas com as mesmas respostas veem a mesma previa,
    e o custo de gerar e o de montar um dicionario;
  - nao monta treino nem dieta. Ela devolve a ESTRUTURA — quantos dias, como a semana se
    divide, que regioes caem em cada sessao, qual protocolo alimentar — e marca como
    bloqueado o conteudo que so existe depois do pagamento;
  - nao promete o que o plano nao inclui. A previa alimentar so aparece para quem tem a
    capacidade ALIMENTACAO; no Essencial ela e substituida por uma nota honesta.

Reusar `determine_split` em vez de reescrever a regra importa: se a previa dissesse
"Upper/Lower" e o motor entregasse PPL depois de pago, a venda teria sido feita com uma
informacao que o produto nao cumpre.
"""
from typing import Any, Dict, List, Optional

from billing_plans import ALIMENTACAO, PROTOCOLOS_AGRESSIVOS
from engine import determine_split, get_day_targets
from muscles import (
    DEFAULT_EMPHASIS_BY_SEX, FRONTEND_MUSCLES, MAX_PRIORITIES, MUSCLE_GROUPS, to_frontend,
)
from nutrition_engine import FORGE_COACH_METHODOLOGY as METODOLOGIA

VERSAO = 1

# ── Catalogo das perguntas ───────────────────────────────────────────────────────────
# Curto de proposito: seis perguntas antes do pagamento, nao um questionario inteiro.
# O questionario completo continua existindo depois, e nao repete o que foi respondido
# aqui.

SEXOS = [
    {"id": "female", "label": "Feminino"},
    {"id": "male", "label": "Masculino"},
]

EXPERIENCIAS = [
    {"id": "Iniciante", "label": "Iniciante",
     "description": "Menos de 1 ano treinando, ou voltando depois de muito tempo."},
    {"id": "Intermediário", "label": "Intermediário",
     "description": "Treina com regularidade há 1 a 3 anos."},
    {"id": "Avançado", "label": "Avançado",
     "description": "Mais de 3 anos consistentes, com controle de carga e progressão."},
]

DIAS_DISPONIVEIS = [2, 3, 4, 5, 6]

OBJETIVOS_DE_TREINO = [
    {"id": "Hipertrofia", "label": "Ganhar músculo"},
    {"id": "Força", "label": "Ganhar força"},
    {"id": "Resistência", "label": "Condicionamento"},
]

# Os alvos do motor sao musculos individuais ("mid_chest", "rear_delts"). Na previa eles
# viram GRUPOS: "Peitoral, Costas, Ombros, Braços" diz o que a sessao trabalha sem
# entregar a composicao do treino, e cabe na tela — a lista crua tem nove itens por dia.
ROTULO_DO_GRUPO = {
    "CHEST": "Peitoral", "BACK": "Costas", "SHOULDERS": "Ombros", "ARMS": "Braços",
    "LEGS": "Pernas", "CORE": "Core",
}

GRUPO_DO_MUSCULO = {m: g for g, ms in MUSCLE_GROUPS.items() for m in ms}

NOME_DO_SPLIT = {
    "full_body": "Corpo inteiro",
    "upper_lower": "Superior / Inferior",
    "ppl": "Push / Pull / Legs",
    "ul_ppl": "Superior-Inferior + Push/Pull/Legs",
    "upper_lower_ppl": "Superior / Inferior + Push/Pull/Legs",
}


def catalogo(capacidades: Optional[set] = None) -> Dict[str, Any]:
    """Tudo que a tela precisa para montar as perguntas, numa chamada so.

    Recebe as capacidades porque as perguntas de alimentacao nao devem sequer aparecer
    para quem escolheu o Essencial: perguntar e depois nao entregar seria pior do que
    nao perguntar."""
    caps = set(capacidades or ())
    inclui_alimentacao = ALIMENTACAO in caps
    permite_agressivo = PROTOCOLOS_AGRESSIVOS in caps

    return {
        "version": VERSAO,
        "sexes": SEXOS,
        "experiences": EXPERIENCIAS,
        "days": DIAS_DISPONIVEIS,
        "training_goals": OBJETIVOS_DE_TREINO,
        "regions": list(FRONTEND_MUSCLES),
        "max_priorities": MAX_PRIORITIES,
        "includes_nutrition": inclui_alimentacao,
        "body_goals": _objetivos_alimentares(permite_agressivo) if inclui_alimentacao else [],
    }


def _objetivos_alimentares(permite_agressivo: bool) -> List[Dict[str, Any]]:
    conjuntos = {"muscle_gain": "bulking_intensity", "fat_loss": "cutting_intensity"}
    padroes = {"muscle_gain": METODOLOGIA["bulking_intensity_default"],
               "fat_loss": METODOLOGIA["cutting_intensity_default"]}
    saida = []
    for g in METODOLOGIA["body_goals"]:
        conjunto = conjuntos.get(g["id"])
        opcoes = []
        if conjunto:
            for chave, cfg in METODOLOGIA[conjunto].items():
                avancado = bool(cfg.get("advanced"))
                # Ritmo agressivo e do Elite. Aparece marcado como bloqueado em vez de
                # sumir: esconder faria a pessoa achar que o produto nao tem, quando na
                # verdade ela e que nao escolheu o plano que tem.
                opcoes.append({
                    "id": chave, "label": cfg["label"], "description": cfg["description"],
                    "recommended": bool(cfg.get("recommended")),
                    "advanced": avancado,
                    "locked": avancado and not permite_agressivo,
                    "delta_pct": round((cfg["kcal_pct"] - 1) * 100),
                })
        saida.append({**{k: v for k, v in g.items()},
                      "default_intensity": padroes.get(g["id"]),
                      "intensities": opcoes})
    return saida


# ── Normalizacao das respostas ───────────────────────────────────────────────────────

class RespostaInvalida(ValueError):
    """Resposta fora do catalogo. Carrega o campo para a tela apontar onde corrigir."""

    def __init__(self, campo: str, mensagem: str):
        super().__init__(mensagem)
        self.campo = campo
        self.mensagem = mensagem


def _um_de(valor, permitidos, campo, mensagem):
    if valor not in permitidos:
        raise RespostaInvalida(campo, mensagem)
    return valor


def normalizar(respostas: Dict[str, Any], capacidades: Optional[set] = None) -> Dict[str, Any]:
    """Valida contra o catalogo e devolve o documento que sera guardado.

    A validacao e do servidor, e nao um espelho da tela: o navegador pode mandar
    "agressivo" sem ter o plano que inclui, e e aqui que isso para."""
    r = dict(respostas or {})
    caps = set(capacidades or ())

    sexo = _um_de(r.get("sex"), {s["id"] for s in SEXOS},
                  "sex", "Escolha o perfil feminino ou masculino.")
    experiencia = _um_de(r.get("experience"), {e["id"] for e in EXPERIENCIAS},
                         "experience", "Escolha seu nível de experiência.")
    objetivo = _um_de(r.get("goal") or "Hipertrofia", {g["id"] for g in OBJETIVOS_DE_TREINO},
                      "goal", "Escolha seu objetivo de treino.")
    try:
        dias = int(r.get("days"))
    except (TypeError, ValueError):
        raise RespostaInvalida("days", "Escolha quantos dias por semana você treina.")
    if dias not in DIAS_DISPONIVEIS:
        raise RespostaInvalida("days", "Escolha quantos dias por semana você treina.")

    # Nenhuma prioridade e uma resposta valida: significa treino equilibrado.
    prioridades = [p for p in (r.get("priorities") or []) if p in FRONTEND_MUSCLES]
    if len(prioridades) > MAX_PRIORITIES:
        raise RespostaInvalida(
            "priorities", f"Escolha no máximo {MAX_PRIORITIES} regiões.")
    # Sem perder a ordem, que e o que define principal x secundaria.
    vistas, ordenadas = set(), []
    for p in prioridades:
        if p not in vistas:
            vistas.add(p)
            ordenadas.append(p)

    doc = {
        "version": VERSAO,
        "sex": sexo,
        "experience": experiencia,
        "goal": objetivo,
        "days": dias,
        "priorities": ordenadas,
    }

    if ALIMENTACAO in caps:
        objetivo_corporal = _um_de(
            r.get("body_goal") or "muscle_gain",
            {g["id"] for g in METODOLOGIA["body_goals"]},
            "body_goal", "Escolha seu objetivo alimentar.")
        doc["body_goal"] = objetivo_corporal
        conjunto = {"muscle_gain": "bulking_intensity",
                    "fat_loss": "cutting_intensity"}.get(objetivo_corporal)
        if conjunto:
            padrao = METODOLOGIA[f"{conjunto}_default"]
            ritmo = r.get("goal_intensity") or padrao
            cfg = METODOLOGIA[conjunto].get(ritmo)
            if cfg is None:
                raise RespostaInvalida("goal_intensity", "Escolha um ritmo válido.")
            if cfg.get("advanced") and PROTOCOLOS_AGRESSIVOS not in caps:
                raise RespostaInvalida(
                    "goal_intensity",
                    "O ritmo agressivo faz parte do FORGE Elite. Escolha outro ritmo ou "
                    "troque de plano.")
            doc["goal_intensity"] = ritmo

    return doc


# ── Previa ───────────────────────────────────────────────────────────────────────────

def _regioes_da_sessao(alvos: List[str]) -> List[str]:
    """Grupos musculares da sessao, na ordem em que o motor os lista, sem repetir."""
    nomes, vistos = [], set()
    for a in alvos:
        grupo = GRUPO_DO_MUSCULO.get(a)
        nome = ROTULO_DO_GRUPO.get(grupo) if grupo else None
        if nome is None:
            # Alvo que nao pertence a nenhum grupo conhecido: melhor mostrar o nome que a
            # interface ja usa do que um identificador interno em ingles.
            nome = to_frontend(a) or a.replace("_", " ").capitalize()
        if nome not in vistos:
            vistos.add(nome)
            nomes.append(nome)
    return nomes


def _semana(dias: int, experiencia: str, objetivo: str) -> Dict[str, Any]:
    split = determine_split(dias, experiencia, objetivo)
    sessoes = []
    for i in range(dias):
        rotulo, alvos = get_day_targets(split, i, dias)
        sessoes.append({
            "label": rotulo,
            "regions": _regioes_da_sessao(list(alvos)),
            # O conteudo e o que fica do outro lado do pagamento.
            "locked": True,
        })
    return {"split": split, "split_label": NOME_DO_SPLIT.get(split, split),
            "sessions": sessoes, "days": dias}


def _foco(prioridades: List[str], sexo: str) -> Dict[str, Any]:
    if prioridades:
        return {
            "declared": True,
            "regions": [{"region": p, "rank": i + 1,
                         "role": "Principal" if i == 0 else "Secundária"}
                        for i, p in enumerate(prioridades)],
            "note": "Suas prioridades recebem mais volume semanal.",
        }
    # Sem prioridade declarada o motor usa a enfase padrao do perfil. Dizer isso e mais
    # util do que mostrar um espaco vazio.
    padrao = DEFAULT_EMPHASIS_BY_SEX.get(sexo, [])
    return {
        "declared": False,
        "regions": [{"region": to_frontend(m), "rank": i + 1, "role": "Sugerida"}
                    for i, m in enumerate(padrao)],
        "note": ("Você não priorizou nenhuma região: o FORGE distribui o volume de forma "
                 "equilibrada, com a ênfase típica do seu perfil."),
    }


def _alimentacao(doc: Dict[str, Any], caps: set) -> Dict[str, Any]:
    if ALIMENTACAO not in caps:
        # Nao prometer o que o plano nao inclui. A nota diz o que existe, sem fingir que
        # o Essencial entrega alimentacao.
        return {
            "included": False,
            "note": ("O FORGE Essencial cobre treino, progressão e histórico. O plano "
                     "alimentar faz parte do Pro e do Elite."),
        }

    objetivo = doc.get("body_goal")
    rotulo_objetivo = next((g["label"] for g in METODOLOGIA["body_goals"]
                            if g["id"] == objetivo), objetivo)
    conjunto = {"muscle_gain": "bulking_intensity",
                "fat_loss": "cutting_intensity"}.get(objetivo)
    protocolo = None
    if conjunto and doc.get("goal_intensity"):
        cfg = METODOLOGIA[conjunto][doc["goal_intensity"]]
        protocolo = {
            "intensity": doc["goal_intensity"],
            "intensity_label": cfg["label"],
            "delta_pct": round((cfg["kcal_pct"] - 1) * 100),
            "protein_g_per_kg": cfg["protein_g_per_kg"],
            "carb_range_g": ([cfg["carb_min_g"], cfg["carb_max_g"]]
                             if cfg.get("carb_mode") == "capped" else None),
        }
    return {
        "included": True,
        "body_goal": objetivo,
        "body_goal_label": rotulo_objetivo,
        "protocol": protocolo,
        # As metas exatas dependem de peso, altura e idade, que o questionario completo
        # pergunta depois de pagar. Prometer numeros agora seria inventar.
        "locked": True,
        "note": ("Suas metas de calorias e macros são calculadas com seu peso e altura "
                 "no questionário completo."),
    }


def montar_previa(doc: Dict[str, Any], capacidades: set, plano: Optional[Dict[str, Any]] = None
                  ) -> Dict[str, Any]:
    """Previa deterministica a partir das respostas ja normalizadas."""
    caps = set(capacidades or ())
    semana = _semana(doc["days"], doc["experience"], doc["goal"])
    foco = _foco(doc.get("priorities") or [], doc.get("sex"))

    return {
        "version": VERSAO,
        "plan_code": (plano or {}).get("code"),
        "plan_name": (plano or {}).get("nome"),
        "headline": _titulo(doc, semana),
        "training": semana,
        "focus": foco,
        "nutrition": _alimentacao(doc, caps),
        # A tela usa isto para decidir o que borrar. O servidor manda o estado; a tela
        # nao inventa bloqueio nem o remove.
        "locked": True,
        "cta": "Ativar meu plano e liberar o FORGE",
    }


def _titulo(doc: Dict[str, Any], semana: Dict[str, Any]) -> str:
    experiencia = doc["experience"].lower()
    return (f"Um plano {semana['split_label']} de {doc['days']} dias por semana, "
            f"ajustado para quem treina em nível {experiencia}.")

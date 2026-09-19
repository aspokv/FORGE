# -*- coding: utf-8 -*-
"""Metadado do Hybrid Training Engine: região, demanda de bíceps, estresse articular.

Por que DERIVAR e não cadastrar
--------------------------------
A especificação do Hybrid pede campos `region`, `bicepsDemand` e `jointStress` em cada
exercício. Quase tudo isso já existe no catálogo, com outro nome:

    clavicular / esternal   ->  primary_muscle upper_chest / mid_chest
    width                   ->  movement_pattern vertical_pull, shoulder_extension
    thickness               ->  movement_pattern horizontal_pull
    kneeDominant            ->  squat, lunge, knee_extension
    hipDominant             ->  hip_hinge, hip_extension
    hamstringCurl           ->  knee_flexion
    calves                  ->  plantar_flexion

Cadastrar um campo `region` em 134 exercícios duplicaria essa informação, e duas fontes
que podem divergir é exatamente como um catálogo ganha um defeito que ninguém percebe:
alguém edita `movement_pattern` e esquece `region`, e a partir daí o motor e a tela
discordam sobre o mesmo exercício.

Então há UMA função por conceito. Ela lê um campo explícito quando ele existe, e deriva no
resto. O campo explícito é a saída de emergência para o caso que a derivação não fecha, e
não o caminho padrão.

O único caso que não fecha
--------------------------
Peitoral costal (inferior). Os três exercícios existem — `dip`, `bb-decline-press`,
`db-decline-press` — e todos estão como `mid_chest`. `bb-decline-press` compartilha
`horizontal_press` com `bb-bench-press`, então não há par (músculo, padrão) que separe os
dois. Esses três recebem `region` explícito em `REGIAO_EXPLICITA`, que é um mapa aqui e
não uma edição em `exercises.json` — assim a exceção fica visível, com o motivo escrito ao
lado, em vez de virar três linhas soltas num JSON de 134 entradas.
"""
from typing import Any, Dict, Optional

# ── Regiões ─────────────────────────────────────────────────────────────────────────

# Peitoral
CLAVICULAR = "clavicular"
ESTERNAL = "sternal"
COSTAL = "costal"

# Costas
LARGURA = "width"                  # puxada vertical e extensão de ombro
ESPESSURA = "thickness"            # remadas horizontais
TRAPEZIO = "traps"

# Pernas
JOELHO = "knee_dominant"
QUADRIL = "hip_dominant"
FLEXAO_DE_JOELHO = "hamstring_curl"
PANTURRILHA = "calves"
ADUTORES = "adductors"

# Os três que a derivação não separa, com o motivo ao lado de cada um.
REGIAO_EXPLICITA: Dict[str, str] = {
    # Declinado divide `horizontal_press` com o supino reto: o padrão não distingue.
    "bb-decline-press": COSTAL,
    "db-decline-press": COSTAL,
    # Paralelas são `vertical_press` em `mid_chest`, o mesmo par do desenvolvimento se
    # alguém cadastrar um. O vetor é para baixo, e é isso que faz delas costal.
    "dip": COSTAL,
}

_POR_PADRAO_DE_COSTAS = {
    "vertical_pull": LARGURA,
    "shoulder_extension": LARGURA,
    "horizontal_pull": ESPESSURA,
    "elevation": TRAPEZIO,
}

_POR_PADRAO_DE_PERNA = {
    "squat": JOELHO,
    "lunge": JOELHO,
    "knee_extension": JOELHO,
    "hip_hinge": QUADRIL,
    "hip_extension": QUADRIL,
    "knee_flexion": FLEXAO_DE_JOELHO,
    "plantar_flexion": PANTURRILHA,
    "adduction": ADUTORES,
    "high_adduction": ADUTORES,
    # Cadeira abdutora é glúteo médio, quadril. Sem esta linha ela caía no default e o
    # motor a oferecia como se fosse dominante de joelho — apareceu numa sessão gerada de
    # verdade, ao lado de agachamento e extensora.
    "abduction": QUADRIL,
}

_COSTAS = {"lats", "upper_back", "traps"}
_PERNAS = {"quads", "hamstrings", "glutes", "adductors", "calves"}


def regiao_de(exercicio: Dict[str, Any]) -> str:
    """A região que o Hybrid usa para rotacionar vetor, e não só músculo.

    Devolve sempre alguma coisa: para os grupos que não têm subdivisão útil (deltoides,
    braços, abdômen) a região é o próprio músculo, o que deixa a rotação funcionar sem
    um caso especial em quem chama.
    """
    eid = exercicio.get("id")
    if eid in REGIAO_EXPLICITA:
        return REGIAO_EXPLICITA[eid]
    # Um `region` gravado no próprio exercício ainda vence a derivação: se um dia o
    # catálogo ganhar o campo, este módulo já o respeita sem precisar mudar.
    gravado = exercicio.get("region")
    if gravado:
        return str(gravado)

    musculo = exercicio.get("primary_muscle") or ""
    padrao = exercicio.get("movement_pattern") or ""

    if musculo == "upper_chest":
        return CLAVICULAR
    if musculo == "mid_chest":
        return ESTERNAL
    if musculo in _COSTAS:
        return _POR_PADRAO_DE_COSTAS.get(padrao, ESPESSURA)
    if musculo in _PERNAS:
        return _POR_PADRAO_DE_PERNA.get(padrao, JOELHO)
    return musculo


# ── Demanda de bíceps ───────────────────────────────────────────────────────────────
#
# O catálogo não tem campo de pegada. Ela está espalhada em dois lugares: nos ids
# (`supinated-*`, `neutral-*`, que é a nomenclatura do próprio FORGE) e nos nomes
# ("triângulo", "neutra", "martelo"). Ler só o id parecia mais limpo — id não muda quando
# alguém reescreve o texto — mas deixava todas as remadas como demanda média ou alta, e a
# restrição de tendão passava a apagar o vetor de espessura inteiro. Então lê os dois, e
# os testes prendem exercício por exercício para um rename não passar despercebido.

ALTA = "high"
MEDIA = "medium"
BAIXA = "low"

# Rosca com o braço ATRÁS da linha do corpo, ou com o cotovelo à frente e o ombro em
# extensão: o bíceps entra alongado sob carga, que é a posição que dói em quem tem o
# tendão sensível. Isto é conhecimento de execução, não algo que o catálogo saiba.
_ROSCA_ALONGADA = {"incline-db-curl", "bayesian-curl", "spider-curl"}

# A pegada está em dois lugares no catálogo, e não em um: `supinated-pulldown` guarda no
# id, `cable-row` ("Remada baixa triângulo na polia") guarda no nome. Ignorar o nome
# deixava TODAS as remadas como demanda média ou alta, e aí a restrição de tendão apagaria
# o vetor de espessura inteiro em vez de trocar um exercício. Foi um teste que mostrou.
_PEGADA_SUPINADA = ("supinated-",)
_PEGADA_NEUTRA = ("neutral-", "hammer")
_NOME_NEUTRO = ("triângulo", "triangulo", "neutra", "martelo")
# Remada com o peito apoiado tira o tronco da conta e reduz a puxada de braço; a máquina
# de remada do FORGE é apoiada, e isso não aparece em nenhum campo.
_APOIADO = {"row"}


def demanda_de_biceps(exercicio: Dict[str, Any]) -> str:
    """Quanto este exercício cobra do bíceps e do tendão distal.

    Serve à restrição `bicepsTendonSensitivity`, que é preferência e penalidade, e não
    lista de proibição: o motor baixa a pontuação desses movimentos em vez de apagá-los
    do catálogo.
    """
    gravado = exercicio.get("biceps_demand") or exercicio.get("bicepsDemand")
    if gravado:
        return str(gravado)

    eid = str(exercicio.get("id") or "")
    nome = str(exercicio.get("name") or "").lower()
    musculo = exercicio.get("primary_muscle") or ""
    padrao = exercicio.get("movement_pattern") or ""
    neutro = (any(p in eid for p in _PEGADA_NEUTRA)
              or any(p in nome for p in _NOME_NEUTRO))

    if eid in _ROSCA_ALONGADA:
        return ALTA
    if musculo == "biceps":
        # Martelo e corda mantêm o antebraço neutro, que é a posição confortável.
        return BAIXA if neutro else MEDIA
    if padrao in ("vertical_pull", "horizontal_pull"):
        if eid.startswith(_PEGADA_SUPINADA):
            return ALTA
        if neutro or eid in _APOIADO:
            return BAIXA
        return MEDIA
    if "biceps" in (exercicio.get("secondary_muscles") or []):
        return MEDIA
    return BAIXA


# ── Estresse articular ──────────────────────────────────────────────────────────────

def estresse_articular(exercicio: Dict[str, Any]) -> str:
    """Quanto o movimento cobra da articulação, derivado do que o catálogo já sabe.

    `stability` e `fatigue` juntos descrevem isso melhor do que um campo novo: um
    movimento livre e pesado cobra articulação, um movimento guiado e leve não. A
    máquina articulada existe justamente para tirar a estabilização do atleta.
    """
    gravado = exercicio.get("joint_stress") or exercicio.get("jointStress")
    if gravado:
        return str(gravado)

    estabilidade = exercicio.get("stability") or "medium"
    fadiga = exercicio.get("fatigue") or "medium"
    equipamento = set(exercicio.get("equipment") or [])
    guiado = bool(equipamento & {"machine", "cable", "smith_machine"})

    # Fadiga sistêmica NÃO é estresse articular, e a primeira versão disto confundia as
    # duas: o leg press é `fatigue=high` com `stability=high`, ou seja, cansa muito e cobra
    # pouco da articulação, e mesmo assim saía como médio. Quem manda aqui é a
    # estabilidade, porque é ela que diz quanto da carga a articulação precisa segurar.
    if estabilidade == "low" and fadiga == "high":
        return ALTA
    if guiado and estabilidade != "low":
        return BAIXA
    if estabilidade == "low":
        return MEDIA
    return MEDIA if fadiga == "high" else BAIXA


def metadados_de(exercicio: Dict[str, Any]) -> Dict[str, str]:
    """Os três de uma vez, no formato que o motor consome."""
    return {
        "region": regiao_de(exercicio),
        "biceps_demand": demanda_de_biceps(exercicio),
        "joint_stress": estresse_articular(exercicio),
    }

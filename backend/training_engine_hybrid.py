# -*- coding: utf-8 -*-
"""FORGE Hybrid Training Engine — alta frequência com rotação de vetor.

O que muda em relação ao resto do motor
---------------------------------------
O FORGE monta a semana assim: uma divisão (`split_type`) diz quais MÚSCULOS caem em cada
dia, e a seleção escolhe exercícios para esses músculos. Isso é suficiente até cinco dias.
Em seis ou sete, a mesma lista de músculos volta duas ou três vezes na semana, e a divisão
por músculo passa a produzir a mesma sessão repetida — hoje `compatible_splits` devolve
Push/Pull/Legs para 6 e para 7 dias, ou seja, PPL duas vezes.

O Hybrid troca a unidade de planejamento: em vez de MÚSCULO por dia, ele planeja VETOR por
dia. Peitoral não aparece três vezes — aparece como clavicular, depois esternal, depois
costal. Costas não aparecem três vezes — aparecem como largura, espessura e mista. É isso
que permite frequência alta sem repetir o mesmo estímulo.

E troca a unidade de volume: cada vetor entra num ROLE.

    PRIMARY     2 a 3 exercícios, o grosso do volume do grupo naquele dia
    SECONDARY   1 a 2 exercícios, volume moderado
    MICRODOSE   1 exercício, 1 a 2 séries, RIR mais alto

O role é o que separa "peitoral tem cinco exposições na semana" de "cinco treinos de peito
por semana". Sem ele, alta frequência vira alto volume, que é como a maioria dos programas
de 6x quebra a recuperação de quem os segue.

O que este módulo NÃO faz
-------------------------
Periodização, progressão, recuperação, cargas e substituições continuam do `engine`. Este
módulo não reimplementa nada disso: ele instala por cima, do mesmo jeito que o v4 e o v5
já fazem, e delega ao construtor anterior toda divisão que não seja híbrida. PPL,
Upper/Lower, ABC, programas femininos e programas salvos passam por aqui sem tocar em
nenhuma linha nova.
"""
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from hybrid_metadata import (
    ALTA, BAIXA, CLAVICULAR, COSTAL, ESPESSURA, ESTERNAL, FLEXAO_DE_JOELHO, JOELHO,
    LARGURA, MEDIA, QUADRIL, demanda_de_biceps, regiao_de,
)

# ── Roles ───────────────────────────────────────────────────────────────────────────

PRIMARY = "primary"
SECONDARY = "secondary"
MICRODOSE = "microdose"

ROLES = (PRIMARY, SECONDARY, MICRODOSE)

ROTULO_DO_ROLE = {
    PRIMARY: "Principal",
    SECONDARY: "Complementar",
    MICRODOSE: "Microdose",
}

# Quantas séries cada role vale, e com quanta folga de esforço. A microdose é o número
# que faz a alta frequência caber: uma série ou duas, longe da falha, para o músculo ser
# ESTIMULADO sem cobrar recuperação.
SERIES_POR_ROLE = {PRIMARY: (3, 4), SECONDARY: (2, 3), MICRODOSE: (1, 2)}
RIR_POR_ROLE = {PRIMARY: "1–3", SECONDARY: "1–3", MICRODOSE: "2–4"}

# ── Vetores ─────────────────────────────────────────────────────────────────────────
#
# Um slot mira um VETOR, que é uma região quando o grupo tem subdivisão útil (peito,
# costas, pernas) e o próprio músculo quando não tem (deltoides, braços, panturrilha).

MISTO_DE_COSTAS = "back_mixed"          # um vertical e um horizontal na mesma sessão
MISTO_DE_PERNA = "legs_mixed"           # joelho e quadril na mesma sessão

VETORES_COMPOSTOS = {
    MISTO_DE_COSTAS: (LARGURA, ESPESSURA),
    MISTO_DE_PERNA: (JOELHO, QUADRIL),
}


# Como cada vetor aparece na tela. `focus` é lido pelo atleta, então ele não pode receber
# nem `knee_dominant` nem o nome do músculo quando o que muda é a região.
ROTULO_DO_VETOR = {
    CLAVICULAR: "Peitoral superior",
    ESTERNAL: "Peitoral esternal",
    COSTAL: "Peitoral inferior",
    LARGURA: "Costas / largura",
    ESPESSURA: "Costas / espessura",
    JOELHO: "Quadríceps",
    QUADRIL: "Posteriores e glúteos",
    FLEXAO_DE_JOELHO: "Flexão de joelho",
    "back_mixed": "Costas completas",
    "legs_mixed": "Pernas completas",
}


def _slot(vetor: str, role: str, quantos: int = 1) -> Dict[str, Any]:
    return {"vetor": vetor, "role": role, "quantos": quantos}


# ── As cinco arquiteturas ───────────────────────────────────────────────────────────
#
# Cada dia declara rótulo, demanda e slots. A demanda já existe no motor (HIGH / MODERATE
# / LOW) e é o que a recuperação e a periodização leem, então as ondas do HYBRID 05 e o
# dia leve do HYBRID 04 saem por ela, e não por um campo paralelo.

HYBRID_01 = "hybrid_01"
HYBRID_02 = "hybrid_02"
HYBRID_03 = "hybrid_03"
HYBRID_04 = "hybrid_04"
HYBRID_05 = "hybrid_05"

ARQUITETURAS: Dict[str, Dict[str, Any]] = {
    HYBRID_01: {
        "label": "Híbrido · Full / Upper / Lower rotacional",
        "resumo": "Seis sessões alternando corpo inteiro, superiores e inferiores, com o "
                  "peitoral e as costas girando de vetor a cada aparição.",
        "dias": 6,
        "sessoes": [
            {"label": "Full A", "demand": "HIGH", "slots": [
                _slot(CLAVICULAR, PRIMARY, 2), _slot(LARGURA, PRIMARY, 2),
                _slot(JOELHO, PRIMARY), _slot("side_delts", SECONDARY)]},
            {"label": "Upper A", "demand": "HIGH", "slots": [
                _slot(ESTERNAL, PRIMARY, 2), _slot(ESPESSURA, PRIMARY, 2),
                _slot("front_delts", SECONDARY), _slot("side_delts", SECONDARY),
                _slot("rear_delts", SECONDARY),
                _slot("triceps", SECONDARY), _slot("biceps", SECONDARY)]},
            {"label": "Lower A", "demand": "MODERATE", "slots": [
                _slot(JOELHO, PRIMARY, 2), _slot(QUADRIL, SECONDARY),
                _slot("adductors", SECONDARY), _slot("calves", SECONDARY)]},
            {"label": "Full B", "demand": "MODERATE", "slots": [
                _slot(COSTAL, PRIMARY, 2), _slot(ESPESSURA, PRIMARY, 2),
                _slot(QUADRIL, PRIMARY, 2), _slot("rear_delts", SECONDARY),
                _slot("abs", SECONDARY)]},
            {"label": "Upper B", "demand": "MODERATE", "slots": [
                _slot(CLAVICULAR, PRIMARY, 2), _slot(LARGURA, PRIMARY, 2),
                _slot("side_delts", SECONDARY), _slot("triceps", SECONDARY),
                _slot("biceps", SECONDARY)]},
            {"label": "Lower B", "demand": "LOW", "slots": [
                _slot(QUADRIL, PRIMARY, 2), _slot(FLEXAO_DE_JOELHO, PRIMARY),
                _slot("calves", SECONDARY), _slot("abs", SECONDARY)]},
        ],
    },
    HYBRID_02: {
        "label": "Híbrido · Peito + Quadríceps / Costas + Posterior",
        "resumo": "Seis sessões que alternam dois blocos: peitoral com quadríceps, e "
                  "costas com posterior. Cada bloco gira de vetor a cada volta.",
        "dias": 6,
        "sessoes": [
            {"label": "A1 · Clavicular + Quadríceps", "demand": "HIGH", "slots": [
                _slot(CLAVICULAR, PRIMARY, 3), _slot(JOELHO, PRIMARY),
                _slot("triceps", SECONDARY), _slot("front_delts", SECONDARY)]},
            {"label": "B1 · Largura + Posterior", "demand": "HIGH", "slots": [
                _slot(LARGURA, PRIMARY, 3), _slot(QUADRIL, PRIMARY, 2),
                _slot("biceps", SECONDARY), _slot("rear_delts", SECONDARY)]},
            {"label": "A2 · Esternal + Quadríceps", "demand": "MODERATE", "slots": [
                _slot(ESTERNAL, PRIMARY, 2), _slot(JOELHO, PRIMARY),
                _slot("triceps", SECONDARY), _slot("calves", SECONDARY),
                _slot("abs", SECONDARY)]},
            {"label": "B2 · Espessura + Posterior", "demand": "MODERATE", "slots": [
                _slot(ESPESSURA, PRIMARY, 3), _slot(FLEXAO_DE_JOELHO, PRIMARY, 2),
                _slot("biceps", SECONDARY), _slot("rear_delts", SECONDARY)]},
            {"label": "A3 · Costal + Quadríceps", "demand": "MODERATE", "slots": [
                _slot(COSTAL, PRIMARY, 2), _slot(JOELHO, PRIMARY, 2),
                _slot("adductors", SECONDARY), _slot("side_delts", SECONDARY)]},
            {"label": "B3 · Costas mistas + Posterior", "demand": "LOW", "slots": [
                _slot(MISTO_DE_COSTAS, PRIMARY, 2), _slot(QUADRIL, PRIMARY, 2),
                _slot("calves", SECONDARY)]},
        ],
    },
    HYBRID_03: {
        "label": "Híbrido · Upper / Lower com microdoses",
        "resumo": "Seis sessões de superiores e inferiores alternadas. Os dias de perna "
                  "carregam uma microdose de peitoral ou costas, que mantém a frequência "
                  "alta sem somar volume.",
        "dias": 6,
        "sessoes": [
            {"label": "Upper A", "demand": "HIGH", "slots": [
                _slot(CLAVICULAR, PRIMARY, 2), _slot(LARGURA, PRIMARY, 2),
                _slot("front_delts", SECONDARY), _slot("side_delts", SECONDARY),
                _slot("triceps", SECONDARY)]},
            {"label": "Lower A", "demand": "HIGH", "slots": [
                _slot(JOELHO, PRIMARY, 2), _slot(QUADRIL, SECONDARY),
                _slot("adductors", SECONDARY), _slot("calves", SECONDARY),
                _slot(ESTERNAL, MICRODOSE)]},
            {"label": "Upper B", "demand": "MODERATE", "slots": [
                _slot(ESTERNAL, PRIMARY, 2), _slot(ESPESSURA, PRIMARY, 2),
                _slot("rear_delts", SECONDARY), _slot("biceps", SECONDARY)]},
            {"label": "Lower B", "demand": "MODERATE", "slots": [
                _slot(QUADRIL, PRIMARY, 2), _slot(FLEXAO_DE_JOELHO, PRIMARY),
                _slot("calves", SECONDARY), _slot(LARGURA, MICRODOSE)]},
            {"label": "Upper C", "demand": "MODERATE", "slots": [
                _slot(COSTAL, PRIMARY, 2), _slot(MISTO_DE_COSTAS, PRIMARY, 2),
                _slot("triceps", SECONDARY), _slot("biceps", SECONDARY)]},
            {"label": "Lower C", "demand": "LOW", "slots": [
                _slot(MISTO_DE_PERNA, PRIMARY, 2), _slot("abs", SECONDARY),
                _slot(CLAVICULAR, MICRODOSE), _slot("side_delts", MICRODOSE)]},
        ],
    },
    HYBRID_04: {
        "label": "Híbrido · 7x Full / Upper / Lower",
        "resumo": "Sete sessões. As seis primeiras giram corpo inteiro, superiores e "
                  "inferiores; a sétima é obrigatoriamente leve, só com isoladores.",
        "dias": 7,
        "sessoes": [
            {"label": "Full A", "demand": "HIGH", "slots": [
                _slot(CLAVICULAR, PRIMARY, 2), _slot(LARGURA, PRIMARY, 2),
                _slot(JOELHO, PRIMARY), _slot("side_delts", SECONDARY)]},
            {"label": "Upper A", "demand": "HIGH", "slots": [
                _slot(ESTERNAL, PRIMARY, 2), _slot(ESPESSURA, PRIMARY, 2),
                _slot("front_delts", SECONDARY),
                _slot("triceps", SECONDARY), _slot("biceps", SECONDARY)]},
            {"label": "Lower A", "demand": "MODERATE", "slots": [
                _slot(JOELHO, PRIMARY, 2), _slot(QUADRIL, SECONDARY),
                _slot("adductors", SECONDARY), _slot("calves", SECONDARY)]},
            {"label": "Full B", "demand": "MODERATE", "slots": [
                _slot(COSTAL, PRIMARY, 2), _slot(ESPESSURA, PRIMARY, 2),
                _slot(QUADRIL, PRIMARY, 2), _slot("rear_delts", SECONDARY),
                _slot("abs", SECONDARY)]},
            {"label": "Upper B", "demand": "MODERATE", "slots": [
                _slot(CLAVICULAR, PRIMARY, 2), _slot(LARGURA, PRIMARY, 2),
                _slot("side_delts", SECONDARY), _slot("triceps", SECONDARY)]},
            {"label": "Lower B", "demand": "MODERATE", "slots": [
                _slot(QUADRIL, PRIMARY, 2), _slot(FLEXAO_DE_JOELHO, PRIMARY),
                _slot("calves", SECONDARY), _slot("abs", SECONDARY)]},
            # O sétimo dia é a razão de esta arquitetura existir separada da 01. Ele é
            # LOW e só de isolador: sete sessões sistêmicas seguidas não é frequência
            # alta, é dívida de recuperação com outro nome.
            {"label": "Full C · leve", "demand": "LOW", "so_isolador": True, "slots": [
                _slot(ESTERNAL, MICRODOSE), _slot(LARGURA, MICRODOSE),
                _slot("side_delts", MICRODOSE), _slot(JOELHO, MICRODOSE),
                _slot(FLEXAO_DE_JOELHO, MICRODOSE), _slot("triceps", MICRODOSE),
                _slot("biceps", MICRODOSE)]},
        ],
    },
    HYBRID_05: {
        "label": "Híbrido · High Frequency Wave",
        "resumo": "Sete sessões em onda de intensidade: duas pesadas, três médias e duas "
                  "leves. A onda é do VOLUME e da prioridade, não da proximidade da falha.",
        "dias": 7,
        "sessoes": [
            {"label": "Onda 1 · alta", "demand": "HIGH", "slots": [
                _slot(CLAVICULAR, PRIMARY, 3), _slot(JOELHO, PRIMARY, 2),
                _slot("front_delts", SECONDARY), _slot("triceps", SECONDARY)]},
            {"label": "Onda 2 · alta", "demand": "HIGH", "slots": [
                _slot(LARGURA, PRIMARY, 3), _slot(QUADRIL, PRIMARY, 2),
                _slot("biceps", SECONDARY)]},
            {"label": "Onda 3 · média", "demand": "MODERATE", "slots": [
                _slot(ESTERNAL, PRIMARY, 2), _slot(ESPESSURA, SECONDARY),
                _slot("side_delts", SECONDARY)]},
            {"label": "Onda 4 · média", "demand": "MODERATE", "slots": [
                _slot(ESPESSURA, PRIMARY, 2), _slot(FLEXAO_DE_JOELHO, PRIMARY),
                _slot("rear_delts", SECONDARY)]},
            {"label": "Onda 5 · média", "demand": "MODERATE", "slots": [
                _slot(COSTAL, PRIMARY, 2), _slot(MISTO_DE_PERNA, PRIMARY, 2),
                _slot("adductors", SECONDARY), _slot("abs", SECONDARY),
                _slot("calves", SECONDARY)]},
            {"label": "Onda 6 · leve", "demand": "LOW", "so_isolador": True, "slots": [
                _slot(CLAVICULAR, MICRODOSE), _slot(LARGURA, MICRODOSE),
                _slot("side_delts", MICRODOSE), _slot("biceps", MICRODOSE)]},
            {"label": "Onda 7 · leve", "demand": "LOW", "so_isolador": True, "slots": [
                _slot(ESTERNAL, MICRODOSE), _slot(ESPESSURA, MICRODOSE),
                _slot(JOELHO, MICRODOSE), _slot("triceps", MICRODOSE)]},
        ],
    },
}

TODAS = tuple(ARQUITETURAS)
DE_SEIS = tuple(k for k, v in ARQUITETURAS.items() if v["dias"] == 6)
DE_SETE = tuple(k for k, v in ARQUITETURAS.items() if v["dias"] == 7)


def e_hibrido(split_type: Optional[str]) -> bool:
    return split_type in ARQUITETURAS


def arquitetura_de(split_type: str) -> Dict[str, Any]:
    return ARQUITETURAS[split_type]


# ── Escolha automática ──────────────────────────────────────────────────────────────

def escolher_arquitetura(dias: int, experiencia: str, prioridades: Sequence[str],
                         preferencia: Optional[str] = None) -> Optional[str]:
    """Qual híbrido cabe neste atleta, sem obrigá-lo a entender os cinco.

    A preferência explícita vence, desde que caiba nos dias disponíveis: pedir um híbrido
    de sete dias treinando seis não é preferência, é um programa que não existe.
    """
    dias = int(dias or 0)
    if preferencia in ARQUITETURAS and ARQUITETURAS[preferencia]["dias"] == dias:
        return preferencia
    if dias not in (6, 7):
        return None

    prioridades = set(prioridades or [])
    peito = {"upper_chest", "mid_chest"} & prioridades
    costas = {"lats", "upper_back"} & prioridades

    if dias == 7:
        # A onda é modo experimental: ela só aparece para quem pediu, porque distribuir
        # a semana por intensidade exige leitura de recuperação que nem todo atleta faz.
        return HYBRID_04
    # Especialização declarada em peito ou costas cai na arquitetura que gira esses dois.
    if peito or costas:
        return HYBRID_02
    # Sem especialização, microdose é o que melhor aproveita seis dias.
    return HYBRID_03 if _avancado(experiencia) else HYBRID_01


def _avancado(experiencia: Optional[str]) -> bool:
    return str(experiencia or "").strip().lower() in (
        "avançado", "avancado", "advanced", "bodybuilder")


# ── Índice por vetor ────────────────────────────────────────────────────────────────

def _indice_por_vetor(exercicios: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    """De vetor para ids. Um exercício aparece na sua região E no seu músculo.

    Os dois são necessários: um slot de `clavicular` precisa da região, e um slot de
    `side_delts` precisa do músculo, porque deltoide lateral não tem subdivisão útil.
    """
    indice: Dict[str, List[str]] = {}
    for e in exercicios:
        for chave in {regiao_de(e), e.get("primary_muscle")}:
            if chave:
                indice.setdefault(chave, []).append(e["id"])
    return indice


def vetores_do_slot(vetor: str) -> Tuple[str, ...]:
    """Um vetor composto vira os vetores que ele mistura, na ordem."""
    return VETORES_COMPOSTOS.get(vetor, (vetor,))


# ── Instalação sobre o engine ───────────────────────────────────────────────────────

def install(engine):
    """Instala o Hybrid por cima do motor, como o v4 e o v5 já fazem.

    Toda divisão que NÃO for híbrida vai para o construtor anterior sem passar por
    nenhuma linha nova. É isso que garante que PPL, Upper/Lower, ABC, programas femininos
    e programas salvos continuem produzindo exatamente o que produziam.
    """
    if getattr(engine, "_HYBRID_ENGINE_INSTALLED", False):
        return engine

    base_build = engine.build_all_sessions
    base_compativeis = engine.compatible_splits
    base_alvos = engine.get_day_targets

    for chave, arq in ARQUITETURAS.items():
        engine.SPLIT_LABELS[chave] = arq["label"]

    indice = _indice_por_vetor(engine.EXERCISES)

    # ── Quais divisões cabem em 6 e 7 dias ──────────────────────────────────────────
    def compativeis(days: int, experience: str = "Intermediário") -> List[str]:
        """As divisões que cabem nos dias disponíveis, com as híbridas DEPOIS das antigas.

        A ordem não é estética. `determine_split` usa `options[0]` como padrão de quem não
        tem preferência gravada, e a maioria dos perfis não tem: o formulário nasce com
        `split_preference` vazio. Pondo as híbridas primeiro, todo atleta de seis dias
        abriria o aplicativo amanhã com outro programa, no meio do ciclo, sem ter pedido —
        o que é exatamente "quebrar programa salvo".

        Então elas entram na lista, ficam selecionáveis e podem ser escolhidas
        automaticamente por `escolher_arquitetura`, mas não sequestram o padrão de quem já
        está treinando.
        """
        anteriores = base_compativeis(days, experience)
        days = max(1, min(7, int(days or 3)))
        if days == 6:
            return anteriores + list(DE_SEIS)
        if days == 7:
            return anteriores + list(DE_SETE) + list(DE_SEIS)
        return anteriores

    # ── Os músculos de cada dia, para tudo que já lê isso ───────────────────────────
    def alvos_do_dia(split_type: str, day_index: int, days: int):
        """O resto do FORGE pergunta "quais músculos caem neste dia" e recebe uma lista.

        O Hybrid planeja por vetor, mas responde essa pergunta na mesma moeda de antes,
        senão o relatório de volume, o validador e a tela de foco parariam de entender as
        sessões híbridas.
        """
        if not e_hibrido(split_type):
            return base_alvos(split_type, day_index, days)
        sessoes = ARQUITETURAS[split_type]["sessoes"]
        dia = sessoes[day_index % len(sessoes)]
        musculos: List[str] = []
        for slot in dia["slots"]:
            for vetor in vetores_do_slot(slot["vetor"]):
                for eid in indice.get(vetor, []):
                    m = engine.EXERCISE_INDEX[eid].get("primary_muscle")
                    if m and m not in musculos:
                        musculos.append(m)
                    break
        return dia["label"], musculos

    # ── A semana híbrida ────────────────────────────────────────────────────────────
    def construir(profile, split_type, days, session_minutes,
                  block_type=None, recovery_data=None):
        """Monta a semana. Divisão não-híbrida vai inteira para o construtor anterior.

        Essa primeira linha é o que garante que PPL, Upper/Lower, ABC, os programas
        femininos e todo programa já salvo continuem saindo exatamente como saíam: eles
        não passam por nenhuma linha deste módulo.
        """
        if not e_hibrido(split_type):
            return base_build(profile, split_type, days, session_minutes,
                              block_type=block_type, recovery_data=recovery_data)

        arq = ARQUITETURAS[split_type]
        bloco = block_type or (profile.get("periodization") or {}).get(
            "block_type", "accumulation")
        vol_mod, rir_base, override_rir = engine._compute_block_modifier(bloco)
        recuperacao = (recovery_data or {}).get("level", "NORMAL")
        sensivel = sensibilidade_de_biceps(profile)
        com_dor = doloridos(profile)

        usados_na_semana: Dict[str, int] = {}
        padroes: Dict[str, List[str]] = {}
        ultimos_do_vetor: Dict[str, Set[str]] = {}
        sessoes: List[Dict[str, Any]] = []

        for i, dia in enumerate(arq["sessoes"][:days]):
            demanda = dia["demand"]
            so_isolador = bool(dia.get("so_isolador"))
            usados_hoje: Set[str] = set()
            itens: List[Dict[str, Any]] = []

            for slot in dia["slots"]:
                for eid in _escolher(engine, slot, profile, indice, demanda, so_isolador,
                                     usados_hoje, usados_na_semana, padroes, sensivel,
                                     com_dor, ultimos_do_vetor):
                    itens.append(prescrever(engine, eid, slot["role"], demanda, profile,
                                            vol_mod, rir_base, override_rir, recuperacao))

            # Fecha o dia: o que cada vetor levou hoje passa a ser "a sessão anterior"
            # dele. Só os vetores tocados hoje viram a página — um vetor que não apareceu
            # continua guardando a última vez em que apareceu de verdade.
            for chave in [k for k in ultimos_do_vetor if k.startswith("__novo__")]:
                ultimos_do_vetor[chave[len("__novo__"):]] = ultimos_do_vetor.pop(chave)

            foco = []
            for slot in dia["slots"]:
                if slot["role"] == PRIMARY:
                    for vetor in vetores_do_slot(slot["vetor"]):
                        rotulo = ROTULO_DO_VETOR.get(vetor) or engine.to_frontend(vetor)
                        if rotulo not in foco:
                            foco.append(rotulo)

            sessoes.append({
                "day": i + 1,
                "label": dia["label"],
                "demand": demanda,
                "focus": foco[:3],
                "exercises": itens,
                # Campos novos, aditivos: quem não os conhece ignora, e quem conhece
                # consegue explicar a sessão sem recalcular nada.
                "architecture": split_type,
                "architecture_label": arq["label"],
            })
        return sessoes

    engine.compatible_splits = compativeis
    engine.get_day_targets = alvos_do_dia
    engine.build_all_sessions = construir
    engine.hybrid_exposures = lambda sessoes: exposicoes_por_musculo(engine, sessoes)
    engine.HYBRID_ARCHITECTURES = ARQUITETURAS
    engine.hybrid_is_hybrid = e_hibrido
    engine._HYBRID_ENGINE_INSTALLED = True
    engine.HYBRID_ENGINE_VERSION = "1.0"
    return engine


# ── Restrições articulares ──────────────────────────────────────────────────────────
#
# Preferência e penalidade, não lista de proibição. A especificação é explícita: "não
# precisa remover automaticamente todo exercício possível". Um sistema que apaga candidatos
# acaba sem nada para prescrever no dia em que o atleta marca duas restrições.

PENALIDADE_POR_DEMANDA_DE_BICEPS = {ALTA: 55.0, MEDIA: 18.0, BAIXA: 0.0}

# Como `limitations` chega do perfil. É uma lista de texto livre na avaliação, então o
# reconhecimento é por trecho, e não por igualdade.
_MARCAS_DE_TENDAO = ("biceps", "bíceps", "tendao", "tendão", "cotovelo", "epicond")


def sensibilidade_de_biceps(profile: Dict[str, Any]) -> bool:
    """O atleta marcou sensibilidade de bíceps, tendão ou cotovelo?

    Aceita a forma nova (`limitations: {"bicepsTendonSensitivity": true}`) e a que já
    existe no FORGE (`limitations: ["dor no tendão do bíceps"]`), porque o campo já está
    no modelo do perfil e na avaliação — ele só nunca tinha chegado à seleção.
    """
    limites = profile.get("limitations")
    if isinstance(limites, dict):
        if limites.get("bicepsTendonSensitivity") or limites.get("biceps_tendon_sensitivity"):
            return True
        limites = [k for k, v in limites.items() if v]
    for item in (limites or []):
        texto = str(item).strip().lower()
        if any(m in texto for m in _MARCAS_DE_TENDAO):
            return True
    return False


def doloridos(profile: Dict[str, Any]) -> Set[str]:
    """Exercícios em que o atleta relatou dor. Saem da seleção de verdade.

    Aqui não é penalidade: dor relatada durante a execução é o único sinal que justifica
    remover, porque insistir nele é o caminho para a lesão que tira o atleta por meses.
    """
    bruto = profile.get("painful_exercises") or profile.get("exercicios_com_dor") or []
    return {str(x) for x in bruto if x}


# ── Seleção ─────────────────────────────────────────────────────────────────────────

def _pontuar(engine, eid: str, profile: Dict[str, Any], slot: Dict[str, Any],
             demanda: str, so_isolador: bool, usados_hoje: Set[str],
             usados_na_semana: Dict[str, int], padroes_recentes: Sequence[str],
             sensivel: bool) -> float:
    """Quanto este exercício serve a ESTE slot, nesta sessão, nesta semana."""
    ex = engine.EXERCISE_INDEX[eid]
    score = 100.0
    role = slot["role"]
    categoria = ex.get("category", "compound")
    fadiga = ex.get("fatigue", "medium")

    # 1. Rotação de vetor. A especificação pede que o algoritmo consulte os últimos
    #    estímulos: repetir `vertical_pull` três sessões seguidas é o defeito a evitar,
    #    mesmo que sejam três máquinas diferentes.
    padrao = ex.get("movement_pattern")
    if padrao in padroes_recentes:
        # Quanto mais recente, mais pesa. O índice 0 é a sessão anterior.
        score -= 40.0 / (1 + padroes_recentes.index(padrao))

    # 2. Não repetir na semana. Um exercício pode voltar, mas não deve ser o primeiro da
    #    fila quando há catálogo sobrando.
    score -= 22.0 * usados_na_semana.get(eid, 0)
    if eid in usados_hoje:
        score -= 200.0

    # 3. Dia leve e microdose querem isolador de baixa fadiga. É o que impede o D7 LOW de
    #    virar um sétimo treino pesado com outro nome.
    if so_isolador or role == MICRODOSE:
        if categoria != "isolation":
            score -= 70.0
        if fadiga == "high":
            score -= 45.0
        elif fadiga == "low":
            score += 12.0
    elif demanda == "LOW":
        # Dia leve não é dia de movimento sistêmico. Sem isto o HYBRID 01 colocava
        # levantamento com trap bar 3x4–8 no D6, que é demanda LOW: apareceu numa semana
        # gerada de verdade. "Menos demanda" tem de mudar o QUE se faz, e não só quantas
        # séries, senão o dia leve é o dia pesado com outro rótulo.
        if fadiga == "high":
            score -= 50.0
        elif fadiga == "low":
            score += 10.0
    elif role == PRIMARY:
        # O trabalho PRINCIPAL da sessão é composto. A penalidade fica no ISOLADOR, e não
        # como bônus no composto, porque num vetor que só tem isolador — flexão de joelho,
        # panturrilha, deltoide lateral — ela se aplica a todo mundo igual e não muda nada.
        # Bonificar o composto, ao contrário, não chegava a virar o jogo: medindo, o bônus
        # de 12 perdia para a penalidade de 40 por repetir o padrão da sessão anterior, e o
        # motor continuava levando o único isolador de largura como trabalho principal.
        if categoria == "isolation":
            score -= 45.0
        elif demanda == "HIGH":
            score += 18.0

    # 4. Restrição articular: penalidade, não blacklist.
    if sensivel:
        score -= PENALIDADE_POR_DEMANDA_DE_BICEPS.get(demanda_de_biceps(ex), 0.0)
        if set(ex.get("equipment") or []) & {"machine", "cable"}:
            score += 10.0
        if ex.get("stability") == "high":
            score += 6.0

    # 5. Prioridade declarada do atleta continua valendo dentro do híbrido.
    if ex.get("primary_muscle") in engine.get_profile_priorities_internal(profile):
        score += 15.0

    # 6. Nível. Não oferecer movimento avançado a quem está começando.
    if ex.get("skill_level") == "advanced":
        if engine.get_experience_level(profile.get("experience", "Intermediário")) == "beginner":
            score -= 30.0
    return score


def _escolher(engine, slot: Dict[str, Any], profile: Dict[str, Any], indice, demanda: str,
              so_isolador: bool, usados_hoje: Set[str], usados_na_semana: Dict[str, int],
              padroes: Dict[str, List[str]], sensivel: bool, com_dor: Set[str],
              ultimos_do_vetor: Dict[str, Set[str]]) -> List[str]:
    """Os exercícios deste slot, na quantidade que o slot pede.

    `ultimos_do_vetor` é o item 5 da especificação — "o algoritmo deve consultar os
    últimos estímulos antes de montar a próxima sessão". Sem ele, a arquitetura de sete
    dias repetia no dia leve a mesma puxada com braço estendido do D5: o vetor largura tem
    só dois isoladores no catálogo, os dois já tinham aparecido na semana, e a penalidade
    por repetir não distinguia "usei na segunda" de "usei ontem".
    """
    escolhidos: List[str] = []
    vetores = vetores_do_slot(slot["vetor"])
    quantos = int(slot.get("quantos", 1))

    for i in range(quantos):
        # Vetor composto alterna: no misto de costas, um vertical e um horizontal.
        vetor = vetores[i % len(vetores)]
        candidatos = [e for e in indice.get(vetor, [])
                      if e not in usados_hoje and e not in com_dor]
        candidatos = engine._filter_candidates(candidatos, profile, usados_hoje)
        if not candidatos:
            continue

        # A ordem destes dois filtros é o produto, e eu inverti uma vez:
        #
        #   1. Dia leve só aceita isolador. Isso é ESTRUTURAL — a especificação diz "não
        #      usar exercícios sistêmicos pesados nesse dia", e um dia leve com barra fixa
        #      deixa de ser leve. Filtro duro.
        #
        #   2. Nada do que este vetor usou na sessão anterior DELE.
        #   3. Entre os que sobraram, quem ainda não apareceu na semana vem primeiro.
        #      Os dois últimos são PREFERÊNCIA: se só restar repetido, repete.
        #
        # Com a ordem trocada, o dia leve escolhia uma barra fixa inédita em vez de
        # repetir um isolador — trocou uma repetição por um composto num dia de descanso
        # ativo, que é o pior dos dois.
        if so_isolador:
            isoladores = [e for e in candidatos
                          if engine.EXERCISE_INDEX[e].get("category") == "isolation"]
            if isoladores:
                candidatos = isoladores
        #   2. Nada do que este mesmo vetor recebeu na sessão anterior dele.
        frescos = [e for e in candidatos if e not in ultimos_do_vetor.get(vetor, set())]
        if frescos:
            candidatos = frescos
        #   3. Entre os que sobraram, quem ainda não apareceu na semana vem primeiro.
        novos = [e for e in candidatos if e not in usados_na_semana]
        if novos:
            candidatos = novos
        recentes = padroes.get(vetor, [])
        melhor = max(candidatos, key=lambda e: _pontuar(
            engine, e, profile, slot, demanda, so_isolador, usados_hoje,
            usados_na_semana, recentes, sensivel))
        escolhidos.append(melhor)
        usados_hoje.add(melhor)
        ultimos_do_vetor.setdefault(f"__novo__{vetor}", set()).add(melhor)
        usados_na_semana[melhor] = usados_na_semana.get(melhor, 0) + 1
        padrao = engine.EXERCISE_INDEX[melhor].get("movement_pattern")
        if padrao:
            padroes.setdefault(vetor, []).insert(0, padrao)
            del padroes[vetor][4:]
    return escolhidos


# ── Prescrição por role ─────────────────────────────────────────────────────────────

def prescrever(engine, eid: str, role: str, demanda: str, profile: Dict[str, Any],
               vol_mod: float, rir_base: int, override_rir: Optional[str],
               nivel_de_recuperacao: str) -> Dict[str, Any]:
    """Séries, repetições e RIR a partir do ROLE, e não só do exercício.

    O RIR sai de `RIR_POR_ROLE` e não vira falha automática em nenhum role: a
    especificação é explícita sobre isso, e o motor já tratava falha como decisão de
    método, nunca como padrão.
    """
    ex = engine.EXERCISE_INDEX[eid]
    piso, teto = SERIES_POR_ROLE[role]
    categoria = ex.get("category", "compound")

    series = teto if demanda == "HIGH" else piso
    if role == MICRODOSE:
        # A microdose é 1 a 2 séries e ponto. Se a demanda ou a periodização pudessem
        # inflar isso, ela deixaria de ser microdose e viraria mais um exercício.
        series = min(2, max(1, series))
    else:
        series = max(2, round(series * vol_mod))

    rir = override_rir or RIR_POR_ROLE[role]
    if not override_rir and role != MICRODOSE:
        try:
            if int(str(rir).split("–")[0].split("-")[0]) > rir_base:
                rir = str(int(rir_base))
        except (ValueError, IndexError):
            pass

    if role != MICRODOSE:
        series, rir = engine._apply_recovery_adjustment(
            series, rir, demanda, nivel_de_recuperacao, categoria)
        series = max(1, series)

    faixa = ex.get("default_rep_range", [8, 12])
    descanso = int(ex.get("default_rest_seconds", 90))
    if role == MICRODOSE:
        descanso = min(descanso, 60)
    elif demanda == "HIGH" and categoria == "compound":
        descanso = max(descanso, 120)

    baseline = profile.get("baseline") or []
    carga = next((b.get("weight", 0) for b in baseline if b.get("exercise_id") == eid), 0)

    return {
        "exercise_id": eid,
        "sets": int(series),
        "reps": f"{faixa[0]}–{faixa[1]}",
        "rir": str(rir),
        "rest": f"{descanso}s",
        "rest_seconds": descanso,
        "load": carga,
        "technique": "Straight Sets",
        "technique_id": "straight",
        # O role acompanha o exercício até a tela: é ele que permite dizer "peitoral, 5
        # exposições na semana" sem mentir que foram 5 treinos de peito.
        "role": role,
        "role_label": ROTULO_DO_ROLE[role],
    }


# ── Contagem de exposições ──────────────────────────────────────────────────────────

def exposicoes_por_musculo(engine, sessoes: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Quantas vezes por semana cada músculo é ESTIMULADO, e em que peso.

    A especificação pede exatamente esta separação: cinco exposições de peitoral não são
    cinco sessões de peito. Sem contar separado, a tela diria "frequência 5" e o atleta
    entenderia cinco treinos pesados.
    """
    contagem: Dict[str, Dict[str, int]] = {}
    for sessao in sessoes:
        vistos: Dict[str, str] = {}
        for item in sessao.get("exercises", []):
            ex = engine.EXERCISE_INDEX.get(item.get("exercise_id"))
            if not ex:
                continue
            musculo = ex.get("primary_muscle")
            role = item.get("role", SECONDARY)
            # Dentro da mesma sessão vale o role mais forte que o músculo recebeu.
            anterior = vistos.get(musculo)
            if anterior is None or ROLES.index(role) < ROLES.index(anterior):
                vistos[musculo] = role
        for musculo, role in vistos.items():
            linha = contagem.setdefault(
                musculo, {"exposicoes": 0, PRIMARY: 0, SECONDARY: 0, MICRODOSE: 0})
            linha["exposicoes"] += 1
            linha[role] += 1
    return contagem

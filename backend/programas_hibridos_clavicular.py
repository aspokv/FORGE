# -*- coding: utf-8 -*-
"""Quatro programas híbridos com prioridade clavicular.

De onde vieram
--------------
Prescritos pelo Nicolas a partir de uma avaliação visual, com a ordem de prioridade
declarada por ele: peitoral clavicular, dorsal/largura, deltoide lateral, região média das
costas, deltoide posterior, braços e, por último, pernas — volume suficiente sem
comprometer a recuperação do tronco.

Entram AO LADO dos quatro híbridos que já existiam, e não no lugar deles: a instrução foi
não apagar nada. São oito híbridos na biblioteca agora, e os nomes destes dizem a ênfase
justamente para a escolha não virar adivinhação.

Duas decisões que valem estar escritas
--------------------------------------
**Todo inclinado de máquina virou Smith.** A prescrição pede "supino inclinado máquina",
"chest press inclinado máquina" e "supino inclinado convergente" em sessões diferentes da
mesma semana, e o catálogo do FORGE não tem prensa inclinada convergente — tem Smith,
barra, halteres e os dois crucifixos inclinados. Perguntei, e a resposta foi Smith: é o que
ele usa, e halter está fora. Registrado aqui porque um dia alguém vai comparar a ficha com
o que está no aplicativo e precisa saber por quê.

**"Chest press convergente" continuou sendo a máquina convergente** (`machine-chest-press`),
que existe e é peitoral médio. Só o que a prescrição chama de INCLINADO virou Smith;
colapsar os dois faria a semana perder um estímulo que ela tem de propósito.

O Programa 2 treina os sete dias
---------------------------------
E isso tem uma consequência visível: sem dia sem sessão, o calendário não marca descanso, e
a tela de "Precisa treinar hoje?" nunca aparece para quem o segue — não há descanso para
trocar. É característica da ficha, não defeito.
"""


def build_programas_hibridos_clavicular(ex, session, phase, program):
    """Os quatro, na ordem em que foram prescritos."""
    return [
        _rotativo_clavicular(ex, session, phase, program),
        _full_body_7x(ex, session, phase, program),
        _upper_lower_alta_frequencia(ex, session, phase, program),
        _ppl_upper_especializacao(ex, session, phase, program),
    ]


# Faixa de RIR da prescrição: compostos 1–2, isoladores 0–2.
COMPOSTO = "1–2"
ISOLADOR = "0–2"


def _rotativo_clavicular(ex, session, phase, program):
    sessoes = [
        session("Segunda · Peito dominante e costas", ["upper_chest", "lats", "biceps"], [
            ex("incline-smith", 3, "6–10", COMPOSTO, "150 s",
               note="Banco entre 20° e 30°. É o exercício que a ficha inteira gira em torno."),
            ex("cable-incline-fly", 2, "10–15", ISOLADOR, "90 s",
               note="Polia baixa para alta, fechando acima da linha do peito."),
            ex("lat-pulldown", 2, "8–12", COMPOSTO, "120 s", note="Pegada neutra, um braço por vez."),
            ex("lateral-raise", 2, "12–20", ISOLADOR, "60 s"),
            ex("dip-machine", 2, "8–12", ISOLADOR, "75 s"),
            ex("preacher-curl", 2, "8–12", ISOLADOR, "75 s"),
        ], demand="HIGH", duration=70),

        session("Terça · Posterior de coxa e ombros", ["hamstrings", "side_delts", "rear_delts"], [
            ex("leg-curl", 3, "8–12", COMPOSTO, "120 s"),
            ex("lying-leg-curl", 2, "10–15", ISOLADOR, "90 s"),
            ex("hip-thrust", 2, "8–12", COMPOSTO, "120 s"),
            ex("machine-lateral-raise", 3, "10–15", ISOLADOR, "60 s"),
            ex("lateral-raise", 2, "12–20", ISOLADOR, "60 s",
               note="Cabo passando por trás do corpo, para alongar o lateral."),
            ex("machine-rear-fly", 3, "12–20", ISOLADOR, "60 s"),
        ], demand="MODERATE", duration=70),

        session("Quarta · Costas dominante e peito", ["lats", "upper_back", "upper_chest"], [
            ex("lat-prayer", 3, "6–10", COMPOSTO, "150 s", note="Puxador articulado, um braço por vez."),
            ex("row", 3, "8–12", COMPOSTO, "120 s"),
            ex("cable-straight-arm-pulldown", 2, "10–15", ISOLADOR, "90 s"),
            ex("incline-smith", 2, "8–12", COMPOSTO, "120 s"),
            ex("cable-hammer-curl", 2, "10–15", ISOLADOR, "75 s"),
            ex("cable-pushdown", 2, "10–15", ISOLADOR, "75 s"),
        ], demand="HIGH", duration=70),

        session("Quinta · Quadríceps e ombros", ["quads", "side_delts", "rear_delts"], [
            ex("hack-squat", 3, "6–10", COMPOSTO, "180 s"),
            ex("leg-extension", 3, "10–15", ISOLADOR, "90 s"),
            ex("leg-press", 2, "10–15", COMPOSTO, "120 s", note="Pés baixos, dominância de quadríceps."),
            ex("machine-lateral-raise", 3, "10–15", ISOLADOR, "60 s"),
            ex("lateral-raise", 2, "12–20", ISOLADOR, "60 s"),
            ex("machine-rear-fly", 2, "12–20", ISOLADOR, "60 s"),
        ], demand="HIGH", duration=70),

        session("Sexta · Peito dominante e costas", ["mid_chest", "upper_chest", "lats"], [
            ex("machine-chest-press", 3, "6–10", COMPOSTO, "150 s",
               note="Convergente, encosto levemente inclinado se a máquina permitir."),
            ex("cable-incline-fly", 2, "10–15", ISOLADOR, "90 s"),
            ex("neutral-pulldown", 2, "8–12", COMPOSTO, "120 s"),
            ex("lateral-raise", 2, "12–20", ISOLADOR, "60 s"),
            ex("dip-machine", 2, "10–15", ISOLADOR, "75 s"),
            ex("cable-preacher", 2, "10–15", ISOLADOR, "75 s"),
        ], demand="MODERATE", duration=65),

        session("Sábado · Costas dominante e peito", ["upper_back", "lats", "upper_chest"], [
            ex("row", 3, "6–10", COMPOSTO, "150 s", note="Remada articulada com o peito apoiado."),
            ex("lat-pulldown", 2, "8–12", COMPOSTO, "120 s"),
            ex("cable-row", 2, "10–15", COMPOSTO, "90 s"),
            ex("machine-rear-fly", 2, "12–20", ISOLADOR, "60 s"),
            ex("incline-smith", 2, "8–12", COMPOSTO, "120 s"),
            ex("preacher-curl", 2, "8–12", ISOLADOR, "75 s"),
            ex("reverse-pushdown", 2, "10–15", ISOLADOR, "75 s"),
        ], demand="HIGH", duration=75),
    ]
    return program(
        "hibrido-clavicular-rotativo-6x", "hibrido", "Híbrido 6× · Rotativo Clavicular",
        "Avançado", 8, "Geral",
        "Seis sessões com peito e costas alternando a dominância, ombro em quase todos os "
        "dias e pernas concentradas em duas sessões. Domingo é descanso.",
        "Prescrição do treinador · avaliação visual",
        [phase("clavicular-rotativo", "Bloco de prioridade clavicular", "Double progression",
               sessoes, weeks="1–8",
               note="Compostos em 1–2 RIR, isoladores em 0–2. Subir carga quando fechar o "
                    "topo da faixa em todas as séries.")])


def _full_body_7x(ex, session, phase, program):
    sessoes = [
        session("Segunda · Full A", ["upper_chest", "lats", "side_delts"], [
            ex("incline-smith", 3, "6–10", COMPOSTO, "150 s"),
            ex("lat-pulldown", 2, "8–12", COMPOSTO, "120 s"),
            ex("lateral-raise", 2, "12–20", ISOLADOR, "60 s"),
            ex("leg-extension", 2, "10–15", ISOLADOR, "90 s"),
            ex("preacher-curl", 2, "8–12", ISOLADOR, "75 s"),
            ex("dip-machine", 2, "8–12", ISOLADOR, "75 s"),
        ], demand="MODERATE", duration=65),

        session("Terça · Full B", ["lats", "upper_chest", "rear_delts"], [
            ex("lat-prayer", 3, "6–10", COMPOSTO, "150 s"),
            ex("incline-smith", 2, "8–12", COMPOSTO, "120 s"),
            ex("machine-rear-fly", 2, "12–20", ISOLADOR, "60 s"),
            ex("leg-curl", 2, "8–12", COMPOSTO, "120 s"),
            ex("cable-hammer-curl", 2, "10–15", ISOLADOR, "75 s"),
            ex("reverse-pushdown", 2, "10–15", ISOLADOR, "75 s"),
        ], demand="MODERATE", duration=65),

        session("Quarta · Full C", ["side_delts", "upper_back", "mid_chest"], [
            ex("machine-lateral-raise", 3, "10–15", ISOLADOR, "60 s"),
            ex("row", 3, "8–12", COMPOSTO, "120 s"),
            ex("cable-incline-fly", 2, "10–15", ISOLADOR, "90 s"),
            ex("hack-squat", 2, "8–12", COMPOSTO, "150 s"),
            ex("cable-curl", 2, "10–15", ISOLADOR, "75 s"),
            ex("dip-machine", 2, "10–15", ISOLADOR, "75 s"),
        ], demand="MODERATE", duration=65),

        session("Quinta · Full D", ["upper_chest", "lats", "side_delts"], [
            ex("incline-smith", 3, "8–12", COMPOSTO, "120 s"),
            ex("neutral-pulldown", 2, "8–12", COMPOSTO, "120 s"),
            ex("lateral-raise", 3, "12–20", ISOLADOR, "60 s"),
            ex("lying-leg-curl", 2, "10–15", ISOLADOR, "90 s"),
            ex("cable-curl", 2, "10–15", ISOLADOR, "75 s"),
            ex("cable-pushdown", 2, "10–15", ISOLADOR, "75 s"),
        ], demand="MODERATE", duration=65),

        session("Sexta · Full E", ["upper_back", "lats", "upper_chest"], [
            ex("row", 3, "6–10", COMPOSTO, "150 s"),
            ex("lat-pulldown", 2, "10–15", COMPOSTO, "120 s"),
            ex("incline-smith", 2, "8–12", COMPOSTO, "120 s"),
            ex("machine-rear-fly", 2, "12–20", ISOLADOR, "60 s"),
            ex("leg-extension", 2, "10–15", ISOLADOR, "90 s"),
            ex("preacher-curl", 2, "8–12", ISOLADOR, "75 s"),
        ], demand="MODERATE", duration=65),

        session("Sábado · Full F", ["side_delts", "upper_chest", "upper_back"], [
            ex("machine-lateral-raise", 3, "10–15", ISOLADOR, "60 s"),
            ex("cable-incline-fly", 2, "10–15", ISOLADOR, "90 s"),
            ex("cable-row", 2, "8–12", COMPOSTO, "120 s"),
            ex("leg-press", 2, "10–15", COMPOSTO, "120 s"),
            ex("cable-pushdown", 2, "10–15", ISOLADOR, "75 s"),
            ex("cable-curl", 2, "10–15", ISOLADOR, "75 s"),
        ], demand="MODERATE", duration=65),

        # O domingo é a válvula da ficha: sete dias de treino só se sustentam se um deles
        # for deliberadamente leve. 3 RIR, e não é sugestão.
        session("Domingo · Full G técnico", ["mid_chest", "lats", "side_delts"], [
            ex("machine-chest-press", 2, "10–15", "3", "75 s"),
            ex("cable-pulldown", 2, "10–15", "3", "75 s"),
            ex("lateral-raise", 2, "15–20", "3", "60 s"),
            ex("machine-rear-fly", 2, "15–20", "3", "60 s"),
            ex("leg-curl", 2, "12–15", "3", "75 s"),
        ], demand="LOW", duration=45),
    ]
    return program(
        "hibrido-clavicular-full-7x", "hibrido", "Híbrido 7× · Full Body Rotativo",
        "Avançado", 8, "Geral",
        "Sete sessões de corpo inteiro, cada uma com uma dominância diferente para espalhar "
        "a fadiga. Domingo é sessão técnica em 3 RIR — a ficha não tem dia de descanso.",
        "Prescrição do treinador · avaliação visual",
        [phase("clavicular-full-7x", "Bloco de alta frequência", "Double progression",
               sessoes, weeks="1–8",
               note="Volume baixo por exposição e frequência alta. O domingo em 3 RIR é o "
                    "que permite os sete dias; tratá-lo como treino normal quebra a ficha.")])


def _upper_lower_alta_frequencia(ex, session, phase, program):
    sessoes = [
        session("Segunda · Upper A", ["upper_chest", "lats", "side_delts"], [
            ex("incline-smith", 3, "6–10", COMPOSTO, "150 s"),
            ex("cable-incline-fly", 2, "10–15", ISOLADOR, "90 s"),
            ex("lat-pulldown", 3, "8–12", COMPOSTO, "120 s"),
            ex("lateral-raise", 3, "12–20", ISOLADOR, "60 s"),
            ex("preacher-curl", 2, "8–12", ISOLADOR, "75 s"),
            ex("dip-machine", 2, "8–12", ISOLADOR, "75 s"),
        ], demand="HIGH", duration=75),

        session("Terça · Lower A", ["hamstrings", "glutes", "side_delts"], [
            ex("leg-curl", 3, "8–12", COMPOSTO, "120 s"),
            ex("lying-leg-curl", 2, "10–15", ISOLADOR, "90 s"),
            ex("hip-thrust", 2, "8–12", COMPOSTO, "120 s"),
            ex("machine-lateral-raise", 3, "10–15", ISOLADOR, "60 s"),
            ex("machine-rear-fly", 3, "12–20", ISOLADOR, "60 s"),
        ], demand="MODERATE", duration=65),

        session("Quarta · Upper B", ["lats", "upper_back", "upper_chest"], [
            ex("lat-prayer", 3, "6–10", COMPOSTO, "150 s"),
            ex("row", 3, "8–12", COMPOSTO, "120 s"),
            ex("cable-straight-arm-pulldown", 2, "10–15", ISOLADOR, "90 s"),
            ex("incline-smith", 2, "8–12", COMPOSTO, "120 s"),
            ex("lateral-raise", 2, "12–20", ISOLADOR, "60 s"),
            ex("cable-curl", 2, "10–15", ISOLADOR, "75 s"),
            ex("cable-pushdown", 2, "10–15", ISOLADOR, "75 s"),
        ], demand="HIGH", duration=80),

        session("Quinta · Lower B", ["quads", "side_delts", "rear_delts"], [
            ex("hack-squat", 3, "6–10", COMPOSTO, "180 s"),
            ex("leg-extension", 3, "10–15", ISOLADOR, "90 s"),
            ex("leg-press", 2, "10–15", COMPOSTO, "120 s"),
            ex("lateral-raise", 3, "12–20", ISOLADOR, "60 s"),
            ex("machine-rear-fly", 2, "15–20", ISOLADOR, "60 s"),
        ], demand="HIGH", duration=70),

        session("Sexta · Upper C", ["mid_chest", "lats", "upper_chest"], [
            ex("machine-chest-press", 3, "6–10", COMPOSTO, "150 s"),
            ex("cable-incline-fly", 2, "10–15", ISOLADOR, "90 s"),
            ex("lat-pulldown", 3, "8–12", COMPOSTO, "120 s"),
            ex("row", 2, "8–12", COMPOSTO, "120 s"),
            ex("lateral-raise", 2, "12–20", ISOLADOR, "60 s"),
            ex("preacher-curl", 2, "8–12", ISOLADOR, "75 s"),
            ex("dip-machine", 2, "8–12", ISOLADOR, "75 s"),
        ], demand="HIGH", duration=80),

        session("Sábado · Upper D", ["lats", "upper_back", "side_delts"], [
            ex("lat-pulldown", 2, "10–15", COMPOSTO, "90 s"),
            ex("row", 2, "10–15", COMPOSTO, "90 s"),
            ex("incline-smith", 2, "10–15", COMPOSTO, "90 s"),
            ex("machine-lateral-raise", 3, "12–20", ISOLADOR, "60 s"),
            ex("machine-rear-fly", 2, "15–20", ISOLADOR, "60 s"),
            ex("cable-curl", 2, "10–15", ISOLADOR, "75 s"),
            ex("cable-pushdown", 2, "10–15", ISOLADOR, "75 s"),
        ], demand="MODERATE", duration=70),
    ]
    return program(
        "hibrido-clavicular-upper-lower", "hibrido",
        "Híbrido 6× · Upper / Lower Alta Frequência", "Avançado", 8, "Geral",
        "Quatro sessões de tronco e duas de pernas, com peito superior e dorsal aparecendo "
        "em quase todas. Domingo é descanso.",
        "Prescrição do treinador · avaliação visual",
        [phase("clavicular-upper-lower", "Bloco de alta frequência de tronco",
               "Double progression", sessoes, weeks="1–8",
               note="Quatro exposições semanais de tronco. As duas sessões de pernas "
                    "existem para não comprometer a recuperação do que é prioridade.")])


def _ppl_upper_especializacao(ex, session, phase, program):
    sessoes = [
        session("Segunda · Push", ["upper_chest", "mid_chest", "side_delts"], [
            ex("incline-smith", 3, "6–10", COMPOSTO, "150 s"),
            ex("machine-chest-press", 2, "8–12", COMPOSTO, "120 s"),
            ex("cable-incline-fly", 2, "10–15", ISOLADOR, "90 s"),
            ex("lateral-raise", 3, "12–20", ISOLADOR, "60 s"),
            ex("dip-machine", 3, "8–12", ISOLADOR, "75 s"),
        ], demand="HIGH", duration=70),

        session("Terça · Pull", ["lats", "upper_back", "biceps"], [
            ex("lat-pulldown", 3, "8–12", COMPOSTO, "120 s"),
            ex("neutral-pulldown", 3, "8–12", COMPOSTO, "120 s"),
            ex("row", 2, "8–12", COMPOSTO, "120 s"),
            ex("cable-straight-arm-pulldown", 2, "10–15", ISOLADOR, "90 s"),
            ex("machine-rear-fly", 2, "12–20", ISOLADOR, "60 s"),
            ex("cable-curl", 3, "8–12", ISOLADOR, "75 s"),
        ], demand="HIGH", duration=75),

        session("Quarta · Lower e deltoides", ["quads", "hamstrings", "side_delts"], [
            ex("hack-squat", 3, "6–10", COMPOSTO, "180 s"),
            ex("leg-extension", 2, "10–15", ISOLADOR, "90 s"),
            ex("leg-curl", 3, "8–12", COMPOSTO, "120 s"),
            ex("lying-leg-curl", 2, "10–15", ISOLADOR, "90 s"),
            ex("machine-lateral-raise", 3, "12–20", ISOLADOR, "60 s"),
            ex("machine-rear-fly", 2, "15–20", ISOLADOR, "60 s"),
        ], demand="HIGH", duration=75),

        session("Quinta · Upper", ["upper_chest", "lats", "upper_back"], [
            ex("incline-smith", 3, "8–12", COMPOSTO, "120 s"),
            ex("cable-incline-fly", 2, "10–15", ISOLADOR, "90 s"),
            ex("lat-prayer", 3, "8–12", COMPOSTO, "120 s"),
            ex("row", 3, "8–12", COMPOSTO, "120 s"),
            ex("lateral-raise", 2, "12–20", ISOLADOR, "60 s"),
        ], demand="MODERATE", duration=70),

        # A sessão mais volumosa da ficha, e de propósito: ombro e braço aguentam densidade
        # que peito e costas não aguentariam na mesma semana.
        session("Sexta · Especialização de ombros e braços",
                ["side_delts", "rear_delts", "biceps", "triceps"], [
            ex("machine-lateral-raise", 3, "10–15", ISOLADOR, "60 s"),
            ex("lateral-raise", 2, "12–20", ISOLADOR, "60 s"),
            ex("machine-rear-fly", 3, "12–20", ISOLADOR, "60 s"),
            ex("preacher-curl", 3, "8–12", ISOLADOR, "75 s"),
            ex("cable-hammer-curl", 2, "10–15", ISOLADOR, "75 s"),
            ex("dip-machine", 3, "8–12", ISOLADOR, "75 s"),
            ex("reverse-pushdown", 2, "10–15", ISOLADOR, "75 s"),
        ], demand="MODERATE", duration=75),

        session("Sábado · Upper", ["upper_back", "lats", "upper_chest"], [
            ex("row", 3, "6–10", COMPOSTO, "150 s"),
            ex("lat-pulldown", 3, "8–12", COMPOSTO, "120 s"),
            ex("cable-straight-arm-pulldown", 2, "10–15", ISOLADOR, "90 s"),
            ex("incline-smith", 3, "8–12", COMPOSTO, "120 s"),
            ex("cable-incline-fly", 2, "12–15", ISOLADOR, "90 s"),
        ], demand="HIGH", duration=70),
    ]
    return program(
        "hibrido-clavicular-ppl-upper", "hibrido",
        "Híbrido 6× · PPL + Upper + Especialização", "Avançado", 8, "Geral",
        "Push, Pull e Lower na primeira metade, dois Upper na segunda e uma sessão inteira "
        "de ombros e braços. Domingo é descanso.",
        "Prescrição do treinador · avaliação visual",
        [phase("clavicular-ppl-upper", "Bloco de especialização", "Double progression",
               sessoes, weeks="1–8",
               note="Mais estímulo concentrado por sessão. A sexta é a mais volumosa porque "
                    "ombro e braço toleram densidade que peito e costas não toleram.")])

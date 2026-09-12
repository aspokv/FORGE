# -*- coding: utf-8 -*-
"""
Hibrido 6x com enfase em peitoral e dorsal, prescrito pelo proprietario em setembro de 2026.

A logica da ficha e a rotacao das enfases, e ela e o motivo de o programa existir:

    PEITORAL   segunda superior/clavicular · quarta medio/esternocostal · sexta inferior
    COSTAS     terca largura/latissimo · quinta espessura/upper back · sabado latissimo
               por extensao do ombro
    PERNAS     segunda, quarta e sexta quadriceps · terca, quinta e sabado posterior e
               gluteos

Cada exercicio aponta para um id que EXISTE no catalogo do FORGE. Os 42 movimentos da ficha
foram conferidos um a um contra `EXERCISES` antes de entrar aqui: id inventado passaria no
import e so apareceria na tela do atleta, sem foto e sem nome proprio.

As regras de execucao da ficha viraram campos, nao texto solto:

  composto    RIR 1-2, descanso 150 s (a ficha pede 2 a 3 minutos)
  isolador    RIR 1, descanso 90 s (a ficha pede 60 a 120 segundos)

A ficha autoriza chegar a 0 RIR na ULTIMA serie dos isoladores. Isso nao vira um campo
porque o RIR aqui e por exercicio, e nao por serie; fica na nota de cada isolador, que e
onde o atleta le antes de executar.
"""

COMPOSTO_RIR = "1–2"
COMPOSTO_DESCANSO = "150 s"
ISOLADOR_RIR = "1"
ISOLADOR_DESCANSO = "90 s"

ULTIMA_SERIE = "Pode chegar a 0 RIR na última série."

PROGRESSAO = (
    "Progressão: quando atingir o topo da faixa de repetições em todas as séries com boa "
    "execução, aumentar 2,5% a 5% da carga e voltar ao piso da faixa. Exemplo em 3x6–8: "
    "8/7/6, depois 8/8/7, depois 8/8/8 — no treino seguinte, sobe a carga e volta a 6."
)

RESUMO = (
    "Híbrido de seis sessões com ênfase rotativa em peitoral e dorsal. Segunda, quarta e "
    "sexta somam quadríceps; terça, quinta e sábado somam posterior e glúteos. Domingo é "
    "descanso. Manter de 6 a 8 semanas antes de alterações relevantes."
)

CUIDADO = (
    "Seis sessões por semana exigem sono e alimentação em dia. Não é necessário levar todos "
    "os exercícios à falha: priorize técnica, amplitude e progressão de carga ou repetições."
)


def build_programa_hibrido_6x(ex, session, phase, program):
    """Versao 1: rotacao de enfases dentro de seis sessoes de corpo dividido."""

    def composto(exercise_id, series, reps, nota=""):
        return ex(exercise_id, series, reps, COMPOSTO_RIR, COMPOSTO_DESCANSO, "straight", nota)

    def isolador(exercise_id, series, reps, nota=""):
        nota = (nota + " " + ULTIMA_SERIE).strip()
        return ex(exercise_id, series, reps, ISOLADOR_RIR, ISOLADOR_DESCANSO, "straight", nota)

    segunda = session("Segunda · Peito superior e quadríceps A", ["Peitoral superior", "Quadríceps"], [
        composto("incline-smith", 3, "6–8", "Banco entre 20 e 30 graus."),
        isolador("cable-incline-fly", 2, "10–15", "Cabo de baixo para cima."),
        composto("hack-squat", 3, "6–10"),
        isolador("leg-extension", 2, "10–15"),
        isolador("lateral-raise", 3, "12–20"),
        isolador("cable-overhead-extension", 2, "10–15", "Tríceps francês no cabo."),
        isolador("standing-calf", 3, "8–12"),
    ], "HIGH", 70)

    terca = session("Terça · Dorsal largura e posterior A", ["Dorsais / largura", "Posterior de coxa"], [
        composto("neutral-pulldown", 3, "6–10", "Pegada neutra média."),
        composto("lat-pulldown", 2, "10–15", "Unilateral, cotovelo em direção ao quadril."),
        composto("rdl", 3, "6–10"),
        isolador("seated-hamstring-curl", 2, "10–15"),
        isolador("machine-rear-fly", 2, "12–20", "Reverse pec deck."),
        isolador("incline-db-curl", 2, "8–12"),
        isolador("cable-crunch", 3, "10–15", "Abdômen: três séries."),
    ], "HIGH", 70)

    quarta = session("Quarta · Peito médio e quadríceps B", ["Peitoral médio", "Quadríceps"], [
        composto("machine-chest-press", 3, "6–10", "Chest press horizontal ou supino máquina."),
        isolador("cable-fly", 2, "10–15", "Crossover na altura do peito."),
        composto("leg-press", 3, "8–12", "Pés mais baixos na plataforma."),
        isolador("single-leg-extension", 2, "10–15"),
        isolador("machine-lateral-raise", 3, "12–20"),
        isolador("cable-pushdown", 2, "8–12"),
        isolador("seated-calf", 3, "10–15"),
    ], "HIGH", 70)

    quinta = session("Quinta · Costas espessura e posterior B", ["Costas / espessura", "Posterior de coxa"], [
        composto("row", 3, "6–10", "Remada apoiada no peito."),
        composto("wide-cable-row", 3, "8–12", "Pegada aberta."),
        composto("back-extension", 3, "8–12", "Extensão a 45 graus, foco em glúteo e posterior."),
        isolador("lying-leg-curl", 2, "10–15"),
        isolador("preacher-curl", 2, "8–12", "Rosca Scott."),
        isolador("cable-rear-delt-crossover", 2, "12–20", "Reverse fly no cabo."),
        isolador("hanging-leg-raise", 3, "10–15", "Abdômen: três séries."),
    ], "HIGH", 70)

    sexta = session("Sexta · Peito inferior e quadríceps C", ["Peitoral inferior", "Quadríceps"], [
        composto("dip", 3, "6–10", "Tronco levemente inclinado à frente."),
        isolador("cable-fly", 2, "10–15", "Crossover de cima para baixo."),
        composto("front-squat", 3, "6–10", "Pendulum squat quando disponível."),
        isolador("leg-extension", 2, "12–15"),
        isolador("lateral-raise", 3, "12–20"),
        isolador("db-overhead-extension", 2, "10–15", "Extensão de tríceps unilateral."),
        isolador("machine-standing-calf", 3, "8–15"),
    ], "HIGH", 70)

    sabado = session("Sábado · Dorsal e posterior C", ["Dorsais", "Posterior de coxa", "Glúteos"], [
        composto("db-row", 3, "8–12", "Unilateral baixa, cotovelo em direção ao quadril."),
        isolador("cable-straight-arm-pulldown", 2, "10–15", "Pullover no cabo ou straight-arm pulldown."),
        composto("hip-thrust", 3, "6–10"),
        isolador("seated-hamstring-curl", 2, "10–15", "Sentada ou unilateral."),
        isolador("db-hammer-curl", 2, "8–12"),
        isolador("cable-rear-delt-crossover", 2, "12–20", "Posterior de ombro no cabo."),
        isolador("reverse-crunch", 3, "10–15", "Abdômen: três séries."),
    ], "HIGH", 70)

    sessoes = [segunda, terca, quarta, quinta, sexta, sabado]
    # A progressao vale para o programa inteiro, e a nota do primeiro exercicio e o campo que
    # sobrevive ao salvamento de programa personalizado — por isso ela mora ali.
    sessoes[0]["exercises"][0]["note"] = (sessoes[0]["exercises"][0]["note"] + " " + PROGRESSAO).strip()

    return program(
        "hibrido-6x-peitoral-dorsal", "abcdef",
        "Híbrido 6× · Peitoral e Dorsal", "Avançado", 6, "Geral",
        RESUMO, "Prescrição do proprietário",
        [phase("base", "Rotação de ênfases", "Híbrido 6×", sessoes, "6–8 semanas", RESUMO + " " + PROGRESSAO)],
        "advanced", CUIDADO, audience_type="unisex",
    )


# ── Versao 2: upper / lower hibrido ──────────────────────────────────────────────────

RESUMO_V2 = (
    "Híbrido de seis sessões em upper e lower alternados. Segunda, quarta e sexta são "
    "membros superiores com ênfase rotativa de peitoral; terça, quinta e sábado são pernas, "
    "divididas em quadríceps, posterior com glúteos e misto. Domingo é descanso."
)

# A V2 escreve a regra do isolador de outro jeito: "0-1 RIR na ultima serie", em vez de
# "1 RIR podendo chegar a 0". O campo segue a ficha, e nao a versao anterior.
ISOLADOR_RIR_V2 = "0–1"
ULTIMA_SERIE_V2 = "O 0 RIR vale para a última série."


def build_programa_hibrido_6x_v2(ex, session, phase, program):
    """Versao 2: a mesma rotacao de enfases, organizada como upper / lower."""

    def composto(exercise_id, series, reps, nota=""):
        return ex(exercise_id, series, reps, COMPOSTO_RIR, COMPOSTO_DESCANSO, "straight", nota)

    def isolador(exercise_id, series, reps, nota=""):
        return ex(exercise_id, series, reps, ISOLADOR_RIR_V2, ISOLADOR_DESCANSO, "straight",
                  (nota + " " + ULTIMA_SERIE_V2).strip())

    sessoes = [
        session("Segunda · Upper A · peito superior e dorsal", ["Peitoral superior", "Dorsais"], [
            composto("db-incline-press", 3, "6–10"),
            composto("cable-pulldown", 3, "8–12", "Pegada aberta, à frente."),
            isolador("cable-incline-fly", 2, "10–15", "Crucifixo inclinado; máquina quando disponível."),
            composto("db-row", 2, "8–12", "Unilateral apoiada."),
            isolador("db-lateral-raise", 3, "12–20"),
            isolador("incline-rope-skullcrusher", 2, "10–15", "Tríceps testa no cabo."),
            isolador("bb-curl", 2, "8–12", "Rosca direta."),
        ], "HIGH", 70),

        session("Terça · Lower A · quadríceps", ["Quadríceps", "Panturrilhas"], [
            composto("hack-squat", 4, "6–10"),
            composto("leg-press", 3, "10–15"),
            isolador("leg-extension", 2, "12–15"),
            isolador("seated-hamstring-curl", 2, "10–15"),
            isolador("standing-calf", 4, "8–12"),
            isolador("cable-crunch", 3, "10–15", "Abdômen: três séries."),
        ], "HIGH", 65),

        session("Quarta · Upper B · peito médio e costas espessura", ["Peitoral médio", "Costas / espessura"], [
            composto("machine-chest-press", 3, "6–10", "Supino reto máquina."),
            composto("row", 3, "6–10", "Remada articulada com apoio."),
            isolador("cable-fly", 2, "12–15", "Crossover horizontal."),
            composto("wide-cable-row", 2, "8–12", "Remada baixa aberta."),
            isolador("machine-rear-fly", 3, "12–20", "Posterior de ombro máquina."),
            isolador("cable-pushdown", 2, "10–15", "Tríceps corda."),
            isolador("preacher-curl", 2, "8–12", "Rosca Scott."),
        ], "HIGH", 70),

        session("Quinta · Lower B · posterior e glúteos", ["Posterior de coxa", "Glúteos"], [
            composto("rdl", 4, "6–10"),
            composto("lying-leg-curl", 3, "8–12"),
            composto("hip-thrust", 3, "8–12"),
            isolador("lunge", 2, "10–12", "Afundo reverso; repetições por perna."),
            isolador("seated-calf", 4, "10–15"),
            isolador("hanging-leg-raise", 3, "10–15", "Abdômen: três séries."),
        ], "HIGH", 65),

        session("Sexta · Upper C · peito inferior e dorsal largura", ["Peitoral inferior", "Dorsais / largura"], [
            composto("dip", 3, "6–10", "Tronco inclinado à frente."),
            composto("neutral-pulldown", 3, "8–12", "Pegada neutra fechada."),
            isolador("cable-fly", 2, "10–15", "Crossover de cima para baixo."),
            isolador("cable-straight-arm-pulldown", 2, "12–15", "Pullover no cabo."),
            isolador("lateral-raise", 3, "12–20"),
            isolador("db-overhead-extension", 2, "10–15", "Tríceps unilateral."),
            isolador("db-hammer-curl", 2, "8–12"),
        ], "HIGH", 70),

        session("Sábado · Lower C · misto", ["Quadríceps", "Posterior de coxa"], [
            composto("front-squat", 3, "6–10"),
            composto("seated-hamstring-curl", 3, "10–15"),
            composto("bulgarian-split-squat", 2, "8–12", "Repetições por perna."),
            isolador("back-extension", 2, "10–15", "Extensão a 45 graus."),
            isolador("leg-extension", 2, "12–15"),
            isolador("machine-standing-calf", 4, "10–15"),
            isolador("reverse-crunch", 3, "10–15", "Abdômen: três séries."),
        ], "HIGH", 70),
    ]
    sessoes[0]["exercises"][0]["note"] = (sessoes[0]["exercises"][0]["note"] + " " + PROGRESSAO).strip()

    return program(
        "hibrido-6x-upper-lower", "abcdef",
        "Híbrido 6× · Upper / Lower", "Avançado", 6, "Geral",
        RESUMO_V2, "Prescrição do proprietário",
        [phase("base", "Upper / Lower híbrido", "Híbrido 6×", sessoes, "6–8 semanas", RESUMO_V2 + " " + PROGRESSAO)],
        "advanced", CUIDADO, audience_type="unisex",
    )


# ── Versao 3: full body rotativo, com trabalho pesado e trabalho leve ────────────────

RESUMO_V3 = (
    "Híbrido de seis sessões em corpo inteiro rotativo. Todo dia tem peito, costas e perna, "
    "mas só um deles é pesado: o que não é da vez entra com duas séries leves, para técnica "
    "e conexão. Domingo é descanso."
)

# A V3 traz uma distincao que as outras nao tem: alem de composto e isolador, ela separa
# trabalho PESADO de trabalho LEVE. O leve nao e um isolador mais curto — e outro objetivo,
# com RIR proprio e ordem explicita de nao ir a falha. Por isso vira um terceiro construtor,
# e nao um parametro escondido.
LEVE_RIR = "2–3"
LEVE_NOTA = "Estímulo leve: duas séries, foco em técnica, amplitude e conexão. Não levar à falha."

CUIDADO_V3 = (
    "Seis sessões por semana em corpo inteiro. O estímulo leve existe para somar volume sem "
    "somar fadiga: leve à falha e ele deixa de cumprir a função. Progressão de carga apenas "
    "nos movimentos principais."
)


def build_programa_hibrido_6x_v3(ex, session, phase, program):
    """Versao 3: corpo inteiro todo dia, com um grupo pesado e os outros leves."""

    def pesado(exercise_id, series, reps, nota=""):
        return ex(exercise_id, series, reps, COMPOSTO_RIR, COMPOSTO_DESCANSO, "straight", nota)

    def isolador(exercise_id, series, reps, nota=""):
        return ex(exercise_id, series, reps, ISOLADOR_RIR, ISOLADOR_DESCANSO, "straight",
                  (nota + " " + ULTIMA_SERIE).strip())

    def leve(exercise_id, reps, nota=""):
        # Duas series, sempre: e a definicao do estimulo leve nesta ficha.
        return ex(exercise_id, 2, reps, LEVE_RIR, ISOLADOR_DESCANSO, "straight",
                  (nota + " " + LEVE_NOTA).strip())

    sessoes = [
        session("Segunda · Peito superior, quadríceps e dorsal leve", ["Peitoral superior", "Quadríceps"], [
            pesado("incline-smith", 3, "6–8"),
            pesado("hack-squat", 3, "6–10"),
            leve("lat-pulldown", "10–15", "Puxada unilateral."),
            isolador("leg-extension", 2, "12–15"),
            isolador("db-lateral-raise", 3, "12–20"),
            isolador("cable-overhead-extension", 2, "10–15", "Tríceps francês."),
        ], "HIGH", 65),

        session("Terça · Dorsal largura, posterior e peito leve", ["Dorsais / largura", "Posterior de coxa"], [
            pesado("neutral-pulldown", 3, "6–10", "Pegada neutra."),
            pesado("rdl", 3, "6–10"),
            leve("pec-deck", "12–15", "Crucifixo máquina."),
            isolador("seated-hamstring-curl", 2, "10–15"),
            isolador("incline-db-curl", 2, "8–12", "Rosca inclinada."),
            isolador("machine-rear-fly", 2, "12–20", "Posterior de ombro."),
        ], "HIGH", 65),

        session("Quarta · Peito médio, quadríceps e costas leve", ["Peitoral médio", "Quadríceps"], [
            pesado("machine-chest-press", 3, "6–10", "Supino reto máquina."),
            pesado("leg-press", 3, "8–12"),
            leve("cable-row", "10–12", "Remada baixa."),
            isolador("single-leg-extension", 2, "12–15", "Extensora unilateral."),
            isolador("machine-lateral-raise", 3, "12–20"),
            isolador("cable-pushdown", 2, "10–15", "Tríceps pulley."),
        ], "HIGH", 65),

        session("Quinta · Costas espessura, posterior e peito leve", ["Costas / espessura", "Posterior de coxa"], [
            pesado("row", 3, "6–10", "Remada apoiada no peito."),
            pesado("lying-leg-curl", 3, "8–12"),
            leve("cable-fly", "12–15", "Crossover."),
            isolador("back-extension", 2, "10–15", "Extensão a 45 graus."),
            isolador("preacher-curl", 2, "8–12", "Rosca Scott."),
            isolador("cable-rear-delt-crossover", 2, "12–20", "Reverse fly."),
        ], "HIGH", 65),

        session("Sexta · Peito inferior, quadríceps e dorsal leve", ["Peitoral inferior", "Quadríceps"], [
            pesado("dip", 3, "6–10", "Paralelas ou supino declinado máquina."),
            pesado("front-squat", 3, "6–10", "Pendulum squat quando disponível."),
            leve("cable-straight-arm-pulldown", "10–15", "Pullover no cabo."),
            isolador("leg-extension", 2, "12–15"),
            isolador("lateral-raise", 3, "12–20"),
            isolador("db-overhead-extension", 2, "10–15", "Tríceps unilateral."),
        ], "HIGH", 65),

        session("Sábado · Dorsal extensão, posterior e peito leve", ["Dorsais", "Posterior de coxa", "Glúteos"], [
            pesado("db-row", 3, "8–12", "Unilateral baixa, cotovelo em direção ao quadril."),
            pesado("hip-thrust", 3, "6–10"),
            leve("cable-incline-fly", "12–15", "Crucifixo inclinado no cabo."),
            isolador("seated-hamstring-curl", 2, "10–15"),
            isolador("db-hammer-curl", 2, "8–12"),
            isolador("cable-rear-delt-crossover", 2, "12–20", "Posterior de ombro no cabo."),
        ], "HIGH", 65),
    ]
    sessoes[0]["exercises"][0]["note"] = (
        sessoes[0]["exercises"][0]["note"] + " Progressão de carga apenas nos movimentos principais.").strip()

    return program(
        "hibrido-6x-full-body", "abcdef",
        "Híbrido 6× · Full Body Rotativo", "Avançado", 6, "Geral",
        RESUMO_V3, "Prescrição do proprietário",
        [phase("base", "Full body rotativo", "Híbrido 6×", sessoes, "6–8 semanas", RESUMO_V3)],
        "advanced", CUIDADO_V3, audience_type="unisex",
    )


def build_programas_hibridos_6x(ex, session, phase, program):
    """As tres versoes da ficha, na ordem em que foram prescritas."""
    return [
        build_programa_hibrido_6x(ex, session, phase, program),
        build_programa_hibrido_6x_v2(ex, session, phase, program),
        build_programa_hibrido_6x_v3(ex, session, phase, program),
    ]

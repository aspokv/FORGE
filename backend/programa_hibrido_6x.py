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
    """Monta o programa. Recebe os construtores de `training_programs` para nao duplicar a
    forma do dicionario em dois lugares."""

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

    return [program(
        "hibrido-6x-peitoral-dorsal", "abcdef",
        "Híbrido 6× · Peitoral e Dorsal", "Avançado", 6, "Geral",
        RESUMO, "Prescrição do proprietário",
        [phase("base", "Rotação de ênfases", "Híbrido 6×", sessoes, "6–8 semanas", RESUMO + " " + PROGRESSAO)],
        "advanced", CUIDADO, audience_type="unisex",
    )]

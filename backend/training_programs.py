"""Normalized complete training programs curated from user-supplied references.

Only the training prescriptions are represented here. Long-form copyrighted text,
photos and branding from the source PDFs are deliberately not redistributed. Every
program is still a draft: the athlete reviews the selected phase in Program Builder
before the existing ownership-checked save endpoint is called.
"""

from copy import deepcopy


PROGRAM_CATEGORIES = [
    {"id": "abc", "label": "ABC", "subtitle": "Três sessões em rotação"},
    {"id": "abcd", "label": "ABCD", "subtitle": "Quatro sessões especializadas"},
    {"id": "abcde", "label": "ABCDE", "subtitle": "Cinco sessões de alto volume"},
    {"id": "abcdef", "label": "ABCDEF", "subtitle": "Seis sessões por microciclo"},
    {"id": "upper_lower", "label": "Upper / Lower", "subtitle": "Tronco e inferiores 2x"},
    {"id": "periodized", "label": "Periodizados", "subtitle": "Fases com estímulos distintos"},
]


TECHNIQUE_NAMES = {
    "straight": "Straight Sets",
    "drop-set": "Drop Set",
    "rest-pause": "Rest-Pause",
    "superset": "Superset",
    "pyramid": "Pyramid",
    "lengthened-partials": "Lengthened Partials",
    "top-set-backoff": "Top Set + Back-off",
}


def ex(exercise_id, sets, reps, rir="1–2", rest="90 s", technique_id="straight", note=""):
    return {
        "exercise_id": exercise_id,
        "sets": sets,
        "reps": reps,
        "rir": rir,
        "rest": rest,
        "load": 0,
        "technique_id": technique_id,
        "technique": TECHNIQUE_NAMES.get(technique_id, "Straight Sets"),
        "note": note,
    }


def session(label, focus, exercises, demand="MODERATE", duration=65):
    return {
        "label": label,
        "focus": focus,
        "demand": demand,
        "duration": duration,
        "exercises": exercises,
    }


def phase(phase_id, label, method, sessions, weeks="", note=""):
    return {
        "id": phase_id,
        "label": label,
        "method": method,
        "weeks": weeks,
        "note": note,
        "sessions": sessions,
    }


def program(program_id, category, name, level, weeks, audience, description, reference, phases,
            safety="standard", warning="", audience_type="unisex"):
    return {
        "id": program_id,
        "category": category,
        "name": name,
        "level": level,
        "duration_weeks": weeks,
        "audience": audience,
        "audience_type": audience_type,
        "description": description,
        "reference": reference,
        "safety": safety,
        "warning": warning,
        "phases": phases,
    }


FEMALE_ADVANCED = phase("base", "Semanas 1–5", "Supersets e especialização Wellness", [
    session("A · Quadríceps", ["Quadríceps", "Glúteos"], [
        ex("leg-press", 4, "12 + 12", "1", "60 s", "superset", "Duas posições de pés; parear com agachamento sumô."),
        ex("goblet-squat", 4, "15", "1–2", "60 s", "superset"),
        ex("leg-extension", 4, "15 + negativas + drop", "0–1", "45 s", "drop-set", "Negativas somente com supervisão."),
        ex("bulgarian-split-squat", 4, "15/cada", "1–2", "60 s", "superset"),
        ex("lunge", 4, "30–60 passos", "1–2", "60 s", "superset"),
    ], "HIGH", 70),
    session("B · Peitoral & Costas", ["Peitoral", "Costas"], [
        ex("db-row", 4, "12–15/cada", "1–2", "30 s", "superset"),
        ex("db-bench-press", 4, "15", "1–2", "30 s", "superset"),
        ex("dip", 4, "falha técnica", "1", "30 s", "superset"),
        ex("cable-row", 4, "15", "1–2", "30 s", "superset"),
        ex("cable-pulldown", 3, "15", "1–2", "30 s", "superset"),
        ex("db-fly", 3, "15", "1–2", "30 s", "superset"),
    ], "MODERATE", 60),
    session("C · Posteriores", ["Posteriores", "Glúteos"], [
        ex("lying-leg-curl", 4, "10 + isometria", "1", "60 s", "superset"),
        ex("seated-hamstring-curl", 4, "15/cada", "1–2", "45 s", "superset"),
        ex("rdl", 4, "12", "1–2", "60 s", "superset"),
        ex("hack-squat", 4, "20/18/15/14", "1–2", "45 s", "pyramid"),
        ex("db-rdl", 3, "12", "1–2", "45 s", "superset", "Controle de quadril; adaptação do good morning da referência."),
    ], "HIGH", 65),
    session("D · Deltoides & Braços", ["Deltoides", "Bíceps", "Tríceps"], [
        ex("db-ohp", 5, "20/15/15/12/12", "1–2", "50 s", "pyramid"),
        ex("db-lateral-raise", 3, "8 + 12", "0–1", "45 s", "drop-set"),
        ex("db-curl", 3, "15", "1–2", "30 s", "superset"),
        ex("dip-machine", 3, "15–20", "1–2", "30 s", "superset"),
        ex("db-hammer-curl", 3, "15", "1–2", "30 s", "superset"),
        ex("ez-skullcrusher", 3, "15–20", "1–2", "30 s", "superset"),
    ], "MODERATE", 60),
], "1–5", "Inclui opções originais de agenda para 2–6 dias; esta versão preserva as quatro sessões principais.")


ENHANCED_HIGH_VOLUME = phase("base", "Microciclo ABCDE", "Bi-sets, tri-sets, séries gigantes e drops", [
    session("A · Braços & Antebraços", ["Bíceps", "Tríceps", "Antebraços"], [
        ex("rope-pushdown", 4, "6–8", "1", "90 s", "superset", "Pico de contração de 3 s."),
        ex("cable-curl", 4, "10–12", "1", "90 s", "superset"),
        ex("db-curl", 4, "10–12", "1", "90 s", "superset"),
        ex("bb-curl", 4, "10–12", "1", "90 s", "superset"),
        ex("db-hammer-curl", 3, "10–12", "1", "30 s"),
        ex("ez-skullcrusher", 4, "10–12", "1", "90 s", "superset"),
        ex("db-overhead-extension", 4, "10–12", "1", "90 s", "superset"),
        ex("cable-pushdown", 3, "10–12", "1", "30 s"),
    ], "HIGH", 80),
    session("B · Pernas Gigante", ["Quadríceps", "Posteriores", "Panturrilhas"], [
        ex("leg-extension", 4, "12–15", "1", "30 s"),
        ex("bb-squat", 3, "10–12", "1", "90 s", "superset", "Início da série gigante."),
        ex("lunge", 3, "10–12/cada", "1", "90 s", "superset"),
        ex("goblet-squat", 3, "10–12", "1", "90 s", "superset"),
        ex("bulgarian-split-squat", 3, "10–12", "1", "90 s", "superset"),
        ex("db-rdl", 3, "10–12", "1", "90 s", "superset"),
        ex("seated-calf", 3, "falha técnica", "1", "60 s"),
        ex("leg-press-calf", 3, "falha técnica", "1", "60 s"),
        ex("standing-calf", 3, "falha técnica", "1", "60 s"),
    ], "HIGH", 90),
    session("C · Peitoral & Abdômen", ["Peitoral", "Core"], [
        ex("bb-bench-press", 4, "10–12", "1", "45 s", "superset"),
        ex("db-bench-press", 4, "10–12", "1", "45 s", "superset", "Squeeze press na referência."),
        ex("db-incline-press", 4, "10–12", "1", "45 s", "superset"),
        ex("db-fly", 4, "10–12", "1", "45 s", "superset"),
        ex("cable-incline-fly", 4, "10–12", "1", "45 s", "superset"),
        ex("dip", 4, "10–12", "1", "45 s", "superset"),
        ex("machine-crunch", 5, "falha técnica", "1", "30 s", "superset"),
        ex("hanging-leg-raise", 5, "falha técnica", "1", "30 s", "superset"),
    ], "HIGH", 80),
    session("D · Ombros & Trapézio", ["Deltoides", "Trapézio"], [
        ex("db-arnold-press", 3, "12", "1", "45 s"),
        ex("db-lateral-raise", 3, "12 + 4 parciais", "0–1", "45 s", "lengthened-partials"),
        ex("db-ohp", 3, "12", "1", "45 s"),
        ex("cable-front-raise", 3, "12", "1", "45 s", "superset"),
        ex("cable-rear-delt-crossover", 3, "drop", "0–1", "45 s", "drop-set"),
        ex("db-shrug", 3, "8 + 4 parciais", "1", "45 s", "lengthened-partials"),
        ex("cable-upright-row", 3, "15", "1", "45 s"),
    ], "HIGH", 65),
    session("E · Costas & Abdômen", ["Costas", "Core"], [
        ex("cable-pulldown", 3, "drop", "0–1", "45 s", "drop-set"),
        ex("db-row", 3, "drop", "0–1", "45 s", "drop-set"),
        ex("bb-row", 3, "drop", "0–1", "45 s", "drop-set"),
        ex("cable-row", 3, "drop", "0–1", "45 s", "drop-set"),
        ex("cable-straight-arm-pulldown", 3, "drop", "0–1", "45 s", "drop-set"),
        ex("cable-crunch", 5, "30", "1", "30 s", "superset"),
        ex("cable-woodchop", 5, "15/cada", "1", "30 s", "superset"),
    ], "HIGH", 75),
], "", "Volume e densidade muito altos; só usar com histórico avançado, recuperação monitorada e técnica consistente.")


MALE_INTERMEDIATE = phase("base", "Ciclo de 4 semanas", "ABC rotativo com um dia de descanso", [
    session("A · Pernas", ["Pernas", "Panturrilhas", "Core"], [
        ex("adductor-machine", 4, "15/15/12/12", "2", "60 s"),
        ex("abductor-machine", 4, "15/15/12/12", "2", "60 s"),
        ex("hip-thrust", 5, "15/15/15/12/12", "1–2", "90 s"),
        ex("leg-extension", 4, "15/15/12/12", "1–2", "60 s"),
        ex("lying-leg-curl", 5, "15/15/15/12/12", "1–2", "60 s"),
        ex("leg-press", 5, "15/15/12/12/10", "1–2", "2 min", "pyramid"),
        ex("hack-squat", 4, "12/12/10/10", "1–2", "2 min", "pyramid", "Adaptação estável do agachamento Smith."),
        ex("standing-calf", 4, "15", "1–2", "60 s"),
        ex("seated-calf", 4, "15", "1–2", "60 s"),
        ex("cable-crunch", 3, "20–30", "2", "60 s"),
    ], "MODERATE", 80),
    session("B · Peito & Braços", ["Peitoral", "Bíceps", "Tríceps"], [
        ex("db-incline-press", 4, "15/15/12/12", "2", "90 s"),
        ex("incline-smith", 4, "12/12/10/10", "1–2", "2 min"),
        ex("smith-bench-press", 4, "12/12/10/10", "1–2", "2 min"),
        ex("dip", 4, "8", "1–2", "90 s"),
        ex("bb-curl", 4, "10–12", "1–2", "60 s"),
        ex("preacher-curl", 4, "12/12/10/10", "1–2", "60 s"),
        ex("db-curl", 4, "10", "1–2", "60 s", "straight", "Isometria alternada."),
        ex("rope-pushdown", 4, "15/15/12/12", "1–2", "60 s"),
        ex("ez-skullcrusher", 4, "12", "1–2", "60 s"),
        ex("db-overhead-extension", 4, "15", "1–2", "60 s"),
    ], "MODERATE", 80),
    session("C · Costas & Ombros", ["Costas", "Deltoides", "Trapézio"], [
        ex("cable-pulldown", 4, "15/15/12/12", "2", "60 s"),
        ex("lat-prayer", 4, "15/15/12/12", "2", "60 s"),
        ex("bb-row", 4, "12/12/10/10", "1–2", "2 min"),
        ex("db-row", 4, "12", "1–2", "90 s"),
        ex("cable-row", 4, "12/12/10/10", "1–2", "90 s"),
        ex("db-ohp", 4, "12/12/10/10", "1–2", "90 s"),
        ex("cable-front-raise", 4, "12", "2", "60 s"),
        ex("db-lateral-raise", 4, "12", "2", "60 s"),
        ex("db-rear-fly", 4, "15/15/12/12", "2", "60 s"),
        ex("db-shrug", 4, "13", "1–2", "60 s"),
    ], "MODERATE", 80),
], "1–4", "Após A/B/C, inserir um dia de descanso e reiniciar o ciclo.")


MALE_ADVANCED = phase("base", "Semanas 1–8", "ABCDE avançado com especialização de pernas", [
    session("A · Pernas / Quadríceps", ["Quadríceps", "Panturrilhas"], [
        ex("adductor-machine", 5, "15", "1", "60 s", "superset", "Isometria de 5 s no pico."),
        ex("abductor-machine", 5, "15", "1", "60 s", "superset"),
        ex("lying-leg-curl", 4, "12", "1–2", "60 s"),
        ex("leg-extension", 4, "10 + 10 + 10", "0–1", "60 s", "drop-set"),
        ex("lunge", 4, "12/cada", "1–2", "60 s"),
        ex("leg-press", 5, "15", "1–2", "60 s"),
        ex("hack-squat", 5, "10/10/8/8/8", "1", "2 min", "pyramid"),
        ex("standing-calf", 5, "15", "1", "60 s", "superset"),
        ex("leg-press-calf", 5, "15", "1", "60 s", "superset"),
    ], "HIGH", 90),
    session("B · Peito & Tríceps", ["Peitoral", "Tríceps"], [
        ex("incline-smith", 5, "12/12/8/8/8", "1", "2 min", "pyramid"),
        ex("cable-incline-fly", 4, "12", "1–2", "60 s"),
        ex("smith-bench-press", 5, "12/12/8/8/8", "1", "2 min", "pyramid"),
        ex("db-pullover", 4, "12", "1–2", "60 s", "superset"),
        ex("dip", 4, "12", "1–2", "60 s", "superset"),
        ex("ez-skullcrusher", 4, "12", "1–2", "60 s"),
        ex("rope-pushdown", 4, "12", "1–2", "60 s"),
        ex("cable-pushdown", 4, "12", "1–2", "60 s"),
    ], "HIGH", 80),
    session("C · Costas", ["Costas", "Trapézio", "Panturrilhas"], [
        ex("bb-row", 4, "12/12/10/10", "1–2", "2 min"),
        ex("db-row", 4, "12/12/10/10", "1–2", "90 s"),
        ex("cable-row", 4, "12/12/10/10", "1–2", "90 s"),
        ex("cable-straight-arm-pulldown", 4, "12", "1–2", "60 s"),
        ex("cable-pulldown", 4, "12/12/10/10", "1–2", "90 s"),
        ex("conventional-deadlift", 5, "12/12/8/8/8", "1", "3 min", "pyramid"),
        ex("db-shrug", 4, "12", "1–2", "60 s"),
        ex("standing-calf", 5, "15", "1", "60 s", "superset"),
        ex("seated-calf", 5, "15", "1", "60 s", "superset"),
    ], "HIGH", 90),
    session("D · Posteriores & Glúteos", ["Posteriores", "Glúteos", "Panturrilhas"], [
        ex("hip-thrust", 5, "12", "1", "60 s", "straight", "Isometria de 3 s no pico."),
        ex("adductor-machine", 5, "12", "1", "60 s", "superset"),
        ex("goblet-squat", 5, "12", "1", "60 s", "superset"),
        ex("db-rdl", 4, "15", "1–2", "60 s"),
        ex("lying-leg-curl", 4, "15", "1–2", "60 s"),
        ex("seated-hamstring-curl", 4, "12", "1–2", "60 s"),
        ex("leg-press", 4, "15 unilateral", "1–2", "60 s"),
        ex("standing-calf", 5, "15", "1", "60 s", "superset"),
        ex("leg-press-calf", 5, "15", "1", "60 s", "superset"),
    ], "HIGH", 85),
    session("E · Ombros & Bíceps", ["Deltoides", "Bíceps"], [
        ex("smith-ohp", 5, "10/10/8/8/8", "1", "2 min", "pyramid"),
        ex("db-lateral-raise", 4, "12", "1", "60 s", "superset"),
        ex("cable-front-raise", 4, "12", "1", "60 s", "superset"),
        ex("db-arnold-press", 4, "12/12/10/10", "1–2", "90 s"),
        ex("machine-rear-fly", 4, "12", "1–2", "60 s", "superset"),
        ex("cable-upright-row", 4, "12", "1–2", "60 s", "superset"),
        ex("preacher-curl", 4, "12", "1–2", "60 s"),
        ex("cable-hammer-curl", 4, "12", "1–2", "60 s"),
        ex("incline-db-curl", 4, "12", "1–2", "60 s"),
    ], "HIGH", 85),
], "1–8", "A referência também inclui um dia separado de cardio e core entre C e D.")


UPPER_LOWER = phase("base", "Upper/Lower A-B", "Quatro sessões com 48–78 h entre lowers", [
    session("Upper A", ["Peitoral", "Costas", "Ombros", "Braços"], [
        ex("bb-bench-press", 5, "8/8/6/6/6", "1–2", "3 min", "pyramid"),
        ex("db-ohp", 4, "8", "1–2", "90 s"),
        ex("pullup", 3, "8", "1–2", "60 s"),
        ex("bb-row", 3, "10", "1–2", "60 s", "superset"),
        ex("db-pullover", 3, "10", "1–2", "60 s", "superset"),
        ex("lateral-raise", 3, "12/cada", "2", "sem descanso"),
        ex("bb-curl", 4, "10", "1–2", "60 s", "superset"),
        ex("dip", 4, "8", "1–2", "60 s"),
    ], "MODERATE", 60),
    session("Lower A", ["Quadríceps", "Posteriores", "Glúteos"], [
        ex("bb-squat", 5, "8/8/6/6/6", "1–2", "3 min", "pyramid"),
        ex("conventional-deadlift", 4, "8", "1–2", "2 min", "straight", "Use variação sumô se tecnicamente dominada."),
        ex("leg-press", 3, "10", "1–2", "60 s"),
        ex("hip-thrust", 4, "15", "1–2", "60 s"),
        ex("lunge", 4, "10/cada", "1–2", "60 s", "superset"),
        ex("seated-hamstring-curl", 3, "12", "1–2", "40 s"),
        ex("seated-calf", 4, "25", "1–2", "45 s"),
        ex("standing-calf", 4, "30", "1–2", "20 s"),
    ], "HIGH", 65),
    session("Upper B", ["Peitoral", "Costas", "Ombros", "Braços"], [
        ex("db-bench-press", 5, "8", "1–2", "2 min"),
        ex("cable-fly", 4, "10", "1–2", "60 s"),
        ex("db-ohp", 4, "10/10/8/6", "1–2", "90 s", "pyramid"),
        ex("bb-row", 4, "10/10/8/8", "1–2", "90 s", "superset"),
        ex("db-pullover", 3, "10", "1–2", "90 s", "superset"),
        ex("lateral-raise", 3, "12/cada", "2", "sem descanso"),
        ex("bb-curl", 4, "10", "1–2", "60 s", "superset"),
        ex("dip", 4, "8", "1–2", "60 s"),
    ], "MODERATE", 60),
    session("Lower B", ["Quadríceps", "Posteriores", "Panturrilhas"], [
        ex("goblet-squat", 4, "12/12/10/10", "1–2", "60 s", "pyramid"),
        ex("lunge", 3, "10/cada", "2", "60 s", "straight", "Cadência lenta controlada."),
        ex("leg-press", 3, "12", "1–2", "40 s"),
        ex("leg-extension", 3, "12", "1–2", "60 s", "superset"),
        ex("hack-squat", 3, "40 s isometria", "2", "60 s", "superset"),
        ex("seated-hamstring-curl", 3, "12", "1–2", "40 s", "straight", "Cadência lenta controlada."),
        ex("seated-calf", 4, "25", "1–2", "45 s"),
    ], "MODERATE", 60),
], "1–12", "Rotina completa de quatro dias; distribua os lowers com pelo menos 48 h de recuperação.")


def six_day_sessions(sets, reps, method="straight", rir="1–2"):
    """Shared exercise architecture for the 12-week six-day reference."""
    return [
        session("A · Quadríceps & Panturrilhas", ["Quadríceps", "Panturrilhas"], [
            ex("leg-extension", sets, reps, rir, "90 s", method), ex("hack-squat", sets, reps, rir, "2 min", method),
            ex("leg-press", sets, reps, rir, "2 min", method), ex("front-squat", sets, reps, rir, "2 min", method),
            ex("lying-leg-curl", sets, reps, rir, "90 s", method), ex("rdl", sets, reps, rir, "2 min", method),
            ex("standing-calf", sets, reps, rir, "60 s", method), ex("seated-calf", sets, reps, rir, "60 s", method),
        ], "HIGH", 85),
        session("B · Peito, Tríceps & Core", ["Peitoral", "Tríceps", "Core"], [
            ex("cable-incline-fly", sets, reps, rir, "90 s", method), ex("incline-smith", sets, reps, rir, "2 min", method),
            ex("db-bench-press", sets, reps, rir, "2 min", method), ex("cable-fly", sets, reps, rir, "90 s", method),
            ex("dip", sets, reps, rir, "90 s", method), ex("cable-pushdown", sets, reps, rir, "60 s", method),
            ex("ez-skullcrusher", sets, reps, rir, "60 s", method), ex("cable-crunch", sets, reps, rir, "60 s", method),
        ], "HIGH", 85),
        session("C · Costas, Bíceps & Antebraços", ["Costas", "Bíceps"], [
            ex("cable-pulldown", sets, reps, rir, "90 s", method), ex("lat-prayer", sets, reps, rir, "90 s", method),
            ex("bb-row", sets, reps, rir, "2 min", method), ex("cable-row", sets, reps, rir, "90 s", method),
            ex("db-row", sets, reps, rir, "90 s", method), ex("conventional-deadlift", sets, reps, rir, "3 min", method),
            ex("bb-curl", sets, reps, rir, "60 s", method), ex("preacher-curl", sets, reps, rir, "60 s", method),
            ex("db-hammer-curl", sets, reps, rir, "60 s", method),
        ], "HIGH", 90),
        session("D · Ombros, Trapézio & Core", ["Deltoides", "Trapézio", "Core"], [
            ex("db-lateral-raise", sets, reps, rir, "60 s", method), ex("smith-ohp", sets, reps, rir, "2 min", method),
            ex("cable-front-raise", sets, reps, rir, "60 s", method), ex("lateral-raise", sets, reps, rir, "60 s", method),
            ex("machine-rear-fly", sets, reps, rir, "60 s", method), ex("cable-upright-row", sets, reps, rir, "60 s", method),
            ex("db-shrug", sets, reps, rir, "60 s", method), ex("hanging-leg-raise", sets, reps, rir, "60 s", method),
        ], "HIGH", 80),
        session("E · Posteriores, Glúteos & Panturrilhas", ["Posteriores", "Glúteos", "Panturrilhas"], [
            ex("lying-leg-curl", sets, reps, rir, "60 s", method), ex("seated-hamstring-curl", sets, reps, rir, "60 s", method),
            ex("rdl", sets, reps, rir, "2 min", method), ex("hip-thrust", sets, reps, rir, "90 s", method),
            ex("abductor-machine", sets, reps, rir, "60 s", method), ex("cable-glute-kickback", sets, reps, rir, "60 s", method),
            ex("goblet-squat", sets, reps, rir, "90 s", method), ex("standing-calf", sets, reps, rir, "60 s", method),
        ], "HIGH", 85),
        session("F · Peitoral & Tríceps", ["Peitoral", "Tríceps"], [
            ex("bb-bench-press", sets, reps, rir, "2 min", method), ex("cable-fly", sets, reps, rir, "90 s", method),
            ex("db-pullover", sets, reps, rir, "90 s", method), ex("db-incline-press", sets, reps, rir, "2 min", method),
            ex("rope-pushdown", sets, reps, rir, "60 s", method), ex("cable-overhead-extension", sets, reps, rir, "60 s", method),
            ex("dip-machine", sets, reps, rir, "60 s", method),
        ], "MODERATE", 70),
    ]


TWELVE_WEEK_PHASES = [
    phase("tempo-4x10", "Fase 1 · Tempo 4×10", "Tempo sob tensão 4 s concêntrica / 5 s excêntrica",
          six_day_sessions(4, "10", "straight", "2"), "1, 5 e 9", "Controle técnico e familiarização; não buscar falha."),
    phase("cadence-4x15", "Fase 2 · Cadência 4×15", "Cadência controlada e intenção explosiva",
          six_day_sessions(4, "15", "straight", "2"), "2, 6 e 10", "Carga reduzida para manter as 15 repetições limpas."),
    phase("triset-12", "Fase 3 · Tri-set 12", "Blocos de três exercícios com descanso após o bloco",
          six_day_sessions(3, "12", "superset", "1–2"), "3, 7 e 11", "Cada trio deve ser organizado em sequência no Program Builder."),
    phase("strength", "Fase 4 · Força & Recuperação", "Compostos, progressão de carga e descanso ampliado", [
        session("A · Agachamento", ["Quadríceps", "Posteriores", "Panturrilhas"], [
            ex("bb-squat", 8, "15→10→8→4", "1–2", "4–5 min", "pyramid", "Escada original normalizada para o limite do builder."),
            ex("seated-hamstring-curl", 6, "8→6", "1–2", "2 min", "pyramid"),
            ex("lying-leg-curl", 6, "8→6", "1–2", "2 min", "pyramid"),
            ex("seated-calf", 4, "20", "1–2", "60 s"),
        ], "HIGH", 80),
        session("B · Supino", ["Peitoral", "Tríceps"], [
            ex("bb-bench-press", 8, "15→12→8→4", "1–2", "4–5 min", "pyramid", "Escada original normalizada para o limite do builder."),
            ex("dip", 6, "8→6", "1–2", "2 min", "pyramid"),
            ex("cable-pushdown", 8, "15→10→6", "1–2", "2 min", "pyramid"),
        ], "HIGH", 70),
        session("C · Terra", ["Costas", "Bíceps"], [
            ex("conventional-deadlift", 8, "15→8→4", "1–2", "4–5 min", "pyramid", "Escada original normalizada para o limite do builder."),
            ex("pullup", 6, "8→6", "1–2", "2 min", "pyramid"),
            ex("bb-curl", 8, "10→8→4", "1–2", "2 min", "pyramid"),
        ], "HIGH", 70),
        session("D · Terra Sumô & Glúteos", ["Posteriores", "Glúteos", "Panturrilhas"], [
            ex("trap-bar-deadlift", 8, "10→8→4", "1–2", "4–5 min", "pyramid", "Use terra sumô somente se houver domínio técnico."),
            ex("lying-leg-curl", 6, "10→8→6", "1–2", "2 min", "pyramid"),
            ex("hip-thrust", 8, "10→8→6", "1–2", "2 min", "pyramid"),
            ex("standing-calf", 8, "15→10→6", "1–2", "90 s", "pyramid"),
        ], "HIGH", 80),
        session("E · Peito & Tríceps", ["Peitoral", "Tríceps"], [
            ex("incline-smith", 8, "15→10→6", "1–2", "3 min", "pyramid"),
            ex("bb-bench-press", 8, "10→8→4", "1–2", "3 min", "pyramid"),
            ex("cable-pushdown", 8, "10→8", "1–2", "2 min", "pyramid"),
        ], "HIGH", 75),
    ], "4, 8 e 12", "Inclui um dia extra de descanso antes do treino de posteriores."),
]


ABCDEF_INTENSIFICATION = phase("base", "Microciclo ABCDEF", "Progressão, pico de contração e intensificadores", [
    session("A · Costas & Panturrilhas", ["Costas", "Panturrilhas"], [
        ex("standing-calf", 4, "15→6 + drops", "1", "60 s", "drop-set"),
        ex("bb-row", 4, "15→6", "1", "2–3 min", "pyramid"),
        ex("cable-row", 3, "10–15", "1", "2 min", "superset"),
        ex("db-row", 3, "10–15", "1", "2 min", "superset"),
        ex("cable-straight-arm-pulldown", 3, "8–12", "1", "60 s"),
        ex("cable-pulldown", 3, "15→6 + drops", "1", "90 s", "drop-set"),
        ex("lat-prayer", 3, "8–12", "1", "45 s"),
        ex("conventional-deadlift", 4, "15→6", "1–2", "2–3 min", "pyramid"),
    ], "HIGH", 85),
    session("B · Peitoral & Core", ["Peitoral", "Core"], [
        ex("incline-smith", 4, "15→6 + strip", "1", "2–3 min", "drop-set"),
        ex("db-bench-press", 4, "15→6 + drops", "1", "2 min", "drop-set"),
        ex("cable-incline-fly", 3, "8–12", "1", "60 s", "superset"),
        ex("db-incline-press", 3, "8–12", "1", "60 s", "superset"),
        ex("db-decline-press", 3, "8–12", "1", "45 s"),
        ex("pec-deck", 3, "8–12 + rest-pause", "0–1", "60 s", "rest-pause"),
        ex("cable-crunch", 3, "máximo técnico", "1", "45 s"),
    ], "HIGH", 80),
    session("C · Quadríceps", ["Quadríceps", "Posteriores", "Adutores"], [
        ex("bb-squat", 4, "15→6", "1", "2–3 min", "pyramid"),
        ex("leg-press", 3, "10 + parciais", "0–1", "90 s", "lengthened-partials"),
        ex("hack-squat", 3, "15→6 + rest-pause", "0–1", "2 min", "rest-pause"),
        ex("leg-extension", 5, "20→6 + drops", "0–1", "90 s", "drop-set"),
        ex("seated-hamstring-curl", 3, "10–15", "1", "45 s"),
        ex("adductor-machine", 5, "10–15", "1", "45 s", "superset"),
        ex("abductor-machine", 5, "10–15", "1", "45 s", "superset"),
    ], "HIGH", 85),
    session("D · Ombros & Panturrilhas", ["Deltoides", "Panturrilhas"], [
        ex("standing-calf", 4, "15→6 + drops", "1", "60 s", "drop-set"),
        ex("seated-calf", 3, "15→6 + rest-pause", "1", "60 s", "rest-pause"),
        ex("db-ohp", 4, "15→6 + drop/rest", "1", "2–3 min", "drop-set"),
        ex("cable-front-raise", 3, "15→6 + drops", "1", "60 s", "drop-set"),
        ex("db-lateral-raise", 3, "8–12 + parciais", "0–1", "45 s", "lengthened-partials"),
        ex("lateral-raise", 3, "8–12", "1", "45 s"),
        ex("machine-rear-fly", 3, "8–12", "1", "45 s"),
    ], "HIGH", 80),
    session("E · Braços & Core", ["Bíceps", "Tríceps", "Core"], [
        ex("bb-curl", 5, "15→6 + rest-pause", "1", "90 s", "rest-pause"),
        ex("preacher-curl", 3, "8–12", "1", "60 s"),
        ex("incline-db-curl", 4, "8–12", "1", "60 s"),
        ex("cable-hammer-curl", 3, "8–12", "1", "60 s"),
        ex("ez-skullcrusher", 4, "15→6 + drops", "1", "90 s", "drop-set"),
        ex("rope-pushdown", 4, "8–12", "1", "60 s"),
        ex("cable-overhead-extension", 4, "8–12 + drop", "1", "60 s", "drop-set"),
        ex("hanging-leg-raise", 3, "máximo técnico", "1", "45 s"),
    ], "HIGH", 85),
    session("F · Posteriores & Glúteos", ["Posteriores", "Glúteos"], [
        ex("lying-leg-curl", 4, "15→6 + rest-pause", "1", "2 min", "rest-pause"),
        ex("seated-hamstring-curl", 4, "10–15 + parciais", "1", "60 s", "lengthened-partials"),
        ex("rdl", 4, "15→6", "1", "60 s", "pyramid"),
        ex("lunge", 3, "10–15/cada", "1", "60 s"),
        ex("hip-thrust", 4, "10–15", "1", "60 s"),
        ex("trap-bar-deadlift", 3, "15→6", "1", "60 s", "pyramid"),
        ex("abductor-machine", 3, "10–15", "1", "60 s"),
    ], "HIGH", 85),
], "", "Estratégia original de seis dias com descanso obrigatório após a terceira sessão.")


TRAINING_PROGRAMS = [
    program("abc-intermediate-4w", "abc", "ABC Intermediário", "Intermediário", 4, "Geral",
            "Ciclo rotativo de pernas, peito/braços e costas/ombros com descanso a cada três sessões.",
            "Júlio Balestrin · material enviado", [MALE_INTERMEDIATE]),
    program("abcd-wellness-advanced", "abcd", "ABCD Wellness Avançado", "Avançado", 5, "Ênfase feminina / Wellness",
            "Quatro sessões com prioridade para membros inferiores e supersets de alta densidade.",
            "Vinicius Piffardini · material enviado", [FEMALE_ADVANCED], audience_type="female"),
    program("abcde-advanced-8w", "abcde", "ABCDE Avançado 3", "Avançado", 8, "Geral",
            "Divisão avançada com duas sessões de pernas, cardio complementar e progressões piramidais.",
            "Júlio Balestrin · material enviado", [MALE_ADVANCED]),
    program("abcde-high-recovery", "abcde", "ABCDE Alta Recuperação", "Especialista", 4, "Atletas avançados",
            "Bi-sets, tri-sets, séries gigantes e drops com volume e densidade excepcionalmente altos.",
            "Fórmula dos Gigantes · material enviado", [ENHANCED_HIGH_VOLUME], "expert",
            "Programa extremo. Não é indicação de uso de substâncias; exige experiência, recuperação monitorada e liberação profissional."),
    program("abcdef-intensification", "abcdef", "ABCDEF Intensificação 6×", "Avançado", 4, "Fisiculturismo",
            "Seis dias de especialização com progressão, contração de pico, drops, parciais e descanso após C.",
            "Material profissional ABCDEF enviado", [ABCDEF_INTENSIFICATION], "advanced",
            "Alto volume: respeite o descanso após a terceira sessão e reduza técnicas se a recuperação cair."),
    program("abcdef-12-week", "abcdef", "ABCDEF 12 Semanas", "Avançado", 12, "Fisiculturismo",
            "Quatro fases repetidas em três blocos: tempo, cadência, tri-sets e força/recuperação.",
            "Johann Schatz · material enviado", TWELVE_WEEK_PHASES, "advanced",
            "Escolha uma fase por vez. A quarta fase usa descanso ampliado e escadas de carga normalizadas."),
    program("upper-lower-12w", "upper_lower", "Upper / Lower 12 Semanas", "Intermediário", 12, "Geral",
            "Dois uppers e dois lowers com ênfase equilibrada em hipertrofia e recuperação entre inferiores.",
            "Paulo Roberto Segóvia · material enviado", [UPPER_LOWER]),
]


from female_reference_programs import build_female_reference_programs
TRAINING_PROGRAMS.extend(build_female_reference_programs(ex, session, phase, program))
from male_reference_programs import build_male_reference_programs
TRAINING_PROGRAMS.extend(build_male_reference_programs(ex, session, phase, program))


def public_program_catalog():
    programs = deepcopy(TRAINING_PROGRAMS)
    for item in programs:
        item["categories"] = [item["category"]]
        if len(item["phases"]) > 1:
            item["categories"].append("periodized")
        for program_phase in item["phases"]:
            for day, workout in enumerate(program_phase["sessions"], start=1):
                workout["day"] = day
                workout["exercise_count"] = len(workout["exercises"])
                workout["total_sets"] = sum(int(exercise["sets"]) for exercise in workout["exercises"])
            program_phase["days_per_week"] = len(program_phase["sessions"])
            program_phase["total_sets"] = sum(workout["total_sets"] for workout in program_phase["sessions"])
        item["phase_count"] = len(item["phases"])
        item["days_per_week"] = max(len(program_phase["sessions"]) for program_phase in item["phases"])
    return {"program_categories": deepcopy(PROGRAM_CATEGORIES), "programs": programs}

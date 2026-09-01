"""Curated FORGE workout-session library.

The library is intentionally deterministic.  Templates are professional starting
points that the athlete selects and then reviews in Program Builder before anything
is persisted.  They never bypass the existing custom-program validation/save flow.
"""

from copy import deepcopy


CATEGORIES = [
    {"id": "push", "label": "Push", "subtitle": "Peito, ombros e tríceps"},
    {"id": "pull", "label": "Pull", "subtitle": "Costas, deltoide posterior e bíceps"},
    {"id": "legs", "label": "Legs", "subtitle": "Quadríceps, posteriores e glúteos"},
    {"id": "upper", "label": "Upper", "subtitle": "Tronco completo"},
    {"id": "lower", "label": "Lower", "subtitle": "Membros inferiores completos"},
    {"id": "full_body", "label": "Full Body", "subtitle": "Corpo inteiro em uma sessão"},
]


def ex(exercise_id, sets, reps, rir="1–2", rest="2 min", technique_id="straight", note=""):
    technique_names = {
        "straight": "Straight Sets",
        "top-set-backoff": "Top Set + Back-off",
        "myo-reps": "Myo-Reps",
        "rest-pause": "Rest-Pause",
        "superset": "Superset",
    }
    return {
        "exercise_id": exercise_id,
        "sets": sets,
        "reps": reps,
        "rir": rir,
        "rest": rest,
        "load": 0,
        "technique_id": technique_id,
        "technique": technique_names.get(technique_id, "Straight Sets"),
        "note": note,
    }


def template(template_id, category, name, style, level, duration, demand, focus, description, exercises):
    return {
        "id": template_id,
        "category": category,
        "name": name,
        "style": style,
        "level": level,
        "duration": duration,
        "demand": demand,
        "focus": focus,
        "description": description,
        "exercises": exercises,
    }


WORKOUT_TEMPLATES = [
    template("push-base", "push", "Push Base", "Equilibrado", "Intermediário", 65, "MODERATE",
             ["Peitoral", "Deltoides", "Tríceps"], "Presses sólidos, volume equilibrado e progressão simples de carga.", [
        ex("bb-bench-press", 3, "6–8", "1–2", "3 min"),
        ex("incline-smith", 3, "8–10", "1–2", "2 min"),
        ex("db-ohp", 3, "8–12", "2", "2 min"),
        ex("lateral-raise", 3, "12–20", "1–2", "60 s"),
        ex("cable-pushdown", 3, "10–15", "1–2", "60 s"),
    ]),
    template("push-chest", "push", "Push Peitoral", "Especialização", "Avançado", 70, "HIGH",
             ["Peitoral superior", "Peitoral", "Tríceps"], "Prioriza peitoral em diferentes ângulos sem abandonar deltoides e tríceps.", [
        ex("db-incline-press", 4, "6–10", "1", "3 min", "top-set-backoff"),
        ex("machine-chest-press", 3, "8–12", "1–2", "2 min"),
        ex("cable-incline-fly", 3, "12–15", "2", "60 s"),
        ex("machine-lateral-raise", 3, "12–20", "1–2", "60 s"),
        ex("cable-overhead-extension", 3, "10–15", "1–2", "60 s"),
    ]),
    template("push-delts", "push", "Push Ombros", "Deltoides + tríceps", "Avançado", 65, "HIGH",
             ["Deltoide lateral", "Deltoide anterior", "Tríceps"], "Sessão de push com prioridade real para ombros e acabamento de tríceps.", [
        ex("smith-ohp", 4, "6–10", "1", "3 min"),
        ex("db-incline-press", 3, "8–12", "2", "2 min"),
        ex("lateral-raise", 4, "12–20", "1–2", "60 s"),
        ex("cable-upright-row", 3, "10–15", "2", "90 s"),
        ex("close-grip-bench", 3, "6–10", "1–2", "2 min"),
        ex("rope-pushdown", 2, "12–15", "1", "60 s"),
    ]),

    template("pull-width", "pull", "Pull Largura", "Dorsais", "Intermediário", 65, "MODERATE",
             ["Dorsais", "Deltoide posterior", "Bíceps"], "Puxadas verticais e trabalho de dorsal com fadiga axial controlada.", [
        ex("neutral-pullup", 3, "6–10", "1–2", "2 min"),
        ex("lat-pulldown", 3, "8–12", "1–2", "90 s"),
        ex("cable-straight-arm-pulldown", 3, "12–15", "2", "60 s"),
        ex("row", 3, "8–12", "2", "2 min"),
        ex("incline-db-curl", 3, "10–15", "1–2", "60 s"),
    ]),
    template("pull-thickness", "pull", "Pull Espessura", "Remadas", "Avançado", 70, "HIGH",
             ["Costas", "Trapézio", "Bíceps"], "Remadas pesadas para espessura com posterior de ombro e bíceps.", [
        ex("bb-row", 4, "6–8", "1", "3 min", "top-set-backoff"),
        ex("row", 3, "8–12", "1–2", "2 min"),
        ex("cable-row", 3, "10–12", "2", "90 s"),
        ex("machine-rear-fly", 3, "12–20", "1–2", "60 s"),
        ex("bb-curl", 3, "8–12", "1–2", "90 s"),
    ]),
    template("pull-low-fatigue", "pull", "Pull Controle", "Baixa fadiga", "Todos os níveis", 55, "LOW",
             ["Dorsais", "Costas", "Braços"], "Máquinas e cabos para alta qualidade técnica com recuperação rápida.", [
        ex("cable-pulldown", 3, "10–15", "2", "90 s"),
        ex("lat-prayer", 3, "10–15", "2", "90 s"),
        ex("cable-row", 3, "10–15", "2", "90 s"),
        ex("cable-face-pull", 3, "12–20", "2", "60 s"),
        ex("preacher-curl", 3, "10–15", "1–2", "60 s"),
        ex("cable-hammer-curl", 2, "12–15", "1–2", "60 s"),
    ]),

    template("legs-quads", "legs", "Legs Quadríceps", "Dominante de joelho", "Avançado", 75, "HIGH",
             ["Quadríceps", "Adutores", "Panturrilhas"], "Grande estímulo de quadríceps com posterior suficiente para equilíbrio articular.", [
        ex("hack-squat", 4, "6–10", "1", "3 min", "top-set-backoff"),
        ex("leg-press", 3, "10–15", "1–2", "2 min"),
        ex("bulgarian-split-squat", 3, "8–12", "2", "2 min"),
        ex("leg-extension", 3, "12–20", "1", "60 s", "myo-reps"),
        ex("leg-curl", 3, "10–15", "2", "60 s"),
        ex("standing-calf", 4, "12–20", "1–2", "60 s"),
    ]),
    template("legs-posterior", "legs", "Legs Posterior", "Cadeia posterior", "Avançado", 75, "HIGH",
             ["Posteriores", "Glúteos", "Panturrilhas"], "Dobradiça de quadril, flexão de joelho e extensão de quadril bem distribuídas.", [
        ex("rdl", 4, "6–10", "1", "3 min"),
        ex("lying-leg-curl", 4, "8–12", "1–2", "90 s"),
        ex("hip-thrust", 3, "8–12", "1–2", "2 min"),
        ex("db-step-up", 3, "8–12", "2", "90 s"),
        ex("abductor-machine", 3, "12–20", "1", "60 s"),
        ex("seated-calf", 4, "12–20", "1–2", "60 s"),
    ]),
    template("legs-balanced", "legs", "Legs Completo", "Equilibrado", "Intermediário", 70, "MODERATE",
             ["Quadríceps", "Posteriores", "Glúteos"], "Sessão completa com volume moderado para todas as regiões da perna.", [
        ex("bb-squat", 3, "6–8", "1–2", "3 min"),
        ex("rdl", 3, "8–10", "1–2", "2 min"),
        ex("leg-press", 3, "10–15", "2", "2 min"),
        ex("seated-hamstring-curl", 3, "10–15", "1–2", "60 s"),
        ex("leg-extension", 2, "12–20", "1", "60 s"),
        ex("leg-press-calf", 4, "12–20", "1–2", "60 s"),
    ]),

    template("upper-balanced", "upper", "Upper Base", "Equilibrado", "Intermediário", 70, "MODERATE",
             ["Peitoral", "Costas", "Ombros", "Braços"], "Um upper completo, eficiente e fácil de progredir duas vezes por semana.", [
        ex("bb-bench-press", 3, "6–8", "1–2", "3 min"),
        ex("row", 3, "8–12", "1–2", "2 min"),
        ex("lat-pulldown", 3, "8–12", "2", "90 s"),
        ex("db-ohp", 3, "8–12", "2", "2 min"),
        ex("lateral-raise", 3, "12–20", "1–2", "60 s"),
        ex("cable-curl", 2, "10–15", "1–2", "60 s"),
        ex("cable-pushdown", 2, "10–15", "1–2", "60 s"),
    ]),
    template("upper-torso", "upper", "Upper Torso", "Peito + costas", "Avançado", 75, "HIGH",
             ["Peitoral superior", "Dorsais", "Costas"], "Mais volume para o tronco, mantendo braços com trabalho direto econômico.", [
        ex("db-incline-press", 4, "6–10", "1", "3 min"),
        ex("neutral-pullup", 3, "6–10", "1–2", "2 min"),
        ex("machine-chest-press", 3, "8–12", "1–2", "2 min"),
        ex("bb-row", 3, "6–10", "1–2", "2 min"),
        ex("cable-incline-fly", 2, "12–15", "2", "60 s"),
        ex("cable-straight-arm-pulldown", 2, "12–15", "2", "60 s"),
        ex("rope-pushdown", 2, "10–15", "1–2", "60 s"),
        ex("bayesian-curl", 2, "10–15", "1–2", "60 s"),
    ]),
    template("upper-delts-arms", "upper", "Upper Delts & Arms", "Especialização", "Avançado", 65, "MODERATE",
             ["Deltoides", "Bíceps", "Tríceps"], "Upper com manutenção de peito e costas e prioridade para deltoides e braços.", [
        ex("smith-ohp", 3, "6–10", "1–2", "2 min"),
        ex("machine-chest-press", 2, "8–12", "2", "2 min"),
        ex("cable-row", 2, "8–12", "2", "2 min"),
        ex("machine-lateral-raise", 4, "12–20", "1", "60 s"),
        ex("machine-rear-fly", 3, "12–20", "1–2", "60 s"),
        ex("incline-db-curl", 3, "10–15", "1–2", "60 s"),
        ex("cable-overhead-extension", 3, "10–15", "1–2", "60 s"),
    ]),

    template("lower-strength", "lower", "Lower Força", "Compostos", "Avançado", 75, "HIGH",
             ["Quadríceps", "Posteriores", "Glúteos"], "Compostos pesados com acessórios suficientes para hipertrofia e estabilidade.", [
        ex("bb-squat", 4, "4–6", "1–2", "4 min", "top-set-backoff"),
        ex("rdl", 3, "6–8", "1–2", "3 min"),
        ex("leg-press", 3, "8–12", "2", "2 min"),
        ex("lying-leg-curl", 3, "8–12", "1–2", "90 s"),
        ex("standing-calf", 4, "10–15", "1–2", "60 s"),
    ]),
    template("lower-quads", "lower", "Lower Quadríceps", "Hipertrofia", "Intermediário", 70, "HIGH",
             ["Quadríceps", "Adutores", "Posteriores"], "Lower dominante de quadríceps com posterior em dose de manutenção produtiva.", [
        ex("front-squat", 3, "6–10", "1–2", "3 min"),
        ex("hack-squat", 3, "8–12", "1–2", "2 min"),
        ex("db-step-up", 3, "8–12", "2", "90 s"),
        ex("leg-extension", 3, "12–20", "1", "60 s", "rest-pause"),
        ex("leg-curl", 3, "10–15", "2", "60 s"),
        ex("adductor-machine", 3, "12–20", "2", "60 s"),
    ]),
    template("lower-glutes", "lower", "Lower Glúteos", "Glúteos + posterior", "Intermediário", 70, "MODERATE",
             ["Glúteos", "Posteriores", "Quadríceps"], "Extensão de quadril, posição alongada e trabalho unilateral bem distribuídos.", [
        ex("hip-thrust", 4, "6–10", "1–2", "3 min"),
        ex("db-rdl", 3, "8–12", "2", "2 min"),
        ex("bulgarian-split-squat", 3, "8–12", "1–2", "2 min"),
        ex("seated-hamstring-curl", 3, "10–15", "1–2", "60 s"),
        ex("cable-glute-kickback", 3, "12–15", "1", "60 s"),
        ex("abductor-machine", 3, "15–20", "1", "60 s"),
    ]),

    template("full-body-base", "full_body", "Full Body Base", "Equilibrado", "Todos os níveis", 65, "MODERATE",
             ["Corpo inteiro", "Progressão", "Eficiência"], "Um padrão de cada família de movimento para evoluir com clareza.", [
        ex("leg-press", 3, "8–12", "1–2", "2 min"),
        ex("bb-bench-press", 3, "6–10", "1–2", "2 min"),
        ex("row", 3, "8–12", "1–2", "2 min"),
        ex("rdl", 3, "8–10", "2", "2 min"),
        ex("lateral-raise", 2, "12–20", "1–2", "60 s"),
        ex("cable-curl", 2, "10–15", "1–2", "60 s"),
        ex("cable-pushdown", 2, "10–15", "1–2", "60 s"),
    ]),
    template("full-body-strength", "full_body", "Full Body Performance", "Força + hipertrofia", "Avançado", 75, "HIGH",
             ["Força", "Compostos", "Corpo inteiro"], "Base pesada nos grandes movimentos com acessórios de baixo custo de fadiga.", [
        ex("bb-squat", 3, "4–6", "1–2", "4 min"),
        ex("bb-bench-press", 3, "4–6", "1–2", "3 min"),
        ex("neutral-pullup", 3, "6–10", "1–2", "2 min"),
        ex("rdl", 3, "6–8", "2", "3 min"),
        ex("machine-lateral-raise", 3, "12–20", "1–2", "60 s"),
        ex("cable-crunch", 3, "12–20", "2", "60 s"),
    ]),
    template("full-body-efficient", "full_body", "Full Body 45", "Alta eficiência", "Intermediário", 45, "LOW",
             ["Corpo inteiro", "Máquinas", "Tempo"], "Sessão curta com exercícios estáveis e transições rápidas para dias corridos.", [
        ex("hack-squat", 3, "8–12", "2", "90 s"),
        ex("machine-chest-press", 3, "8–12", "2", "90 s"),
        ex("cable-pulldown", 3, "8–12", "2", "90 s"),
        ex("seated-hamstring-curl", 3, "10–15", "2", "60 s"),
        ex("machine-lateral-raise", 2, "12–20", "1–2", "60 s"),
        ex("cable-curl", 2, "10–15", "1–2", "60 s", "superset"),
        ex("rope-pushdown", 2, "10–15", "1–2", "60 s", "superset"),
    ]),
]


def public_catalog():
    """Return session templates and complete programs with calculated metadata."""
    templates = deepcopy(WORKOUT_TEMPLATES)
    for item in templates:
        item["exercise_count"] = len(item["exercises"])
        item["total_sets"] = sum(int(exercise["sets"]) for exercise in item["exercises"])
    # Imported lazily to keep the small session primitives reusable without a
    # circular module dependency during application startup.
    from training_programs import public_program_catalog

    return {
        "categories": deepcopy(CATEGORIES),
        "templates": templates,
        **public_program_catalog(),
    }

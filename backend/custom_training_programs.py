"""User-authored complete programs shown under the Custom library category.

Keep custom routines isolated from the curated/reference catalog so future routines can
be added without mixing them with imported professional programs. The installer is
idempotent because runtime bootstrap and tests may import it more than once.
"""

from copy import deepcopy


CUSTOM_CATEGORY = {
    "id": "custom",
    "label": "Custom",
    "subtitle": "Treinos criados por você",
}


def _rest(value=None):
    # The submitted routine does not define rest for every exercise. Keep that fact
    # visible instead of inventing a number; the live workout already has its normal
    # fallback timer for prescriptions without a numeric duration.
    return value or "Padrão FORGE"


def build_custom_training_programs(ex, session, phase, program):
    hybrid_phase = phase(
        "upper-full-body-hybrid",
        "Bloco 4–6 semanas",
        "Upper + Full Body · Double Progression",
        [
            session("Segunda · Upper A", ["Peitoral", "Costas", "Deltoides", "Braços"], [
                ex("incline-smith", 3, "5–8", "2", _rest("2–3 min")),
                ex("machine-chest-press", 3, "6–10", "1–2", _rest("2 min")),
                ex("row", 3, "6–10", "1–2", _rest()),
                ex("cable-pulldown", 3, "8–12", "1–2", _rest(), note="Pegada neutra."),
                ex("cable-fly", 2, "12–15", "1", _rest()),
                ex("lateral-raise", 3, "12–20", "1–2", _rest()),
                ex("cable-overhead-extension", 2, "10–15", "1–2", _rest()),
                ex("cable-curl", 2, "10–15", "1–2", _rest(), note="Execução controlada; interromper se houver desconforto."),
            ], "HIGH", 65),
            session("Terça · Full Body A", ["Quadríceps", "Posteriores", "Peitoral", "Costas"], [
                ex("hack-squat", 3, "6–10", "2", _rest()),
                ex("leg-press", 3, "10–15", "1–2", _rest()),
                ex("leg-extension", 2, "12–20", "1", _rest()),
                ex("leg-curl", 2, "10–15", "1–2", _rest()),
                ex("db-incline-press", 2, "10–15", "3", _rest(), note="Microdose de peito; baixa fadiga. Preferir máquina inclinada quando disponível."),
                ex("cable-row", 2, "10–15", "2–3", _rest(), note="Executar unilateralmente quando o equipamento permitir."),
                ex("lateral-raise", 2, "15–20", "1–2", _rest()),
                ex("standing-calf", 3, "8–15", "1–2", _rest(), note="Pode usar máquina equivalente."),
            ], "MODERATE", 65),
            session("Quarta · Upper B", ["Costas", "Peitoral", "Deltoide posterior", "Bíceps"], [
                ex("row", 3, "6–10", "1–2", _rest()),
                ex("cable-pulldown", 3, "8–12", "1–2", _rest(), note="Pegada neutra."),
                ex("cable-row", 2, "10–15", "1–2", _rest(), note="Executar unilateralmente quando o equipamento permitir."),
                ex("db-incline-press", 3, "8–12", "2", _rest(), note="Halteres ou máquina inclinada."),
                ex("cable-incline-fly", 2, "12–20", "1–2", _rest(), note="Cabo baixo para cima."),
                ex("machine-rear-fly", 3, "12–20", "1–2", _rest(), note="Máquina ou cabo."),
                ex("preacher-curl", 2, "10–15", "1–2", _rest(), note="Preferir máquina; carga controlada."),
                ex("cable-hammer-curl", 2, "10–15", "1–2", _rest(), note="Não perseguir falha se houver desconforto."),
            ], "HIGH", 65),
            session("Sexta · Upper C", ["Peitoral", "Deltoides", "Tríceps"], [
                ex("machine-chest-press", 3, "6–10", "1–2", _rest()),
                ex("incline-smith", 2, "8–12", "2", _rest()),
                ex("cable-fly", 2, "12–20", "1", _rest()),
                ex("lateral-raise", 3, "12–20", "1–2", _rest()),
                ex("machine-ohp", 2, "8–12", "2", _rest()),
                ex("cable-overhead-extension", 3, "8–12", "1–2", _rest()),
                ex("cable-pushdown", 2, "12–20", "1–2", _rest()),
            ], "HIGH", 65),
            session("Sábado · Full Body B", ["Posteriores", "Quadríceps", "Peitoral", "Costas"], [
                ex("rdl", 3, "6–10", "2", _rest()),
                ex("leg-curl", 3, "8–12", "1–2", _rest(), note="Sentada ou deitada."),
                ex("hack-squat", 2, "10–15", "2", _rest(), note="Hack squat ou leg press."),
                ex("leg-extension", 2, "12–20", "1–2", _rest()),
                ex("db-incline-press", 2, "10–15", "3", _rest(), note="Microdose de peito; preferir máquina inclinada quando disponível."),
                ex("cable-pulldown", 2, "10–15", "2–3", _rest(), note="Pegada neutra."),
                ex("lateral-raise", 2, "15–20", "1–2", _rest()),
                ex("machine-standing-calf", 3, "10–15", "1–2", _rest()),
            ], "MODERATE", 65),
            session("Domingo · Upper D", ["Peitoral", "Costas", "Deltoides", "Braços"], [
                ex("machine-chest-press", 2, "10–15", "2", _rest(), note="Peito leve/pump; evitar cargas máximas."),
                ex("cable-fly", 2, "15–20", "1–2", _rest()),
                ex("cable-pulldown", 3, "10–15", "1–2", _rest(), note="Pegada neutra."),
                ex("row", 2, "10–15", "1–2", _rest()),
                ex("lateral-raise", 3, "15–20", "1–2", _rest()),
                ex("cable-curl", 2, "12–15", "1–2", _rest(), note="Carga confortável e execução lenta."),
                ex("cable-pushdown", 2, "12–20", "1–2", _rest()),
            ], "MODERATE", 60),
        ],
        "4–6 semanas",
        "Agenda enviada: Seg Upper A, Ter Full Body A, Qua Upper B, Qui descanso, Sex Upper C, Sáb Full Body B, Dom Upper D. "
        "Progressão: Double Progression; priorizar repetições, técnica, controle e só então carga. "
        "Queda persistente de desempenho, recuperação insuficiente ou desconforto: reduzir primeiro 1–2 séries semanais da região afetada. "
        "O pullover no cabo da sexta permanece opcional e não entra no volume padrão. Técnicas avançadas não são aplicadas automaticamente. "
        "A duração exibida na biblioteca é apenas estimativa técnica do FORGE porque o plano enviado não fixou duração por sessão.",
    )

    return [
        program(
            "custom-upper-full-body-hybrid-6x",
            "custom",
            "Upper + Full Body Híbrido",
            "Avançado",
            6,
            "Custom",
            "Hipertrofia com alta frequência de estímulo, foco em peitoral, costas e desenvolvimento geral do tronco; pernas em duas exposições semanais.",
            "Treino Custom · enviado pelo usuário",
            [hybrid_phase],
            "advanced",
            "Programa de alta frequência. A própria prescrição pede ajuste de volume quando desempenho, recuperação ou conforto piorarem.",
            audience_type="male",
        )
    ]


def install(training_programs_module):
    categories = training_programs_module.PROGRAM_CATEGORIES
    programs = training_programs_module.TRAINING_PROGRAMS

    if not any(item.get("id") == CUSTOM_CATEGORY["id"] for item in categories):
        categories.append(deepcopy(CUSTOM_CATEGORY))

    existing = {item.get("id") for item in programs}
    for item in build_custom_training_programs(
        training_programs_module.ex,
        training_programs_module.session,
        training_programs_module.phase,
        training_programs_module.program,
    ):
        if item.get("id") not in existing:
            programs.append(item)
            existing.add(item.get("id"))

    return {"categories": categories, "programs": programs}

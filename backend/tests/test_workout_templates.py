import json
from pathlib import Path

from workout_templates import CATEGORIES, WORKOUT_TEMPLATES, public_catalog
from training_programs import PROGRAM_CATEGORIES, TRAINING_PROGRAMS


EXERCISE_IDS = {
    item["id"]
    for item in json.loads((Path(__file__).parents[1] / "exercises.json").read_text(encoding="utf-8"))
}


def test_library_has_four_professional_variants_per_category_including_female_curation():
    assert [item["id"] for item in CATEGORIES] == ["push", "pull", "legs", "upper", "lower", "full_body"]
    for category in CATEGORIES:
        variants = [item for item in WORKOUT_TEMPLATES if item["category"] == category["id"]]
        assert len(variants) == 4
        assert len([item for item in variants if item["audience"] == "female"]) == 1


def test_every_template_uses_real_catalog_exercises_and_complete_prescriptions():
    template_ids = set()
    for template in WORKOUT_TEMPLATES:
        assert template["id"] not in template_ids
        template_ids.add(template["id"])
        assert 4 <= len(template["exercises"]) <= 8
        assert template["duration"] >= 40
        exercise_ids = [item["exercise_id"] for item in template["exercises"]]
        assert len(exercise_ids) == len(set(exercise_ids))
        assert set(exercise_ids) <= EXERCISE_IDS
        for exercise in template["exercises"]:
            assert 1 <= exercise["sets"] <= 8
            assert exercise["reps"]
            assert exercise["rir"]
            assert exercise["rest"]


def test_public_catalog_calculates_counts_without_mutating_source():
    catalog = public_catalog()
    assert len(catalog["templates"]) == 24
    first = catalog["templates"][0]
    assert first["exercise_count"] == len(first["exercises"])
    assert first["total_sets"] == sum(item["sets"] for item in first["exercises"])
    first["exercises"].clear()
    assert WORKOUT_TEMPLATES[0]["exercises"]


def test_complete_program_library_covers_every_supported_split():
    # "hibrido" entrou porque as fichas de seis dias com enfase rotativa nao sao mais um
    # ABCDEF: a divisao gira enfases em vez de rodar letras, e misturadas na mesma gaveta
    # quem procura um ABCDEF encontra outra coisa.
    assert [item["id"] for item in PROGRAM_CATEGORIES] == [
        "abc", "abcd", "abcde", "abcdef", "upper_lower", "hibrido", "periodized"
    ]
    # A contagem e um alarme de "confirme que foi de proposito", e nao uma regra: subiu de
    # 23 para 27 quando os quatro hibridos de prioridade clavicular foram ACRESCENTADOS aos
    # quatro que ja existiam. Quem mexer aqui tem de saber o que esta somando.
    assert len(TRAINING_PROGRAMS) == 27
    assert {item["category"] for item in TRAINING_PROGRAMS} >= {
        "abc", "abcd", "abcde", "abcdef", "upper_lower", "hibrido"
    }
    assert sum(len(item["phases"]) for item in TRAINING_PROGRAMS) == 30


def test_complete_programs_only_use_supported_exercises_and_safe_builder_shapes():
    ids = set()
    for program in TRAINING_PROGRAMS:
        assert program["id"] not in ids
        ids.add(program["id"])
        assert program["duration_weeks"] >= 4 or program["id"] == "female-shape-de-cavala" or program["id"].startswith("male-")
        assert program["phases"]
        for phase in program["phases"]:
            assert 3 <= len(phase["sessions"]) <= 7
            for session in phase["sessions"]:
                assert session["duration"] >= 45
                assert session["exercises"]
                for exercise in session["exercises"]:
                    assert exercise["exercise_id"] in EXERCISE_IDS
                    assert 1 <= exercise["sets"] <= (10 if program["id"] == "female-advanced-7" else 8)
                    assert exercise["reps"]
                    assert exercise["rir"]
                    assert exercise["rest"]


def test_program_metadata_and_expert_guard_are_exposed_without_source_mutation():
    catalog = public_catalog()
    assert len(catalog["programs"]) == 27
    periodized = next(item for item in catalog["programs"] if item["id"] == "abcdef-12-week")
    assert "abcdef" in periodized["categories"]
    assert "periodized" in periodized["categories"]
    assert periodized["phase_count"] == 4
    assert all(phase["total_sets"] > 0 for phase in periodized["phases"])
    expert = next(item for item in catalog["programs"] if item["safety"] == "expert")
    assert expert["warning"]
    catalog["programs"][0]["phases"].clear()
    assert TRAINING_PROGRAMS[0]["phases"]


def test_female_program_is_machine_filterable():
    wellness = next(item for item in TRAINING_PROGRAMS if item["id"] == "abcd-wellness-advanced")
    assert wellness["audience_type"] == "female"


def test_os_quatro_hibridos_antigos_continuam_na_biblioteca():
    """A instrucao foi ACRESCENTAR, nao substituir.

    Os nomes dos quatro novos sao parecidos com os dos quatro antigos — "Rotativo",
    "Full Body Rotativo", "Upper / Lower". Trocar um pelo outro por engano numa
    refatoracao futura nao levantaria erro nenhum sem este teste.
    """
    ids = {p["id"] for p in TRAINING_PROGRAMS}
    antigos = {p["id"] for p in TRAINING_PROGRAMS if p["category"] == "hibrido"
               and not p["id"].startswith("hibrido-clavicular")}
    assert len(antigos) == 4, antigos
    novos = {i for i in ids if i.startswith("hibrido-clavicular")}
    assert len(novos) == 4, novos
    assert not (antigos & novos)


def test_os_hibridos_claviculares_sao_distinguiveis_entre_si():
    """Oito hibridos na mesma gaveta: se dois forem iguais, escolher vira adivinhacao."""
    novos = [p for p in TRAINING_PROGRAMS if p["id"].startswith("hibrido-clavicular")]
    nomes = [p["name"] for p in novos]
    assert len(set(nomes)) == 4, nomes
    # Cada um tem um numero de sessoes ou uma forma que o separa dos outros.
    assinaturas = {(len(p["phases"][0]["sessions"]),
                    tuple(s["label"].split(" · ")[1] for s in p["phases"][0]["sessions"]))
                   for p in novos}
    assert len(assinaturas) == 4, "dois programas tem a mesma semana"


def test_o_full_body_7x_nao_tem_dia_de_descanso():
    """E caracteristica da ficha, e tem consequencia na tela.

    Sem dia sem sessao, o calendario nao marca descanso — e a opcao de trocar o dia de
    treino, que so aparece no descanso, nunca aparece para quem segue este programa. Fica
    registrado para nao ser lido como defeito depois.
    """
    p = next(x for x in TRAINING_PROGRAMS if x["id"] == "hibrido-clavicular-full-7x")
    assert len(p["phases"][0]["sessions"]) == 7
    assert "Domingo" in p["phases"][0]["sessions"][-1]["label"]

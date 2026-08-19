"""FORGE manual workout — parser unit tests.

Pure functions only: no server, no Mongo, no network. Everything here must hold before
the API layer is even considered, and it is the gate that proves the importer never
invents a set, a rep or an exercise it did not read in the text.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from manual_workout import (  # noqa: E402
    MAX_IMPORT_CHARS, REVIEW_EXERCISE_UNMATCHED, REVIEW_REPS_MISSING, REVIEW_SETS_MISSING,
    REVIEW_AMBIGUOUS, REVIEW_MULTIPLE_OPTIONS,
    draft_to_custom_program, match_exercise, parse_intensity, parse_rest, parse_technique,
    parse_workout_text, normalize_reps, resolve_exercise_name, validate_draft,
)
from engine import EXERCISE_INDEX  # noqa: E402


EXAMPLE_1 = """SEGUNDA — PUSH
Supino reto — 4x8-10 — 90s — RIR 2
Supino inclinado com halteres — 3x10
Desenvolvimento — 3x8-12
Elevação lateral — 4x12-15
Tríceps corda — 3x12

TERÇA — PULL
Puxada aberta — 4x8-10
Remada curvada — 4x8
Remada baixa — 3x10-12
Rosca direta — 3x10
Rosca martelo — 3x12"""

EXAMPLE_2 = """Treino A - Peito e tríceps
1. Supino reto: 4 séries de 8 a 10 repetições
2. Crucifixo inclinado: 3x12
3. Paralelas: 3 séries até próximo da falha
Descanso: 90 segundos"""

EXAMPLE_3 = """PERNAS
Agachamento | 4 | 6-8 | descanso 2 min | RPE 8
Leg press | 4 | 10-12 | 90s
Extensora | 3 | 12-15 | drop-set na última"""


def flat(draft):
    return [x for s in draft["sessions"] for x in s["exercises"]]


# --- the three examples from the spec ---------------------------------------------

def test_example_1_two_days_ten_exercises_all_matched():
    draft = parse_workout_text(EXAMPLE_1)
    assert draft["stats"] == {"days": 2, "exercises": 10, "needs_review": 0}
    assert [s["label"] for s in draft["sessions"]] == ["SEGUNDA — PUSH", "TERÇA — PULL"]
    first = draft["sessions"][0]["exercises"][0]
    assert first["exercise_id"] == "bb-bench-press"
    assert first["sets"] == 4 and first["reps"] == "8–10"
    assert first["rest"] == "90 s" and first["rir"] == "2"
    # every exercise resolved to a real catalog id
    assert all(x["exercise_id"] in EXERCISE_INDEX for x in flat(draft))


def test_example_1_second_day_exercises_resolve():
    draft = parse_workout_text(EXAMPLE_1)
    pull = {x["raw_name"]: x["exercise_id"] for x in draft["sessions"][1]["exercises"]}
    assert pull["Puxada aberta"] == "cable-pulldown"
    assert pull["Remada curvada"] == "bb-row"
    assert pull["Remada baixa"] == "cable-row"
    assert pull["Rosca martelo"] == "db-hammer-curl"


def test_example_2_numbered_lines_and_day_level_rest():
    draft = parse_workout_text(EXAMPLE_2)
    assert draft["stats"]["days"] == 1
    items = flat(draft)
    assert len(items) == 3
    # "Descanso: 90 segundos" is a day default, not a fourth exercise
    assert all(x["rest"] == "90 s" for x in items)
    assert items[0]["sets"] == 4 and items[0]["reps"] == "8–10"
    assert items[1]["exercise_id"] == "cable-incline-fly" and items[1]["reps"] == "12"


def test_example_2_missing_reps_is_flagged_never_invented():
    draft = parse_workout_text(EXAMPLE_2)
    paralelas = flat(draft)[2]
    assert paralelas["exercise_id"] == "dip"
    assert paralelas["sets"] == 3          # "3 séries" was read
    assert paralelas["reps"] == ""         # "até próximo da falha" is not a rep range
    assert paralelas["needs_review"] is True
    assert REVIEW_REPS_MISSING in paralelas["review_reasons"]
    assert "falha" in paralelas["note"].lower()


def test_example_3_pipe_layout_rpe_and_technique():
    draft = parse_workout_text(EXAMPLE_3)
    items = flat(draft)
    assert draft["sessions"][0]["label"] == "PERNAS"
    assert [x["exercise_id"] for x in items] == ["bb-squat", "leg-press", "leg-extension"]
    assert items[0]["sets"] == 4 and items[0]["reps"] == "6–8" and items[0]["rest"] == "2 min"
    # RPE 8 -> RIR 2, and the conversion is stated in the note instead of hidden
    assert items[0]["rir"] == "2"
    assert "RPE 8" in items[0]["note"]
    assert items[2]["technique_id"] == "drop-set"
    assert "drop-set" in items[2]["note"].lower()


# --- rejections ---------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["", "   ", "\n\n\n"])
def test_empty_text_is_rejected(bad):
    with pytest.raises(ValueError):
        parse_workout_text(bad)


def test_text_without_workout_structure_is_rejected():
    with pytest.raises(ValueError):
        parse_workout_text("oi, tudo bem? queria saber o preço da consultoria")


def test_oversized_text_is_rejected():
    with pytest.raises(ValueError):
        parse_workout_text("Supino reto 4x10\n" * (MAX_IMPORT_CHARS // 10))


# --- prescription formats -----------------------------------------------------------

@pytest.mark.parametrize("line,sets,reps", [
    ("Supino reto — 4x10", 4, "10"),
    ("Supino reto — 4 x 8-12", 4, "8–12"),
    ("Supino reto: 3 séries de 10", 3, "10"),
    ("Supino reto: 3 séries de 8 a 10 repetições", 3, "8–10"),
    ("Supino reto — 3x12-15", 3, "12–15"),
    ("Supino reto | 4 | 6-8", 4, "6–8"),
])
def test_sets_and_reps_variants(line, sets, reps):
    item = flat(parse_workout_text("PEITO\n" + line))[0]
    assert item["sets"] == sets
    assert item["reps"] == reps


def test_sets_without_reps_flags_review_and_keeps_sets():
    item = flat(parse_workout_text("PEITO\nSupino reto: 4 séries"))[0]
    assert item["sets"] == 4
    assert item["reps"] == ""
    assert REVIEW_REPS_MISSING in item["review_reasons"]


@pytest.mark.parametrize("raw,expected", [
    ("descanso 60s", "60 s"),
    ("90 segundos", "90 s"),
    ("descanso 2 min", "2 min"),
    ("3 minutos", "3 min"),
    ("sem info", ""),
])
def test_rest_in_seconds_and_minutes(raw, expected):
    assert parse_rest(raw) == expected


@pytest.mark.parametrize("raw,rir", [
    ("RIR 2", "2"),
    ("rir 1-2", "1–2"),
    ("RPE 8", "2"),
    ("RPE 10", "0"),
    ("até a falha", "0"),
])
def test_rir_and_rpe(raw, rir):
    assert parse_intensity(raw)[0] == rir


def test_rpe_conversion_is_explained_not_silent():
    rir, explanation = parse_intensity("RPE 7")
    assert rir == "3"
    assert "RPE 7" in explanation and "RIR 3" in explanation


@pytest.mark.parametrize("raw,tech_id", [
    ("drop-set na última", "drop-set"),
    ("dropset final", "drop-set"),
    ("bi-set com crucifixo", "superset"),
    ("rest-pause", "rest-pause"),
    ("myo-reps", "myo-reps"),
    ("cadência 3-0-1", ""),
])
def test_advanced_techniques(raw, tech_id):
    assert parse_technique(raw)[0] == tech_id


def test_unrecognized_text_is_preserved_in_the_note():
    item = flat(parse_workout_text("PEITO\nSupino reto — 4x10 — cadência 3-0-1 controlada"))[0]
    assert "cadência" in item["note"] or "cadencia" in item["note"]


def test_normalize_reps_uses_the_app_dash():
    assert normalize_reps("8-10") == "8–10"
    assert normalize_reps("8 a 10") == "8–10"
    assert normalize_reps("12") == "12"


# --- matching -----------------------------------------------------------------------

def test_exact_catalog_name_matches_exactly():
    eid, confidence, _ = match_exercise("Supino inclinado com halteres")
    assert eid == "db-incline-press" and confidence == "exact"


def test_unknown_exercise_is_never_invented():
    eid, confidence, suggestions = match_exercise("Zercher squat com corrente")
    assert eid is None
    assert confidence == "none"
    assert suggestions  # alternatives are offered for the athlete to choose from


def test_unmatched_exercise_blocks_activation():
    draft = parse_workout_text("PEITO\nZercher squat com corrente — 4x10")
    item = flat(draft)[0]
    assert item["exercise_id"] is None
    assert REVIEW_EXERCISE_UNMATCHED in item["review_reasons"]
    assert validate_draft(draft)  # non-empty: activation is blocked


# --- draft validation and conversion ------------------------------------------------

def test_valid_draft_has_no_blocking_errors():
    assert validate_draft(parse_workout_text(EXAMPLE_1)) == []


def test_draft_missing_sets_blocks_activation():
    draft = parse_workout_text(EXAMPLE_2)
    errors = validate_draft(draft)
    assert errors and any("repeti" in e for e in errors)


def test_draft_converts_to_the_existing_custom_program_shape():
    cp = draft_to_custom_program(parse_workout_text(EXAMPLE_1), "athlete-1")
    assert cp["profile_id"] == "athlete-1"
    assert cp["source"] == "manual_import"
    assert [s["day"] for s in cp["sessions"]] == [1, 2]
    item = cp["sessions"][0]["exercises"][0]
    # exactly the keys engine.build_program_v2's custom path reads — no review metadata
    assert set(item) == {"exercise_id", "sets", "reps", "rir", "rest", "load",
                         "technique", "technique_id", "note"}
    assert isinstance(item["sets"], int) and isinstance(item["load"], float)


def test_conversion_defaults_do_not_leak_review_fields():
    cp = draft_to_custom_program(parse_workout_text(EXAMPLE_3), "athlete-1")
    for session in cp["sessions"]:
        for x in session["exercises"]:
            assert "needs_review" not in x and "raw_name" not in x


def test_sanitization_strips_control_characters_from_pasted_text():
    draft = parse_workout_text("PEITO\nSupino\x00 reto\x07 — 4x10")
    assert "\x00" not in draft["sessions"][0]["exercises"][0]["raw_name"]
    assert "\x07" not in draft["sessions"][0]["exercises"][0]["raw_name"]


# --- casos reais reportados em produção (camada 1: matching determinístico) ---------

def test_alternatives_with_ou_offer_both_instead_of_failing():
    """"Barra fixa ou puxada alta": duas opções reais, nenhuma escolhida pelo parser."""
    r = resolve_exercise_name("Barra fixa ou puxada alta")
    assert r["exercise_id"] is None
    assert r["confidence"] == "options"
    assert r["options"] == ["pullup", "cable-pulldown"]


def test_alternatives_with_slash_are_split_too():
    r = resolve_exercise_name("Desenvolvimento / elevação lateral")
    assert r["confidence"] == "options"
    assert set(r["options"]) == {"db-ohp", "db-lateral-raise"}


def test_alternatives_where_only_one_resolves_uses_that_one():
    r = resolve_exercise_name("Tríceps na polia ou extensão cruzada")
    assert r["exercise_id"] == "cable-pushdown"


def test_alternatives_pointing_at_the_same_exercise_do_not_become_options():
    r = resolve_exercise_name("Paralelas / Dips")
    assert r["exercise_id"] == "dip"
    assert r["confidence"] != "options"


def test_word_order_variation_matches_the_existing_catalog_entry():
    """"Remada com peito apoiado" == "Remada apoiada no peito" (ordem trocada)."""
    r = resolve_exercise_name("Remada com peito apoiado")
    assert r["exercise_id"] == "row"


def test_gender_and_plural_folding():
    assert resolve_exercise_name("Rosca inclinada com halter")["exercise_id"] == "incline-db-curl"


def test_bayesian_curl_exists_in_the_catalog_now():
    assert "bayesian-curl" in EXERCISE_INDEX
    for name in ["Rosca Bayesian", "rosca bayesiana", "bayesian curl"]:
        assert resolve_exercise_name(name)["exercise_id"] == "bayesian-curl", name


def test_romanian_deadlift_maps_to_the_existing_rdl_entry():
    """O RDL ja existia como "Stiff / RDL com barra" — alias, nao entrada duplicada."""
    for name in ["Levantamento romeno", "RDL", "levantamento terra romeno", "stiff"]:
        assert resolve_exercise_name(name)["exercise_id"] == "rdl", name


def test_conventional_deadlift_still_maps_to_its_own_entry():
    assert resolve_exercise_name("Levantamento terra")["exercise_id"] == "conventional-deadlift"


def test_ambiguous_name_is_never_forced_into_a_match():
    """"Remada alta com peito apoiado" mistura dois exercicios diferentes do catalogo."""
    r = resolve_exercise_name("Remada alta com peito apoiado")
    assert r["exercise_id"] is None
    assert r["confidence"] == "ambiguous"
    assert r["suggestions"]


def test_reported_cases_end_to_end_through_the_parser():
    text = """DIA 1
Barra fixa ou puxada alta — 4x8
Remada com peito apoiado — 3x10
Rosca Bayesian — 3x12
Levantamento romeno — 4x8
Remada alta com peito apoiado — 3x12"""
    items = flat(parse_workout_text(text))
    assert [x["exercise_id"] for x in items] == [None, "row", "bayesian-curl", "rdl", None]
    assert items[0]["review_reasons"] == [REVIEW_MULTIPLE_OPTIONS]
    assert items[4]["review_reasons"] == [REVIEW_AMBIGUOUS]
    # os dois resolvidos por alias nao pedem revisao
    assert not items[1]["needs_review"] and not items[2]["needs_review"] and not items[3]["needs_review"]

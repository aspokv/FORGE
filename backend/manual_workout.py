"""FORGE manual workout — free-text importer and normalizer.

Turns a workout pasted as plain Portuguese text into the SAME structure the app already
uses for manual programs: profile.custom_program, consumed by engine.build_program_v2's
custom path (day / label / demand / focus / exercises[exercise_id, sets, reps, rir, rest,
load, technique, technique_id, note]). There is deliberately no second program model:
whatever this module produces has to survive build_program_v2, /workout/complete and
/exercises/substitute untouched.

Parsing is fully deterministic — no LLM. The imported text is DATA, never instructions:
nothing here interpolates it into a prompt or executes it. Anything the parser cannot
read with confidence is preserved verbatim in `note` and flagged for human review instead
of being guessed, so activation can require a real athlete decision.
"""
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from engine import EXERCISE_INDEX, EXERCISES as ENGINE_EXERCISES

MAX_IMPORT_CHARS = 20000
MAX_DAYS = 14
MAX_EXERCISES_PER_DAY = 40
MAX_LABEL_CHARS = 80
MAX_NOTE_CHARS = 300
MAX_SETS = 12

REVIEW_EXERCISE_UNMATCHED = "exercise_unmatched"
REVIEW_LOW_CONFIDENCE = "low_confidence_match"
REVIEW_SETS_MISSING = "sets_missing"
REVIEW_REPS_MISSING = "reps_missing"
REVIEW_MULTIPLE_OPTIONS = "multiple_options"
REVIEW_AMBIGUOUS = "ambiguous_match"

# Words that carry no identity in an exercise name — "Remada apoiada NO peito" and
# "Remada COM peito apoiado" are the same movement written in a different order.
STOPWORDS = {
    "com", "sem", "no", "na", "nos", "nas", "de", "do", "da", "dos", "das", "em",
    "a", "o", "os", "as", "e", "para", "pra", "por", "ao", "aos", "num", "numa",
}

# "X ou Y" / "X / Y" in a pasted line means the athlete may do either one.
_ALTERNATIVES = re.compile(r"\s+ou\s+|\s+/\s+", re.I)

# Technique ids that really exist in server.TECHNIQUES — never map to anything else.
TECHNIQUE_PATTERNS: List[Tuple[str, str, str]] = [
    (r"\bmechanical\s*drop", "mechanical-drop-set", "Mechanical Drop Set"),
    (r"\bdrop[\s-]*set|\bdropset", "drop-set", "Drop Set"),
    (r"\brest[\s-]*pause", "rest-pause", "Rest-Pause"),
    (r"\bmyo[\s-]*reps?", "myo-reps", "Myo-Reps"),
    (r"\bcluster", "cluster", "Cluster Set"),
    (r"\bpiramide|\bpyramid", "pyramid", "Pyramid"),
    (r"\bparciais|\blengthened", "lengthened-partials", "Lengthened Partials"),
    (r"\btop\s*set", "top-set-backoff", "Top Set + Back-off"),
    (r"\bbi[\s-]*set|\bsuper[\s-]*set|\bsuperset", "superset", "Superset"),
]

# Free-text names athletes actually write, mapped to the catalog. Only unambiguous
# equivalences live here; anything debatable is left to the scorer, which flags it.
EXERCISE_ALIASES: Dict[str, str] = {
    "supino reto": "bb-bench-press",
    "supino": "bb-bench-press",
    "supino reto barra": "bb-bench-press",
    "supino reto com halteres": "db-bench-press",
    "supino inclinado": "db-incline-press",
    "supino declinado": "db-decline-press",
    "supino fechado": "close-grip-bench",
    "crucifixo": "db-fly",
    "crucifixo inclinado": "cable-incline-fly",
    "crucifixo inverso": "db-rear-fly",
    "voador": "pec-deck",
    "peck deck": "pec-deck",
    "paralelas": "dip",
    "mergulho": "dip",
    "barra fixa": "pullup",
    "puxada": "cable-pulldown",
    "puxada aberta": "cable-pulldown",
    "puxada alta": "cable-pulldown",
    "puxada frontal": "cable-pulldown",
    "pulldown": "cable-pulldown",
    "remada curvada": "bb-row",
    "remada baixa": "cable-row",
    "remada unilateral": "db-row",
    "remada serrote": "db-row",
    "remada alta": "cable-upright-row",
    "desenvolvimento": "db-ohp",
    "desenvolvimento militar": "db-ohp",
    "elevacao lateral": "db-lateral-raise",
    "elevacao frontal": "cable-front-raise",
    "face pull": "cable-face-pull",
    "encolhimento": "db-shrug",
    "rosca direta": "bb-curl",
    "rosca alternada": "db-curl",
    "rosca martelo": "db-hammer-curl",
    "martelo": "db-hammer-curl",
    "rosca scott": "preacher-curl",
    "rosca concentrada": "db-cable-curl",
    "triceps corda": "cable-pushdown",
    "triceps pulley": "cable-pushdown",
    "triceps testa": "ez-skullcrusher",
    "triceps frances": "cable-overhead-extension",
    "triceps banco": "dip-machine",
    "agachamento": "bb-squat",
    "agachamento livre": "bb-squat",
    "agachamento frontal": "front-squat",
    "agachamento bulgaro": "bulgarian-split-squat",
    "leg press": "leg-press",
    "extensora": "leg-extension",
    "cadeira extensora": "leg-extension",
    "flexora": "lying-leg-curl",
    "mesa flexora": "lying-leg-curl",
    "cadeira flexora": "seated-hamstring-curl",
    "stiff": "rdl",
    # O RDL/levantamento romeno JA existe no catalogo como "Stiff / RDL com barra":
    # estes sao apelidos dele, nao um exercicio novo.
    "rdl": "rdl",
    "levantamento romeno": "rdl",
    "levantamento terra romeno": "rdl",
    "terra romeno": "rdl",
    "stiff romeno": "rdl",
    "romeno": "rdl",
    "levantamento terra": "conventional-deadlift",
    "terra": "conventional-deadlift",
    "rosca bayesian": "bayesian-curl",
    "rosca bayesiana": "bayesian-curl",
    "bayesian curl": "bayesian-curl",
    "bayesian": "bayesian-curl",
    "remada com peito apoiado": "row",
    "remada peito apoiado": "row",
    "afundo": "lunge",
    "avanco": "lunge",
    "passada": "lunge",
    "elevacao pelvica": "hip-thrust",
    "abdutora": "abductor-machine",
    "adutora": "adductor-machine",
    "panturrilha": "standing-calf",
    "panturrilha em pe": "standing-calf",
    "panturrilha sentado": "seated-calf",
    "abdominal": "machine-crunch",
    "prancha": "side-plank",
}

WEEKDAYS = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
GROUP_WORDS = [
    "push", "pull", "legs", "upper", "lower", "full body", "fullbody", "peito", "peitoral",
    "costas", "pernas", "perna", "ombro", "ombros", "biceps", "triceps", "gluteo", "gluteos",
    "posterior", "posteriores", "quadriceps", "panturrilha", "abdomen", "core", "braco",
    "bracos", "superiores", "inferiores", "dorsal", "deltoide", "membros",
]


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize(text: str) -> str:
    """Accent-free, lowercase, punctuation-free, single-spaced — matching key only."""
    base = strip_accents(text or "").lower()
    base = re.sub(r"[^a-z0-9\s]", " ", base)
    return re.sub(r"\s+", " ", base).strip()


def sanitize(text: str, limit: int) -> str:
    """Server-side sanitation for anything that came from the pasted text: control chars
    out, whitespace collapsed, hard length cap. React escapes on render; this keeps the
    stored document itself clean and bounded."""
    clean = "".join(ch for ch in (text or "") if unicodedata.category(ch)[0] != "C")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:limit]


_CATALOG_BY_NAME = {normalize(e["name"]): e["id"] for e in ENGINE_EXERCISES}


def _stem(token: str) -> str:
    """Minimal Portuguese folding: plural and gender agreement only, so that
    "apoiada"/"apoiado" and "halteres"/"halter" stop being different words."""
    # halteres -> halter (plural -es de palavras terminadas em r/s/z/l)
    if len(token) > 5 and token.endswith("es") and token[-3] in "rszl":
        token = token[:-2]
    elif len(token) > 4 and token.endswith("s"):
        token = token[:-1]
    if len(token) > 4 and token.endswith("a"):
        token = token[:-1] + "o"
    return token


def token_set(text: str) -> frozenset:
    """Identity of an exercise name as a bag of meaningful words — word order and
    connectives are irrelevant."""
    return frozenset(_stem(t) for t in normalize(text).split() if t not in STOPWORDS)


_CATALOG_BY_TOKENS: Dict[frozenset, str] = {}
_CATALOG_TOKENS: List[Tuple[frozenset, str]] = []
for _e in ENGINE_EXERCISES:
    _ts = token_set(_e["name"])
    _CATALOG_BY_TOKENS.setdefault(_ts, _e["id"])
    _CATALOG_TOKENS.append((_ts, _e["id"]))

_TOKENS_BY_ID: Dict[str, frozenset] = {eid: ts for ts, eid in _CATALOG_TOKENS}

_ALIAS_BY_TOKENS: Dict[frozenset, str] = {}
for _alias, _eid in EXERCISE_ALIASES.items():
    _ALIAS_BY_TOKENS.setdefault(token_set(_alias), _eid)

# Which catalog entries each word appears in — used to tell a harmless extra word
# ("olímpica") from one that distinguishes a different exercise ("alta").
_TOKEN_TO_IDS: Dict[str, set] = {}
for _ts, _eid in _CATALOG_TOKENS:
    for _t in _ts:
        _TOKEN_TO_IDS.setdefault(_t, set()).add(_eid)


def _token_score(candidate: frozenset, target: frozenset) -> float:
    if not candidate or not target:
        return 0.0
    return len(candidate & target) / len(candidate | target)


def match_exercise(raw_name: str) -> Tuple[Optional[str], str, List[str]]:
    """Resolves a free-text exercise name to a catalog id.

    Returns (exercise_id | None, confidence, suggestions). Confidence is one of
    exact / alias / fuzzy / none. Only exact and alias are trusted enough to skip review:
    a fuzzy hit is still surfaced to the athlete with alternatives, and an unmatched name
    never becomes an invented exercise — it stays None and blocks activation until chosen.
    """
    key = normalize(raw_name)
    if not key:
        return None, "none", []

    if key in _CATALOG_BY_NAME:
        return _CATALOG_BY_NAME[key], "exact", []
    if key in EXERCISE_ALIASES:
        return EXERCISE_ALIASES[key], "alias", []

    # Same words, any order, ignoring connectives: "Remada com peito apoiado" ==
    # "Remada apoiada no peito". Confident enough to skip review.
    tokens = token_set(raw_name)
    if tokens in _CATALOG_BY_TOKENS:
        return _CATALOG_BY_TOKENS[tokens], "exact", []
    if tokens in _ALIAS_BY_TOKENS:
        return _ALIAS_BY_TOKENS[tokens], "alias", []

    scored = sorted(
        ((_token_score(tokens, ts), eid) for ts, eid in _CATALOG_TOKENS),
        key=lambda t: t[0], reverse=True,
    )
    # Alias keys are short phrases; score them too so "puxada aberta na polia" still lands.
    alias_scored = sorted(
        ((_token_score(tokens, ts), eid) for ts, eid in _ALIAS_BY_TOKENS.items()),
        key=lambda t: t[0], reverse=True,
    )
    best_score, best_id = scored[0] if scored else (0.0, None)
    if alias_scored and alias_scored[0][0] > best_score:
        best_score, best_id = alias_scored[0]

    suggestions: List[str] = []
    for _, eid in scored[:5]:
        if eid not in suggestions:
            suggestions.append(eid)

    if best_score >= 0.5 and best_id:
        # A leftover word that identifies a DIFFERENT catalog exercise means the name
        # carries a distinction this match would silently discard — "Remada alta com
        # peito apoiado" is not "Remada apoiada no peito", because "alta" belongs to
        # "Remada alta no cabo". Those stay unresolved on purpose.
        leftover = tokens - _TOKENS_BY_ID.get(best_id, frozenset())
        if any(_TOKEN_TO_IDS.get(t, set()) - {best_id} for t in leftover):
            return None, "ambiguous", suggestions
        return best_id, "fuzzy", suggestions
    return None, "none", suggestions


def split_alternatives(raw_name: str) -> List[str]:
    """"Barra fixa ou puxada alta" -> two candidate names."""
    parts = [p.strip() for p in _ALTERNATIVES.split(raw_name or "") if p.strip()]
    return parts if len(parts) > 1 else [(raw_name or "").strip()]


def resolve_exercise_name(raw_name: str) -> Dict[str, Any]:
    """Resolves a pasted name that may offer alternatives.

    When the text says "X ou Y" and both are real exercises, neither is chosen for the
    athlete: both come back as `options` for them to pick. A single resolvable name
    behaves exactly like before.
    """
    candidates = split_alternatives(raw_name)
    if len(candidates) == 1:
        eid, confidence, suggestions = match_exercise(raw_name)
        return {"exercise_id": eid, "confidence": confidence,
                "suggestions": suggestions, "options": [eid] if eid else []}

    resolved: List[Tuple[str, str]] = []
    suggestions: List[str] = []
    for candidate in candidates:
        eid, confidence, sugg = match_exercise(candidate)
        if eid and eid not in [r[0] for r in resolved]:
            resolved.append((eid, confidence))
        for s in sugg:
            if s not in suggestions:
                suggestions.append(s)

    options = [eid for eid, _ in resolved]
    if len(options) >= 2:
        extra = [s for s in suggestions if s not in options][:3]
        return {"exercise_id": None, "confidence": "options",
                "suggestions": options + extra, "options": options}
    if len(options) == 1:
        return {"exercise_id": options[0], "confidence": resolved[0][1],
                "suggestions": [], "options": options}
    return {"exercise_id": None, "confidence": "none", "suggestions": suggestions[:5], "options": []}


# --- attribute extraction ----------------------------------------------------------

_SETS_REPS_X = re.compile(r"(\d{1,2})\s*[x×]\s*(\d{1,3}\s*(?:[-–]|a|at[eé])\s*\d{1,3}|\d{1,3})", re.I)
_SETS_REPS_WORDS = re.compile(
    r"(\d{1,2})\s*s[eé]ries?\s*(?:de|com)?\s*(\d{1,3}\s*(?:[-–]|a|at[eé])\s*\d{1,3}|\d{1,3})?\s*(?:repeti[cç][oõ]es|reps?)?",
    re.I,
)
_REST_SECONDS = re.compile(r"(\d{2,3})\s*(?:s\b|seg\b|segundos?\b)", re.I)
_REST_MINUTES = re.compile(r"(\d{1,2})\s*(?:min\b|minutos?\b)", re.I)
_RIR = re.compile(r"\brir\s*:?\s*(\d{1,2}(?:\s*[-–]\s*\d{1,2})?)", re.I)
_RPE = re.compile(r"\brpe\s*:?\s*(\d{1,2}(?:[.,]\d)?)", re.I)
_FAILURE = re.compile(r"at[eé]\s+(?:a\s+|o\s+)?(?:pr[oó]xim[oa]\s+d[ao]\s+)?falha", re.I)


def normalize_reps(raw: str) -> str:
    """8-10 / 8 a 10 / 8 ate 10 -> the 8–12 form already used across the app."""
    if not raw:
        return ""
    txt = re.sub(r"\s*(?:[-–]|a|at[eé])\s*", "–", raw.strip(), flags=re.I)
    return re.sub(r"\s+", "", txt)


def parse_rest(text: str) -> str:
    m = _REST_MINUTES.search(text)
    if m:
        return f"{int(m.group(1))} min"
    m = _REST_SECONDS.search(text)
    if m:
        return f"{int(m.group(1))} s"
    return ""


def parse_intensity(text: str) -> Tuple[str, str]:
    """Returns (rir, explanation). RPE is converted with the standard RIR = 10 - RPE and
    the conversion is written into the note, so the athlete sees exactly what happened
    instead of a silently rewritten number."""
    m = _RIR.search(text)
    if m:
        return re.sub(r"\s*[-–]\s*", "–", m.group(1).strip()), ""
    m = _RPE.search(text)
    if m:
        try:
            rpe = float(m.group(1).replace(",", "."))
        except ValueError:
            return "", ""
        if 0 <= rpe <= 10:
            rir = int(round(10 - rpe))
            return str(rir), f"RPE {m.group(1)} convertido para RIR {rir}"
    if _FAILURE.search(text):
        return "0", "Prescrito ate a falha"
    return "", ""


def parse_technique(text: str) -> Tuple[str, str]:
    for pattern, tech_id, tech_name in TECHNIQUE_PATTERNS:
        if re.search(pattern, strip_accents(text), re.I):
            return tech_id, tech_name
    return "", ""


def _split_segments(line: str) -> List[str]:
    parts = re.split(r"\s*[|]\s*|\s+[—–]\s+|\s*:\s*|\s+-\s+", line)
    return [p.strip() for p in parts if p and p.strip()]


def _looks_like_exercise(line: str) -> bool:
    return bool(
        _SETS_REPS_X.search(line)
        or _SETS_REPS_WORDS.search(line)
        or re.match(r"^\s*\d{1,2}[\.\)]\s+\S", line)
    )


def is_day_header(line: str) -> bool:
    """A header names a day/session; it never carries a set prescription."""
    if _looks_like_exercise(line):
        return False
    key = normalize(line)
    if not key or len(key) > 60:
        return False
    if any(key.startswith(d) or f" {d}" in key for d in WEEKDAYS):
        return True
    if re.match(r"^treino\s+[a-z0-9]", key):
        return True
    if re.match(r"^(dia|day)\s*\d+", key):
        return True
    tokens = key.split()
    if any(w in tokens for w in GROUP_WORDS):
        return True
    letters = [c for c in line if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and len(tokens) <= 6


def _parse_exercise_line(line: str, default_rest: str) -> Optional[Dict[str, Any]]:
    cleaned = re.sub(r"^\s*\d{1,2}\s*[\.\)\-]\s*", "", line).strip()
    cleaned = re.sub(r"^[•\-\*]\s*", "", cleaned).strip()
    if not cleaned:
        return None

    segments = _split_segments(cleaned)
    if not segments:
        return None

    raw_name = segments[0]
    attr_text = " ".join(segments[1:])

    # Pipe layout "Agachamento | 4 | 6-8 | ...": bare number then a rep range.
    sets: Optional[int] = None
    reps = ""
    rep_only = r"\d{1,3}\s*(?:[-–]|a|at[eé])\s*\d{1,3}|\d{1,3}"
    if (len(segments) >= 3 and re.fullmatch(r"\d{1,2}", segments[1])
            and re.fullmatch(rep_only, segments[2], re.I)):
        sets = int(segments[1])
        reps = normalize_reps(segments[2])
        attr_text = " ".join(segments[3:])
    else:
        m = _SETS_REPS_X.search(attr_text) or _SETS_REPS_X.search(cleaned)
        if m:
            sets = int(m.group(1))
            reps = normalize_reps(m.group(2))
            # A name that swallowed the prescription ("Supino reto 4x8") keeps only the name.
            raw_name = _SETS_REPS_X.sub("", raw_name).strip()
        else:
            m = _SETS_REPS_WORDS.search(attr_text) or _SETS_REPS_WORDS.search(cleaned)
            if m:
                sets = int(m.group(1))
                reps = normalize_reps(m.group(2) or "")
                raw_name = _SETS_REPS_WORDS.sub("", raw_name).strip()

    if not normalize(raw_name):
        return None
    if sets is not None and not (1 <= sets <= MAX_SETS):
        sets = None

    rest = parse_rest(attr_text) or parse_rest(cleaned) or default_rest
    rir, intensity_note = parse_intensity(attr_text if attr_text else cleaned)
    technique_id, technique_name = parse_technique(attr_text or cleaned)

    # Everything the parser did not consume is preserved verbatim — never dropped.
    leftovers = attr_text
    for pattern in (_SETS_REPS_X, _SETS_REPS_WORDS, _REST_MINUTES, _REST_SECONDS, _RIR, _RPE):
        leftovers = pattern.sub(" ", leftovers)
    leftovers = re.sub(r"\b(descanso|rest|repeti[cç][oõ]es|reps?|s[eé]ries?)\b", " ", leftovers, flags=re.I)
    leftovers = re.sub(r"[\s,;.]+", " ", leftovers).strip(" -–—|")

    note_parts = [p for p in (intensity_note, leftovers) if p]
    note = sanitize(" · ".join(note_parts), MAX_NOTE_CHARS)

    resolution = resolve_exercise_name(raw_name)
    exercise_id = resolution["exercise_id"]
    confidence = resolution["confidence"]
    suggestions = resolution["suggestions"]
    options = resolution["options"]

    # Minimum structure to count as an exercise at all: either a prescription was read,
    # or the name resolves to a real exercise. Prose ("queria saber o preço da
    # consultoria") satisfies neither and is dropped as noise instead of becoming a
    # phantom exercise.
    if sets is None and not reps and exercise_id is None and not options:
        return None

    reasons: List[str] = []
    if confidence == "options":
        reasons.append(REVIEW_MULTIPLE_OPTIONS)
    elif confidence == "ambiguous":
        reasons.append(REVIEW_AMBIGUOUS)
    elif exercise_id is None:
        reasons.append(REVIEW_EXERCISE_UNMATCHED)
    elif confidence == "fuzzy":
        reasons.append(REVIEW_LOW_CONFIDENCE)
    if sets is None:
        reasons.append(REVIEW_SETS_MISSING)
    if not reps:
        reasons.append(REVIEW_REPS_MISSING)

    return {
        "exercise_id": exercise_id,
        "raw_name": sanitize(raw_name, MAX_LABEL_CHARS),
        "match_confidence": confidence,
        "suggestions": suggestions[:5],
        "options": options,
        "sets": sets,
        "reps": reps,
        "rir": rir,
        "rest": rest,
        "load": 0,
        "technique_id": technique_id or "straight",
        "technique": technique_name or "Straight Sets",
        "note": note,
        "needs_review": bool(reasons),
        "review_reasons": reasons,
    }


def parse_workout_text(text: str, name: str = "") -> Dict[str, Any]:
    """Free text -> draft. Raises ValueError with a message meant for the athlete."""
    if not text or not text.strip():
        raise ValueError("Cole o treino antes de interpretar.")
    if len(text) > MAX_IMPORT_CHARS:
        raise ValueError(f"Texto muito grande: maximo de {MAX_IMPORT_CHARS} caracteres.")

    lines = [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln]

    days: List[Dict[str, Any]] = []
    warnings: List[str] = []
    current: Optional[Dict[str, Any]] = None
    default_rest = ""

    for line in lines:
        # "Descanso: 90 segundos" on its own line is a default for the day, not an exercise.
        stripped_key = normalize(re.split(r"[:|]", line)[0])
        if stripped_key in ("descanso", "descanso geral", "rest", "intervalo") and parse_rest(line):
            default_rest = parse_rest(line)
            if current:
                for item in current["exercises"]:
                    if not item["rest"]:
                        item["rest"] = default_rest
            continue

        if is_day_header(line):
            if len(days) >= MAX_DAYS:
                warnings.append(f"Limite de {MAX_DAYS} dias atingido: o restante do texto foi ignorado.")
                break
            current = {
                "day": len(days) + 1,
                "label": sanitize(line, MAX_LABEL_CHARS),
                "demand": "MODERATE",
                "focus": [],
                "exercises": [],
            }
            days.append(current)
            continue

        item = _parse_exercise_line(line, default_rest)
        if item is None:
            warnings.append(f"Linha ignorada por nao parecer um exercicio: {sanitize(line, 60)}")
            continue

        if current is None:
            current = {"day": 1, "label": "Sessão 1", "demand": "MODERATE", "focus": [], "exercises": []}
            days.append(current)
        if len(current["exercises"]) >= MAX_EXERCISES_PER_DAY:
            warnings.append(f"{current['label']}: limite de {MAX_EXERCISES_PER_DAY} exercicios atingido.")
            continue
        current["exercises"].append(item)

    days = [d for d in days if d["exercises"]]
    for i, d in enumerate(days):
        d["day"] = i + 1

    if not days:
        raise ValueError(
            "Nao foi possivel identificar exercicios nesse texto. Use uma linha por exercicio, "
            "por exemplo: Supino reto — 4x8-10 — 90s."
        )

    total = sum(len(d["exercises"]) for d in days)
    review = sum(1 for d in days for x in d["exercises"] if x["needs_review"])

    return {
        "name": sanitize(name, MAX_LABEL_CHARS) or "Treino importado",
        "source": "manual_import",
        "sessions": days,
        "warnings": warnings,
        "stats": {"days": len(days), "exercises": total, "needs_review": review},
    }


def validate_draft(draft: Dict[str, Any]) -> List[str]:
    """Blocking errors for activation. A draft may be saved half-resolved; it may never
    be activated half-resolved."""
    errors: List[str] = []
    sessions = draft.get("sessions") or []
    if not sessions:
        errors.append("O treino precisa de pelo menos um dia.")
    if len(sessions) > MAX_DAYS:
        errors.append(f"Maximo de {MAX_DAYS} dias por treino.")
    for s in sessions:
        label = s.get("label") or f"Dia {s.get('day')}"
        items = s.get("exercises") or []
        if not items:
            errors.append(f"{label}: sem exercicios.")
        for i, x in enumerate(items, 1):
            ref = f"{label} · exercicio {i}"
            if not x.get("exercise_id") or x["exercise_id"] not in EXERCISE_INDEX:
                errors.append(f"{ref}: escolha um exercicio do catalogo.")
            sets = x.get("sets")
            if not isinstance(sets, int) or isinstance(sets, bool) or not (1 <= sets <= MAX_SETS):
                errors.append(f"{ref}: informe o numero de series (1 a {MAX_SETS}).")
            if not (x.get("reps") or "").strip():
                errors.append(f"{ref}: informe a faixa de repeticoes.")
    return errors


def draft_to_custom_program(draft: Dict[str, Any], profile_id: str, session_minutes: int = 60) -> Dict[str, Any]:
    """Draft -> the exact custom_program document build_program_v2 already consumes.
    Review-only fields (raw_name, suggestions, needs_review...) are dropped here: they
    belong to the editing step, not to the active plan."""
    sessions = []
    for i, s in enumerate(draft.get("sessions") or []):
        sessions.append({
            "day": i + 1,
            "label": sanitize(s.get("label") or f"Sessão {i+1}", MAX_LABEL_CHARS),
            "demand": s.get("demand") if s.get("demand") in ("HIGH", "MODERATE", "LOW") else "MODERATE",
            "focus": [sanitize(f, MAX_LABEL_CHARS) for f in (s.get("focus") or [])][:3],
            "exercises": [{
                "exercise_id": x["exercise_id"],
                "sets": int(x["sets"]),
                "reps": sanitize(x.get("reps") or "", 20),
                "rir": sanitize(x.get("rir") or "1–2", 20),
                "rest": sanitize(x.get("rest") or "2 min", 20),
                "load": float(x.get("load") or 0),
                "technique": sanitize(x.get("technique") or "Straight Sets", 60),
                "technique_id": sanitize(x.get("technique_id") or "straight", 40),
                "note": sanitize(x.get("note") or "", MAX_NOTE_CHARS),
            } for x in (s.get("exercises") or [])],
        })
    return {
        "profile_id": profile_id,
        "name": sanitize(draft.get("name") or "Treino manual", MAX_LABEL_CHARS),
        "week": "Microciclo manual",
        "session_minutes": int(session_minutes or 60),
        "source": draft.get("source") if draft.get("source") in ("manual", "manual_import") else "manual",
        "sessions": sessions,
    }

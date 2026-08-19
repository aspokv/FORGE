"""FORGE — importador de dieta em texto livre.

Mesma arquitetura do importador de treino: parser determinístico, matching híbrido
contra um catálogo FECHADO (os 62 alimentos de foods.json) e nada inventado — o que não
dá para ler com confiança é marcado para revisão em vez de virar número.

O resultado sai no MESMO formato que generate_daily_plan já produz
(`meals[].foods[]` construídos por build_food_item), então o plano importado passa por
/api/nutrition/plan, /substitute e /meal-status sem mudança nenhuma nesses caminhos.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from nutrition_engine import FOOD_INDEX, _food_macros, build_food_item
from text_match import CatalogMatcher, normalize, sanitize, token_set

MAX_IMPORT_CHARS = 20000
MAX_MEALS = 10
MAX_ITEMS_PER_MEAL = 25
MAX_LABEL_CHARS = 60
MAX_NOTE_CHARS = 200
MAX_GRAMS = 3000

REVIEW_FOOD_UNMATCHED = "food_unmatched"
REVIEW_LOW_CONFIDENCE = "low_confidence_match"
REVIEW_AMBIGUOUS = "ambiguous_match"
REVIEW_QUANTITY_MISSING = "quantity_missing"
REVIEW_ESTIMATED_PORTION = "estimated_portion"
REVIEW_AI_SUGGESTED = "ai_suggested"

# Medidas caseiras: conversões DECLARADAS, não exatas. Todo item convertido por elas
# nasce marcado como estimativa, para o atleta confirmar o peso.
HOUSEHOLD_GRAMS: Dict[str, float] = {
    "colher de sopa": 15, "colheres de sopa": 15, "colher sopa": 15,
    "colher de cha": 5, "colheres de cha": 5,
    "xicara": 120, "xicaras": 120,
    "concha": 80, "conchas": 80,
    "fatia": 25, "fatias": 25,
    "scoop": 30, "scoops": 30, "dose": 30, "doses": 30,
    "punhado": 30, "punhados": 30,
    "file": 120, "files": 120, "posta": 120, "postas": 120,
    "copo": 200, "copos": 200,
    "pote": 170, "potes": 170,
}

# Peso por unidade, quando o texto diz "2 ovos" e não "100g de ovo".
FOOD_UNIT_GRAMS: Dict[str, float] = {
    "eggs-whole": 50, "egg-whites": 33,
    "banana": 100, "apple": 130, "orange": 130, "papaya": 150, "mango": 150,
    "bread-white": 50, "bread-whole": 25,
    "tapioca": 60, "brazil-nuts": 5,
}

# Unidades de massa/volume: conversão exata (ml tratado como g, que é o que a tabela
# nutricional assume para leite, iogurte e líquidos em geral).
_MASS_UNITS = {"g": 1.0, "grama": 1.0, "gramas": 1.0, "gr": 1.0,
               "kg": 1000.0, "quilo": 1000.0, "quilos": 1000.0,
               "ml": 1.0, "mililitro": 1.0, "mililitros": 1.0,
               "l": 1000.0, "litro": 1000.0, "litros": 1000.0}

MEAL_WORDS = [
    "cafe da manha", "cafe", "desjejum", "almoco", "jantar", "janta", "ceia",
    "lanche", "lanche da manha", "lanche da tarde", "lanche da noite",
    "pre treino", "pos treino", "pre-treino", "pos-treino", "refeicao", "merenda",
    "colacao", "sobremesa",
]

_QUANTITY = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?)\s*"
    r"(kg|g|gr|gramas?|ml|mililitros?|l|litros?|quilos?|"
    r"colher(?:es)? de sopa|colher(?:es)? de cha|colher(?:es)? sopa|xicaras?|conchas?|fatias?|"
    r"scoops?|doses?|punhados?|files?|postas?|copos?|potes?|unidades?|un)?\b",
    re.I,
)
_SPLIT_ITEMS = re.compile(r"\s+\+\s+|\s*,\s*|\s+e\s+", re.I)


def _clean_line(line: str) -> str:
    line = re.sub(r"^\s*\d{1,2}\s*[\.\)]\s+", "", line)
    return re.sub(r"^[\-•\*–]\s*", "", line).strip()


def is_meal_header(line: str) -> bool:
    """Cabeçalho nomeia a refeição e nunca traz quantidade de alimento."""
    key = normalize(line)
    if not key or len(key) > 50:
        return False
    if re.match(r"^refeicao\s*\d*", key) or re.match(r"^\d+\s*a?\s*refeicao", key):
        return True
    if _QUANTITY.match(line) and _QUANTITY.match(line).group(1):
        return False
    tokens = key.split()
    if any(key.startswith(w) for w in MEAL_WORDS):
        return True
    letras = [c for c in line if c.isalpha()]
    return bool(letras) and all(c.isupper() for c in letras) and len(tokens) <= 5


def parse_quantity(text: str) -> Tuple[Optional[float], str, str]:
    """Devolve (valor, unidade normalizada, resto do texto)."""
    m = _QUANTITY.match(text)
    if not m or not m.group(1):
        return None, "", text.strip()
    valor = float(m.group(1).replace(",", "."))
    unidade = normalize(m.group(2) or "")
    resto = text[m.end():].strip()
    resto = re.sub(r"^(de|da|do|of)\s+", "", resto, flags=re.I).strip()
    return valor, unidade, resto


def to_grams(quantity: Optional[float], unit: str, food_id: Optional[str]) -> Tuple[Optional[float], bool]:
    """(gramas, estimado). `estimado` marca conversão por medida caseira ou por
    unidade — número que o atleta precisa confirmar, nunca apresentado como exato."""
    if quantity is None:
        return None, False
    if unit in _MASS_UNITS:
        return round(quantity * _MASS_UNITS[unit], 1), False
    if unit in HOUSEHOLD_GRAMS:
        base = HOUSEHOLD_GRAMS[unit]
        if unit.startswith("colher") and food_id == "olive-oil":
            base = 8  # azeite: colher de sopa não pesa 15 g
        return round(quantity * base, 1), True
    if unit in ("unidade", "unidades", "un", ""):
        if food_id and food_id in FOOD_UNIT_GRAMS:
            return round(quantity * FOOD_UNIT_GRAMS[food_id], 1), True
        if food_id:
            catalogo = FOOD_INDEX.get(food_id) or {}
            if catalogo.get("unit_grams"):
                return round(quantity * float(catalogo["unit_grams"]), 1), True
        return None, False
    return None, False


def build_matcher(learned: Optional[Dict[str, str]] = None) -> CatalogMatcher:
    entries = {f["id"]: f["name"] for f in FOOD_INDEX.values()}
    aliases: Dict[str, str] = {}
    for f in FOOD_INDEX.values():
        for a in f.get("aliases") or []:
            aliases.setdefault(normalize(a), f["id"])
    matcher = CatalogMatcher(entries, aliases)
    return matcher.with_learned(learned or {})


def _parse_item(text: str, matcher: CatalogMatcher) -> Optional[Dict[str, Any]]:
    text = _clean_line(text)
    if not text:
        return None
    quantity, unit, resto = parse_quantity(text)
    nome = resto or text
    if not normalize(nome):
        return None

    food_id, confidence, suggestions = matcher.match(nome)
    if food_id is None and confidence == "none" and quantity is None:
        return None  # nem quantidade nem alimento: é ruído, não item

    grams, estimated = to_grams(quantity, unit, food_id)
    if grams is not None and not (0 < grams <= MAX_GRAMS):
        grams, estimated = None, False

    reasons: List[str] = []
    if confidence == "ambiguous":
        reasons.append(REVIEW_AMBIGUOUS)
    elif food_id is None:
        reasons.append(REVIEW_FOOD_UNMATCHED)
    elif confidence == "fuzzy":
        reasons.append(REVIEW_LOW_CONFIDENCE)
    if grams is None:
        reasons.append(REVIEW_QUANTITY_MISSING)
    elif estimated:
        reasons.append(REVIEW_ESTIMATED_PORTION)

    return {
        "food_id": food_id,
        "raw_name": sanitize(nome, MAX_LABEL_CHARS),
        "raw_text": sanitize(text, MAX_LABEL_CHARS),
        "match_confidence": confidence,
        "suggestions": suggestions[:5],
        "quantity": quantity,
        "unit": unit,
        "grams": grams,
        "estimated": estimated,
        "needs_review": bool(reasons),
        "review_reasons": reasons,
    }


def parse_diet_text(text: str, matcher: Optional[CatalogMatcher] = None,
                    name: str = "") -> Dict[str, Any]:
    """Texto livre -> rascunho de dieta. Levanta ValueError com mensagem para o atleta."""
    if not text or not text.strip():
        raise ValueError("Cole a dieta antes de interpretar.")
    if len(text) > MAX_IMPORT_CHARS:
        raise ValueError(f"Texto muito grande: maximo de {MAX_IMPORT_CHARS} caracteres.")

    matcher = matcher or build_matcher()
    linhas = [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    linhas = [ln for ln in linhas if ln]

    meals: List[Dict[str, Any]] = []
    warnings: List[str] = []
    atual: Optional[Dict[str, Any]] = None

    for linha in linhas:
        if is_meal_header(linha):
            if len(meals) >= MAX_MEALS:
                warnings.append(f"Limite de {MAX_MEALS} refeicoes atingido: o resto foi ignorado.")
                break
            atual = {"name": sanitize(linha, MAX_LABEL_CHARS), "items": []}
            meals.append(atual)
            continue

        candidatos = [linha]
        if matcher.match(_clean_line(linha))[0] is None:
            partes = [p for p in _SPLIT_ITEMS.split(_clean_line(linha)) if p.strip()]
            if len(partes) > 1 and sum(1 for p in partes if matcher.match(p)[0]) >= 2:
                candidatos = partes

        for candidato in candidatos:
            item = _parse_item(candidato, matcher)
            if item is None:
                if len(candidatos) == 1:
                    warnings.append(f"Linha ignorada por nao parecer alimento: {sanitize(linha, 50)}")
                continue
            if atual is None:
                atual = {"name": "Refeicao 1", "items": []}
                meals.append(atual)
            if len(atual["items"]) >= MAX_ITEMS_PER_MEAL:
                warnings.append(f"{atual['name']}: limite de {MAX_ITEMS_PER_MEAL} itens atingido.")
                continue
            atual["items"].append(item)

    meals = [m for m in meals if m["items"]]
    if not meals:
        raise ValueError(
            "Nao foi possivel identificar alimentos nesse texto. Use uma linha por item, "
            "por exemplo: 150g de arroz branco."
        )

    draft = {"name": sanitize(name, MAX_LABEL_CHARS) or "Dieta importada",
             "source": "manual_import", "meals": meals, "warnings": warnings}
    return recompute(draft)


def item_macros(item: Dict[str, Any]) -> Dict[str, float]:
    """Macros reais do item, direto da tabela do catálogo. Item sem alimento
    resolvido ou sem gramas vale zero — nunca um chute."""
    if not item.get("food_id") or item["food_id"] not in FOOD_INDEX or not item.get("grams"):
        return {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    kcal, protein, carbs, fat = _food_macros(item["food_id"], float(item["grams"]))
    return {"kcal": round(float(kcal), 1), "protein_g": round(float(protein), 1),
            "carbs_g": round(float(carbs), 1), "fat_g": round(float(fat), 1)}


def recompute(draft: Dict[str, Any]) -> Dict[str, Any]:
    """Recalcula macros por item, por refeição e do dia. É a única fonte dos números:
    nada de total vindo do cliente."""
    dia = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    pendentes = 0
    for meal in draft.get("meals") or []:
        totais = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
        for item in meal.get("items") or []:
            macros = item_macros(item)
            item["macros"] = macros
            for k in totais:
                totais[k] = round(totais[k] + macros[k], 1)
            if item.get("needs_review"):
                pendentes += 1
        meal["totals"] = totais
        for k in dia:
            dia[k] = round(dia[k] + totais[k], 1)
    draft["daily_totals"] = dia
    draft["stats"] = {
        "meals": len(draft.get("meals") or []),
        "items": sum(len(m.get("items") or []) for m in draft.get("meals") or []),
        "needs_review": pendentes,
    }
    return draft


def validate_draft(draft: Dict[str, Any]) -> List[str]:
    """Erros que impedem salvar como plano base."""
    erros: List[str] = []
    meals = draft.get("meals") or []
    if not meals:
        erros.append("A dieta precisa de pelo menos uma refeicao.")
    for meal in meals:
        nome = meal.get("name") or "Refeicao"
        itens = meal.get("items") or []
        if not itens:
            erros.append(f"{nome}: sem alimentos.")
        for i, item in enumerate(itens, 1):
            ref = f"{nome} - item {i}"
            if not item.get("food_id") or item["food_id"] not in FOOD_INDEX:
                erros.append(f"{ref}: escolha um alimento do catalogo.")
            grams = item.get("grams")
            if not isinstance(grams, (int, float)) or not (0 < float(grams) <= MAX_GRAMS):
                erros.append(f"{ref}: informe a quantidade em gramas.")
    return erros


def unmatched_names(draft: Dict[str, Any]) -> List[str]:
    nomes: List[str] = []
    for meal in draft.get("meals") or []:
        for item in meal.get("items") or []:
            if not item.get("food_id") and item.get("match_confidence") == "none":
                nome = (item.get("raw_name") or "").strip()
                if nome and nome not in nomes:
                    nomes.append(nome)
    return nomes


def apply_resolution(draft: Dict[str, Any], resolved: Dict[str, str],
                     confidence: str, review_reason: Optional[str]) -> Dict[str, Any]:
    for meal in draft.get("meals") or []:
        for item in meal.get("items") or []:
            if item.get("food_id") or item.get("match_confidence") != "none":
                continue
            fid = resolved.get((item.get("raw_name") or "").strip())
            if not fid or fid not in FOOD_INDEX:
                continue
            item["food_id"] = fid
            item["match_confidence"] = confidence
            razoes = [r for r in (item.get("review_reasons") or []) if r != REVIEW_FOOD_UNMATCHED]
            if review_reason:
                razoes.insert(0, review_reason)
            # Agora que há alimento, uma quantidade em unidades pode ser convertida.
            if item.get("grams") is None:
                grams, estimated = to_grams(item.get("quantity"), item.get("unit") or "", fid)
                if grams is not None:
                    item["grams"], item["estimated"] = grams, estimated
                    razoes = [r for r in razoes if r != REVIEW_QUANTITY_MISSING]
                    if estimated and REVIEW_ESTIMATED_PORTION not in razoes:
                        razoes.append(REVIEW_ESTIMATED_PORTION)
            item["review_reasons"] = razoes
            item["needs_review"] = bool(razoes)
    return recompute(draft)


def draft_to_plan(draft: Dict[str, Any]) -> Dict[str, Any]:
    """Rascunho -> o MESMO formato que generate_daily_plan produz, para o plano
    importado circular pelos endpoints que já existem sem adaptação."""
    meals = []
    for meal in draft.get("meals") or []:
        foods = []
        for item in meal.get("items") or []:
            if not item.get("food_id") or not item.get("grams"):
                continue
            foods.append(build_food_item(item["food_id"], float(item["grams"])))
        totais = meal.get("totals") or {}
        meals.append({
            "name": sanitize(meal.get("name") or "Refeicao", MAX_LABEL_CHARS),
            # Numa dieta trazida pronta o alvo da refeicao e o que ela de fato entrega.
            "target_cal": round(totais.get("kcal", 0)),
            "target_protein": round(totais.get("protein_g", 0)),
            "target_fat": round(totais.get("fat_g", 0), 1),
            "foods": foods,
            "coherence_score": None,
        })
    dia = draft.get("daily_totals") or {}
    return {
        "meals": meals,
        "daily_totals": dia,
        "targets": {"goal_calories": round(dia.get("kcal", 0)),
                    "protein_g": round(dia.get("protein_g", 0), 1),
                    "carbs_g": round(dia.get("carbs_g", 0), 1),
                    "fat_g": round(dia.get("fat_g", 0), 1)},
        "source": "manual_import",
        "name": sanitize(draft.get("name") or "Dieta importada", MAX_LABEL_CHARS),
    }

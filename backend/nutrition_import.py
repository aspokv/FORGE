"""FORGE — importador de dieta em texto livre.

Mesma arquitetura do importador de treino: parser determinístico, matching híbrido
contra um catálogo FECHADO (os alimentos de foods.json) e nada inventado — o que não
dá para ler com confiança é marcado para revisão em vez de virar número.

O resultado sai no MESMO formato que generate_daily_plan já produz
(`meals[].foods[]` construídos por build_food_item), então o plano importado passa por
/api/nutrition/plan, /substitute e /meal-status sem mudança nenhuma nesses caminhos.

Os formatos que uma dieta de nutricionista usa
----------------------------------------------
O parser nasceu lendo "150g de arroz" — quantidade na frente. Uma dieta real colada por um
atleta veio assim, e saiu pela metade:

    Whey: 40 g
    Carne bovina/frango/peixe: 200 g
    Legumes/verduras: à vontade
    250 g batata inglesa → 200 g batata-doce → 150 g aipim

Quantidade DEPOIS do nome, opções separadas por barra, "à vontade" e uma tabela de trocas.
Nenhum dos quatro era lido: o whey e a banana sumiam, a batata chegava sem gramas e a
tabela de trocas virava três itens a mais na ceia. Cada um desses formatos tem a sua
função abaixo, e todos terminam no mesmo item de sempre.
"""
import math
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
# "Legumes: à vontade". Conta uma porção de referência, e diz que contou.
REVIEW_FREE_PORTION = "free_portion"

MAX_SUBSTITUTIONS = 20
MAX_OPTIONS_PER_SUBSTITUTION = 6
MAX_ALTERNATIVES = 5

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

# As unidades que um número pode trazer. Com e sem acento: "xícara", "colher de chá" e
# "filé" é como quase todo mundo escreve, e sem o acento aqui essas medidas caíam como
# parte do NOME ("xícara de arroz") e a quantidade se perdia.
_UNIDADES = (
    r"kg|g|gr|gramas?|ml|mililitros?|l|litros?|quilos?|"
    r"colher(?:es)?\s+de\s+sopa|colher(?:es)?\s+de\s+ch[aá]|colher(?:es)?\s+sopa|"
    r"x[ií]caras?|conchas?|fatias?|scoops?|doses?|punhados?|fil[eé]s?|postas?|copos?|potes?|"
    r"unidades?|un"
)

_QUANTITY = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(" + _UNIDADES + r")?\b", re.I)

# Quantidade no FIM: "Whey: 40 g", "Banana 120g", "Arroz - 4 colheres de sopa",
# "Iogurte (170 g)". O nome termina num caractere que não é separador, para o separador
# não ficar grudado nele.
_QUANTIDADE_NO_FIM = re.compile(
    r"^(?P<nome>.*?[^\s:=\-–—(])\s*(?P<sep>[:=\-–—(])?\s*"
    r"(?P<valor>\d+(?:[.,]\d+)?)\s*(?P<unidade>" + _UNIDADES + r")?\.?\s*\)?\s*$",
    re.I,
)

# "à vontade" e o que quer dizer o mesmo. Só no fim da linha, que é onde a dieta escreve.
_A_VONTADE = re.compile(
    r"[\s:=\-–—(]*\b(?:[àa]\s+vontade|a\s+gosto|quanto\s+quiser|livres?|liberad[oa]s?)\)?\.?\s*$",
    re.I,
)

# Vírgula entre dois números é decimal ("1,5 kg"), e não separa item.
_SPLIT_ITEMS = re.compile(r"\s+\+\s+|\s*,(?!\d)\s*|\s+e\s+", re.I)

# Opções do mesmo item: "Carne bovina/frango/peixe", "frango ou peixe". A barra só conta
# entre letras, para "1/2" continuar sendo número.
_ALTERNATIVAS = re.compile(r"(?<=[^\W\d_])\s*/\s*(?=[^\W\d_])|\s+ou\s+|\s*,\s*", re.I)
_TEM_ALTERNATIVA = re.compile(r"(?<=[^\W\d_])\s*/\s*(?=[^\W\d_])|\s+ou\s+", re.I)
# Opções com quantidade própria: "100 g de arroz ou 250 g de batata". A barra só não
# separa entre dois números ("1/2").
_SEPARA_OPCOES = re.compile(r"\s+ou\s+|(?<!\d)\s*/\s*|\s*/\s*(?!\d)", re.I)

# Tabela de trocas: "250 g batata → 200 g batata-doce → 150 g aipim". Seta em qualquer
# lugar do texto; dentro de uma seção de substituições, também "=", "ou", ";" e "|".
_SETAS = re.compile(r"\s*(?:→|⇒|⟶|➔|➜|➝|⇄|↔|<->|->|=>)\s*")
_SEPARA_TROCA = re.compile(r"\s*(?:→|⇒|⟶|➔|➜|➝|⇄|↔|<->|->|=>|=|;|\|)\s*|\s+ou\s+|\s+/\s+", re.I)
_CABECALHO_DE_TROCAS = ("substituic", "substituto", "substituir", "trocas", "troca de",
                        "equivalenc", "opcoes de troca", "opcoes de substituic",
                        "lista de substituic", "lista de troca")

# Primeira linha que dá nome à dieta, e não a uma refeição.
_TITULO = ("dieta", "plano alimentar", "cardapio", "protocolo", "planejamento alimentar",
           "estrategia")


def _clean_line(line: str) -> str:
    line = re.sub(r"^\s*\d{1,2}\s*[\.\)]\s+", "", line)
    return re.sub(r"^[\-•\*–]\s*", "", line).strip()


def _e_refeicao_numerada(key: str) -> bool:
    return bool(re.match(r"^refeicao\s*\d*", key) or re.match(r"^\d+\s*a?\s*refeicao", key))


def is_meal_header(line: str) -> bool:
    """Cabeçalho nomeia a refeição e nunca traz quantidade de alimento."""
    key = normalize(line)
    if not key or len(key) > 50:
        return False
    if _e_refeicao_numerada(key):
        return True
    if _QUANTITY.match(line) and _QUANTITY.match(line).group(1):
        return False
    # Quantidade no fim também é item: "Café com leite: 200 ml" começa com "café" e é
    # bebida, e "WHEY: 40 G" é caixa-alta e é suplemento.
    if _quantidade_no_fim(line):
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


def _quantidade_no_fim(text: str) -> Optional[Tuple[float, str, str]]:
    """(valor, unidade, nome) quando a linha TERMINA na quantidade: "Whey: 40 g".

    Número sem unidade só vale depois de separador ("Ovos: 3"). Sem separador, "Ômega 3"
    viraria três unidades de ômega. E número grudado em outro número é horário — "Café da
    manhã (07:00)" é cabeçalho, e não zero unidades de café.
    """
    m = _QUANTIDADE_NO_FIM.match(text or "")
    if not m:
        return None
    valor = float(m.group("valor").replace(",", "."))
    unidade = normalize(m.group("unidade") or "")
    nome = m.group("nome")
    if valor <= 0:
        return None
    if not unidade and (not m.group("sep") or re.search(r"\d$", nome)):
        return None
    return valor, unidade, _limpar_nome(nome)


def _limpar_nome(nome: str) -> str:
    nome = re.sub(r"[\s:=\-–—(]+$", "", nome or "").strip()
    return re.sub(r"^(de|da|do|of)\s+", "", nome, flags=re.I).strip()


def _tirar_a_vontade(text: str) -> Tuple[bool, str]:
    """"Legumes: à vontade" -> (True, "Legumes")."""
    m = _A_VONTADE.search(text or "")
    if not m or not normalize(text[:m.start()]):
        return False, text
    return True, text[:m.start()].strip()


def separar_quantidade(text: str) -> Tuple[Optional[float], str, str, bool]:
    """(valor, unidade, nome, à vontade) para os dois jeitos de escrever um item.

    Quantidade na frente continua sendo lida primeiro, exatamente como antes. Quando a
    linha traz as duas — "1 scoop de whey (30 g)" ou "Whey: 1 scoop (30 g)" — vale o peso:
    é o número que a pessoa pesou, e a medida caseira é só a forma de servir.
    """
    livre, text = _tirar_a_vontade(text)
    valor, unidade, resto = parse_quantity(text)
    if valor is not None:
        fim = _quantidade_no_fim(resto)
        if fim and fim[1] in _MASS_UNITS:
            valor, unidade, resto = fim
        return valor, unidade, _limpar_nome(resto), livre
    fim = _quantidade_no_fim(text)
    if fim:
        valor, unidade, nome = fim
        if unidade in _MASS_UNITS:
            antes = _quantidade_no_fim(nome)
            if antes:
                nome = antes[2]
        return valor, unidade, nome, livre
    return None, "", _limpar_nome(text), livre


def _alternativas(nome: str) -> List[str]:
    """As opções de "Carne bovina/frango/peixe". Lista vazia quando não há opção."""
    if not _TEM_ALTERNATIVA.search(nome or ""):
        return []
    partes = [p.strip() for p in _ALTERNATIVAS.split(nome) if normalize(p)]
    return partes if len(partes) > 1 else []


def _casar(nome: str, matcher: CatalogMatcher) -> Tuple[Optional[str], str, List[str], List[str]]:
    """(alimento, confiança, sugestões, alternativas).

    Com opções no texto, o item fica com a PRIMEIRA que o catálogo conhece e as outras
    viram alternativas — na mesma quantidade, que é o que "Carne bovina/frango/peixe:
    200 g" diz. O nome inteiro só vence se casar de verdade (exato ou apelido): um casamento
    aproximado de "carne bovina frango peixe" escolheria um e jogaria os outros fora.
    """
    food_id, confidence, suggestions = matcher.match(nome)
    partes = _alternativas(nome)
    if not partes or (food_id and confidence in ("exact", "alias")):
        return food_id, confidence, suggestions, []
    achados: List[Tuple[str, str]] = []
    faltou = False
    for parte in partes:
        fid, conf, _ = matcher.match(parte)
        if not fid:
            faltou = True
        elif fid not in [a[0] for a in achados]:
            achados.append((fid, conf))
    if not achados:
        return food_id, confidence, suggestions, []
    principal, conf_principal = achados[0]
    alternativas = [fid for fid, _ in achados[1:]][:MAX_ALTERNATIVES]
    if faltou and conf_principal in ("exact", "alias"):
        # Uma das opções não foi reconhecida: o item passa, mas pede um olhar.
        conf_principal = "fuzzy"
    sugestoes = alternativas + [s for s in suggestions if s != principal and s not in alternativas]
    return principal, conf_principal, sugestoes, alternativas


def _e_verdura(food_id: Optional[str]) -> bool:
    return bool(food_id) and (FOOD_INDEX.get(food_id) or {}).get("category") == "VEGETABLE"


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


def review_reasons(confidence: str, food_id: Optional[str], grams: Optional[float],
                   estimated: bool, a_vontade: bool = False) -> List[str]:
    """Por que um item pede confirmação. Uma regra só, usada ao ler o texto e ao salvar o
    rascunho: sem isso, salvar recalculava os motivos por outro caminho e o aviso de
    "à vontade" virava "medida caseira" no meio da revisão."""
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
        reasons.append(REVIEW_FREE_PORTION if a_vontade else REVIEW_ESTIMATED_PORTION)
    return reasons


def _porcao_a_vontade(food_id: Optional[str]) -> Tuple[Optional[float], bool]:
    """Gramas contadas para "à vontade" — só em verdura e legume.

    A porção de referência do catálogo entra na conta e nasce marcada como estimativa.
    Fora das verduras nada é preenchido: "arroz à vontade" pode ser 100 g ou 400 g, e
    chutar ali tira a meta do dia do lugar. Esse caso continua pedindo o número.
    """
    if not _e_verdura(food_id):
        return None, False
    porcao = (FOOD_INDEX.get(food_id) or {}).get("grams")
    return (float(porcao), True) if porcao else (None, False)


def _opcoes_com_quantidade(text: str) -> Optional[List[Tuple[Optional[float], str, str, bool]]]:
    """"100 g de arroz ou 250 g de batata": cada opção com a SUA quantidade.

    None quando menos de duas opções trazem quantidade — aí é o caso de "Frango ou peixe:
    150 g", uma quantidade só para todas, que _casar resolve.
    """
    partes = [p.strip() for p in _SEPARA_OPCOES.split(text) if normalize(p)]
    if len(partes) < 2:
        return None
    lidas = [separar_quantidade(p) for p in partes[:MAX_OPTIONS_PER_SUBSTITUTION]]
    if sum(1 for valor, _, _, _ in lidas if valor is not None) < 2:
        return None
    return lidas


def _item_de_opcoes(text: str, opcoes, matcher: CatalogMatcher) -> Optional[Dict[str, Any]]:
    """O item é a primeira opção que o catálogo conhece, com a quantidade DELA. As opções
    inteiras vão para `_troca` e viram uma linha da tabela de trocas: com quantidades
    diferentes não são alternativas "na mesma quantidade", são equivalências."""
    troca: List[Dict[str, Any]] = []
    principal = None
    for valor, unidade, nome, _ in opcoes:
        fid, conf, sugestoes = matcher.match(nome)
        grams, estimated = to_grams(valor, unidade, fid)
        if grams is not None and not (0 < grams <= MAX_GRAMS):
            grams, estimated = None, False
        troca.append({"food_id": fid, "raw_name": sanitize(nome, MAX_LABEL_CHARS),
                      "grams": grams, "estimated": estimated, "match_confidence": conf})
        if principal is None and fid:
            principal = (valor, unidade, nome, fid, conf, sugestoes, grams, estimated)
    if principal is None:
        return None
    valor, unidade, nome, fid, conf, sugestoes, grams, estimated = principal
    reasons = review_reasons(conf, fid, grams, estimated)
    return {
        "food_id": fid, "raw_name": sanitize(nome, MAX_LABEL_CHARS),
        "raw_text": sanitize(text, MAX_LABEL_CHARS), "match_confidence": conf,
        "suggestions": sugestoes[:5], "alternativas": [], "a_vontade": False,
        "quantity": valor, "unit": unidade, "grams": grams, "estimated": estimated,
        "needs_review": bool(reasons), "review_reasons": reasons, "_troca": troca,
    }


def _parse_item(text: str, matcher: CatalogMatcher) -> Optional[Dict[str, Any]]:
    text = _clean_line(text)
    if not text:
        return None
    opcoes = _opcoes_com_quantidade(text)
    if opcoes:
        item = _item_de_opcoes(text, opcoes, matcher)
        if item:
            return item
    quantity, unit, nome, a_vontade = separar_quantidade(text)
    nome = nome or text
    if not normalize(nome):
        return None

    food_id, confidence, suggestions, alternativas = _casar(nome, matcher)
    if food_id is None and confidence == "none" and quantity is None and not a_vontade:
        return None  # nem quantidade nem alimento: é ruído, não item

    grams, estimated = to_grams(quantity, unit, food_id)
    if grams is not None and not (0 < grams <= MAX_GRAMS):
        grams, estimated = None, False
    if grams is None and a_vontade:
        grams, estimated = _porcao_a_vontade(food_id)

    reasons = review_reasons(confidence, food_id, grams, estimated, a_vontade)
    return {
        "food_id": food_id,
        "raw_name": sanitize(nome, MAX_LABEL_CHARS),
        "raw_text": sanitize(text, MAX_LABEL_CHARS),
        "match_confidence": confidence,
        "suggestions": suggestions[:5],
        "alternativas": alternativas,
        "a_vontade": a_vontade,
        "quantity": quantity,
        "unit": unit,
        "grams": grams,
        "estimated": estimated,
        "needs_review": bool(reasons),
        "review_reasons": reasons,
    }


def _e_cabecalho_de_trocas(linha: str) -> bool:
    key = normalize(linha)
    return (bool(key) and len(key) <= 60 and any(key.startswith(w) for w in _CABECALHO_DE_TROCAS)
            and not (_QUANTITY.match(linha) and _QUANTITY.match(linha).group(1)))


def _e_titulo(linhas: List[str], matcher: CatalogMatcher) -> bool:
    """A primeira linha dá nome à dieta, e não a uma refeição?

    "DIETA — 83 KG | RECOMPOSIÇÃO" é caixa-alta e curta, e por isso era lida como uma
    refeição vazia. Título é o que começa como título ("Dieta", "Plano alimentar"…), ou
    uma linha que não é alimento nem refeição logo antes de uma refeição.
    """
    if not linhas:
        return False
    primeira = _clean_line(linhas[0])
    key = normalize(primeira)
    if not key or len(key) > 80 or _e_refeicao_numerada(key):
        return False
    if any(key.startswith(w) for w in MEAL_WORDS):
        return False
    if any(key.startswith(w) for w in _TITULO):
        return True
    if len(linhas) < 2 or not is_meal_header(linhas[1]):
        return False
    valor, _, nome, _ = separar_quantidade(primeira)
    return valor is None and matcher.match(nome)[0] is None


def _cabecalho_com_itens(linha: str, matcher: CatalogMatcher) -> Optional[Tuple[str, str]]:
    """"Almoço: arroz 150 g, frango 120 g" -> ("Almoço", "arroz 150 g, frango 120 g").

    Sem isto a linha inteira virava o NOME da refeição e os alimentos sumiam. Só separa
    quando o que vem depois dos dois-pontos é alimento — "Café: 200 ml" é o café.
    """
    m = re.match(r"^\s*([^:]{2,40}?)\s*:\s*(.+)$", linha)
    if not m:
        return None
    cabecalho, resto = m.group(1).strip(), m.group(2).strip()
    key = normalize(cabecalho)
    if not (_e_refeicao_numerada(key) or any(key.startswith(w) for w in MEAL_WORDS)):
        return None
    if _quantidade_no_fim(cabecalho) or (_QUANTITY.match(cabecalho) and _QUANTITY.match(cabecalho).group(1)):
        return None
    partes = [p for p in _SPLIT_ITEMS.split(resto) if normalize(p)]
    if not any(matcher.match(separar_quantidade(p)[2])[0] for p in partes):
        return None
    return cabecalho, resto


def _ler_troca(linha: str, matcher: CatalogMatcher) -> Optional[List[Dict[str, Any]]]:
    """Uma linha da tabela de trocas: cada opção com o alimento e as gramas dela."""
    partes = [p for p in _SEPARA_TROCA.split(_clean_line(linha)) if normalize(p)]
    if len(partes) < 2:
        return None
    opcoes = []
    for parte in partes[:MAX_OPTIONS_PER_SUBSTITUTION]:
        valor, unidade, nome, _ = separar_quantidade(_clean_line(parte))
        food_id, confidence, _ = matcher.match(nome)
        grams, estimated = to_grams(valor, unidade, food_id)
        if grams is not None and not (0 < grams <= MAX_GRAMS):
            grams, estimated = None, False
        opcoes.append({"food_id": food_id, "raw_name": sanitize(nome or parte, MAX_LABEL_CHARS),
                       "grams": grams, "estimated": estimated, "match_confidence": confidence})
    return opcoes


def _itens_da_linha(linha: str, matcher: CatalogMatcher) -> List[str]:
    """Os itens de uma linha. Uma linha com dois alimentos vira dois itens — mas uma linha
    com OPÇÕES ("frango ou peixe") é um item só, e quantidade no fim não impede de separar
    ("Arroz 100 g, feijão 80 g")."""
    limpa = _clean_line(linha)
    nome = separar_quantidade(limpa)[2]
    if not _alternativas(nome) and matcher.match(nome)[0] is not None:
        return [limpa]  # a linha inteira é um alimento ("Creme de arroz + whey")
    # "+" separa item sempre: "Arroz 100 g + frango ou peixe 150 g" são dois itens, e o
    # segundo tem opções. Sem isto, as opções engoliam o arroz.
    segmentos = [s for s in re.split(r"\s+\+\s+", limpa) if normalize(s)]
    if len(segmentos) > 1:
        return [p for seg in segmentos for p in _itens_do_segmento(seg, matcher)]
    return _itens_do_segmento(limpa, matcher)


def _itens_do_segmento(segmento: str, matcher: CatalogMatcher) -> List[str]:
    nome = separar_quantidade(segmento)[2]
    if _alternativas(nome) or matcher.match(nome)[0] is not None:
        return [segmento]
    partes = [p for p in _SPLIT_ITEMS.split(segmento) if normalize(p)]
    if len(partes) > 1 and sum(1 for p in partes if matcher.match(separar_quantidade(p)[2])[0]) >= 2:
        return partes
    return [segmento]


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
    substituicoes: List[Dict[str, Any]] = []
    warnings: List[str] = []
    atual: Optional[Dict[str, Any]] = None
    titulo = ""
    # Título da seção de trocas em que o texto está, ou None fora dela. Dentro dela nada
    # vira item de refeição: é tabela de equivalência, e não comida a mais na ceia.
    secao_de_trocas: Optional[str] = None

    if _e_titulo(linhas, matcher):
        titulo = sanitize(_clean_line(linhas[0]), MAX_LABEL_CHARS)
        linhas = linhas[1:]

    for linha in linhas:
        limpa = _clean_line(linha)
        if _e_cabecalho_de_trocas(limpa):
            secao_de_trocas = sanitize(re.sub(r"[\s:]+$", "", limpa), MAX_LABEL_CHARS)
            continue

        if _SETAS.search(limpa) or (secao_de_trocas and _SEPARA_TROCA.search(limpa)):
            opcoes = _ler_troca(limpa, matcher)
            if opcoes:
                if len(substituicoes) < MAX_SUBSTITUTIONS:
                    substituicoes.append({"titulo": secao_de_trocas or "Substituições",
                                          "opcoes": opcoes})
                continue

        com_itens = _cabecalho_com_itens(linha, matcher)
        if com_itens or is_meal_header(linha):
            secao_de_trocas = None
            if len(meals) >= MAX_MEALS:
                warnings.append(f"Limite de {MAX_MEALS} refeicoes atingido: o resto foi ignorado.")
                break
            nome_da_refeicao = com_itens[0] if com_itens else linha
            atual = {"name": sanitize(nome_da_refeicao, MAX_LABEL_CHARS), "items": []}
            meals.append(atual)
            if not com_itens:
                continue
            linha = com_itens[1]
        elif secao_de_trocas:
            warnings.append(f"Linha da tabela de trocas sem troca reconhecida: {sanitize(linha, 50)}")
            continue

        candidatos = _itens_da_linha(linha, matcher)
        for candidato in candidatos:
            item = _parse_item(candidato, matcher)
            if item is None:
                if len(candidatos) == 1:
                    warnings.append(f"Linha ignorada por nao parecer alimento: {sanitize(linha, 50)}")
                continue
            if atual is None:
                atual = {"name": "Refeicao 1", "items": []}
                meals.append(atual)
            equivalencia = item.pop("_troca", None)
            if len(atual["items"]) >= MAX_ITEMS_PER_MEAL:
                warnings.append(f"{atual['name']}: limite de {MAX_ITEMS_PER_MEAL} itens atingido.")
                continue
            atual["items"].append(item)
            if equivalencia and len(substituicoes) < MAX_SUBSTITUTIONS:
                substituicoes.append({"titulo": atual["name"], "opcoes": equivalencia})

    meals = [m for m in meals if m["items"]]
    if not meals:
        raise ValueError(
            "Nao foi possivel identificar alimentos nesse texto. Use uma linha por item, "
            "por exemplo: 150g de arroz branco."
        )

    # O nome que a própria dieta traz vence o genérico que a tela manda.
    pedido = sanitize(name, MAX_LABEL_CHARS)
    if normalize(pedido) == "dieta importada":
        pedido = ""
    draft = {"name": pedido or titulo or "Dieta importada",
             "source": "manual_import", "meals": meals, "substituicoes": substituicoes,
             "warnings": warnings}
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
                if grams is None and item.get("a_vontade"):
                    grams, estimated = _porcao_a_vontade(fid)
                if grams is not None:
                    item["grams"], item["estimated"] = grams, estimated
                    razoes = [r for r in razoes if r != REVIEW_QUANTITY_MISSING]
                    motivo = REVIEW_FREE_PORTION if item.get("a_vontade") else REVIEW_ESTIMATED_PORTION
                    if estimated and motivo not in razoes:
                        razoes.append(motivo)
            item["review_reasons"] = razoes
            item["needs_review"] = bool(razoes)
    return recompute(draft)


def draft_to_plan(draft: Dict[str, Any],
                  targets_do_atleta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Preserva os totais da dieta confirmada como metas do plano importado.

    O questionario pode ser mantido como referencia, nunca substituir a dieta que
    o usuario acabou de revisar. Itens pendentes sao bloqueados na ativacao.
    """
    meals = []
    for meal in draft.get("meals") or []:
        foods = []
        for item in meal.get("items") or []:
            if not item.get("food_id") or not item.get("grams"):
                continue
            food = build_food_item(item["food_id"], float(item["grams"]))
            alternativas = [a for a in (item.get("alternativas") or [])
                            if a in FOOD_INDEX and a != item["food_id"]][:MAX_ALTERNATIVES]
            if alternativas:
                # Mesma quantidade: é o que a dieta escreveu ("Carne/frango: 150 g").
                food["alternativas"] = [{"food_id": a, "name": FOOD_INDEX[a]["name"]}
                                        for a in alternativas]
            if item.get("a_vontade"):
                food["a_vontade"] = True
            foods.append(food)
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
    alvos = targets_from_import_totals(dia)
    return {
        "meals": meals,
        "daily_totals": dia,
        "targets": alvos,
        "targets_source": "manual_import",
        "assessment_targets": dict(targets_do_atleta or {}),
        "source": "manual_import",
        "name": sanitize(draft.get("name") or "Dieta importada", MAX_LABEL_CHARS),
        "substituicoes": _trocas_do_plano(draft.get("substituicoes")),
    }


def sanitize_substitutions(substituicoes: Any) -> List[Dict[str, Any]]:
    """A tabela de trocas que volta do navegador, revalidada: alimento do catálogo ou
    nenhum, gramas dentro do limite, texto limpo e tamanho limitado."""
    limpas: List[Dict[str, Any]] = []
    for troca in (substituicoes or [])[:MAX_SUBSTITUTIONS]:
        if not isinstance(troca, dict):
            continue
        opcoes = []
        for op in (troca.get("opcoes") or [])[:MAX_OPTIONS_PER_SUBSTITUTION]:
            if not isinstance(op, dict):
                continue
            food_id = op.get("food_id") if op.get("food_id") in FOOD_INDEX else None
            try:
                grams = float(op["grams"]) if op.get("grams") is not None else None
            except (TypeError, ValueError):
                grams = None
            if grams is not None and not (0 < grams <= MAX_GRAMS):
                grams = None
            opcoes.append({"food_id": food_id,
                           "raw_name": sanitize(op.get("raw_name") or "", MAX_LABEL_CHARS),
                           "grams": grams, "estimated": bool(op.get("estimated"))})
        if len(opcoes) >= 2:
            limpas.append({"titulo": sanitize(troca.get("titulo") or "", MAX_LABEL_CHARS)
                           or "Substituições", "opcoes": opcoes})
    return limpas


def _trocas_do_plano(substituicoes: Any) -> List[Dict[str, Any]]:
    """A tabela de trocas como o plano guarda: cada opção com o nome do catálogo para a
    tela mostrar sem carregar o catálogo inteiro. Uma opção que o catálogo não conhece
    continua aparecendo com o texto da dieta — sumir com ela seria a dieta pela metade
    de novo."""
    plano = []
    for troca in sanitize_substitutions(substituicoes):
        opcoes = [{"food_id": op["food_id"],
                   "name": FOOD_INDEX[op["food_id"]]["name"] if op["food_id"] else op["raw_name"],
                   "grams": op["grams"]}
                  for op in troca["opcoes"]]
        plano.append({"titulo": troca["titulo"], "opcoes": opcoes})
    return plano


def targets_from_import_totals(totals: Dict[str, Any]) -> Dict[str, float]:
    """Mesmo arredondamento da previa; kcal vem do catalogo, nao de 4/4/9."""
    return {
        "goal_calories": round(totals.get("kcal", 0)),
        **{key: round(totals.get(key, 0), 1)
           for key in ("protein_g", "carbs_g", "fat_g")},
    }


async def restore_import_targets(db, profile_id: str, stored):
    """Corrige importacoes antigas uma vez, sem alterar refeicoes ou historico.

    Compare-and-set impede uma leitura atrasada de sobrescrever um plano novo.
    O marcador preserva ajustes explicitos posteriores ao reparo.
    """
    plan = (stored or {}).get("plan") or {}
    if plan.get("source") != "manual_import" or plan.get("targets_source"):
        return stored
    totals = plan.get("daily_totals") or {}
    keys = ("kcal", "protein_g", "carbs_g", "fat_g")
    if not all(isinstance(totals.get(k), (int, float))
               and math.isfinite(totals[k]) and totals[k] >= 0 for k in keys):
        return stored
    if totals["kcal"] <= 0:
        return stored
    targets = targets_from_import_totals(totals)
    result = await db.nutrition_plans.update_one(
        {"profile_id": profile_id, "plan": plan},
        {"$set": {"plan.targets": targets, "plan.targets_source": "manual_import"}})
    if not result.matched_count:
        return await db.nutrition_plans.find_one({"profile_id": profile_id}, {"_id": 0})
    return {**stored, "plan": {**plan, "targets": targets, "targets_source": "manual_import"}}

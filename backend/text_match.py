"""FORGE — matching híbrido de texto livre contra um catálogo fechado.

Generalização do que já roda no importador de treino (manual_workout.py): mesmas regras,
sem depender de exercícios. Nutrição usa isto para alimentos.

A ordem de resolução é sempre a mesma, da mais barata para a mais cara:
  exato -> alias escrito -> conjunto de palavras -> alias aprendido -> (IA, fora daqui)

E a regra que não muda: o que não dá para resolver com confiança NÃO é adivinhado. Vira
`None` com sugestões, para uma pessoa decidir.
"""
import re
import unicodedata
from typing import Dict, FrozenSet, List, Optional, Tuple

# Palavras que não carregam identidade em nome de item ("arroz COM feijão",
# "peito DE frango"): removê-las é o que faz ordem e conectivo pararem de importar.
STOPWORDS = {
    "com", "sem", "no", "na", "nos", "nas", "de", "do", "da", "dos", "das", "em",
    "a", "o", "os", "as", "e", "para", "pra", "por", "ao", "aos", "num", "numa",
    "tipo", "ou",
}

FUZZY_THRESHOLD = 0.5


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize(text: str) -> str:
    """Sem acento, minúsculo, sem pontuação, espaço único — chave de comparação."""
    base = strip_accents(text or "").lower()
    base = re.sub(r"[^a-z0-9\s]", " ", base)
    return re.sub(r"\s+", " ", base).strip()


def sanitize(text: str, limit: int) -> str:
    """Higiene do que veio colado: sem caracteres de controle, espaço colapsado e
    tamanho limitado. O React escapa na renderização; isto mantém o documento salvo
    limpo e limitado."""
    clean = "".join(ch for ch in (text or "") if unicodedata.category(ch)[0] != "C")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:limit]


def stem(token: str) -> str:
    """Dobra mínima do português: plural e concordância de gênero, só.
    "cozida"/"cozido" e "ovos"/"ovo" deixam de ser palavras diferentes."""
    if len(token) > 5 and token.endswith("es") and token[-3] in "rszl":
        token = token[:-2]
    elif len(token) > 4 and token.endswith("s"):
        token = token[:-1]
    if len(token) > 4 and token.endswith("a"):
        token = token[:-1] + "o"
    return token


def token_set(text: str) -> FrozenSet[str]:
    return frozenset(stem(t) for t in normalize(text).split() if t not in STOPWORDS)


def token_score(candidate: FrozenSet[str], target: FrozenSet[str]) -> float:
    if not candidate or not target:
        return 0.0
    return len(candidate & target) / len(candidate | target)


class CatalogMatcher:
    """Resolve texto livre para um id de catálogo.

    `entries` é {id: nome}; `aliases` é {texto normalizado: id}. `learned` pode ser
    injetado depois (aliases aprendidos, vindos do banco) sem reconstruir o índice.
    """

    def __init__(self, entries: Dict[str, str], aliases: Optional[Dict[str, str]] = None):
        self.entries = dict(entries)
        self.aliases = dict(aliases or {})
        self.by_name = {normalize(name): eid for eid, name in self.entries.items()}
        self.tokens_by_id = {eid: token_set(name) for eid, name in self.entries.items()}
        self.by_tokens: Dict[FrozenSet[str], str] = {}
        for eid, ts in self.tokens_by_id.items():
            self.by_tokens.setdefault(ts, eid)
        self.alias_tokens: Dict[FrozenSet[str], str] = {}
        for alias, eid in self.aliases.items():
            if eid in self.entries:
                self.alias_tokens.setdefault(token_set(alias), eid)
        # Em quais itens cada palavra aparece — distingue uma palavra sobrando que é
        # inofensiva de uma que identifica OUTRO item do catálogo.
        self.token_to_ids: Dict[str, set] = {}
        for eid, ts in self.tokens_by_id.items():
            for t in ts:
                self.token_to_ids.setdefault(t, set()).add(eid)

    def with_learned(self, learned: Dict[str, str]) -> "CatalogMatcher":
        """Novo matcher com os aliases aprendidos somados aos escritos à mão."""
        if not learned:
            return self
        merged = {**self.aliases, **{k: v for k, v in learned.items() if v in self.entries}}
        return CatalogMatcher(self.entries, merged)

    def match(self, raw: str) -> Tuple[Optional[str], str, List[str]]:
        """(id | None, confiança, sugestões). Confiança:
        exact / alias / fuzzy / ambiguous / none. Só exact e alias dispensam revisão."""
        key = normalize(raw)
        if not key:
            return None, "none", []
        if key in self.by_name:
            return self.by_name[key], "exact", []
        if key in self.aliases and self.aliases[key] in self.entries:
            return self.aliases[key], "alias", []

        tokens = token_set(raw)
        if tokens in self.by_tokens:
            return self.by_tokens[tokens], "exact", []
        if tokens in self.alias_tokens:
            return self.alias_tokens[tokens], "alias", []

        scored = sorted(((token_score(tokens, ts), eid) for eid, ts in self.tokens_by_id.items()),
                        key=lambda t: t[0], reverse=True)
        alias_scored = sorted(((token_score(tokens, ts), eid) for ts, eid in self.alias_tokens.items()),
                              key=lambda t: t[0], reverse=True)
        best_score, best_id = scored[0] if scored else (0.0, None)
        if alias_scored and alias_scored[0][0] > best_score:
            best_score, best_id = alias_scored[0]

        suggestions: List[str] = []
        for _, eid in scored[:5]:
            if eid not in suggestions:
                suggestions.append(eid)

        if best_score >= FUZZY_THRESHOLD and best_id:
            # Palavra sobrando que identifica OUTRO item do catálogo significa que o
            # texto carrega uma distinção que este match jogaria fora.
            leftover = tokens - self.tokens_by_id.get(best_id, frozenset())
            if any(self.token_to_ids.get(t, set()) - {best_id} for t in leftover):
                return None, "ambiguous", suggestions
            return best_id, "fuzzy", suggestions
        return None, "none", suggestions

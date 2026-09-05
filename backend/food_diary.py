"""Consumed food snapshots. Does not modify the plan generator's food catalog."""
from nutrition_engine import FOOD_INDEX

MACROS = ("kcal", "protein_g", "carbs_g", "fat_g")
_COMMON_DIARY_ROWS = [
    ("diary-cookie-cracker", "Biscoito cream cracker", 432, 8.8, 68.7, 14.4, ["bolacha salgada", "cream cracker"]),
    ("diary-cookie-cornstarch", "Biscoito de maisena", 443, 7.8, 75.2, 12.0, ["bolacha maisena", "biscoito doce"]),
    ("diary-cookie-filled", "Biscoito recheado de chocolate", 472, 6.0, 68.0, 20.0, ["bolacha recheada", "cookie recheado"]),
    ("diary-cookie-chocolate-chip", "Cookie com gotas de chocolate", 488, 5.8, 64.0, 23.0, ["cookie", "bolacha cookie"]),
    ("diary-bread-cheese", "Pão de queijo assado", 363, 5.1, 34.2, 23.8, ["pao de queijo"]),
    ("diary-cake-chocolate", "Bolo de chocolate", 371, 5.0, 53.0, 16.0, ["bolo", "bolo chocolate"]),
    ("diary-chocolate-milk", "Chocolate ao leite", 535, 7.6, 59.4, 29.7, ["chocolate", "barra de chocolate"]),
    ("diary-ice-cream", "Sorvete de creme", 207, 3.5, 24.0, 11.0, ["sorvete", "gelado"]),
    ("diary-condensed-milk", "Leite condensado", 321, 7.9, 54.4, 8.7, ["leite condensado"]),
    ("diary-soda-cola", "Refrigerante de cola", 42, 0.0, 10.6, 0.0, ["refrigerante", "refri", "cola"]),
    ("diary-orange-juice", "Suco de laranja", 45, 0.7, 10.4, 0.2, ["suco", "suco laranja"]),
    ("diary-beer", "Cerveja", 43, 0.5, 3.6, 0.0, ["cerveja", "chopp"]),
    ("diary-pizza-mozzarella", "Pizza de mussarela", 266, 11.0, 33.0, 10.0, ["pizza", "pizza queijo"]),
    ("diary-hamburger", "Hambúrguer bovino grelhado", 250, 26.0, 0.0, 17.0, ["hamburguer", "carne de hamburguer"]),
    ("diary-hot-dog", "Cachorro-quente completo", 247, 9.0, 22.0, 14.0, ["cachorro quente", "hot dog"]),
    ("diary-sausage", "Linguiça suína assada", 296, 19.0, 2.0, 24.0, ["linguica", "linguiça assada"]),
    ("diary-beef-steak", "Bife bovino grelhado", 252, 27.3, 0.0, 15.5, ["bife", "carne bovina", "carne grelhada"]),
    ("diary-beef-stew", "Carne bovina cozida", 219, 29.0, 0.0, 11.0, ["carne de panela", "carne cozida"]),
    ("diary-pork-ribs", "Costela suína assada", 355, 25.0, 0.0, 28.0, ["costelinha", "costela de porco"]),
    ("diary-fried-chicken", "Frango empanado frito", 297, 18.0, 17.0, 18.0, ["frango frito", "frango empanado"]),
    ("diary-fried-egg", "Ovo frito", 196, 13.6, 0.8, 15.3, ["ovo na frigideira"]),
    ("diary-french-fries", "Batata frita", 312, 3.4, 41.0, 15.0, ["fritas", "batatinha frita"]),
    ("diary-cassava-fried", "Mandioca frita", 300, 1.6, 49.0, 11.0, ["aipim frito", "macaxeira frita"]),
    ("diary-farofa", "Farofa pronta", 406, 4.0, 77.0, 9.0, ["farofa"]),
    ("diary-acai", "Açaí com xarope", 110, 1.2, 21.5, 2.7, ["acai", "tigela de acai"]),
    ("diary-brigadeiro", "Brigadeiro", 338, 6.0, 54.0, 11.0, ["brigadeiro", "docinho"]),
    ("diary-beef-heart", "Coração bovino cozido", 165, 28.5, 0.1, 4.7, ["coracao", "coração de boi", "miúdo bovino"]),
    ("diary-chicken-heart", "Coração de frango grelhado", 207, 26.4, 0.1, 10.6, ["coracao de frango", "coração de galinha", "miúdo de frango"]),
]

_COMMON_DIARY_FOODS = {fid: {"id": fid, "name": name, "grams": 100, "kcal": kcal,
    "protein_g": protein, "carbs_g": carbs, "fat_g": fat, "aliases": aliases,
    "source": "Valor médio estimado por 100 g — confirme o rótulo quando disponível"}
    for fid, name, kcal, protein, carbs, fat, aliases in _COMMON_DIARY_ROWS}

# Opções populares ficam disponíveis imediatamente, mesmo se o provedor mundial
# estiver lento. Os valores são por porção de 30 g e o rótulo continua sendo a
# referência final, pois sabor e lote podem alterar a composição.
_BRANDED_WHEY_ROWS = [
    ("growth-whey-concentrado", "Whey Protein Concentrado — Growth Supplements", 120, 23, 4.5, 2.0, ["growth whey", "whey growth"]),
    ("max-titanium-top-whey", "Top Whey 3W — Max Titanium", 120, 21, 4.6, 2.0, ["max titanium whey", "top whey"]),
    ("integralmedica-nutri-whey", "Nutri Whey Protein — Integralmédica", 119, 22, 4.0, 1.7, ["integralmedica whey", "nutri whey"]),
    ("dux-whey-concentrado", "Whey Protein Concentrado — DUX Nutrition", 118, 22, 3.3, 1.8, ["dux whey", "whey dux"]),
    ("probiotica-100-pure-whey", "100% Pure Whey — Probiótica", 121, 23, 3.8, 1.7, ["probiotica whey", "pure whey"]),
    ("soldiers-whey-concentrado", "Whey Protein Concentrado — Soldiers Nutrition", 119, 23, 3.5, 1.6, ["soldiers whey", "whey soldiers"]),
    ("black-skull-whey-100-hd", "Whey 100% HD — Black Skull", 120, 21, 5.0, 1.7, ["black skull whey", "whey hd"]),
    ("adaptogen-tasty-whey", "Tasty Whey — Adaptogen Science", 119, 21, 5.0, 1.6, ["adaptogen whey", "tasty whey"]),
    ("essential-pure-whey", "Pure Whey — Essential Nutrition", 116, 22, 3.0, 1.8, ["essential whey", "pure whey essential"]),
    ("optimum-gold-standard-whey", "Gold Standard 100% Whey — Optimum Nutrition", 120, 24, 3.0, 1.0, ["optimum whey", "gold standard whey", "on whey"]),
]
_BRANDED_WHEY_FOODS = {fid: {"id": fid, "name": name, "grams": 30, "kcal": kcal,
    "protein_g": protein, "carbs_g": carbs, "fat_g": fat, "aliases": aliases,
    "source": "Valor típico por porção de 30 g — confirme o rótulo do sabor escolhido"}
    for fid, name, kcal, protein, carbs, fat, aliases in _BRANDED_WHEY_ROWS}

DIARY_FOODS = {**FOOD_INDEX, **_COMMON_DIARY_FOODS, **_BRANDED_WHEY_FOODS, "diary-beef-ribs-roasted": {
    "id": "diary-beef-ribs-roasted", "name": "Costela bovina assada, sem óleo, com sal (sem osso)",
    "grams": 100, "kcal": 360, "protein_g": 28.5, "carbs_g": 0, "fat_g": 27.4,
    "source": "TBCA BRC0352F — 100 g da parte comestível",
    "source_url": "https://www.tbca.net.br/base-dados-en/int_statistical_composition.php?cod_produto=BRC0352F",
}}

def food_snapshot(items, extra_foods=None):
    catalog = {**DIARY_FOODS, **(extra_foods or {})}
    rows = []
    totals = {k: 0.0 for k in MACROS}
    for item in items:
        food = catalog.get(item.food_id)
        if not food:
            raise ValueError("Alimento não encontrado no catálogo.")
        values = {k: round(float(food.get(k, 0)) * item.grams / float(food.get("grams", 100)), 2) for k in MACROS}
        rows.append({"food_id": item.food_id, "name": food["name"], "grams": item.grams,
                     "source": food.get("source", "Catálogo FORGE"), **values})
        for k in MACROS:
            totals[k] += values[k]
    return {"foods": rows, "totals": {k: round(v, 2) for k, v in totals.items()}}

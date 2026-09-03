"""Consumed food snapshots. Does not modify the plan generator's food catalog."""
from nutrition_engine import FOOD_INDEX

MACROS = ("kcal", "protein_g", "carbs_g", "fat_g")
DIARY_FOODS = {**FOOD_INDEX, "diary-beef-ribs-roasted": {
    "id": "diary-beef-ribs-roasted", "name": "Costela bovina assada, sem óleo, com sal (sem osso)",
    "grams": 100, "kcal": 360, "protein_g": 28.5, "carbs_g": 0, "fat_g": 27.4,
    "source": "TBCA BRC0352F — 100 g da parte comestível",
    "source_url": "https://www.tbca.net.br/base-dados-en/int_statistical_composition.php?cod_produto=BRC0352F",
}}

def food_snapshot(items):
    rows = []
    totals = {k: 0.0 for k in MACROS}
    for item in items:
        food = DIARY_FOODS.get(item.food_id)
        if not food:
            raise ValueError("Alimento não encontrado no catálogo.")
        values = {k: round(float(food.get(k, 0)) * item.grams / float(food.get("grams", 100)), 2) for k in MACROS}
        rows.append({"food_id": item.food_id, "name": food["name"], "grams": item.grams,
                     "source": food.get("source", "Catálogo FORGE"), **values})
        for k in MACROS:
            totals[k] += values[k]
    return {"foods": rows, "totals": {k: round(v, 2) for k, v in totals.items()}}

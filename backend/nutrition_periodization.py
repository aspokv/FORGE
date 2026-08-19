"""FORGE — periodização calórica semanal.

Do plano base até uma meta calórica, em progressão linear por semanas.

Regras, nesta ordem de prioridade:
  1. Proteína é FIXA em gramas — a mesma do plano base, em todas as semanas.
  2. Gordura nunca desce abaixo do piso de segurança (0,8 g/kg de peso corporal, o
     mesmo mínimo que FORGE_COACH_METHODOLOGY já aplica no resto do app).
  3. O que sobra de caloria vira carboidrato.

Quando a matemática pede menos gordura que o piso, a gordura trava no piso e a
diferença vai para o carboidrato. Quando nem isso fecha a meta — porque proteína fixa
mais o piso de gordura já custam mais do que a meta da semana — a semana é marcada
como inviável, com o motivo. O motor não "resolve" isso cortando proteína ou furando o
piso: quem decide se o plano base precisa mudar é uma pessoa.
"""
from typing import Any, Dict, List, Optional

from nutrition_engine import FORGE_COACH_METHODOLOGY

KCAL_PROTEIN = 4
KCAL_CARB = 4
KCAL_FAT = 9

MAX_WEEKS = 52
MIN_WEEKS = 1
MIN_WEEKLY_KCAL = 800  # abaixo disso nada de automático é seguro


def fat_floor_g(weight_kg: float, goal: str = "fat_loss") -> float:
    """Piso de gordura em gramas/dia. Vem da metodologia do próprio FORGE, para não
    existirem duas regras diferentes de gordura mínima no mesmo app."""
    faixa = FORGE_COACH_METHODOLOGY["fat_range_g_per_kg"].get(
        goal, FORGE_COACH_METHODOLOGY["fat_range_g_per_kg"]["maintenance"])
    return round(float(weight_kg) * float(faixa[0]), 1)


def resolve_target_kcal(base_kcal: float, target_kcal: Optional[float] = None,
                        pct: Optional[float] = None) -> float:
    """Meta em kcal absoluta ou em % (negativa corta, positiva aumenta)."""
    if target_kcal is not None:
        return round(float(target_kcal))
    if pct is not None:
        return round(float(base_kcal) * (1 + float(pct) / 100.0))
    raise ValueError("Informe a caloria final ou a porcentagem de ajuste.")


def build_week(week: int, week_kcal: float, protein_g: float, floor_g: float,
               base_fat_g: float, base_carbs_g: float) -> Dict[str, Any]:
    protein_kcal = protein_g * KCAL_PROTEIN
    restante = week_kcal - protein_kcal

    avisos: List[str] = []
    piso_aplicado = False

    minimo_gordura_kcal = floor_g * KCAL_FAT
    if restante < minimo_gordura_kcal:
        # Nem proteína fixa + piso de gordura cabem na meta: não dá para atingir
        # a semana só mexendo em macro.
        kcal_minima = round(protein_kcal + minimo_gordura_kcal)
        return {
            "week": week,
            "kcal": round(week_kcal),
            "protein_g": round(protein_g, 1),
            "fat_g": floor_g,
            "carbs_g": 0.0,
            "fat_floor_applied": True,
            "feasible": False,
            "warnings": [
                f"Meta de {round(week_kcal)} kcal nao e atingivel mantendo proteina "
                f"({round(protein_g)} g) e o piso de gordura ({floor_g} g): o minimo "
                f"seguro e {kcal_minima} kcal. Reavalie o plano base."
            ],
        }

    # Divide o restante entre gordura e carboidrato preservando a proporção do plano
    # base — o perfil da dieta original é mantido enquanto der.
    base_fat_kcal = base_fat_g * KCAL_FAT
    base_carb_kcal = base_carbs_g * KCAL_CARB
    base_total = base_fat_kcal + base_carb_kcal
    fracao_gordura = (base_fat_kcal / base_total) if base_total > 0 else 0.3

    fat_kcal = restante * fracao_gordura
    fat_g = fat_kcal / KCAL_FAT
    if fat_g < floor_g:
        fat_g = floor_g
        piso_aplicado = True
        avisos.append(
            f"Gordura travada no piso de {floor_g} g; a diferenca foi para o carboidrato.")

    carbs_g = (restante - fat_g * KCAL_FAT) / KCAL_CARB
    if carbs_g < 0:
        carbs_g = 0.0
        avisos.append("Carboidrato zerado para respeitar o piso de gordura.")

    return {
        "week": week,
        "kcal": round(week_kcal),
        "protein_g": round(protein_g, 1),
        "fat_g": round(fat_g, 1),
        "carbs_g": round(carbs_g, 1),
        "fat_floor_applied": piso_aplicado,
        "feasible": True,
        "warnings": avisos,
    }


def build_periodization(base: Dict[str, float], weight_kg: float, weeks: int,
                        target_kcal: Optional[float] = None, pct: Optional[float] = None,
                        goal: str = "fat_loss") -> Dict[str, Any]:
    """Progressão linear do plano base até a meta, semana a semana.

    A semana `weeks` fecha exatamente na meta; as intermediárias são os degraus.
    """
    weeks = int(weeks)
    if not (MIN_WEEKS <= weeks <= MAX_WEEKS):
        raise ValueError(f"Duracao deve estar entre {MIN_WEEKS} e {MAX_WEEKS} semanas.")

    base_kcal = float(base.get("kcal") or 0)
    protein_g = float(base.get("protein_g") or 0)
    base_fat_g = float(base.get("fat_g") or 0)
    base_carbs_g = float(base.get("carbs_g") or 0)
    if base_kcal <= 0 or protein_g <= 0:
        raise ValueError("Plano base sem calorias ou sem proteina: gere ou importe a dieta primeiro.")
    if float(weight_kg) <= 0:
        raise ValueError("Peso corporal necessario para calcular o piso de gordura.")

    alvo = resolve_target_kcal(base_kcal, target_kcal, pct)
    if alvo < MIN_WEEKLY_KCAL:
        raise ValueError(f"Meta calorica muito baixa: minimo de {MIN_WEEKLY_KCAL} kcal.")

    floor_g = fat_floor_g(weight_kg, goal)
    passo = (alvo - base_kcal) / weeks

    semanas = [build_week(i, base_kcal + passo * i, protein_g, floor_g, base_fat_g, base_carbs_g)
               for i in range(1, weeks + 1)]

    return {
        "base": {"kcal": round(base_kcal), "protein_g": round(protein_g, 1),
                 "fat_g": round(base_fat_g, 1), "carbs_g": round(base_carbs_g, 1)},
        "target_kcal": alvo,
        "weeks": weeks,
        "direction": "deficit" if alvo < base_kcal else ("surplus" if alvo > base_kcal else "flat"),
        "weight_kg": round(float(weight_kg), 1),
        "fat_floor_g": floor_g,
        "goal": goal,
        "table": semanas,
        "infeasible_weeks": [w["week"] for w in semanas if not w["feasible"]],
    }


def sanitize_edited_table(table: List[Dict[str, Any]], weight_kg: float,
                          goal: str = "fat_loss") -> List[Dict[str, Any]]:
    """Revalida a tabela depois de edição manual: kcal é sempre recalculada a partir
    dos macros (o cliente não decide o total), e o piso de gordura continua valendo —
    editar à mão não é rota de fuga da regra de segurança."""
    floor_g = fat_floor_g(weight_kg, goal)
    limpa: List[Dict[str, Any]] = []
    for i, linha in enumerate(table or [], 1):
        protein_g = max(0.0, float(linha.get("protein_g") or 0))
        carbs_g = max(0.0, float(linha.get("carbs_g") or 0))
        fat_g = max(0.0, float(linha.get("fat_g") or 0))
        avisos: List[str] = []
        if fat_g < floor_g:
            fat_g = floor_g
            avisos.append(f"Gordura ajustada para o piso de {floor_g} g.")
        kcal = protein_g * KCAL_PROTEIN + carbs_g * KCAL_CARB + fat_g * KCAL_FAT
        limpa.append({
            "week": i,
            "kcal": round(kcal),
            "protein_g": round(protein_g, 1),
            "fat_g": round(fat_g, 1),
            "carbs_g": round(carbs_g, 1),
            "fat_floor_applied": bool(avisos),
            "feasible": kcal >= MIN_WEEKLY_KCAL,
            "warnings": avisos + ([] if kcal >= MIN_WEEKLY_KCAL else
                                  [f"Abaixo do minimo de {MIN_WEEKLY_KCAL} kcal."]),
        })
    return limpa

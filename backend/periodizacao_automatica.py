# -*- coding: utf-8 -*-
"""Periodização automática da dieta: o plano anda sozinho, semana a semana (Elite).

Por que existe
--------------
O pedido: "vou seguir essa dieta por quatro semanas; estou em emagrecimento, então ele vai
cortando o carboidrato automaticamente. Se estou em ganho de massa, vai fazendo superávit."

O FORGE tinha as duas metades e nenhuma fazia isso:

  - a aba "Periodização" montava uma tabela semana a semana, gravava, e NINGUÉM lia a
    tabela depois. Era uma calculadora;
  - o Conselho lê o resultado toda semana e propõe um ajuste, mas muda só a META. O prato
    continuava o mesmo: a pessoa via "carboidrato 190 g" e o arroz do almoço não mudava.

Aqui as duas se juntam num plano que ANDA: o degrau da semana entra na meta e nas
porções das refeições, e a balança pode segurar o degrau.

As regras
---------
1. Proteína é fixa e a gordura também. Quem mexe é o carboidrato — no corte e no ganho.
   Proteína protege o músculo no déficit e não precisa subir no superávit; mexer em três
   macros de uma vez esconderia qual deles causou o resultado.
2. A semana 1 é a dieta como ela está. Os degraus começam na semana 2: a primeira semana
   é a referência contra a qual as outras se medem.
3. O passo é uma fração da caloria base, com teto absoluto — a mesma forma do passo do
   Conselho, para não existirem dois tamanhos de ajuste no mesmo produto.
4. Pisos que nenhum degrau atravessa: carboidrato de 1,5 g/kg no corte (abaixo disso o
   treino cai antes da gordura), 1200 kcal, e no ganho um superávit de no máximo 20%.
   Quando o degrau bate num piso, ele trava ali e a tela diz por quê.
5. A balança pode SEGURAR o degrau, nunca inventar outro. Perdendo mais de 1% do peso por
   semana no corte, ou ganhando mais de 0,5% no ganho, o degrau da semana não vem: o
   plano espera. Sem pesagens suficientes o calendário segue, e a tela pede a pesagem de
   sexta — que é o que dá à balança o poder de segurar.
"""
from datetime import date as Data
from typing import Any, Dict, List, Optional, Tuple

from conselho import PERDA_RAPIDA, PISO_KCAL, RITMO_ESPERADO, TETO_DO_PASSO_KCAL, numero

CORTE, GANHO = "corte", "ganho"
FASES = (CORTE, GANHO)
DURACOES = (2, 4, 6, 8, 12)
RITMOS = ("suave", "moderado", "forte")

# Fração da caloria base por degrau. O corte tem passos maiores que o ganho: um superávit
# grande vira gordura mais rápido do que um déficit grande vira músculo perdido.
PASSO_POR_RITMO = {
    CORTE: {"suave": 0.04, "moderado": 0.06, "forte": 0.08},
    GANHO: {"suave": 0.02, "moderado": 0.03, "forte": 0.04},
}
TETO_DO_PASSO = {CORTE: TETO_DO_PASSO_KCAL, GANHO: 150.0}
PASSO_MINIMO_KCAL = 50.0
CARBO_MINIMO_G_POR_KG = 1.5
SUPERAVIT_MAXIMO = 0.20
GANHO_RAPIDO = RITMO_ESPERADO["muscle_gain"][1]
KCAL_CARBO = 4


def fase_do_objetivo(objetivo: Optional[str]) -> Optional[str]:
    objetivo = str(objetivo or "").lower()
    if objetivo == "fat_loss":
        return CORTE
    if objetivo == "muscle_gain":
        return GANHO
    return None


def passo_kcal(base_kcal: float, fase: str, ritmo: str) -> float:
    passo = min(float(base_kcal) * PASSO_POR_RITMO[fase][ritmo], TETO_DO_PASSO[fase])
    return round(max(PASSO_MINIMO_KCAL, passo))


def montar_progressao(base: Dict[str, float], peso_kg: float, fase: str, semanas: int,
                      ritmo: str) -> Dict[str, Any]:
    """A tabela das semanas: kcal e macros de cada uma, e onde um piso travou.

    Levanta ValueError com frase de tela quando a periodização não faz sentido.
    """
    if fase not in FASES:
        raise ValueError("Escolha corte ou ganho de massa.")
    if int(semanas) not in DURACOES:
        raise ValueError("Escolha 2, 4, 6, 8 ou 12 semanas.")
    if ritmo not in RITMOS:
        raise ValueError("Escolha o ritmo: suave, moderado ou forte.")
    kcal = float(base.get("kcal") or 0)
    proteina = float(base.get("protein_g") or 0)
    carbo = float(base.get("carbs_g") or 0)
    gordura = float(base.get("fat_g") or 0)
    if kcal <= 0 or proteina <= 0:
        raise ValueError("Seu plano ainda não tem meta de calorias e proteína. Gere ou importe a dieta primeiro.")
    if not peso_kg or float(peso_kg) <= 0:
        raise ValueError("Registre seu peso antes: o piso de carboidrato é calculado por ele.")

    piso_carbo = round(CARBO_MINIMO_G_POR_KG * float(peso_kg))
    if fase == CORTE and carbo <= piso_carbo:
        raise ValueError(f"Seu carboidrato ({round(carbo)} g) já está no mínimo seguro para "
                         f"o seu peso ({piso_carbo} g). Um corte agora sairia do treino, não da gordura.")

    passo = passo_kcal(kcal, fase, ritmo)
    sentido = -1 if fase == CORTE else 1
    teto_ganho = kcal * (1 + SUPERAVIT_MAXIMO)
    linhas = []
    for degrau in range(int(semanas)):
        alvo = kcal + sentido * passo * degrau
        travou = None
        if fase == GANHO and alvo > teto_ganho:
            alvo, travou = teto_ganho, f"superávit no teto de {int(SUPERAVIT_MAXIMO * 100)}%"
        novo_carbo = carbo + (alvo - kcal) / KCAL_CARBO
        if fase == CORTE and novo_carbo < piso_carbo:
            novo_carbo = float(piso_carbo)
            alvo = kcal + (novo_carbo - carbo) * KCAL_CARBO
            travou = f"carboidrato no piso de {piso_carbo} g"
        if fase == CORTE and alvo < PISO_KCAL:
            alvo = PISO_KCAL
            novo_carbo = carbo + (alvo - kcal) / KCAL_CARBO
            travou = f"caloria no piso de {int(PISO_KCAL)} kcal"
        linhas.append({"semana": degrau + 1, "degrau": degrau, "kcal": round(alvo),
                       "protein_g": round(proteina, 1), "carbs_g": round(novo_carbo, 1),
                       "fat_g": round(gordura, 1), "travou": travou})
    return {"fase": fase, "ritmo": ritmo, "semanas": int(semanas), "passo_kcal": passo,
            "piso_carbo_g": piso_carbo, "base": {"kcal": round(kcal), "protein_g": round(proteina, 1),
                                                 "carbs_g": round(carbo, 1), "fat_g": round(gordura, 1)},
            "tabela": linhas}


def semana_do_calendario(inicio: Data, hoje: Data) -> int:
    return max(1, (hoje - inicio).days // 7 + 1)


def decidir_degrau(fase: str, tendencia: Dict[str, Any]) -> Tuple[str, str]:
    """("avancar" | "segurar", motivo). A balança só pode segurar, nunca inventar degrau."""
    if not tendencia.get("suficiente"):
        return "avancar", ("Sem pesagens suficientes para conferir o ritmo: segui o calendário. "
                           "Pese toda sexta-feira para a balança poder segurar o degrau quando precisar.")
    peso = float(tendencia.get("peso_atual") or 0)
    kg = float(tendencia.get("kg_por_semana") or 0)
    fracao = kg / peso if peso else 0.0
    ritmo = f"{numero(kg, 2, sinal=True)} kg por semana ({numero(fracao * 100, 1, sinal=True)}%)"
    if fase == CORTE and fracao < -PERDA_RAPIDA:
        return "segurar", (f"Você está a {ritmo}. Acima de {int(PERDA_RAPIDA * 100)}% por semana a "
                           f"perda começa a sair de músculo: segurei o degrau desta semana.")
    if fase == GANHO and fracao > GANHO_RAPIDO:
        return "segurar", (f"Você está a {ritmo}. Acima de {numero(GANHO_RAPIDO * 100, 1)}% por "
                           f"semana o ganho vira gordura: segurei o degrau desta semana.")
    return "avancar", f"Seu peso anda a {ritmo}, dentro do ritmo. Degrau aplicado."


# ── O prato ─────────────────────────────────────────────────────────────────────────────

def _base_do_item(item: Dict[str, Any], catalogo_diario: Dict[str, Any]) -> Dict[str, Any]:
    return catalogo_diario.get(item.get("food_id")) or item.get("food") or {}


def e_fonte_de_carbo(item: Dict[str, Any], catalogo_motor: Dict[str, Any],
                     catalogo_diario: Dict[str, Any]) -> bool:
    """Alimento cujo papel no prato é o carboidrato: arroz, batata, pão, fruta, aveia.

    Verdura não entra, mesmo tendo mais carboidrato que proteína: cortar brócolis para
    cortar carboidrato seria tirar a parte do prato que segura a fome. Item "à vontade"
    também não: a porção dele é referência, não prescrição.
    """
    if item.get("a_vontade"):
        return False
    if (catalogo_motor.get(item.get("food_id")) or {}).get("category") == "VEGETABLE":
        return False
    base = _base_do_item(item, catalogo_diario)
    kcal = float(base.get("kcal") or 0)
    return kcal > 0 and float(base.get("carbs_g") or 0) * KCAL_CARBO >= 0.5 * kcal


def _carbo_do_item(item, catalogo_diario) -> float:
    base = _base_do_item(item, catalogo_diario)
    return float(base.get("carbs_g") or 0) * float(item.get("grams") or 0) / max(1.0, float(base.get("grams") or 100))


def _arredondar(gramas: float) -> float:
    """De 5 em 5 g: "130 g de arroz" se pesa; "127,4 g" não."""
    return float(max(5, int(round(gramas / 5.0)) * 5))


def ajustar_refeicoes(refeicoes: List[Dict[str, Any]], delta_carbo_g: float, catalogo_motor,
                      catalogo_diario, build_food_item) -> Tuple[List[Dict[str, Any]], float, List[Dict[str, Any]]]:
    """Leva o carboidrato do dia `delta_carbo_g` para cima ou para baixo, no prato.

    Todas as fontes de carboidrato mudam na mesma proporção: o almoço continua sendo o
    almoço, só com menos (ou mais) arroz. Devolve (refeições, delta aplicado de verdade,
    mudanças), porque o arredondamento de 5 g faz o aplicado diferir um pouco do pedido.
    """
    fontes = [(i, j) for i, r in enumerate(refeicoes) for j, item in enumerate(r.get("foods") or [])
              if e_fonte_de_carbo(item, catalogo_motor, catalogo_diario)]
    total = sum(_carbo_do_item(refeicoes[i]["foods"][j], catalogo_diario) for i, j in fontes)
    if total <= 0 or not delta_carbo_g:
        return refeicoes, 0.0, []
    fator = max(0.2, (total + float(delta_carbo_g)) / total)
    novas = [dict(r, foods=list(r.get("foods") or [])) for r in refeicoes]
    aplicado, mudancas = 0.0, []
    for i, j in fontes:
        item = novas[i]["foods"][j]
        gramas = _arredondar(float(item["grams"]) * fator)
        if gramas == float(item["grams"]):
            continue
        antes = _carbo_do_item(item, catalogo_diario)
        if item.get("food_id") in catalogo_motor and not item.get("manual"):
            novo = {**item, **build_food_item(item["food_id"], gramas)}
        else:
            novo = {**item, "grams": gramas}
        delta_item = _carbo_do_item(novo, catalogo_diario) - antes
        novas[i]["foods"][j] = novo
        novas[i]["target_cal"] = round(float(novas[i].get("target_cal") or 0) + delta_item * KCAL_CARBO)
        aplicado += delta_item
        mudancas.append({"refeicao": novas[i].get("name"), "alimento": _base_do_item(item, catalogo_diario).get("name") or item["food_id"],
                         "de": float(item["grams"]), "para": gramas})
    return novas, round(aplicado, 1), mudancas

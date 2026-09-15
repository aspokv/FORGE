# -*- coding: utf-8 -*-
"""Montar a refeicao escolhendo alimento por alimento, dentro de cada funcao do prato.

O que este arquivo resolve: a pessoa quer escolher o que vai comer, e nao receber uma
combinacao pronta. O motor ja sabia calcular a GRAMA de qualquer conjunto de alimentos
(`calculate_meal_portions`) e o endpoint que grava a escolha ja aceitava uma lista livre —
o que faltava era dizer QUAIS alimentos cabem em cada espaco daquela refeicao.

Por que por FUNCAO e nao numa lista unica: esta escrito em maiusculas dentro do motor,
"MACROS AJUSTAM A REFEICAO, MACROS NAO INVENTAM A REFEICAO". Escolha livre de uma lista so
produz prato que fecha o numero e nao e comida — arroz com aveia, banana e whey soma 700
kcal com macro perfeito e ninguem come. Separar por funcao mantem a liberdade de escolha e
tira a possibilidade de montar um prato absurdo sem perceber.

Nada aqui calcula macro nem porcao. Isto e uma VITRINE: diz o que cabe em cada espaco, com
o que ja existia no motor. Quem dimensiona continua sendo `calculate_meal_portions`.
"""
from typing import Any, Dict, List, Optional

from nutrition_engine import (FOOD_FAMILIES, FOOD_INDEX, MEAL_TEMPLATES, _food_compatible,
                              _infer_meal_type)

# Os papeis tem nome tecnico no motor ("primary_protein"). A pessoa le "Proteina". A ordem
# desta lista tambem e a ordem da tela: proteina primeiro porque e o que ancora o prato e o
# que mais pesa na conta; gordura por ultimo porque e quase sempre opcional.
ROTULOS = {
    "primary_protein": ("Proteína", "O que ancora o prato."),
    "secondary_protein": ("Proteína extra", "Opcional, para completar a conta."),
    "primary_carb": ("Carboidrato", "A energia da refeição."),
    "fruit": ("Fruta", "Entra pelo carboidrato rápido e pelo volume."),
    "vegetable": ("Acompanhamento", "Volume e saciedade quase sem caloria."),
    "fat_source": ("Gordura", "Pouca quantidade, muita caloria."),
}

ORDEM = ["primary_protein", "secondary_protein", "primary_carb", "fruit",
         "vegetable", "fat_source"]


def _candidatos(componente: Dict[str, Any], perfil: Dict[str, Any]) -> List[str]:
    """Os alimentos que cabem num espaco, ja sem o que a pessoa nao pode comer.

    A familia manda quando existe: ela e mais estreita que a categoria e foi escrita a mao
    para cada papel. Sem familia, cai na categoria, que e o comportamento que
    `generate_meal` ja tem para o mesmo componente.
    """
    familia = componente.get("family")
    if familia:
        ids = FOOD_FAMILIES.get(familia) or []
    else:
        ids = [f["id"] for f in FOOD_INDEX.values()
               if f.get("category") == componente.get("category")]
    saida = []
    for fid in ids:
        alimento = FOOD_INDEX.get(fid)
        if not alimento:
            continue
        if componente.get("role") not in (alimento.get("roles") or []) and familia is None:
            continue
        if not _food_compatible(alimento, perfil, set()):
            continue
        saida.append(fid)
    return saida


def _cartao_do_alimento(fid: str, do_metodo: bool) -> Dict[str, Any]:
    """O que a tela precisa para a pessoa decidir sem abrir o alimento.

    Caloria por 100 g, e nao a porcao final: a porcao so existe depois que o conjunto todo
    esta escolhido, porque `calculate_meal_portions` distribui a meta entre os alimentos.
    Mostrar uma grama aqui seria um numero que muda sozinho na tela seguinte.
    """
    a = FOOD_INDEX.get(fid) or {}
    base = max(1, a.get("grams", 100))
    fator = 100.0 / base
    return {
        "food_id": fid,
        "name": a.get("name", fid),
        "kcal_por_100g": round((a.get("kcal", 0) or 0) * fator),
        "protein_por_100g": round((a.get("protein_g", 0) or 0) * fator, 1),
        "carb_por_100g": round((a.get("carbs_g", 0) or 0) * fator, 1),
        "fat_por_100g": round((a.get("fat_g", 0) or 0) * fator, 1),
        "metodo": do_metodo,
    }


def _ids_do_metodo() -> set:
    """Os alimentos que o treinador usa, para eles aparecerem marcados na lista.

    Import local: `metodo_do_treinador` e importado por `nutrition_engine`, e um import no
    topo daqui reabriria um caminho circular quando este modulo for carregado cedo.
    """
    from metodo_do_treinador import FAMILIAS_DO_METODO
    return {fid for ids in FAMILIAS_DO_METODO.values() for fid in ids}


def espacos_da_refeicao(nome_da_refeicao: str, perfil: Dict[str, Any],
                        escolhidos: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Os espacos daquela refeicao, cada um com o que pode entrar ali.

    `escolhidos` marca o que ja foi selecionado, para a tela nao precisar cruzar as duas
    listas sozinha e correr o risco de discordar do servidor sobre o que esta escolhido.
    """
    tipo = _infer_meal_type(nome_da_refeicao)
    template = MEAL_TEMPLATES.get(tipo) or MEAL_TEMPLATES["lunch"]
    do_metodo = _ids_do_metodo()
    ja = set(escolhidos or [])

    por_papel: Dict[str, Dict[str, Any]] = {}
    for componente in template:
        papel = componente.get("role")
        ids = _candidatos(componente, perfil)
        if not ids:
            # Espaco sem nenhuma opcao viavel para esta pessoa nao entra na tela. Mostrar um
            # espaco vazio e obrigatorio deixaria ela travada sem entender por que.
            continue
        if papel in por_papel:
            # O mesmo papel pode aparecer duas vezes no template (cutting repete vegetal).
            # Na tela isso e um espaco so, com a uniao das opcoes.
            por_papel[papel]["_ids"].update(ids)
            continue
        rotulo, explicacao = ROTULOS.get(papel, (papel, ""))
        por_papel[papel] = {
            "papel": papel, "rotulo": rotulo, "explicacao": explicacao,
            "obrigatorio": bool(componente.get("required")),
            "_ids": set(ids),
        }

    # Qual espaco ficou com cada alimento ja escolhido. Precisa ser decidido ANTES de montar
    # as listas: "Proteina" e "Proteina extra" oferecem os mesmos alimentos, e sem isto a
    # pessoa veria o ovo que ela acabou de escolher disponivel de novo no espaco seguinte.
    dono = {}
    for papel in ORDEM:
        espaco = por_papel.get(papel)
        if not espaco:
            continue
        for fid in sorted(espaco["_ids"]):
            if fid in ja and fid not in dono.values():
                dono[papel] = fid
                break

    saida = []
    for papel in ORDEM:
        espaco = por_papel.get(papel)
        if not espaco:
            continue
        meu = dono.get(papel)
        tomados = {f for p, f in dono.items() if p != papel}
        ids = sorted(espaco.pop("_ids") - tomados,
                     key=lambda f: (f not in do_metodo, FOOD_INDEX.get(f, {}).get("name", f)))
        espaco["alimentos"] = [_cartao_do_alimento(f, f in do_metodo) for f in ids]
        espaco["escolhido"] = meu
        saida.append(espaco)
    return saida


def falta_escolher(espacos: List[Dict[str, Any]]) -> List[str]:
    """Os rotulos dos espacos obrigatorios ainda vazios.

    Existe para a tela poder dizer O QUE falta, em vez de so desabilitar o botao de
    confirmar e deixar a pessoa procurando o que ela esqueceu.
    """
    return [e["rotulo"] for e in espacos if e.get("obrigatorio") and not e.get("escolhido")]

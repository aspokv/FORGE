# -*- coding: utf-8 -*-
"""Refeições do jeito do atleta: excluir, criar e montar cada refeição do plano (Elite).

Por que existe
--------------
Em "Suas refeições" o atleta podia acrescentar uma refeição e trocar um alimento por vez,
sempre com o motor decidindo as gramas. Não podia EXCLUIR uma refeição, nem montar uma do
zero com o que quisesse. O pedido veio assim: "quero excluir café da manhã e almoço,
adicionar de novo e botar o que eu quero". Livre arbítrio, para quem assina o Elite.

O que cada ação faz, e o que ela não faz
----------------------------------------
Excluir tira a refeição, e só ela. As outras NÃO crescem para cobrir o buraco: quem exclui
está redesenhando o dia, e o motor redistribuir a caloria por conta própria desfaria a
decisão que a pessoa acabou de tomar.

Criar e editar gravam exatamente os alimentos e as gramas escolhidos. O motor não
redimensiona nada — é a diferença entre "Montar refeição por refeição", onde o método
propõe, e esta tela, onde a pessoa decide.

As metas seguem a natureza do plano. Numa dieta importada a meta É o que a dieta entrega
(foi assim que ela foi ativada), então a meta acompanha o plano novo. Num plano gerado a
meta vem do questionário — é a necessidade do atleta, e ela não muda porque o cardápio
mudou. A diferença fica visível na tela, que é onde ela deve ficar.

Os registros de hoje acompanham a refeição
------------------------------------------
"Concluir", "Pular" e "Registrar o que comi" são gravados pelo ÍNDICE da refeição no dia.
Excluir a primeira refeição faz a segunda virar a primeira; sem mover os registros, o
almoço concluído apareceria como café da manhã concluído. `mapa_ao_excluir` e
`mapa_ao_inserir` dizem para onde cada registro vai. Só o dia de hoje é movido: os dias
passados registram o que aconteceu, e reescrevê-los seria mudar a história.
"""
from typing import Any, Dict, List, Optional, Tuple

MAXIMO_DE_REFEICOES = 6
MAXIMO_DE_ITENS = 12
MACROS = ("kcal", "protein_g", "carbs_g", "fat_g")


def e_livre(refeicao: Dict[str, Any]) -> bool:
    """Refeição que a pessoa montou, ou que tem alimento pesado por ela.

    Nenhum redimensionamento automático pode tocar nessas: o número ali foi decidido por
    alguém, e não calculado.
    """
    return bool(refeicao.get("livre")) or any(
        item.get("manual") for item in (refeicao.get("foods") or []))


def montar_itens(itens: List[Tuple[str, float]], catalogo_motor: Dict[str, Any],
                 catalogo_diario: Dict[str, Any], build_food_item) -> List[Dict[str, Any]]:
    """Os alimentos da refeição, no formato que o plano já usa.

    Alimento do motor sai por `build_food_item`, igual ao plano gerado (com "2 ovos" e o
    resto da exibição). Alimento que só existe no diário sai como item manual, que é o
    formato que a montagem por refeição já grava para eles. Levanta ValueError com frase
    de tela quando um alimento não existe.
    """
    alimentos = []
    for food_id, gramas in itens:
        gramas = round(float(gramas), 1)
        if food_id in catalogo_motor:
            alimentos.append(build_food_item(food_id, gramas))
        elif food_id in catalogo_diario:
            alimentos.append({"food_id": food_id, "grams": gramas,
                              "food": catalogo_diario[food_id], "manual": True})
        else:
            raise ValueError("Um dos alimentos não está no catálogo. Busque de novo e escolha da lista.")
    return alimentos


def macros_dos_itens(alimentos: List[Dict[str, Any]], catalogo_diario: Dict[str, Any]) -> Dict[str, float]:
    """O que os alimentos entregam, pela grama de cada um.

    Usa o catálogo do diário, que contém o do motor e também os alimentos que só o diário
    conhece. A soma do motor (`sum_plan_totals`) só enxerga os 63 dele, e contaria zero
    para um item manual — o dia pareceria menor do que o prato.
    """
    total = {m: 0.0 for m in MACROS}
    for item in alimentos:
        base = catalogo_diario.get(item.get("food_id")) or item.get("food") or {}
        fator = float(item.get("grams") or 0) / max(1.0, float(base.get("grams") or 100))
        for m in MACROS:
            total[m] += float(base.get(m) or 0) * fator
    return {m: round(v, 1) for m, v in total.items()}


def refeicao_livre(nome: str, alimentos: List[Dict[str, Any]],
                   catalogo_diario: Dict[str, Any]) -> Dict[str, Any]:
    """A refeição montada pela pessoa. O alvo dela é o que ela entrega, como numa dieta
    trazida pronta — não existe "meta da refeição" que a pessoa não escolheu."""
    totais = macros_dos_itens(alimentos, catalogo_diario)
    return {
        "name": nome.strip(),
        "foods": alimentos,
        "target_cal": round(totais["kcal"]),
        "target_protein": round(totais["protein_g"]),
        "target_fat": round(totais["fat_g"], 1),
        "archetype_id": None,
        "coherence_score": None,
        "livre": True,
    }


def totais_do_plano(refeicoes: List[Dict[str, Any]], catalogo_diario: Dict[str, Any]) -> Dict[str, float]:
    total = {m: 0.0 for m in MACROS}
    for refeicao in refeicoes:
        parcial = macros_dos_itens(refeicao.get("foods") or [], catalogo_diario)
        for m in MACROS:
            total[m] += parcial[m]
    return {m: round(v, 1) for m, v in total.items()}


def mapa_ao_excluir(indice: int, quantas: int) -> Dict[int, Optional[int]]:
    """Para onde vai o registro de cada refeição quando a de `indice` sai.

    A excluída vai para None (o registro dela sai junto); as depois dela sobem uma
    posição; as antes ficam onde estão e nem aparecem no mapa.
    """
    mapa: Dict[int, Optional[int]] = {indice: None}
    for antigo in range(indice + 1, quantas):
        mapa[antigo] = antigo - 1
    return mapa


def mapa_ao_inserir(posicao: int, quantas: int) -> Dict[int, int]:
    """Para onde vai o registro de cada refeição quando uma nova entra em `posicao`."""
    return {antigo: antigo + 1 for antigo in range(posicao, quantas)}


def ordem_dos_movimentos(mapa: Dict[int, Optional[int]]) -> List[Tuple[int, Optional[int]]]:
    """A ordem que nunca sobrescreve um registro que ainda não saiu do lugar.

    Descendo (exclusão), vai do menor para o maior: a posição de destino já foi esvaziada.
    Subindo (inserção), vai do maior para o menor, pelo mesmo motivo. As remoções vêm
    primeiro porque liberam a vaga que a primeira descida vai ocupar.
    """
    remocoes = [(a, n) for a, n in mapa.items() if n is None]
    descidas = sorted(((a, n) for a, n in mapa.items() if n is not None and n < a))
    subidas = sorted(((a, n) for a, n in mapa.items() if n is not None and n > a), reverse=True)
    return remocoes + descidas + subidas

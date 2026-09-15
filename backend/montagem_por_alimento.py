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


# ── Busca livre, para quem ja sabe o que quer ───────────────────────────────────────────
#
# A lista por funcao resolve para a maioria. Quem treina ha anos sabe o que vai comer e nao
# quer rolar cinco espacos para achar. Para essa pessoa existe a busca.
#
# Uma diferenca importante entre os dois catalogos, e ela decide como o alimento entra:
#
#   - os 62 alimentos do motor de plano tem papel e limite de porcao. O motor DIMENSIONA
#     eles: a pessoa escolhe, e a grama sai da conta da refeicao;
#   - os outros 234 existem so no diario. Tem macro, e nao tem papel nem limite. O motor
#     nao tem como saber se aquilo e a proteina que ancora o prato ou um acompanhamento, e
#     muito menos qual porcao e razoavel. Entao a PESSOA diz a grama.
#
# Nao inventamos papel nem limite para os 234. Chutar "porcao confortavel" de um alimento
# que ninguem classificou seria o motor afirmando com confianca algo que ele nao sabe.

from text_match import normalize, token_score, token_set  # noqa: E402


def _chave_do_nome(nome: str) -> str:
    """Identidade de um alimento pelo nome, para achar o mesmo item escrito de dois jeitos.

    Sem acento, sem pontuacao e com as palavras ordenadas: "Batata-doce cozida" e "Batata
    doce cozida" caem na mesma chave, e "Arroz branco" nao se confunde com "Arroz integral".
    """
    texto = normalize(nome or "")
    return " ".join(sorted(p for p in texto.split() if p))


def _macros_por_100(alimento: Dict[str, Any]) -> Dict[str, Any]:
    base = max(1, alimento.get("grams", 100))
    fator = 100.0 / base
    return {
        "kcal_por_100g": round((alimento.get("kcal", 0) or 0) * fator),
        "protein_por_100g": round((alimento.get("protein_g", 0) or 0) * fator, 1),
        "carb_por_100g": round((alimento.get("carbs_g", 0) or 0) * fator, 1),
        "fat_por_100g": round((alimento.get("fat_g", 0) or 0) * fator, 1),
    }


def _distancia(a: str, b: str, teto: int) -> int:
    """Damerau-Levenshtein com corte: troca de letras VIZINHAS custa 1, e nao 2.

    A diferenca importa para o caso real: "abulmina" e "albumina" diferem por uma
    transposicao. Em Levenshtein puro isso custa 2 e cai fora do teto; aqui custa 1 e a
    busca acha. O corte existe para nao gastar tempo comparando palavras obviamente
    diferentes num catalogo de quase trezentos itens.
    """
    if abs(len(a) - len(b)) > teto:
        return teto + 1
    anterior_anterior: List[int] = []
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            atual[j] = min(anterior[j] + 1, atual[j - 1] + 1,
                           anterior[j - 1] + (ca != cb))
            if (i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb):
                atual[j] = min(atual[j], anterior_anterior[j - 2] + 1)
        if min(atual) > teto:
            return teto + 1
        anterior_anterior, anterior = anterior, atual
    return anterior[-1]


def _casa_palavra(palavra: str, palavras_do_texto: List[str]) -> bool:
    """Uma palavra digitada casa alguma palavra do texto, a menos de um ou dois erros.

    Palavra a palavra, e nao a frase inteira: "abulmina" contra "Albumina (clara de ovo
    desidratada)" daria uma distancia enorme comparando as frases completas.
    """
    if len(palavra) < 4:
        # Palavra curta demais: um erro de digitacao nela e metade da palavra, e a busca
        # comecaria a casar qualquer coisa. Prefixo ainda vale.
        return any(p.startswith(palavra) for p in palavras_do_texto)
    teto = 1 if len(palavra) <= 5 else 2
    return any(_distancia(palavra, p, teto) <= teto
               for p in palavras_do_texto if abs(len(p) - len(palavra)) <= teto)


def _quase_igual(termo: str, texto: str) -> bool:
    """TODAS as palavras digitadas casam alguma palavra do texto.

    Todas, e nao alguma: "batata doce" tem de achar batata doce, e nao trazer junto toda
    batata do catalogo so porque a primeira palavra bateu.
    """
    palavras = termo.split()
    if not palavras:
        return False
    do_texto = texto.split()
    return all(_casa_palavra(p, do_texto) for p in palavras)


def buscar_para_montagem(consulta: str, perfil: Dict[str, Any],
                         limite: int = 20) -> List[Dict[str, Any]]:
    """Alimentos dos dois catalogos que casam com o texto digitado.

    Tolera erro de digitacao de verdade, e nao so por palavra inteira: "abulmina" acha
    albumina. Quem digita de pe na cozinha troca letra de lugar, e esse caso exato foi o que
    o atleta reclamou quando a busca do diario nao achava a albumina dele.

    A restricao alimentar vale aqui tambem: nao adianta esconder o leite da lista por funcao
    e entregar ele na busca.
    """
    from food_diary import DIARY_FOODS

    termo = normalize(consulta or "")
    if len(termo) < 2:
        return []
    alvo = token_set(consulta)
    do_metodo = _ids_do_metodo()

    achados = []
    for fid, alimento in DIARY_FOODS.items():
        nome = alimento.get("name") or fid
        texto = " ".join([nome] + list(alimento.get("aliases") or []))
        normalizado = normalize(texto)
        if termo in normalizado:
            pontos = 2.0
        elif _quase_igual(termo, normalizado):
            pontos = 1.0
        else:
            pontos = token_score(token_set(texto), alvo)
            if pontos < 0.5:
                continue

        dimensionavel = fid in FOOD_INDEX
        if dimensionavel and not _food_compatible(FOOD_INDEX[fid], perfil, set()):
            continue
        # O alimento so do diario nao passa pelo filtro do motor porque nao tem categoria
        # nem id conhecido pelas listas de alergia. O que da para checar, checa-se.
        if not dimensionavel and fid in set(perfil.get("avoid_foods") or []):
            continue

        achados.append({
            "food_id": fid, "name": nome,
            "dimensionavel": dimensionavel,
            "metodo": fid in do_metodo,
            "_pontos": pontos,
            **_macros_por_100(alimento),
        })

    achados.sort(key=lambda a: (-a["_pontos"], not a["dimensionavel"], a["name"]))

    # O mesmo alimento existe duas vezes no catalogo em dois casos conhecidos (batata-doce e
    # castanha-do-para): um registro no motor de plano e outro so no diario, com macro
    # ligeiramente diferente. Na busca isso aparece como duas linhas iguais, e a pessoa nao
    # tem como saber qual escolher.
    #
    # A desduplicacao e feita AQUI, e nao apagando um dos ids: alguem pode ter o id do
    # diario gravado no historico dele, e remover o alimento apagaria o registro de uma
    # refeicao que a pessoa de fato comeu. O que fica e o do motor, porque ele dimensiona
    # sozinho e o outro obrigaria a pessoa a pesar.
    vistos = set()
    unicos = []
    for a in achados:
        chave = _chave_do_nome(a["name"])
        if chave in vistos:
            continue
        vistos.add(chave)
        a.pop("_pontos", None)
        unicos.append(a)
    return unicos[:limite]

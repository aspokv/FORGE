# -*- coding: utf-8 -*-
"""Carboidrato concentrado no dia que treina o ponto fraco.

A ideia veio do atleta: "meu dia prioritario e peito e braco, que e meu ponto fraco, entao
bota mais carboidrato nesse dia". Faz sentido fisiologico — carboidrato e o que sustenta
volume e intensidade — e o FORGE e um dos poucos lugares que consegue fazer isso sozinho,
porque sabe qual sessao treina qual musculo E sabe a meta alimentar da pessoa.

A REGRA QUE TORNA ISSO SEGURO: a semana soma exatamente o mesmo. Nao e comer mais, e comer
no dia certo. Se os dias prioritarios simplesmente ganhassem carboidrato a mais, quem esta
em corte entraria num superavit acidental sem pedir — e o pior tipo de defeito e o que
engorda a pessoa em silencio. Por isso os pesos sao NORMALIZADOS: o que sobe num dia sai de
outro, e o total fecha igual ao que o motor ja calculou.

Proteina nao cicla. Ela sustenta massa magra todo dia, inclusive no descanso, e mexer nela
por causa do treino seria trocar o que funciona por uma ideia bonita. Gordura tambem fica
fixa: ela carrega hormonio e vitamina, nao energia de sessao.
"""
import unicodedata
from typing import Any, Dict, List, Optional

# Quanto de carboidrato cada tipo de dia PEDE, antes de normalizar. Sao pesos relativos, nao
# multiplicadores finais: a normalizacao depois ajusta todos para a semana fechar igual.
PESO_PRIORITARIO = 1.25
PESO_TREINO = 1.00
PESO_DESCANSO = 0.70

# Limites depois da normalizacao. Sem eles, uma semana com um unico dia de treino jogaria
# quase todo o carboidrato nele, e a pessoa passaria seis dias sem energia para viver.
MINIMO_DO_DIA = 0.55
MAXIMO_DO_DIA = 1.55

DIAS_DA_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", str(texto or "").lower()).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.split())


def dia_prioritario(foco_da_sessao, prioridades) -> bool:
    """A sessao treina algum musculo que a pessoa marcou como ponto fraco?

    O cruzamento e exato porque os dois lados usam o MESMO vocabulario: o perfil oferece
    "Peitoral superior", "Dorsais / largura", "Quadriceps", e a sessao declara `focus` com
    esses mesmos nomes. Nada de heuristica ou traducao — verificado no catalogo.
    """
    alvos = {_normalizar(p) for p in (prioridades or []) if p}
    if not alvos:
        return False
    return any(_normalizar(f) in alvos for f in (foco_da_sessao or []))


def classificar_semana(sessoes_por_dia, prioridades) -> List[str]:
    """Classifica os sete dias em prioritario, treino ou descanso.

    `sessoes_por_dia` e uma lista de 7 posicoes, segunda a domingo; cada posicao e a sessao
    daquele dia ou None.
    """
    classes = []
    for sessao in (sessoes_por_dia or [None] * 7)[:7]:
        if not sessao:
            classes.append("descanso")
        elif dia_prioritario(sessao.get("focus"), prioridades):
            classes.append("prioritario")
        else:
            classes.append("treino")
    while len(classes) < 7:
        classes.append("descanso")
    return classes


def _fatores(classes: List[str]) -> List[float]:
    """Os multiplicadores finais de carboidrato, ja normalizados e dentro dos limites.

    A normalizacao e o coracao: divide-se cada peso pela media dos pesos, entao a soma dos
    sete fatores e sempre 7 — e 7 x meta_diaria continua sendo a meta da semana.

    Depois de limitar os extremos a soma sai do lugar, e por isso ela e reequilibrada de
    novo. Duas passagens bastam na pratica; a terceira so mexeria na terceira casa decimal.
    """
    pesos = [{"prioritario": PESO_PRIORITARIO, "treino": PESO_TREINO}.get(c, PESO_DESCANSO)
             for c in classes]
    total = sum(pesos)
    if total <= 0:
        return [1.0] * len(pesos)
    fatores = [p * len(pesos) / total for p in pesos]
    for _ in range(2):
        fatores = [min(MAXIMO_DO_DIA, max(MINIMO_DO_DIA, f)) for f in fatores]
        soma = sum(fatores)
        if soma <= 0:
            return [1.0] * len(fatores)
        fatores = [f * len(fatores) / soma for f in fatores]
    return fatores


def ciclar_semana(alvos: Dict[str, Any], sessoes_por_dia, prioridades,
                  ativo: bool = True) -> Optional[Dict[str, Any]]:
    """As metas de cada dia da semana, com o carboidrato deslocado para o ponto fraco.

    Devolve None quando NAO ha o que ciclar, e esse caminho importa tanto quanto o outro:

      - sem ponto fraco marcado, nao existe "dia prioritario" e inventar um seria decidir
        pela pessoa;
      - sem nenhum dia de treino, ou com todos os dias iguais, ciclar seria mover numero sem
        motivo.

    Quando devolve None a tela usa a meta diaria unica de sempre, que e o comportamento
    atual — entao ninguem perde nada por nao ter configurado prioridade.
    """
    if not ativo:
        return None
    classes = classificar_semana(sessoes_por_dia, prioridades)
    if "prioritario" not in classes:
        return None
    if len(set(classes)) == 1:
        return None

    carbo_base = float(alvos.get("carbs_g") or 0)
    proteina = float(alvos.get("protein_g") or 0)
    gordura = float(alvos.get("fat_g") or 0)
    if carbo_base <= 0:
        return None

    fatores = _fatores(classes)
    dias = []
    for indice, (nome, classe, fator) in enumerate(zip(DIAS_DA_SEMANA, classes, fatores)):
        carbo = round(carbo_base * fator, 1)
        # A caloria do dia e recalculada a partir dos macros, e nao herdada: se ela ficasse
        # fixa enquanto o carboidrato muda, os dois numeros se contradiriam na mesma tela.
        kcal = round(proteina * 4 + carbo * 4 + gordura * 9)
        dias.append({
            "indice": indice,
            "dia": nome,
            "classe": classe,
            "carbs_g": carbo,
            "protein_g": round(proteina, 1),
            "fat_g": round(gordura, 1),
            "goal_calories": kcal,
            "variacao": round(fator - 1, 3),
        })

    return {
        "dias": dias,
        "base": {"carbs_g": round(carbo_base, 1), "protein_g": round(proteina, 1),
                 "fat_g": round(gordura, 1),
                 "goal_calories": round(alvos.get("goal_calories") or 0)},
        "semana": {
            "carbs_g": round(sum(d["carbs_g"] for d in dias), 1),
            "protein_g": round(sum(d["protein_g"] for d in dias), 1),
            "fat_g": round(sum(d["fat_g"] for d in dias), 1),
            "goal_calories": sum(d["goal_calories"] for d in dias),
        },
        "prioridades": list(prioridades or []),
    }


def semana_do_programa(programa: Dict[str, Any]) -> Optional[List[Optional[Dict[str, Any]]]]:
    """Monta os sete dias, de segunda a domingo, a partir do programa de treino.

    O mapa dia-da-sessao -> dia-da-semana vive em `calendar.weekdays` e SO existe quando o
    atleta montou a agenda. Sem ele nao da para saber que dia treina o ponto fraco, e
    chutar seria pior que nao ciclar — devolve None, e o chamador cai na meta unica.
    """
    calendario = (programa or {}).get("calendar") or {}
    mapa = calendario.get("weekdays")
    if not mapa:
        return None
    por_dia: List[Optional[Dict[str, Any]]] = [None] * 7
    for sessao in (programa or {}).get("sessions") or []:
        indice = mapa.get(str(sessao.get("day")))
        if isinstance(indice, int) and 0 <= indice < 7:
            por_dia[indice] = sessao
    return por_dia if any(por_dia) else None


def motivo_de_nao_ciclar(programa: Dict[str, Any], prioridades) -> Optional[str]:
    """Por que a ciclagem nao se aplica, em palavras que a tela pode mostrar.

    Dizer "nao da" sem dizer por que deixa a pessoa sem acao. Cada motivo aqui tem um
    conserto que ela mesma consegue fazer.
    """
    if not (prioridades or []):
        return "Escolha um ponto fraco no seu perfil para o carboidrato se concentrar nele."
    if semana_do_programa(programa) is None:
        return "Monte os dias da semana no seu treino para o carboidrato acompanhar a agenda."
    classes = classificar_semana(semana_do_programa(programa), prioridades)
    if "prioritario" not in classes:
        return "Nenhum treino da sua semana trabalha o ponto fraco que você escolheu."
    if len(set(classes)) == 1:
        return "Sua semana não tem variação entre os dias, então não há o que concentrar."
    return None


def ciclar_por_sessao(alvos: Dict[str, Any], sessoes, dias_de_treino: int,
                      prioridades) -> Optional[Dict[str, Any]]:
    """A ciclagem que vale para TODO atleta, inclusive quem nao tem agenda por dia da semana.

    Descoberta que mudou o desenho: o mapa "segunda = peito" so existe quando o rotulo da
    sessao comeca com o dia da semana, o que acontece em treino colado a mao ("SEGUNDA —
    PUSH") mas nao nos programas que o motor gera ("Upper 1", "Lower 1"). Nesses, o FORGE
    nao amarra sessao a calendario: ele avanca o ponteiro conforme a pessoa conclui.

    Entao a pergunta certa nao e "que dia da semana e hoje", e sim "que sessao vem agora".
    A composicao da semana continua conhecida — quantas sessoes sao prioritarias, quantas
    nao, e quantos dias de descanso sobram — e isso basta para normalizar: a semana fecha no
    mesmo total sem ninguem precisar dizer que treina na terca.

    Devolve o fator de cada CLASSE de dia. Quem consome descobre a classe da sessao de hoje e
    aplica o fator dela.
    """
    total_sessoes = len(sessoes or [])
    if not total_sessoes:
        return None
    treino_por_semana = max(1, min(7, int(dias_de_treino or total_sessoes)))
    prioritarias = sum(1 for s in sessoes if dia_prioritario((s or {}).get("focus"), prioridades))
    if not prioritarias:
        return None

    # A semana tipica: as sessoes que cabem nela, na proporcao em que aparecem na rotacao,
    # mais os dias sem treino.
    fracao_prioritaria = prioritarias / total_sessoes
    dias_prioritarios = fracao_prioritaria * treino_por_semana
    dias_de_outro_treino = treino_por_semana - dias_prioritarios
    dias_de_descanso = 7 - treino_por_semana
    if dias_prioritarios <= 0 or (dias_de_outro_treino <= 0 and dias_de_descanso <= 0):
        return None

    peso_total = (dias_prioritarios * PESO_PRIORITARIO
                  + dias_de_outro_treino * PESO_TREINO
                  + dias_de_descanso * PESO_DESCANSO)
    if peso_total <= 0:
        return None
    escala = 7 / peso_total

    carbo_base = float(alvos.get("carbs_g") or 0)
    proteina = float(alvos.get("protein_g") or 0)
    gordura = float(alvos.get("fat_g") or 0)
    if carbo_base <= 0:
        return None

    def _linha(classe, peso):
        fator = min(MAXIMO_DO_DIA, max(MINIMO_DO_DIA, peso * escala))
        carbo = round(carbo_base * fator, 1)
        return {"classe": classe, "carbs_g": carbo, "protein_g": round(proteina, 1),
                "fat_g": round(gordura, 1),
                "goal_calories": round(proteina * 4 + carbo * 4 + gordura * 9),
                "variacao": round(fator - 1, 3)}

    classes = {"prioritario": _linha("prioritario", PESO_PRIORITARIO),
               "treino": _linha("treino", PESO_TREINO),
               "descanso": _linha("descanso", PESO_DESCANSO)}

    semana_carbo = (dias_prioritarios * classes["prioritario"]["carbs_g"]
                    + dias_de_outro_treino * classes["treino"]["carbs_g"]
                    + dias_de_descanso * classes["descanso"]["carbs_g"])

    return {
        "por_classe": classes,
        "composicao": {"sessoes": total_sessoes, "prioritarias": prioritarias,
                       "treinos_por_semana": treino_por_semana,
                       "dias_de_descanso": dias_de_descanso},
        "base": {"carbs_g": round(carbo_base, 1), "protein_g": round(proteina, 1),
                 "fat_g": round(gordura, 1),
                 "goal_calories": round(alvos.get("goal_calories") or 0)},
        "semana": {"carbs_g": round(semana_carbo, 1),
                   "carbs_g_plano": round(carbo_base * 7, 1)},
        "prioridades": list(prioridades or []),
    }


def classe_da_sessao(sessao, prioridades) -> str:
    """A classe do dia de hoje: sem sessao e descanso, com o ponto fraco e prioritario."""
    if not sessao:
        return "descanso"
    return "prioritario" if dia_prioritario(sessao.get("focus"), prioridades) else "treino"


# Quantos gramas de carboidrato cada 100 g do alimento carrega, ja PRONTO. Serve para
# traduzir "some 143 g de carboidrato" em "cerca de 2 conchas de arroz", que e a unica forma
# de a pessoa agir sem calculadora.
CARBO_POR_100G = {
    "rice-white": 28.1, "rice-brown": 25.8, "potato": 11.9, "sweet-potato": 18.4,
    "pasta": 30.9, "pasta-whole": 28.0, "oats": 66.6, "tapioca": 58.5, "cassava": 30.1,
    "bread-white": 58.6, "bread-whole": 49.9, "couscous": 25.3, "banana": 26.0,
}


def onde_colocar(diferenca_g: float, refeicoes) -> Optional[Dict[str, Any]]:
    """Traduz a diferenca de carboidrato em comida, e diz em que refeicao ela cabe.

    Dizer "hoje sao 582 g de carboidrato" sem dizer ONDE deixa a pessoa parada: ela sabe o
    alvo e nao sabe o movimento. O conselho aqui e deliberadamente simples — acrescente na
    refeicao que ja tem mais carboidrato, que costuma ser a que cerca o treino.

    Escolhe o alimento fonte a partir do PROPRIO plano da pessoa, e nao de uma lista fixa:
    mandar comer arroz para quem montou o plano com tapioca seria conselho de outro app.
    """
    if not diferenca_g or not refeicoes:
        return None

    melhor_refeicao, melhor_item, melhor_carbo = None, None, 0.0
    for refeicao in refeicoes:
        for item in refeicao.get("foods") or []:
            fid = item.get("food_id")
            por_100 = CARBO_POR_100G.get(fid)
            if not por_100:
                continue
            carbo_no_prato = por_100 * float(item.get("grams") or 0) / 100.0
            if carbo_no_prato > melhor_carbo:
                melhor_refeicao, melhor_item, melhor_carbo = refeicao, item, carbo_no_prato
    if not melhor_item:
        return None

    por_100 = CARBO_POR_100G[melhor_item["food_id"]]
    gramas = round(abs(diferenca_g) / por_100 * 100)
    if gramas < 10:
        return None
    return {
        "refeicao": melhor_refeicao.get("name"),
        "alimento": (melhor_item.get("food") or {}).get("name") or melhor_item.get("food_id"),
        "gramas": gramas,
        "acao": "some" if diferenca_g > 0 else "tire",
    }

# -*- coding: utf-8 -*-
"""O metodo do treinador, extraido dos protocolos reais dos alunos dele.

De onde isto vem: 65 protocolos alimentares que o treinador montou a mao para 18 alunos, ao
longo de varias fases de cada um. O que esta aqui nao e teoria de livro — e o padrao que se
repete nos documentos dele, com as razoes que ele mesmo escreveu ao lado de cada escolha.

O QUE O MOTOR DO FORGE JA FAZIA e continua fazendo: calcular meta calorica e macro a partir
do perfil. Este arquivo NAO substitui nada disso. Ele acrescenta a camada que faltava — COMO
distribuir esses macros ao longo do dia, e o que muda entre um dia low e um dia high.

A diferenca pratica: o motor sabia dizer "2.871 kcal com 440 g de carboidrato". O metodo diz
que esse carboidrato se concentra em volta do treino, que no dia low o pos-treino vai SEM
amido, e que a gordura do dia low fica num horario so.

Nenhum dado de aluno entra aqui. Nomes, fotos e medidas ficaram fora; o que foi extraido e a
estrutura, que e o que se aplica a qualquer pessoa.
"""
from typing import Any, Dict, List, Optional

# ── A arquitetura de refeicoes ──────────────────────────────────────────────────────────
#
# O treinador nomeia refeicao pela FUNCAO, nao pela hora: "pre-treino", "pos-treino". Isso
# importa porque quem treina as 6h e quem treina as 19h recebem a mesma estrutura, e nao um
# "cafe da manha" que nao faz sentido para o segundo.

PAPEIS = {
    "pre_treino": {
        "nome": "Pré-treino",
        "porque": "Carboidrato rápido e proteína logo antes da sessão, sem fibra e sem gordura "
                  "para não pesar o estômago.",
        "fontes_carbo": ["banana", "rice-flour", "oats", "rice-cream-whey"],
        "fontes_proteina": ["diary-supp-whey", "diary-supp-whey-isolate"],
        "sem": ["gordura", "fibra_alta"],
    },
    "pos_treino": {
        "nome": "Pós-treino",
        "porque": "Proteína inteira com amido para repor o que a sessão gastou. É a refeição "
                  "que mais muda entre um dia low e um dia high.",
        "fontes_carbo": ["potato", "sweet-potato", "rice-white"],
        "fontes_proteina": ["chicken-breast", "beef-grill", "tilapia"],
        "acompanha": ["broccoli", "zucchini", "diary-veg-cauliflower"],
    },
    "almoco": {
        "nome": "Almoço",
        "porque": "A refeição maior do dia, e o único horário com gordura nos dias low.",
        "fontes_carbo": ["rice-white", "potato", "beans-carioca"],
        "fontes_proteina": ["beef-grill", "chicken-breast", "tilapia"],
        "fontes_gordura": ["olive-oil"],
        "acompanha": ["lettuce", "tomato", "broccoli"],
    },
    "lanche": {
        "nome": "Lanche da tarde",
        "porque": "Mingau de aveia com whey: prático, e o carboidrato aqui acompanha o dia.",
        "fontes_carbo": ["oats"],
        "fontes_proteina": ["diary-supp-whey", "yogurt-natural", "cheese-cottage"],
    },
    "lanche_final": {
        "nome": "Lanche final da tarde",
        "porque": "Fruta com proteína magra, para chegar ao jantar sem fome acumulada.",
        "fontes_carbo": ["apple", "orange", "diary-fruit-pineapple"],
        "fontes_proteina": ["egg-whites", "eggs-whole", "cheese-cottage"],
    },
    "jantar": {
        "nome": "Jantar",
        "porque": "Proteína e vegetais. O amido aqui só aparece em dia high ou em fase de ganho.",
        "fontes_carbo": ["sweet-potato", "potato"],
        "fontes_proteina": ["chicken-breast", "beef-grill", "tilapia"],
        "acompanha": ["broccoli", "zucchini", "green-beans"],
    },
    "ceia": {
        "nome": "Ceia",
        "porque": "Opcional, e sempre proteína lenta: claras, ovo ou cottage.",
        "fontes_proteina": ["egg-whites", "eggs-whole", "cheese-cottage"],
    },
}

ORDEM_DO_DIA = ["pre_treino", "pos_treino", "almoco", "lanche", "lanche_final", "jantar", "ceia"]


# ── Como o carboidrato se distribui ─────────────────────────────────────────────────────
#
# Medido nos protocolos: a fracao do carboidrato do dia que cai em cada refeicao. O dia low e
# o dia high nao diferem so no total — eles diferem no FORMATO. No low o carboidrato some do
# pos-treino e do almoco e sobra o que cerca o treino; no high ele volta para as duas.

DISTRIBUICAO = {
    "low": {
        "pre_treino": 0.30,      # banana pequena + whey
        "pos_treino": 0.00,      # "Sem batata aqui" — escrito assim no protocolo
        "almoco": 0.00,          # so vegetais e salada
        "lanche": 0.30,          # 20 g de aveia
        "lanche_final": 0.30,    # uma fruta
        "jantar": 0.10,
        "ceia": 0.00,
    },
    "high": {
        "pre_treino": 0.30,      # banana maior + aveia
        "pos_treino": 0.22,      # a batata volta
        "almoco": 0.22,          # arroz volta
        "lanche": 0.16,
        "lanche_final": 0.05,
        "jantar": 0.05,
        "ceia": 0.00,
    },
    # Fase de ganho: o carboidrato entra em todas as refeicoes e em volume.
    "ganho": {
        "pre_treino": 0.22,
        "pos_treino": 0.18,
        "almoco": 0.26,
        "lanche": 0.14,
        "lanche_final": 0.08,
        "jantar": 0.12,
        "ceia": 0.00,
    },
}


# ── Os protocolos de ciclagem, com os nomes que ele usa ─────────────────────────────────
#
# Os nomes sao dele, tirados dos proprios arquivos: "3 Low 1 High", "4LOW1HIGH", "6LOW1HIGH".
# A escolha entre eles e o quanto a pessoa aguenta de restricao antes do dia de recarga.

PROTOCOLOS = {
    "3low1high": {"nome": "3 low, 1 high", "low": 3, "high": 1,
                  "para_quem": "Corte com recarga frequente. O mais usado."},
    "4low1high": {"nome": "4 low, 1 high", "low": 4, "high": 1,
                  "para_quem": "Corte mais agressivo, para quem responde bem à restrição."},
    "6low1high": {"nome": "6 low, 1 high", "low": 6, "high": 1,
                  "para_quem": "Fase final de corte ou pré-competição."},
    "saturacao": {"nome": "Saturação", "low": 0, "high": 1,
                  "para_quem": "Recarga de glicogênio em bloco, antes de avaliação ou evento."},
}


# ── As regras, com a razao que ele escreveu ─────────────────────────────────────────────
#
# Cada uma saiu de uma observacao literal nos protocolos. A razao importa tanto quanto a
# regra: e ela que faz o atleta obedecer em vez de achar que o aplicativo errou.

REGRAS = [
    {"chave": "pesagem", "regra": "Todos os alimentos são pesados já prontos.",
     "porque": "É como a tabela nutricional mede. O peso de compra e o peso de panela saem "
               "disso por conversão."},
    {"chave": "gordura_low", "regra": "Nos dias low, a gordura fica em um único horário.",
     "porque": "Concentrar o azeite no almoço deixa as outras refeições mais leves e libera "
               "caloria para a proteína."},
    {"chave": "sem_amido_pos_low", "regra": "No dia low, o pós-treino vai sem amido.",
     "porque": "Escrito no protocolo como 'Sem batata aqui'. A proteína e os legumes bastam "
               "quando o objetivo do dia é esvaziar o glicogênio."},
    {"chave": "folhas_livres", "regra": "Salada de folhas verdes é à vontade.",
     "porque": "Volume e saciedade praticamente sem caloria. Não entra na conta."},
    {"chave": "canela", "regra": "Canela a gosto no pré-treino e no mingau.",
     "porque": "Ajuda na sensibilidade à insulina — observação dele, escrita no protocolo."},
    {"chave": "citrico_digestao", "regra": "Uma fruta cítrica nas refeições grandes.",
     "porque": "Laranja ou abacaxi ajudam na digestão quando o volume de comida é alto."},
    {"chave": "batata_volume", "regra": "Em fase de ganho, batata inglesa antes da doce.",
     "porque": "É mais fácil de comer em volume que a batata-doce — razão dele, literal."},
    {"chave": "agua", "regra": "Mínimo de 4 litros de água por dia.",
     "porque": "Aparece em todos os protocolos, independente da fase."},
    {"chave": "substituicao", "regra": "Toda fonte tem alternativa dentro do mesmo papel.",
     "porque": "Os protocolos sempre trazem 'ou': frango ou patinho, batata-doce ou inglesa. "
               "Plano que não aceita troca é plano que a pessoa abandona."},
]


def distribuicao_do_dia(tipo: str) -> Dict[str, float]:
    """A fracao do carboidrato do dia em cada refeicao, pelo tipo de dia."""
    return dict(DISTRIBUICAO.get(tipo) or DISTRIBUICAO["high"])


def carbo_por_refeicao(carbo_do_dia: float, tipo: str) -> Dict[str, float]:
    """Divide o carboidrato do dia entre as refeicoes, no formato do metodo.

    A soma fecha no total do dia: a distribuicao e normalizada, entao mudar uma fracao nao
    faz o dia inteiro ganhar ou perder carboidrato sem ninguem perceber.
    """
    fracoes = distribuicao_do_dia(tipo)
    total = sum(fracoes.values())
    if total <= 0:
        return {papel: 0.0 for papel in ORDEM_DO_DIA}
    base = float(carbo_do_dia or 0)
    return {papel: round(base * (fracoes.get(papel, 0.0) / total), 1) for papel in ORDEM_DO_DIA}


def regra(chave: str) -> Optional[Dict[str, str]]:
    for r in REGRAS:
        if r["chave"] == chave:
            return r
    return None


def protocolo(chave: str) -> Optional[Dict[str, Any]]:
    return PROTOCOLOS.get(chave)


def ciclo_do_protocolo(chave: str) -> List[str]:
    """A sequencia de dias de um protocolo: ['low','low','low','high'] para o 3 por 1."""
    p = PROTOCOLOS.get(chave)
    if not p:
        return []
    return ["low"] * int(p["low"]) + ["high"] * int(p["high"])


# ── O metodo traduzido nos numeros da pessoa ────────────────────────────────────────────
#
# Ate aqui o arquivo e descritivo: fracoes, fontes e razoes. O que segue transforma isso no
# dia DELA — "pre-treino: 132 g de carboidrato, e as fontes sao estas".
#
# Uma escolha importante de honestidade: os dois formatos abaixo, low e high, sao formatos de
# DIA DE TREINO. Foi assim que eles aparecem nos protocolos. Nao existe aqui um formato de dia
# de descanso, porque ele nao foi escrito — e inventar uma redistribuicao para um dia sem
# treino seria por na boca do treinador uma regra que nao e dele. Em dia de descanso o bloco
# mostra os formatos como referencia e nao aponta nenhum como "o de hoje".

def _nome_de_exibicao(food_id: str) -> str:
    """O nome do alimento como a pessoa le, sem o rodape tecnico do catalogo.

    O import do catalogo e feito AQUI DENTRO, e nao no topo: `nutrition_engine` importa
    este modulo para montar as combinacoes do metodo, e `food_diary` importa
    `nutrition_engine`. Import no topo fecharia o ciclo e quebraria a carga do app.
    """
    from food_diary import DIARY_FOODS
    alimento = DIARY_FOODS.get(food_id)
    if not alimento:
        return food_id
    nome = alimento.get("name") or food_id
    # "Whey Protein — valor medio de mercado" vira "Whey Protein": o rodape existe para a
    # tabela nutricional, e nao para uma lista de opcoes de refeicao.
    for separador in ("—", " - "):
        if separador in nome:
            nome = nome.split(separador)[0]
    return nome.strip()


def _nomes(ids) -> List[str]:
    return [_nome_de_exibicao(f) for f in (ids or [])]


def refeicoes_do_formato(carbo_do_dia: float, tipo: str) -> List[Dict[str, Any]]:
    """As refeicoes do dia, na ordem do metodo, com o carboidrato ja dividido em gramas.

    Refeicao que nao recebe carboidrato NAO some da lista: no dia low o almoco continua
    existindo, so vai sem amido — e e justamente isso que a pessoa precisa ver. Sumir daria a
    entender que ela pula o almoco.
    """
    divisao = carbo_por_refeicao(carbo_do_dia, tipo)
    saida = []
    for papel in ORDEM_DO_DIA:
        dados = PAPEIS[papel]
        gramas = divisao.get(papel, 0.0)
        saida.append({
            "papel": papel,
            "nome": dados["nome"],
            "porque": dados["porque"],
            "carbo_g": round(gramas),
            "sem_carbo": gramas <= 0 and bool(dados.get("fontes_carbo")),
            "carbo": _nomes(dados.get("fontes_carbo")),
            "proteina": _nomes(dados.get("fontes_proteina")),
            "gordura": _nomes(dados.get("fontes_gordura")),
            "acompanha": _nomes(dados.get("acompanha")),
        })
    return saida


# Dia de treino e dia de treino; dia de descanso nao tem formato escrito. A classe vem da
# ciclagem, que ja sabe se hoje treina o ponto fraco, treina normal ou descansa.
_TIPO_POR_CLASSE = {"prioritario": "high", "treino": "low", "descanso": None}


def tipo_do_dia(classe: Optional[str]) -> Optional[str]:
    """Traduz a classe da ciclagem no formato do metodo, ou None quando nao ha formato.

    O dia do ponto fraco e o dia high: e nele que o carboidrato sobe e o amido volta ao
    pos-treino e ao almoco. Os outros dias de treino seguem o formato low, que e o padrao dos
    protocolos. O descanso fica sem formato de proposito — ver a nota no topo desta secao.
    """
    return _TIPO_POR_CLASSE.get(classe or "")


FORMATOS = {
    "low": {"rotulo": "Dia low", "resumo": "Carboidrato em volta do treino. Sem amido no pós-treino e no almoço."},
    "high": {"rotulo": "Dia high", "resumo": "O amido volta ao pós-treino e ao almoço. É o dia de recarga."},
    "ganho": {"rotulo": "Fase de ganho", "resumo": "Carboidrato em todas as refeições, e em volume."},
}


def metodo_do_dia(carbo_low: float, carbo_high: float, classe: Optional[str] = None) -> Dict[str, Any]:
    """O método inteiro pronto para a tela: os dois formatos, qual é o de hoje, e as regras."""
    hoje = tipo_do_dia(classe)
    formatos = {}
    for tipo, carbo in (("low", carbo_low), ("high", carbo_high)):
        formatos[tipo] = {**FORMATOS[tipo], "carbo_g": round(carbo or 0),
                          "refeicoes": refeicoes_do_formato(carbo or 0, tipo)}
    return {"hoje": hoje, "classe": classe, "formatos": formatos,
            "regras": [dict(r) for r in REGRAS],
            "protocolos": [{"chave": c, **p} for c, p in PROTOCOLOS.items()]}


# ── As combinacoes do metodo, para o motor de plano ─────────────────────────────────────
#
# Ate aqui o metodo era DESCRITIVO: o atleta lia a arquitetura do dia e aplicava sozinho.
# O que segue faz o FORGE MONTAR nesse padrao — quando a pessoa monta o plano refeicao por
# refeicao, as opcoes oferecidas sao as combinacoes que o treinador usa, e nao um sorteio
# dentro de todo o catalogo.
#
# Duas notas de fidelidade, porque elas mudam o que o atleta recebe:
#
# 1. O motor de plano tem catalogo PROPRIO (foods.json, 62 alimentos) e menor que o do
#    diario (296). Quatro fontes citadas nos papeis acima so existem no diario:
#    whey, whey isolado, couve-flor e abacaxi. O whey tem equivalente no motor
#    (`whey-protein`) e e usado; couve-flor e abacaxi nao tem, e no lugar deles entram
#    outras fontes DO PROPRIO metodo para o mesmo papel — abobrinha e vagem no lugar da
#    couve-flor, maca e laranja no lugar do abacaxi. Nenhum alimento de fora dele entra.
#
# 2. O metodo nao tem "cafe da manha", porque nomeia refeicao por funcao. O FORGE nomeia a
#    primeira refeicao assim, entao o mingau de aveia com whey — que e o lanche dele —
#    tambem e oferecido no cafe da manha. E a refeicao dele que serve a esse horario.

FAMILIAS_DO_METODO = {
    "METODO_CARBO_PRE": ["oats", "rice-flour", "rice-cream-whey"],
    "METODO_PROTEINA_RAPIDA": ["whey-protein", "rice-cream-whey"],
    "METODO_FRUTA_PRE": ["banana"],
    "METODO_AMIDO_POS": ["potato", "sweet-potato", "rice-white"],
    "METODO_PROTEINA_SOLIDA": ["chicken-breast", "beef-grill", "tilapia"],
    "METODO_LEGUME": ["broccoli", "zucchini", "green-beans"],
    "METODO_SALADA": ["lettuce", "tomato", "broccoli"],
    "METODO_CARBO_ALMOCO": ["rice-white", "potato"],
    "METODO_GORDURA": ["olive-oil"],
    "METODO_AVEIA": ["oats"],
    "METODO_PROTEINA_LANCHE": ["whey-protein", "yogurt-natural", "cheese-cottage"],
    "METODO_FRUTA": ["apple", "orange", "banana"],
    "METODO_PROTEINA_LENTA": ["egg-whites", "eggs-whole", "cheese-cottage"],
    "METODO_AMIDO_JANTAR": ["sweet-potato", "potato"],
}


def _c(role, category, family, required=True):
    return {"role": role, "category": category, "family": family, "required": required}


# `metodo: True` e o que faz estas combinacoes aparecerem ANTES das outras na hora de
# escolher. Nao e um numero maior de pontuacao — e uma preferencia declarada, que se le no
# codigo e que nao se confunde com qualidade nutricional.
COMBOS_DO_METODO = [
    {"id": "metodo_pre_banana", "label": "Pré-treino do método", "metodo": True,
     "meal_types": ["pre_workout"], "components": [
         _c("fruit", "FRUIT", "METODO_FRUTA_PRE"),
         _c("primary_protein", "PROTEIN", "METODO_PROTEINA_RAPIDA")]},

    # O rotulo nao nomeia alimento: a familia aceita creme de arroz, farinha de arroz E
    # aveia, e a tela chegou a mostrar "Creme de arroz do metodo" com aveia em flocos. O que
    # distingue este combo do outro pre-treino e a ausencia da fruta, e e isso que o nome diz.
    {"id": "metodo_pre_creme", "label": "Pré-treino sem fruta do método", "metodo": True,
     "meal_types": ["pre_workout"], "components": [
         _c("primary_carb", "CARBOHYDRATE", "METODO_CARBO_PRE"),
         _c("primary_protein", "PROTEIN", "METODO_PROTEINA_RAPIDA")]},

    {"id": "metodo_pos_treino", "label": "Pós-treino do método", "metodo": True,
     "meal_types": ["post_workout"], "components": [
         _c("primary_protein", "PROTEIN", "METODO_PROTEINA_SOLIDA"),
         _c("primary_carb", "CARBOHYDRATE", "METODO_AMIDO_POS"),
         _c("vegetable", "VEGETABLE", "METODO_LEGUME")]},

    {"id": "metodo_almoco", "label": "Almoço do método", "metodo": True,
     "meal_types": ["lunch"], "components": [
         _c("primary_protein", "PROTEIN", "METODO_PROTEINA_SOLIDA"),
         _c("primary_carb", "CARBOHYDRATE", "METODO_CARBO_ALMOCO"),
         _c("vegetable", "VEGETABLE", "METODO_SALADA"),
         # A gordura do dia low fica num horario so, e o horario e este.
         _c("fat_source", "FAT", "METODO_GORDURA")]},

    {"id": "metodo_lanche_final", "label": "Lanche final do método", "metodo": True,
     "meal_types": ["snack"], "components": [
         _c("fruit", "FRUIT", "METODO_FRUTA"),
         _c("primary_protein", "PROTEIN", "METODO_PROTEINA_LENTA")]},

    {"id": "metodo_jantar", "label": "Jantar do método", "metodo": True,
     "meal_types": ["dinner"], "components": [
         _c("primary_protein", "PROTEIN", "METODO_PROTEINA_SOLIDA"),
         _c("primary_carb", "CARBOHYDRATE", "METODO_AMIDO_JANTAR"),
         _c("vegetable", "VEGETABLE", "METODO_LEGUME")]},
]


# Combinacoes que JA estavam no motor e ja sao do metodo dele: os MEAL_COMBOS nasceram
# observando os protocolos. Elas nao sao duplicadas aqui — sao apenas MARCADAS, para
# aparecerem na frente junto com as demais. Duplicar criaria duas combinacoes caindo no
# mesmo prato, e a desduplicacao apagaria uma das duas em silencio.
IDS_JA_DO_METODO = ["forge_oats_whey_banana"]

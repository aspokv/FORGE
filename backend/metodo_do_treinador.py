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

from food_diary import DIARY_FOODS  # noqa: E402


def _nome_de_exibicao(food_id: str) -> str:
    """O nome do alimento como a pessoa le, sem o rodape tecnico do catalogo."""
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

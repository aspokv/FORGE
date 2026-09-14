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

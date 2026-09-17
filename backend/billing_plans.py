"""Catalogo central de planos e matriz de capacidades do FORGE.

Fonte de verdade unica: preco, moeda, periodicidade, id do plano no Mercado Pago e o
que cada plano libera moram AQUI, no backend. O navegador envia apenas o CODIGO do
plano — nunca preco, valor ou preapproval_plan_id — e o servidor resolve o resto nesta
allow-list. Aceitar qualquer um desses campos vindos do cliente seria permitir que
alguem assinasse o Elite pagando o preco do Essencial.

Precos em centavos de proposito: float em dinheiro acumula erro de arredondamento, e a
comparacao com o valor que o Mercado Pago devolve precisa ser exata.
"""
import os
from typing import Any, Dict, List, Optional

MOEDA = "BRL"
FREQUENCIA = 1
TIPO_DE_FREQUENCIA = "months"

# ── Capacidades ──────────────────────────────────────────────────────────────────────
# Um nome por recurso protegido. As rotas perguntam por capacidade, nunca por plano:
# assim um plano novo nao exige caçar condicionais espalhadas pelo codigo.
TREINO = "workout"
PROGRESSAO = "progression"
HISTORICO = "history"
SUBSTITUICAO_DE_EXERCICIO = "exercise_substitution"
ALIMENTACAO = "nutrition"
SUBSTITUICAO_DE_ALIMENTO = "food_substitution"
REGENERAR_ALIMENTACAO = "nutrition_regenerate"
INTENSIDADES_PADRAO = "standard_intensities"
PROTOCOLOS_AGRESSIVOS = "aggressive_protocols"
ANALISES_AVANCADAS = "advanced_analytics"
VARIACOES_DE_TREINO = "workout_variations"

CAPACIDADES_ESSENCIAL = {TREINO, PROGRESSAO, HISTORICO, SUBSTITUICAO_DE_EXERCICIO}
# PROTOCOLOS_AGRESSIVOS era exclusivo do Elite e passou para o Pro por decisao do dono do
# produto. Ninguem perde nada com a mudanca: Elite continua contendo tudo do Pro, entao
# quem ja assinava o Elite mantem exatamente o mesmo acesso.
CAPACIDADES_PRO = CAPACIDADES_ESSENCIAL | {
    ALIMENTACAO, SUBSTITUICAO_DE_ALIMENTO, REGENERAR_ALIMENTACAO, INTENSIDADES_PADRAO,
    VARIACOES_DE_TREINO, PROTOCOLOS_AGRESSIVOS}
CAPACIDADES_ELITE = CAPACIDADES_PRO | {ANALISES_AVANCADAS}

ESSENCIAL, PRO, ELITE = "essential", "pro", "elite"

# ── Planos ───────────────────────────────────────────────────────────────────────────
# "recursos" lista o que ESTA disponivel hoje. "em_breve" e separado de proposito: anunciar
# como pronto o que ainda nao existe seria vender o que nao entregamos.
PLANOS: List[Dict[str, Any]] = [
    {
        "code": ESSENCIAL,
        "nome": "FORGE ESSENCIAL",
        "preco_centavos": 3990,
        "ordem": 1,
        "recomendado": False,
        "ativo": True,
        "para_quem": ("Para quem quer um treino personalizado, progressão organizada e "
                      "acompanhamento da evolução."),
        "recursos": [
            "Treino personalizado",
            "Perfil feminino ou masculino",
            "Escolha de regiões prioritárias",
            "Progressão de treino",
            "Histórico de sessões",
            "Substituição de exercícios",
            "Acompanhamento básico",
            "Acesso pelo celular e desktop",
        ],
        "em_breve": [],
        "capacidades": CAPACIDADES_ESSENCIAL,
        "env_plan_id": "MP_ESSENTIAL_PLAN_ID",
    },
    {
        "code": PRO,
        "nome": "FORGE PRO",
        "preco_centavos": 6990,
        "ordem": 2,
        "recomendado": True,
        "ativo": True,
        "para_quem": ("Para quem quer combinar treino e alimentação personalizada para "
                      "acelerar seus resultados."),
        "recursos": [
            "Tudo do FORGE Essencial",
            "Plano alimentar personalizado",
            "Ganho de massa",
            "Emagrecimento",
            "Recomposição corporal",
            "Intensidades: controlada, leve, moderada e agressiva",
            "Modos Agressivo/Atleta",
            "Cutting com protocolo low-carb avançado",
            "Ganho de massa agressivo",
            "Substituições alimentares equivalentes",
            "Whey, carnes, ovos e outras alternativas compatíveis",
            "Regeneração e ajustes do plano",
            "Acompanhamento integrado de treino e alimentação",
        ],
        "em_breve": [],
        "capacidades": CAPACIDADES_PRO,
        "env_plan_id": "MP_PRO_PLAN_ID",
    },
    {
        "code": ELITE,
        "nome": "FORGE ELITE",
        "preco_centavos": 9990,
        "ordem": 3,
        "recomendado": False,
        "ativo": True,
        "para_quem": ("Para atletas e usuários avançados que querem máxima personalização, "
                      "protocolos intensos e controle completo."),
        "recursos": [
            "Tudo do FORGE Pro",
            "Modo de treino avançado e manual",
            "Importação de treino por texto",
            # Saiu de "em_breve" quando o Conselho entrou no ar. Anunciar como pronto o
            # que nao existe seria vender o que nao entregamos, e o inverso tambem custa:
            # deixar em "em breve" o que ja esta no ar esconde o motivo de assinar.
            "O Conselho: toda semana o FORGE lê seus números e decide um ajuste",
            "Previsão semanal conferida: o motor diz se acertou",
            "Maior nível de personalização",
        ],
        # Separado de proposito: sao promessas, nao entregas.
        "em_breve": [
            "Periodização avançada",
            "Acesso prioritário a futuros recursos premium",
        ],
        "capacidades": CAPACIDADES_ELITE,
        "env_plan_id": "MP_ELITE_PLAN_ID",
    },
]

PLANOS_POR_CODIGO: Dict[str, Dict[str, Any]] = {p["code"]: p for p in PLANOS}


def plano_minimo_com(capacidade: str) -> Optional[Dict[str, Any]]:
    """O plano ATIVO mais barato que inclui esta capacidade.

    Existe para que nenhuma mensagem de "faça upgrade" precise citar um plano pelo nome.
    Quando `aggressive_protocols` saiu do Elite para o Pro, toda frase escrita a mao
    passou a mandar a pessoa comprar o plano errado, mais caro, por um recurso que o mais
    barato ja entregava. Perguntar a tabela em vez de repetir o nome evita isso para
    sempre."""
    candidatos = [p for p in PLANOS if p.get("ativo") and capacidade in p["capacidades"]]
    return min(candidatos, key=lambda p: p["preco_centavos"]) if candidatos else None


def plano(code: Optional[str]) -> Optional[Dict[str, Any]]:
    """Plano da allow-list, ou None. Unica porta de entrada para resolver um codigo."""
    if not code:
        return None
    return PLANOS_POR_CODIGO.get(str(code).strip().lower())


def plano_ativo(code: Optional[str]) -> Optional[Dict[str, Any]]:
    p = plano(code)
    return p if p and p.get("ativo") else None


def preco_em_reais(p: Dict[str, Any]) -> float:
    return round(p["preco_centavos"] / 100, 2)


def mp_plan_id(p: Dict[str, Any]) -> Optional[str]:
    """Id do preapproval_plan no Mercado Pago, vindo do ambiente.

    Lido em tempo de chamada e nao no import: o processo pode subir antes das variaveis
    existirem, e os testes precisam trocar isso sem reimportar o modulo."""
    return (os.environ.get(p["env_plan_id"]) or "").strip() or None


def capacidades_do_plano(code: Optional[str]) -> set:
    p = plano(code)
    return set(p["capacidades"]) if p else set()


def catalogo_publico() -> List[Dict[str, Any]]:
    """O que a interface consome. Sem capacidades internas e sem id do Mercado Pago —
    a tela nao precisa disso e expor o id de plano so ajudaria quem quiser forjar."""
    return [
        {
            "code": p["code"],
            "nome": p["nome"],
            "preco": preco_em_reais(p),
            "preco_centavos": p["preco_centavos"],
            "moeda": MOEDA,
            "periodicidade": "mensal",
            "frequencia": FREQUENCIA,
            "tipo_de_frequencia": TIPO_DE_FREQUENCIA,
            "recomendado": p["recomendado"],
            "ordem": p["ordem"],
            "para_quem": p["para_quem"],
            "recursos": list(p["recursos"]),
            "em_breve": list(p["em_breve"]),
            "cobranca": "Cobrança mensal recorrente",
        }
        for p in sorted(PLANOS, key=lambda x: x["ordem"]) if p.get("ativo")
    ]

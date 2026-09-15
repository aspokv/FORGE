# -*- coding: utf-8 -*-
"""Achar, na biblioteca, o programa que melhor serve a este atleta.

Por que isto existe: quando a pessoa troca a regiao prioritaria, o programa GERADO pelo
motor se recalcula sozinho — mas quem esta num programa completo da biblioteca fica com um
retrato fixo, que nao reage. Antes a unica coisa que o FORGE sabia dizer era "escolha outro
programa na Biblioteca", e a pessoa ficava olhando 23 programas sem saber qual.

O que este modulo faz e responder a pergunta que ela tem: dados os DIAS que ela treina, o
PERFIL dela e a REGIAO que ela quer priorizar, qual dos programas cadastrados entrega mais
daquilo. A resposta sai com o porque, e nao so com o nome.

Como a nota e formada, em ordem de peso:

  1. DIAS. Um programa de seis dias para quem treina tres nao serve, por melhor que seja o
     resto. Diferenca de um dia ainda passa, com desconto; de dois em diante e eliminado.
  2. PRIORIDADE. A fracao das series do microciclo que cai na regiao escolhida, pesada pela
     ordem: a primeira prioridade vale mais que a segunda. Conta por SERIE e nao por
     exercicio, porque quatro series de um movimento treinam mais que uma de quatro.
  3. PERFIL. Programa marcado para um sexo nao e oferecido ao outro.
  4. NIVEL e SEGURANCA. Volume avancado e recuperacao excepcional so entram para quem
     declarou experiencia compativel.

Nada aqui cria sessao nem exercicio: o modulo so ESCOLHE entre o que ja esta cadastrado.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from muscles import to_internal

_RAIZ = Path(__file__).parent
with open(_RAIZ / "exercises.json", encoding="utf-8") as _f:
    _EXERCICIOS = {e["id"]: e for e in json.load(_f)}

# Diferenca de dias tolerada. Um dia a mais ou a menos a pessoa ajusta; dois ja e outro
# programa, com outra logica de recuperacao.
DIFERENCA_MAXIMA_DE_DIAS = 1

# Peso de cada posicao da prioridade. A primeira e a principal; a terceira ainda conta, e
# conta menos — e o mesmo escalonamento que o motor usa ao montar um programa do zero.
PESO_DA_ORDEM = [1.0, 0.6, 0.35]

NIVEL_DO_ATLETA = {"recreativo": 1, "intermediário": 2, "intermediario": 2,
                   "avançado": 3, "avancado": 3, "bodybuilder": 4}
NIVEL_DO_PROGRAMA = {"iniciante": 1, "intermediário": 2, "intermediario": 2,
                     "avançado": 3, "avancado": 3, "profissional": 4, "bodybuilder": 4}


def _nivel(texto: str, tabela: Dict[str, int]) -> int:
    return tabela.get(str(texto or "").strip().lower(), 2)


def _sexo(valor) -> str:
    v = str(valor or "").strip().lower()
    if v in ("feminino", "female", "f"):
        return "female"
    if v in ("masculino", "male", "m"):
        return "male"
    return ""


def _fase_principal(programa: Dict[str, Any]) -> Dict[str, Any]:
    """A fase que representa o programa para efeito de escolha.

    A primeira, e nao a mais pesada: e por ela que a pessoa comeca, e comparar programas
    pela fase mais intensa de cada um daria vantagem a quem tem uma fase de pico no fim.
    """
    fases = programa.get("phases") or []
    return fases[0] if fases else {}


def dias_do_programa(programa: Dict[str, Any]) -> int:
    fase = _fase_principal(programa)
    return len(fase.get("sessions") or [])


def _series_por_musculo(programa: Dict[str, Any]) -> Dict[str, float]:
    """Quantas series o microciclo entrega para cada musculo.

    O musculo secundario conta METADE: ele recebe estimulo real, e menos que o primario.
    Ignorar o secundario subestimaria um programa que ataca a regiao por vias indiretas.
    """
    contagem: Dict[str, float] = {}
    for sessao in _fase_principal(programa).get("sessions") or []:
        for item in sessao.get("exercises") or []:
            exercicio = _EXERCICIOS.get(item.get("exercise_id"))
            if not exercicio:
                continue
            series = float(item.get("sets") or 0)
            if series <= 0:
                continue
            primario = exercicio.get("primary_muscle")
            if primario:
                contagem[primario] = contagem.get(primario, 0.0) + series
            for secundario in exercicio.get("secondary_muscles") or []:
                contagem[secundario] = contagem.get(secundario, 0.0) + series * 0.5
    return contagem


def _cobertura(programa: Dict[str, Any], prioridades_internas: List[str]) -> float:
    """A fracao das series do microciclo que cai nas regioes escolhidas, pesada pela ordem.

    Fracao e nao total absoluto: um programa de seis dias tem mais series que um de tres em
    qualquer musculo, e comparar o numero cru escolheria sempre o mais longo.
    """
    if not prioridades_internas:
        return 0.0
    series = _series_por_musculo(programa)
    total = sum(series.values()) or 1.0
    nota = 0.0
    for i, musculo in enumerate(prioridades_internas):
        peso = PESO_DA_ORDEM[i] if i < len(PESO_DA_ORDEM) else PESO_DA_ORDEM[-1]
        nota += peso * (series.get(musculo, 0.0) / total)
    return nota


def _serve_ao_perfil(programa: Dict[str, Any], sexo: str) -> bool:
    alvo = str(programa.get("audience_type") or "").strip().lower()
    if alvo in ("", "unisex", "all", "geral"):
        return True
    return alvo == sexo or not sexo


def avaliar(programa: Dict[str, Any], perfil: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A nota de um programa para este atleta, ou None quando ele nao serve.

    Devolver None em vez de nota baixa e deliberado: um programa de seis dias para quem
    treina tres nao e "pior", ele e inviavel, e oferecer com ressalva convidaria a pessoa a
    escolher algo que ela nao consegue cumprir.
    """
    dias_da_pessoa = int(perfil.get("days") or 0)
    dias = dias_do_programa(programa)
    if not dias:
        return None
    diferenca = abs(dias - dias_da_pessoa) if dias_da_pessoa else 0
    if dias_da_pessoa and diferenca > DIFERENCA_MAXIMA_DE_DIAS:
        return None

    sexo = _sexo(perfil.get("sex"))
    if not _serve_ao_perfil(programa, sexo):
        return None

    nivel_pessoa = _nivel(perfil.get("experience"), NIVEL_DO_ATLETA)
    # Volume avancado e recuperacao excepcional nao sao "mais treino": sao programas que
    # assumem uma capacidade de recuperar que nem todo mundo tem.
    if programa.get("safety") in ("expert", "advanced") and nivel_pessoa < 3:
        return None

    prioridades = [to_internal(p) for p in (perfil.get("priorities") or [])]
    cobertura = _cobertura(programa, prioridades)

    nivel_programa = _nivel(programa.get("level"), NIVEL_DO_PROGRAMA)
    # Estar um degrau acima incomoda menos que estar dois abaixo: quem evoluiu fica sem
    # estimulo, e isso e pior que um programa levemente exigente demais.
    distancia_de_nivel = abs(nivel_programa - nivel_pessoa)

    nota = (cobertura * 100.0
            - diferenca * 12.0
            - distancia_de_nivel * 6.0)

    return {
        "id": programa.get("id"),
        "nome": programa.get("name"),
        "categoria": programa.get("category"),
        "dias": dias,
        "nivel": programa.get("level"),
        "nota": round(nota, 2),
        "cobertura": round(cobertura, 4),
        "diferenca_de_dias": diferenca,
    }


def _porque(escolhido: Dict[str, Any], perfil: Dict[str, Any]) -> str:
    """A frase que a pessoa le. Sem ela, a recomendacao e um palpite com nome bonito."""
    regioes = [p for p in (perfil.get("priorities") or [])]
    partes = [f"{escolhido['dias']} sessões por semana"]
    if escolhido["diferenca_de_dias"]:
        partes[0] += f" (você marcou {perfil.get('days')})"
    if regioes and escolhido["cobertura"] > 0:
        partes.append(f"{round(escolhido['cobertura'] * 100)}% do volume nas suas prioridades "
                      f"({', '.join(regioes[:2])})")
    if escolhido.get("nivel"):
        partes.append(f"nível {str(escolhido['nivel']).lower()}")
    return "Escolhido por " + ", ".join(partes) + "."


def recomendar(perfil: Dict[str, Any], catalogo: Optional[List[Dict[str, Any]]] = None,
               quantos: int = 3) -> Dict[str, Any]:
    """Os programas da biblioteca que melhor servem a este atleta, do melhor para o pior."""
    if catalogo is None:
        from training_programs import TRAINING_PROGRAMS
        catalogo = TRAINING_PROGRAMS

    avaliados = [a for a in (avaliar(p, perfil) for p in catalogo) if a]
    avaliados.sort(key=lambda a: (-a["nota"], a["diferenca_de_dias"], a["nome"]))
    melhores = avaliados[:quantos]
    return {
        "recomendados": melhores,
        "melhor": melhores[0] if melhores else None,
        "porque": _porque(melhores[0], perfil) if melhores else "",
        "avaliados": len(avaliados),
    }

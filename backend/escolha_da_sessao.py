# -*- coding: utf-8 -*-
"""Escolher qual sessão treinar hoje.

Por que isto existe
-------------------
Um atleta adiantou o treino do fim de semana e, no dia seguinte, o FORGE ofereceu de novo a
sessão que ele acabara de fazer — a rotação não sabia que ele tinha treinado fora da ordem.
Ele quis fazer a sessão seguinte e não teve como: a tela mostra UMA sessão, a que o ponteiro
aponta, e não havia onde escolher outra. Sem poder escolher, não dá para registrar carga, e
sem registro o treino não existe para o motor.

O caminho que existia era a Biblioteca, que SUBSTITUI a sessão ativa por um modelo: resolve
o dia estragando o programa.

O que a escolha é
-----------------
Uma decisão DATADA: "hoje eu faço a sessão X". Vale para aquele dia, vence sozinha, e o
programa continua sendo a verdade por baixo. Ao concluir, a rotação segue a partir do que
foi FEITO — quem fez o B hoje recebe o C amanhã, que é o que qualquer pessoa espera.

Não move o ponteiro na hora da escolha, de propósito: escolher e não treinar é comum — a
pessoa abre o aplicativo, olha as opções, fecha. Mover o ponteiro ali deixaria a rotação
adiantada por um treino que não aconteceu.
"""
from datetime import date as Data
from typing import Any, Dict, List, Optional


def _data(valor: Any) -> Optional[Data]:
    if isinstance(valor, Data):
        return valor
    try:
        return Data.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def normalizar(escolha: Any, hoje: Data) -> Optional[Dict[str, Any]]:
    """A escolha, se ainda for de hoje. Qualquer outra coisa vira None, sem levantar erro.

    Uma escolha de ontem não vale: o dia dela passou, e mantê-la faria o atleta abrir o
    aplicativo amanhã e receber a sessão que ele escolheu anteontem.

    Dado malformado no banco também não pode derrubar a montagem do programa — o treino do
    dia vale mais que a exceção.
    """
    if not isinstance(escolha, dict):
        return None
    quando = _data(escolha.get("data"))
    try:
        dia = int(escolha.get("day"))
    except (TypeError, ValueError):
        return None
    if not quando or quando != hoje:
        return None
    return {"data": quando.isoformat(), "day": dia}


def dia_escolhido(escolha: Any, hoje: Data, dias_validos: List[int]) -> Optional[int]:
    """O dia escolhido para hoje, se ele ainda existir no programa.

    `dias_validos` entra porque o programa muda: quem escolheu o dia 5 e depois trocou para
    uma divisão de três dias tem uma escolha que aponta para o vazio. Devolver None ali faz
    o ponteiro normal assumir, em vez de a tela ficar sem sessão nenhuma.
    """
    limpa = normalizar(escolha, hoje)
    if not limpa:
        return None
    return limpa["day"] if limpa["day"] in (dias_validos or []) else None


def validar(dia: Any, dias_validos: List[int]) -> int:
    """Confere o que o atleta pediu. Levanta `ValueError` com frase de tela."""
    try:
        escolhido = int(dia)
    except (TypeError, ValueError):
        raise ValueError("Escolha uma sessão do seu programa.")
    if escolhido not in (dias_validos or []):
        raise ValueError("Essa sessão não está no seu programa.")
    return escolhido

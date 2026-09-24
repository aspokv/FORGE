# -*- coding: utf-8 -*-
"""Treinar num dia de descanso, e descansar no dia que seria de treino.

Por que isto existe
-------------------
Um atleta do FORGE ia viajar no fim de semana e quis adiantar o treino de sábado para a
quinta, que na agenda dele é descanso. Não havia como: na tela de treino, dia de descanso
é renderizado sem sessão, sem lista de exercícios e sem botão de iniciar. O único caminho
oferecido era a Biblioteca — que APLICA um modelo e substitui a sessão ativa, ou seja,
mexe no programa para resolver uma semana atípica.

A vida do atleta tem viagem, plantão e imprevisto. Mover um treino dentro da semana não
deveria exigir reescrever o programa.

O que a troca é, e o que ela não é
----------------------------------
É uma EXCEÇÃO DATADA: "a sessão do dia X acontece no dia Y". Vale para aquelas duas datas
e mais nada. Não altera o programa, não muda a divisão, não mexe na rotação — o programa
continua sendo a verdade, e a troca é uma anotação por cima dele.

Não é remarcação recorrente. Quem quer treinar em outros dias TODA semana está pedindo
outro programa, e isso se resolve na avaliação ou no Program Builder, onde a decisão é
registrada e o motor recalcula volume e recuperação. Uma exceção que se repete sozinha
viraria um segundo programa invisível, divergindo do que o atleta acha que segue.

Trocas vencidas somem
---------------------
Uma troca do passado não tem efeito nenhum e só atrapalharia a leitura. Elas são filtradas
por data na hora de aplicar, e não dependem de ninguém lembrar de limpar.
"""
from datetime import date as Data
from typing import Any, Dict, List, Optional, Tuple

# Quantos dias para frente uma troca pode alcançar.
#
# Uma semana. A agenda do FORGE é semanal, e mover um treino para fora da semana dele não
# é mover: é mudar o programa por outro caminho, sem o motor recalcular nada. Além disso,
# quanto mais longe a troca alcança, mais tempo o atleta passa vendo uma agenda que não é
# a do programa dele.
ALCANCE_EM_DIAS = 7


def _data(valor: Any) -> Optional[Data]:
    """Aceita `date` ou ISO. Devolve None para qualquer outra coisa, sem levantar erro.

    Uma troca malformada gravada no banco não pode derrubar a montagem do programa: o
    treino do dia vale mais que a exceção.
    """
    if isinstance(valor, Data):
        return valor
    try:
        return Data.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def normalizar(trocas: Any, hoje: Data) -> List[Dict[str, str]]:
    """As trocas que ainda valem, em ordem, sem repetição e sem lixo.

    `hoje` entra porque o que venceu não vale: uma troca cujas DUAS datas já passaram não
    muda nada no presente e só polui a lista.
    """
    limpas: List[Dict[str, str]] = []
    vistas = set()
    for item in (trocas or []):
        if not isinstance(item, dict):
            continue
        treino = _data(item.get("treinar_em"))
        descanso = _data(item.get("descansar_em"))
        if not treino or not descanso or treino == descanso:
            continue
        if treino < hoje and descanso < hoje:
            continue
        chave = (treino, descanso)
        if chave in vistas:
            continue
        vistas.add(chave)
        limpas.append({"treinar_em": treino.isoformat(),
                       "descansar_em": descanso.isoformat()})
    return limpas


def validar(treinar_em: Any, descansar_em: Any, hoje: Data) -> Tuple[Data, Data]:
    """Confere o que o atleta pediu. Levanta `ValueError` com frase de tela.

    As mensagens são as que a pessoa lê, e por isso dizem o que fazer — não o que a
    validação sentiu.
    """
    treino = _data(treinar_em)
    descanso = _data(descansar_em)
    if not treino or not descanso:
        raise ValueError("Escolha duas datas válidas.")
    if treino == descanso:
        raise ValueError("Escolha um dia diferente para descansar.")
    if treino < hoje:
        raise ValueError("Não dá para treinar num dia que já passou.")
    if descanso < hoje:
        raise ValueError("Não dá para descansar num dia que já passou.")
    for rotulo, valor in (("treinar", treino), ("descansar", descanso)):
        if (valor - hoje).days > ALCANCE_EM_DIAS:
            raise ValueError(f"Só dá para {rotulo} até {ALCANCE_EM_DIAS} dias à frente.")
    return treino, descanso


def aplicar(mapa_por_data: Dict[str, Any], trocas: Any, hoje: Data) -> Dict[str, Any]:
    """Reescreve o calendário de datas aplicando as trocas que valem.

    `mapa_por_data` é {data ISO: sessão ou None}. Devolve um mapa novo; não muda o que
    entrou, porque quem chama usa o original para saber o que o PROGRAMA diz — e a
    diferença entre os dois é o que a tela mostra como "trocado".

    A ordem importa: primeiro o dia de descanso recebe a sessão, depois o dia de origem é
    esvaziado. Fazer ao contrário perderia a sessão quando as duas datas se cruzam entre
    trocas encadeadas.
    """
    resultado = dict(mapa_por_data)
    for troca in normalizar(trocas, hoje):
        origem, destino = troca["descansar_em"], troca["treinar_em"]
        if origem not in resultado or destino not in resultado:
            # Data fora da janela que o chamador montou: a troca continua guardada e volta
            # a valer quando a janela alcançar, em vez de ser descartada em silêncio.
            continue
        resultado[destino] = resultado.get(origem)
        resultado[origem] = None
    return resultado


def descreve(troca: Dict[str, str]) -> str:
    """Uma linha para a tela, sem inventar nome de dia da semana em português."""
    return f"Treino de {troca['descansar_em']} movido para {troca['treinar_em']}"

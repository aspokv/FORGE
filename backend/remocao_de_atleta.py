# -*- coding: utf-8 -*-
"""FORGE — tirar um atleta da lista, e tirar um atleta do banco.

Sao duas coisas diferentes, e confundi-las custa caro nas duas direcoes.

ARQUIVAR e a resposta para "a lista esta cheia de conta que nao usa". Some da tela,
continua no banco, volta com um clique. Nada se perde, e por isso e o padrao.

EXCLUIR apaga a pessoa e TODO o rastro dela. Nao tem volta, entao tem trava.

Por que este modulo existe separado da rota
-------------------------------------------
Excluir um atleta e deletar de 30 colecoes. A lista foi levantada LENDO O BANCO, e nao
o codigo: uma varredura por `db.<colecao>.<metodo>({"profile_id"` encontrava 16, e o
banco tem 30. Ficavam de fora, entre outras, `sets`, `weight_logs`,
`nutrition_assessments`, `hydration_logs`, `weekly_reviews` e `conselho_semanal` — parte
delas legado que ninguem escreve mais, mas que tem dado de gente de verdade.

Dado orfao nao da erro: ele so fica la, com o nome e o peso de alguem que pediu para ser
apagado. Por isso a suite nao confere apenas as colecoes desta lista — ela varre TODAS as
colecoes do banco procurando o id, e quebra se sobrar qualquer coisa. Colecao nova criada
no futuro aparece ali sozinha.
"""
from typing import Any, Dict, List, Tuple

# (colecao, campo que guarda o identificador do atleta).
#
# Varias colecoes tem mais de uma chave (`profile_id` e `user_id` apontando para o mesmo
# id). Uma e suficiente, e a escolhida e a que o codigo usa para LER — se um dia as duas
# divergirem, a varredura da suite denuncia.
COLECOES_DO_ATLETA: Tuple[Tuple[str, str], ...] = (
    ("profiles", "id"),
    ("assessments", "profile_id"),
    ("nutrition_assessments", "profile_id"),
    ("set_logs", "profile_id"),
    ("sets", "profile_id"),
    ("recovery", "profile_id"),
    ("workout_completions", "profile_id"),
    ("workout_session_drafts", "profile_id"),
    ("manual_workout_drafts", "profile_id"),
    ("program_versions", "profile_id"),
    ("weekly_reviews", "profile_id"),
    ("conselho_semanal", "profile_id"),
    ("hydration_logs", "profile_id"),
    ("visual_assessments", "profile_id"),
    ("nutrition_plans", "profile_id"),
    ("nutrition_plan_drafts", "profile_id"),
    ("nutrition_import_drafts", "profile_id"),
    ("nutrition_adherence", "profile_id"),
    ("nutrition_consumed_extras", "profile_id"),
    ("nutrition_preferences", "profile_id"),
    ("nutrition_periodization", "profile_id"),
    ("nutrition_shopping_checks", "profile_id"),
    ("nutrition_weight_logs", "profile_id"),
    ("weight_logs", "profile_id"),
    ("subscriptions", "user_id"),
    ("subscription_attempts", "user_id"),
    ("pix_attempts", "user_id"),
    ("password_resets", "user_id"),
    ("ai_usage", "user_id"),
    ("users", "id"),
)

# Colecoes que guardam o email e nao o id.
COLECOES_POR_EMAIL: Tuple[Tuple[str, str], ...] = (
    ("signup_attempts", "email"),
)

# O que NAO se apaga, com o motivo. Isto e uma decisao, nao um esquecimento, e a suite
# cobra que continue assim.
COLECOES_PRESERVADAS: Dict[str, str] = {
    "admin_audit_log":
        "E o registro do que o administrador fez, inclusive esta exclusao. Apagar o "
        "rastro junto com a pessoa destruiria a unica prova de que a decisao existiu.",
    "billing_events":
        "E o livro de idempotencia dos webhooks do Mercado Pago, indexado por evento e "
        "nao por pessoa. Apagar faria um webhook repetido ser processado de novo.",
    "rate_limits":
        "Contadores por chave de requisicao, sem dono, e que expiram sozinhos.",
    "login_attempts":
        "Trava de forca bruta por email. Apagar junto daria a quem for excluido uma "
        "forma de zerar o bloqueio.",
    "exercise_aliases":
        "Catalogo de exercicios do proprio FORGE, igual para todo mundo. Nenhum "
        "documento ali pertence a um atleta.",
    "exercise_suggestions":
        "Catalogo de sugestoes de exercicio do produto, sem dono e igual para todos.",
    "food_suggestions":
        "Catalogo de alimentos do produto, sem dono e igual para todos.",
}


async def remover_dados(db, atleta_id: str, email: str = "") -> Dict[str, int]:
    """Apaga o atleta e tudo que e dele. Devolve quantos documentos sairam de cada lugar.

    A contagem nao e enfeite: ela vai para a auditoria. Sem ela, "excluido" e uma
    afirmacao sem prova, e ninguem consegue responder depois o que exatamente sumiu.

    `users` fica por ULTIMO de proposito. Se a remocao falhar no meio, a conta ainda
    existe e da para tentar de novo; na ordem inversa, sobraria dado sem dono e sem
    ninguem para reencontra-lo pela tela.
    """
    removidos: Dict[str, int] = {}
    for colecao, campo in COLECOES_DO_ATLETA:
        resultado = await db[colecao].delete_many({campo: atleta_id})
        if resultado.deleted_count:
            removidos[colecao] = resultado.deleted_count
    if email:
        for colecao, campo in COLECOES_POR_EMAIL:
            resultado = await db[colecao].delete_many({campo: email.lower()})
            if resultado.deleted_count:
                removidos[colecao] = resultado.deleted_count
    return removidos


async def orfaos(db, atleta_id: str, email: str = "") -> List[str]:
    """Procura qualquer coisa do atleta que tenha sobrado, em TODAS as colecoes.

    Existe para a suite, e e ela que protege a lista la de cima de envelhecer: colecao
    nova, criada por outra funcionalidade daqui a seis meses, aparece aqui sem ninguem
    precisar lembrar de atualizar nada.
    """
    chaves = ("profile_id", "user_id", "athlete_id", "id")
    achados: List[str] = []
    for nome in await db.list_collection_names():
        if nome in COLECOES_PRESERVADAS:
            continue
        condicoes: List[Dict[str, Any]] = [{chave: atleta_id} for chave in chaves]
        if email:
            condicoes.append({"email": email.lower()})
        quantos = await db[nome].count_documents({"$or": condicoes})
        if quantos:
            achados.append(f"{nome}: {quantos}")
    return achados

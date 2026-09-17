# -*- coding: utf-8 -*-
"""FORGE — as rotas do Conselho.

Esta camada e de proposito burra: ela LE o banco, entrega as linhas cruas para
`conselho.observar` e devolve o que `conselho.decidir` respondeu. Nenhuma regra de
treinamento mora aqui, e isso e o que permite a suite de `conselho.py` rodar sem Mongo e
ainda assim cobrir o produto inteiro.

Uma decisao de contrato que vale explicar: o Conselho e SEMANAL e idempotente dentro da
semana. Abrir a tela cinco vezes na quarta-feira devolve o mesmo conselho, com o mesmo
motivo e a mesma previsao. Um conselho que muda a cada toque nao e um conselho, e o placar
de previsoes viraria ficcao se cada visita criasse uma aposta nova.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import conselho as motor
from auth import get_current_user
from billing_plans import ANALISES_AVANCADAS
from entitlements import exigir_capacidade

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conselho", tags=["conselho"])

JANELA_DE_CONSUMO = 7
JANELA_DE_SERIES = 42          # seis semanas: tres de base, uma corrente, e folga
JANELA_DE_CHECKINS = 28        # quatro amostras de cada dia da semana, no melhor caso


def _semana_de(momento: datetime) -> str:
    ano, semana, _ = momento.isocalendar()
    return f"{ano}-S{semana:02d}"


def _musculo_por_exercicio() -> Dict[str, str]:
    """De exercicio para musculo primario, direto do catalogo do proprio FORGE.

    A chave e `muscle`. `exercises.json` guarda `primary_muscle`, mas `server.EXERCISES` e
    a versao ja traduzida para a interface, e ali o campo se chama `muscle` — e o mesmo
    nome que `analyze_program` usa. Ler o nome do arquivo em vez do nome do objeto devolvia
    um mapa VAZIO, e um mapa vazio nao quebra nada: `volume_por_semana` simplesmente
    descartava todas as series e o Conselho dizia "poucas semanas de treino" para quem
    treinava havia um mes. Defeito silencioso, encontrado olhando a tela.
    """
    from server import EXERCISES  # tardio: evita ciclo de import com o servidor
    return {e["id"]: e.get("muscle") or e.get("primary_muscle")
            for e in EXERCISES if e.get("muscle") or e.get("primary_muscle")}


def _nome_por_exercicio() -> Dict[str, str]:
    """De exercicio para o nome que o atleta reconhece.

    Sem isto a frase do Conselho sai "Voce perdeu repeticao em squat", com o
    identificador do banco no meio de um texto que a pessoa le.
    """
    from server import EXERCISES
    return {e["id"]: e.get("name") for e in EXERCISES if e.get("name")}


async def _ler_atleta(db, perfil_id: str) -> Dict[str, Any]:
    """Uma leitura do atleta a partir do que esta gravado, sem nenhuma decisao."""
    hoje = datetime.now(timezone.utc).date()
    desde_consumo = (hoje - timedelta(days=JANELA_DE_CONSUMO - 1)).isoformat()
    desde_series = (hoje - timedelta(days=JANELA_DE_SERIES)).isoformat()
    desde_checkin = (hoje - timedelta(days=JANELA_DE_CHECKINS)).isoformat()

    guardado = await db.nutrition_plans.find_one({"profile_id": perfil_id}, {"_id": 0, "plan": 1})
    plano = (guardado or {}).get("plan") or {}
    alvos = plano.get("targets") or {}
    alvo_kcal = alvos.get("goal_calories")

    # O consumo reusa a MESMA soma da tela de Nutricao. Dois totais diferentes para a
    # mesma comida destruiriam a confianca nos dois.
    from nutrition_routes import MACROS_DA_SEMANA, _totais_do_dia
    filtro = {"profile_id": perfil_id, "date": {"$gte": desde_consumo}}
    linhas = await db.nutrition_adherence.find(filtro, {"_id": 0}).sort("created_at", 1).to_list(None)
    extras = await db.nutrition_consumed_extras.find(filtro, {"_id": 0}).to_list(None)
    por_dia: Dict[str, Dict[str, Any]] = {}
    for linha in linhas:
        data = str(linha.get("date") or "")
        if data:
            por_dia.setdefault(data, {"linhas": {}, "extras": []})["linhas"][linha.get("meal_index")] = linha
    for extra in extras:
        data = str(extra.get("date") or "")
        if data:
            por_dia.setdefault(data, {"linhas": {}, "extras": []})["extras"].append(extra)

    dias_de_consumo = []
    for data in sorted(por_dia):
        conteudo = por_dia[data]
        totais = _totais_do_dia(plano.get("meals") or [], list(conteudo["linhas"].values()),
                               conteudo["extras"])
        if any(totais[m] for m in MACROS_DA_SEMANA):
            dias_de_consumo.append({"date": data, **totais})

    pesagens = await db.nutrition_weight_logs.find(
        {"profile_id": perfil_id}, {"_id": 0}).sort("date", -1).to_list(40)
    series = await db.set_logs.find(
        {"profile_id": perfil_id, "created_at": {"$gte": desde_series}},
        {"_id": 0}).sort("created_at", 1).to_list(3000)
    checkins = await db.recovery.find(
        {"profile_id": perfil_id, "local_date": {"$gte": desde_checkin}},
        {"_id": 0}).sort("created_at", 1).to_list(200)

    perfil = await db.profiles.find_one({"id": perfil_id},
                                        {"_id": 0, "goal": 1, "body_goal": 1, "latest_weight": 1})
    objetivo = plano.get("goal") or alvos.get("goal") or (perfil or {}).get("goal") \
        or (perfil or {}).get("body_goal")

    return motor.observar(
        objetivo=objetivo,
        dias_de_consumo=dias_de_consumo,
        janela_dias=JANELA_DE_CONSUMO,
        alvo_kcal=alvo_kcal,
        pesagens=pesagens,
        series=series,
        musculo_por_exercicio=_musculo_por_exercicio(),
        checkins=checkins,
        nome_por_exercicio=_nome_por_exercicio(),
    )


def _sem_underscore(documento: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not documento:
        return None
    return {k: v for k, v in documento.items() if k != "_id"}


@router.get("")
async def conselho_da_semana(request: Request, user=Depends(get_current_user)):
    """O conselho desta semana, o placar da anterior, e a leitura que gerou os dois.

    A leitura vai junto de proposito. Um veredito sem os numeros que o produziram e um
    palpite com tipografia bonita, e a pessoa tem que poder discordar do motor olhando a
    mesma coisa que ele olhou.
    """
    db = request.app.state.db
    await exigir_capacidade(db, user, ANALISES_AVANCADAS)
    perfil_id = user["id"]
    agora = datetime.now(timezone.utc)
    semana = _semana_de(agora)

    estado = await _ler_atleta(db, perfil_id)

    # O placar: a previsao da semana passada contra o que realmente aconteceu.
    anterior = await db.conselho_semanal.find_one(
        {"profile_id": perfil_id, "semana": {"$ne": semana}}, {"_id": 0},
        sort=[("semana", -1)])
    placar = None
    if anterior:
        placar = motor.conferir_previsao(anterior.get("previsao"), estado)
        if anterior.get("conferido") != placar:
            await db.conselho_semanal.update_one(
                {"profile_id": perfil_id, "semana": anterior["semana"]},
                {"$set": {"conferido": placar,
                          "conferido_em": agora.isoformat()}})

    # Idempotencia: a semana ja decidida nao e decidida de novo.
    desta_semana = await db.conselho_semanal.find_one(
        {"profile_id": perfil_id, "semana": semana}, {"_id": 0})
    if desta_semana:
        decisao = desta_semana.get("decisao") or {}
        aplicada = desta_semana.get("aplicada")
    else:
        decisao = motor.decidir(estado)
        await db.conselho_semanal.insert_one({
            "id": str(uuid.uuid4()), "profile_id": perfil_id, "semana": semana,
            "criado_em": agora.isoformat(), "decisao": decisao,
            "previsao": decisao.get("previsao"), "estado": estado,
            "aplicada": None, "conferido": None,
        })
        aplicada = None

    conferidas = await db.conselho_semanal.find(
        {"profile_id": perfil_id, "conferido": {"$ne": None}},
        {"_id": 0, "conferido": 1}).to_list(60)

    return {
        "semana": semana,
        "decisao": decisao,
        "aplicada": aplicada,
        "estado": estado,
        "placar_anterior": placar,
        "retrospecto": motor.retrospecto([c["conferido"] for c in conferidas]),
    }


class AplicarIn(BaseModel):
    aceitar: bool = True


@router.post("/aplicar")
async def aplicar_conselho(payload: AplicarIn, request: Request,
                           user=Depends(get_current_user)):
    """O atleta confirma a mudanca proposta. O motor nunca aplica sozinho.

    Isto nao e cerimonia: o motor propoe uma alavanca por semana com base em tres
    semanas de dado, e quem conhece o contexto que o banco nao tem — uma viagem, uma
    gripe, uma prova — e a pessoa. Aplicar sem perguntar transformaria um conselho bom
    numa mudanca indesejada, que e como se perde a confianca de uma vez so.

    Hoje so a alavanca calorica tem aplicacao automatica, porque ela mexe num numero que
    o proprio FORGE ja sabe editar com trava de proteina e piso de gordura. Agenda,
    descarga e volume voltam `manual`: a mudanca esta escrita, e quem mexe no treino e o
    atleta, na tela de treino, onde ele ve o que esta trocando.
    """
    db = request.app.state.db
    await exigir_capacidade(db, user, ANALISES_AVANCADAS)
    perfil_id = user["id"]
    agora = datetime.now(timezone.utc)
    semana = _semana_de(agora)

    registro = await db.conselho_semanal.find_one(
        {"profile_id": perfil_id, "semana": semana}, {"_id": 0})
    if not registro:
        raise HTTPException(404, "Nao existe conselho desta semana ainda.")
    if registro.get("aplicada"):
        return {"status": "ja_aplicada", "aplicada": registro["aplicada"]}

    decisao = registro.get("decisao") or {}
    mudanca = decisao.get("mudanca")
    if not payload.aceitar:
        resultado = {"status": "recusada", "em": agora.isoformat()}
        await db.conselho_semanal.update_one(
            {"profile_id": perfil_id, "semana": semana}, {"$set": {"aplicada": resultado}})
        return {"status": "recusada"}
    if not mudanca:
        raise HTTPException(422, "O conselho desta semana nao propoe mudanca.")

    if mudanca.get("tipo") != "kcal":
        resultado = {"status": "manual", "tipo": mudanca.get("tipo"), "em": agora.isoformat()}
        await db.conselho_semanal.update_one(
            {"profile_id": perfil_id, "semana": semana}, {"$set": {"aplicada": resultado}})
        return {"status": "manual", "mudanca": mudanca,
                "mensagem": "Essa mudanca e no treino, e quem faz e voce, na tela de treino."}

    guardado = await db.nutrition_plans.find_one({"profile_id": perfil_id}, {"_id": 0, "plan": 1})
    plano = (guardado or {}).get("plan") or {}
    alvos = dict(plano.get("targets") or {})
    if not alvos.get("goal_calories"):
        raise HTTPException(422, "Seu plano nao tem meta calorica para ajustar.")

    # Proteina fixa em gramas e gordura no piso: as mesmas travas de
    # `nutrition_periodization`. O que sobra de caloria vira carboidrato.
    from nutrition_periodization import KCAL_CARB, fat_floor_g
    peso = (estado_peso := (registro.get("estado") or {}).get("peso") or {}).get("peso_atual") \
        or (await db.profiles.find_one({"id": perfil_id}, {"_id": 0, "latest_weight": 1}) or {}).get("latest_weight")
    antes = float(alvos["goal_calories"])
    depois = float(mudanca["para"])
    delta_kcal = depois - antes

    gordura_atual = float(alvos.get("fat_g") or 0)
    piso_gordura = fat_floor_g(float(peso), str(decisao.get("objetivo") or "maintenance")) if peso else 0
    carbo_atual = float(alvos.get("carbs_g") or 0)
    novo_carbo = carbo_atual + delta_kcal / KCAL_CARB
    if novo_carbo < 0:
        # Carboidrato nao vai a negativo: o que faltar sai da gordura, ate o piso.
        sobra = -novo_carbo * KCAL_CARB
        novo_carbo = 0.0
        gordura_atual = max(piso_gordura, gordura_atual - sobra / 9)

    alvos.update({"goal_calories": round(depois, 0), "carbs_g": round(novo_carbo, 1),
                  "fat_g": round(gordura_atual, 1)})
    plano["targets"] = alvos
    await db.nutrition_plans.update_one({"profile_id": perfil_id},
                                        {"$set": {"plan": plano}}, upsert=True)

    resultado = {"status": "aplicada", "tipo": "kcal", "de": round(antes, 0),
                 "para": round(depois, 0), "em": agora.isoformat()}
    await db.conselho_semanal.update_one(
        {"profile_id": perfil_id, "semana": semana}, {"$set": {"aplicada": resultado}})
    logger.info("conselho aplicado perfil=%s semana=%s delta=%s", perfil_id, semana,
                round(delta_kcal, 0))
    return {"status": "aplicada", "targets": alvos, "aplicada": resultado}


@router.get("/historico")
async def historico(request: Request, user=Depends(get_current_user)):
    """As decisoes passadas com o que cada previsao deu. O placar tem que ser auditavel."""
    db = request.app.state.db
    await exigir_capacidade(db, user, ANALISES_AVANCADAS)
    linhas = await db.conselho_semanal.find(
        {"profile_id": user["id"]},
        {"_id": 0, "estado": 0}).sort("semana", -1).to_list(52)
    conferidas = [l["conferido"] for l in linhas if l.get("conferido")]
    return {"semanas": linhas, "retrospecto": motor.retrospecto(conferidas)}

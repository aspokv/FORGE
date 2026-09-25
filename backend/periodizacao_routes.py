# -*- coding: utf-8 -*-
"""Rotas da periodização automática da dieta. O porquê e as regras estão em
`periodizacao_automatica.py`; aqui só se lê o banco, aplica e grava.

A semana é aplicada de forma PREGUIÇOSA: quando o atleta abre a nutrição (GET /plan) ou
esta tela, o que venceu desde a última visita é aplicado. Não existe tarefa agendada no
FORGE, e um relógio no servidor para isso seria infraestrutura nova por um motivo que a
abertura do aplicativo já resolve. Quem some duas semanas volta com o degrau certo para
a semana em que está, decidido com a balança daquele momento.
"""
import copy
import logging
import uuid
from datetime import date as CalendarDate, datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import periodizacao_automatica as pa
import refeicoes_livres
from auth import get_current_user
from billing_plans import ALIMENTACAO, PERIODIZACAO_DA_DIETA
from conselho import tendencia_de_peso
from entitlements import acesso_de, exigir_capacidade
from food_diary import DIARY_FOODS
from nutrition_engine import FOOD_INDEX, build_food_item
from workout_calendar import calendar_today

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nutrition/periodizacao", tags=["periodizacao-da-dieta"])
COLECAO = "periodizacao_da_dieta"


class PeriodizacaoIn(BaseModel):
    fase: Optional[str] = None
    semanas: int = 4
    ritmo: str = "moderado"


def _dia(valor: Any) -> Optional[CalendarDate]:
    try:
        return CalendarDate.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


async def _contexto(db, perfil_id: str) -> Dict[str, Any]:
    perfil = await db.profiles.find_one({"id": perfil_id}, {"_id": 0}) or {}
    guardado = await db.nutrition_plans.find_one({"profile_id": perfil_id}, {"_id": 0}) or {}
    plano = guardado.get("plan") or {}
    pesagens = await db.nutrition_weight_logs.find(
        {"profile_id": perfil_id}, {"_id": 0}).sort("date", -1).to_list(60)
    na = perfil.get("nutrition_assessment") or {}
    peso = perfil.get("latest_weight") or (pesagens[0]["weight_kg"] if pesagens else None) or na.get("weight_kg")
    return {"perfil": perfil, "plano": plano, "pesagens": pesagens, "peso": peso,
            "objetivo": na.get("goal")}


def _base_do_plano(plano: Dict[str, Any]) -> Dict[str, float]:
    alvos = plano.get("targets") or {}
    totais = plano.get("daily_totals") or {}
    return {"kcal": float(alvos.get("goal_calories") or totais.get("kcal") or 0),
            "protein_g": float(alvos.get("protein_g") or totais.get("protein_g") or 0),
            "carbs_g": float(alvos.get("carbs_g") or totais.get("carbs_g") or 0),
            "fat_g": float(alvos.get("fat_g") or totais.get("fat_g") or 0)}


def _progressao(ctx, payload: PeriodizacaoIn) -> Dict[str, Any]:
    fase = payload.fase or pa.fase_do_objetivo(ctx["objetivo"])
    if not fase:
        raise HTTPException(422, "Seu objetivo é manutenção. Escolha se esta fase é de corte ou de ganho de massa.")
    if not (ctx["plano"].get("meals")):
        raise HTTPException(404, "Gere ou importe seu plano alimentar antes de periodizar.")
    try:
        piso_do_prato = pa.carbo_minimo_do_prato(ctx["plano"].get("meals") or [], FOOD_INDEX, DIARY_FOODS)
        return pa.montar_progressao(_base_do_plano(ctx["plano"]), ctx["peso"], fase,
                                    payload.semanas, payload.ritmo, piso_do_prato)
    except ValueError as erro:
        raise HTTPException(422, str(erro))


def _exemplo_no_prato(plano, progressao) -> list:
    """Como o prato fica na ÚLTIMA semana: "Arroz 150 g → 120 g". É o que a pessoa
    entende — "carboidrato 190 g" não diz nada no almoço."""
    final = progressao["tabela"][-1]["carbs_g"] - progressao["base"]["carbs_g"]
    _, _, mudancas = pa.ajustar_refeicoes(copy.deepcopy(plano.get("meals") or []), final,
                                          FOOD_INDEX, DIARY_FOODS, build_food_item)
    return mudancas[:8]


async def _pode(db, user) -> bool:
    try:
        return PERIODIZACAO_DA_DIETA in ((await acesso_de(db, user)).get("capabilities") or [])
    except Exception:  # noqa: BLE001 — sem acesso lido, a tela mostra o convite
        return False


def _publico(doc):
    return {k: v for k, v in (doc or {}).items() if k != "_id"} if doc else None


# ── A semana ────────────────────────────────────────────────────────────────────────────

async def aplicar_semana_pendente(db, perfil_id: str, hoje: Optional[CalendarDate] = None) -> Optional[Dict[str, Any]]:
    """Aplica o que venceu desde a última visita. Idempotente e seguro contra duas abas:
    a semana só é gravada se `semana_aplicada` ainda for a que foi lida."""
    doc = await db[COLECAO].find_one({"profile_id": perfil_id, "status": "ativa"}, {"_id": 0})
    if not doc:
        return None
    hoje = hoje or calendar_today()
    semana = pa.semana_do_calendario(_dia(doc["inicio"]), hoje)
    total = int(doc["semanas"])
    ja = int(doc.get("semana_aplicada") or 1)
    if semana <= ja:
        return doc
    agora = datetime.now(timezone.utc).isoformat()

    if semana > total:
        await db[COLECAO].update_one({"profile_id": perfil_id, "status": "ativa", "semana_aplicada": ja},
                                     {"$set": {"status": "concluida", "concluida_em": agora}})
        return await db[COLECAO].find_one({"profile_id": perfil_id}, {"_id": 0})

    ctx = await _contexto(db, perfil_id)
    tendencia = tendencia_de_peso(list(reversed(ctx["pesagens"])))
    decisao, motivo = pa.decidir_degrau(doc["fase"], tendencia, doc.get("ritmo") or "moderado")
    degrau = int(doc.get("degrau") or 0)
    if decisao == "avancar":
        degrau = min(total - 1, degrau + (semana - ja))
    linha = doc["tabela"][degrau]

    plano = ctx["plano"]
    alvos = dict(plano.get("targets") or {})
    delta = float(linha["carbs_g"]) - float(alvos.get("carbs_g") or doc["base"]["carbs_g"])
    refeicoes, aplicado, mudancas = pa.ajustar_refeicoes(plano.get("meals") or [], delta,
                                                          FOOD_INDEX, DIARY_FOODS, build_food_item)
    historico = {"semana": semana, "degrau": degrau, "decisao": decisao, "motivo": motivo,
                 "kcal": linha["kcal"], "carbs_g": linha["carbs_g"], "travou": linha.get("travou"),
                 "mudancas": mudancas[:8], "em": agora}
    r = await db[COLECAO].update_one(
        {"profile_id": perfil_id, "status": "ativa", "semana_aplicada": ja},
        {"$set": {"semana_aplicada": semana, "degrau": degrau}, "$push": {"historico": historico}})
    if r.modified_count == 0:
        return await db[COLECAO].find_one({"profile_id": perfil_id}, {"_id": 0})

    alvos.update({"goal_calories": linha["kcal"], "protein_g": linha["protein_g"],
                  "carbs_g": linha["carbs_g"], "fat_g": linha["fat_g"]})
    plano["targets"] = alvos
    plano["meals"] = refeicoes
    plano["daily_totals"] = refeicoes_livres.totais_do_plano(refeicoes, DIARY_FOODS)
    await db.nutrition_plans.update_one({"profile_id": perfil_id}, {"$set": {"plan": plano}})
    logger.info("periodizacao perfil=%s semana=%s degrau=%s decisao=%s", perfil_id, semana, degrau, decisao)
    return await db[COLECAO].find_one({"profile_id": perfil_id}, {"_id": 0})


async def periodizacao_ativa(db, perfil_id: str) -> bool:
    return bool(await db[COLECAO].find_one({"profile_id": perfil_id, "status": "ativa"}, {"_id": 1}))


# ── Rotas ───────────────────────────────────────────────────────────────────────────────

@router.get("")
async def estado(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    liberado = await _pode(db, user)
    doc = await aplicar_semana_pendente(db, user["id"]) if liberado else None
    if not doc:
        doc = await db[COLECAO].find_one({"profile_id": user["id"]}, {"_id": 0}, sort=[("criada_em", -1)])
    ctx = await _contexto(db, user["id"])
    semana = pa.semana_do_calendario(_dia(doc["inicio"]), calendar_today()) if doc and doc.get("status") == "ativa" else None
    return {"liberado": liberado, "periodizacao": _publico(doc), "semana_atual": semana,
            "fase_sugerida": pa.fase_do_objetivo(ctx["objetivo"]), "peso": ctx["peso"],
            "ultima_pesagem": (ctx["pesagens"][0].get("date") if ctx["pesagens"] else None)}


@router.post("/previa")
async def previa(payload: PeriodizacaoIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    await exigir_capacidade(db, user, PERIODIZACAO_DA_DIETA)
    ctx = await _contexto(db, user["id"])
    progressao = _progressao(ctx, payload)
    return {**progressao, "no_prato": _exemplo_no_prato(ctx["plano"], progressao)}


@router.post("/ativar")
async def ativar(payload: PeriodizacaoIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    await exigir_capacidade(db, user, PERIODIZACAO_DA_DIETA)
    perfil_id = user["id"]
    if await periodizacao_ativa(db, perfil_id):
        raise HTTPException(409, "Já existe uma periodização em andamento. Encerre ela antes de começar outra.")
    ctx = await _contexto(db, perfil_id)
    progressao = _progressao(ctx, payload)
    agora = datetime.now(timezone.utc).isoformat()
    # O plano de antes fica guardado: se a fase não servir, dá para voltar a ele.
    await db.nutrition_plan_versions.insert_one({
        "id": str(uuid.uuid4()), "profile_id": perfil_id, "archived_at": agora,
        "reason": "periodizacao_inicio", "plan": ctx["plano"]})
    doc = {"id": str(uuid.uuid4()), "profile_id": perfil_id, "status": "ativa",
           "inicio": calendar_today().isoformat(), "criada_em": agora,
           "semana_aplicada": 1, "degrau": 0, **progressao,
           "historico": [{"semana": 1, "degrau": 0, "decisao": "inicio", "kcal": progressao["base"]["kcal"],
                          "carbs_g": progressao["base"]["carbs_g"], "em": agora,
                          "motivo": "Semana 1 é a sua dieta como ela está: a referência para as próximas."}]}
    await db[COLECAO].insert_one(dict(doc))
    return {"periodizacao": doc}


@router.post("/encerrar")
async def encerrar(request: Request, user=Depends(get_current_user)):
    """Encerra a fase. O plano fica como está na semana em que parou."""
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    r = await db[COLECAO].update_one({"profile_id": user["id"], "status": "ativa"},
                                     {"$set": {"status": "encerrada",
                                               "encerrada_em": datetime.now(timezone.utc).isoformat()}})
    if r.matched_count == 0:
        raise HTTPException(404, "Não há periodização em andamento.")
    return {"status": "encerrada"}

"""FORGE Nutrition API routes."""
import logging
import copy
import unicodedata
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timezone, timedelta, date as CalendarDate
from food_diary import DIARY_FOODS, food_snapshot
from lista_de_compras import montar_lista, anotar_peso_cru
from ciclagem_de_carboidrato import ciclar_por_sessao, classe_da_sessao, onde_colocar
from montagem_por_alimento import (buscar_para_montagem, espacos_da_refeicao,
                                   falta_escolher)
from engine import build_program_v2
from external_food_catalog import search_external_foods, resolve_external_food
import uuid, random

from auth import get_current_user
from billing_plans import (ALIMENTACAO, DIARIO_LIVRE, BUSCA_ALIMENTOS_PLANO, PROTOCOLOS_AGRESSIVOS, plano,
                           plano_minimo_com)
from entitlements import acesso_de, exigir_capacidade
from escolha_humana import escolhas_da_refeicao
import receitas as receitas_do_forge
from nutrition_import import restore_import_targets
from nutrition_engine import _intensity_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])

# Tentativas de regeneracao antes de desistir e devolver erro claro ao usuario.
GENERATION_ATTEMPTS = 6

from nutrition_engine import (
    compute_macro_targets, generate_daily_plan, validate_daily_plan, check_plan_hard_limits,
    normalizar_altura_cm,
    find_substitutes, recalculate_substitution_portion, FOOD_INDEX, tolerancia_de_caloria,
    FORGE_COACH_METHODOLOGY, sum_plan_totals,
    get_meal_archetype_options, redistribute_remaining_targets, aplicar_teto_de_carboidrato,
    calculate_meal_portions, calculate_meal_coherence_score, _infer_meal_type, generate_meal,
    build_food_item,
)


class NutritionAssessmentIn(BaseModel):
    weight_kg: float = Field(gt=0, le=300)
    height_cm: float = Field(gt=0, le=280)  # metros sao normalizados em _normalizar_medidas
    age: int = Field(ge=10, le=120)
    sex: str = "male"
    goal: str = "maintenance"
    # Intensidade do emagrecimento: "leve" | "moderado" | "agressivo". Opcional de
    # proposito — perfil antigo, sem escolha, segue no calculo legado (resolve_cut_protocol
    # devolve None) e nao tem o alvo calorico alterado por esta feature.
    intensity: Optional[str] = None
    activity_level: str = "moderate"
    training_days: int = Field(ge=1, le=7)
    meal_count: int = Field(ge=3, le=6)
    training_time: Optional[str] = None
    preferred_foods: List[str] = []
    disliked_foods: List[str] = []
    avoid_foods: List[str] = []
    allergies: List[str] = []
    dietary_restrictions: List[str] = []
    cooking_time: str = "medium"


class MealStatusIn(BaseModel):
    meal_index: int = Field(ge=0, le=5)
    status: Literal["completed", "skipped"] = "completed"
    date: Optional[CalendarDate] = None


class ConsumedFoodIn(BaseModel):
    food_id: str = Field(min_length=1, max_length=120)
    grams: float = Field(gt=0, le=5000, allow_inf_nan=False)


# As refeicoes do diario livre sao as MESMAS do motor de nutricao
# (`_REFEICAO_PARA_TAGS`), e nao uma lista nova. Se um dia a leitura semanal for olhar o
# que a pessoa comeu de verdade, os dois lados precisam falar a mesma lingua — duas
# taxonomias de refeicao no mesmo produto viram dois relatorios que nao batem.
REFEICOES_DO_DIARIO = {
    "breakfast": "Café da manhã",
    "morning_snack": "Lanche da manhã",
    "pre_workout": "Pré-treino",
    "post_workout": "Pós-treino",
    "lunch": "Almoço",
    "snack": "Lanche da tarde",
    "dinner": "Jantar",
    "supper": "Ceia",
}


class ConsumedMealIn(BaseModel):
    date: CalendarDate
    meal_index: Optional[int] = Field(default=None, ge=0, le=5)
    entry_id: uuid.UUID
    foods: List[ConsumedFoodIn] = Field(min_length=1, max_length=40)
    # Presente = diario livre ("registrei meu almoco"), que e do Elite. Ausente = o extra
    # anonimo de sempre, que o Pro continua tendo. Assim ninguem perde o que ja usava.
    refeicao: Optional[str] = None


class SubstituteFoodIn(BaseModel):
    meal_index: int = Field(ge=0)
    food_id: str
    food_index: Optional[int] = Field(default=None, ge=0)
    substitute_food_id: Optional[str] = None
    search: Optional[str] = Field(default=None, max_length=120)


class WeightLogIn(BaseModel):
    weight_kg: float = Field(gt=0, le=300)
    date: Optional[str] = None


class MealOptionsIn(BaseModel):
    meal_index: int = Field(ge=0)
    variety_seed: Optional[int] = None


class SwapFoodIn(BaseModel):
    meal_index: int = Field(ge=0)
    food_ids: List[str]
    food_id: str
    substitute_food_id: Optional[str] = None


class ItemManualIn(BaseModel):
    """Alimento que o motor nao sabe dimensionar, com a grama dita pela pessoa.

    Existe porque 234 dos 296 alimentos do catalogo vivem so no diario: tem macro, e nao
    tem papel nem limite de porcao. Chutar uma porcao confortavel para eles seria o motor
    afirmando com confianca algo que ele nao sabe.
    """
    food_id: str = Field(min_length=1, max_length=120)
    grams: float = Field(gt=0, le=2000)


class ComporRefeicaoIn(BaseModel):
    meal_index: int = Field(ge=0)
    manuais: List[ItemManualIn] = Field(default_factory=list, max_length=8)
    # Ate 8: o marcador de coerencia do motor ja pune prato com 6 ou mais itens, entao
    # aceitar uma lista longa seria convidar a pessoa a montar algo que o proprio motor
    # considera ruim.
    food_ids: List[str] = Field(default_factory=list, max_length=8)


class ObjetivoIn(BaseModel):
    """Trocar so o objetivo e o ritmo, sem refazer o questionario inteiro."""
    goal: str = Field(min_length=2, max_length=30)
    intensity: Optional[str] = Field(default=None, max_length=30)


class RefeicaoNovaIn(BaseModel):
    """Acrescentar uma refeicao ao plano, sem refazer o cardapio."""
    nome: str = Field(min_length=2, max_length=40)
    # Onde ela entra. None significa no fim.
    posicao: Optional[int] = Field(default=None, ge=0, le=5)


class ChooseMealIn(BaseModel):
    meal_index: int = Field(ge=0)
    archetype_id: str = "default"
    food_ids: List[str]
    # Opcional e com valor padrao: todo chamador que ja existia continua funcionando sem
    # mudar uma linha.
    manuais: List[ItemManualIn] = Field(default_factory=list, max_length=8)


class PreferenceIn(BaseModel):
    food_id: str
    signal: str = Field(pattern="^(liked|avoided|neutral)$")


def _build_empty_draft(targets, meal_count, goal):
    m = FORGE_COACH_METHODOLOGY
    dist = m["meal_distribution"].get(meal_count, m["meal_distribution"][4])
    names = m["meal_names"].get(meal_count, m["meal_names"][4])
    gc, gp, gf = targets["goal_calories"], targets["protein_g"], targets["fat_g"]
    meals = [{"name": names[i], "target_cal": round(gc * dist[i]), "target_protein": round(gp * dist[i]),
              "target_fat": round(gf * dist[i], 1), "foods": [], "archetype_id": None}
             for i in range(meal_count)]
    return {"meals": meals, "locked": [False] * meal_count, "targets": targets, "goal": goal, "meal_count": meal_count}


def _locked_used_ids(draft):
    used = set()
    for i, locked in enumerate(draft["locked"]):
        if locked:
            for it in draft["meals"][i]["foods"]:
                used.add(it["food_id"])
    return used


async def _load_preferences(db, profile_id):
    rows = await db.nutrition_preferences.find({"profile_id": profile_id}, {"_id": 0}).to_list(500)
    return {r["food_id"]: {"signal": r.get("signal", "neutral"), "chosen_count": r.get("chosen_count", 0)} for r in rows}


async def _record_choice_preferences(db, profile_id, food_ids):
    now = datetime.now(timezone.utc).isoformat()
    for fid in food_ids:
        await db.nutrition_preferences.update_one(
            {"profile_id": profile_id, "food_id": fid},
            {"$inc": {"chosen_count": 1}, "$set": {"updated_at": now},
             "$setOnInsert": {"signal": "neutral"}},
            upsert=True)


def owned_nutrition_target(user: dict, requested: Optional[str] = None) -> str:
    if user.get("role") == "SUPER_ADMIN":
        return requested or user["id"]
    return user["id"]


# Campos sem os quais compute_macro_targets nao roda. O onboarding de treino pode
# semear nutrition_assessment so com objetivo/intensidade; esse documento parcial nao
# pode passar por completo, senao a geracao quebraria com KeyError em vez de pedir o
# questionario.
CAMPOS_OBRIGATORIOS = ("weight_kg", "height_cm", "age", "training_days")


def _normalizar_medidas(dados: dict) -> dict:
    """
    Converte altura em metros para centimetros antes de gravar.

    O campo pede cm e a pessoa digita "1,63". Guardar isso como 1,63 cm produz uma TMB de
    algumas centenas de kcal e um plano inteiro errado — sem nenhum erro aparecer.
    """
    if dados.get("height_cm") is not None:
        dados["height_cm"] = normalizar_altura_cm(dados["height_cm"])
    return dados


def _assessment_completo(na) -> bool:
    return bool(na) and all(na.get(k) for k in CAMPOS_OBRIGATORIOS)


def _exigir_assessment(na, target, operacao):
    """400 com o motivo REAL no log do servidor.

    O perfil pode ter plano e nao ter questionario: ate a correcao do carry-forward em
    save_assessment, "Refazer avaliacao" fazia replace_one do perfil inteiro e levava o
    nutrition_assessment junto. Quem passou por isso ficava com o plano visivel e a
    regeneracao recusada."""
    if _assessment_completo(na):
        return
    faltando = [k for k in CAMPOS_OBRIGATORIOS if not (na or {}).get(k)]
    logger.warning("%s bloqueado para profile_id=%s: nutrition_assessment %s (faltando: %s)",
                   operacao, target, "ausente" if not na else "incompleto",
                   ", ".join(faltando) or "-")
    raise HTTPException(400, "Assessment nutricional nao encontrado. Faca o questionario primeiro.")


def _com_protocolo(na, targets):
    """Injeta no assessment o teto de carboidrato por alimento quando o protocolo tem um.

    Mesmo mecanismo que generate_daily_plan usa — _food_compatible e o portao unico de
    elegibilidade. Sem isto, o fluxo guiado ofereceria arroz e pao a quem escolheu o
    protocolo agressivo, e a tela diria "Agressivo" sobre um plano que nao e."""
    protocolo = (targets or {}).get("cut_protocol") or {}
    if protocolo.get("carb_mode") != "capped":
        return na
    cfg = FORGE_COACH_METHODOLOGY["cutting_intensity"][protocolo["intensity"]]
    return {**(na or {}), "_max_food_carb_g_per_100g": cfg["max_food_carb_g_per_100g"]}


@router.get("/assessment")
async def get_assessment(request: Request, user=Depends(get_current_user)):
    """Devolve o questionario salvo para a tela abrir com as escolhas ja feitas —
    inclusive a intensidade vinda do onboarding. Antes isto era um stub que so devolvia
    uma mensagem, entao a area de Alimentacao sempre reabria em branco."""
    db = request.app.state.db
    profile = await db.profiles.find_one({"id": user["id"]}, {"_id": 0, "nutrition_assessment": 1})
    na = (profile or {}).get("nutrition_assessment")
    return {"assessment": na or None, "complete": _assessment_completo(na)}


# Suplementos proteicos do catalogo — usados so para rotular a opcao na interface.
SUPLEMENTOS = {"whey-protein", "rice-cream-whey"}


def _macros_da_porcao(food_id, grams):
    f = FOOD_INDEX.get(food_id) or {}
    k = grams / max(1, f.get("grams") or 100)
    return {"kcal": round(f.get("kcal", 0) * k),
            "protein_g": round(f.get("protein_g", 0) * k, 1),
            "carbs_g": round(f.get("carbs_g", 0) * k, 1),
            "fat_g": round(f.get("fat_g", 0) * k, 1)}


def _selo(food_id, macros, macros_originais, mais_equivalente):
    """Selo discreto da opcao. Deriva dos dados reais do alimento e da comparacao com o
    original — a interface so renderiza, sem recalcular nada."""
    if mais_equivalente:
        return "Mais equivalente"
    if food_id in SUPLEMENTOS:
        return "Suplemento"
    tags = (FOOD_INDEX.get(food_id) or {}).get("tags") or []
    if macros["fat_g"] > macros_originais["fat_g"] + 5 or "fattier_protein" in tags:
        return "Maior teor de gordura"
    if "quick" in tags:
        return "Pratica"
    return None


def _opcoes_de_intensidade(nome_do_conjunto, permite_agressivo: bool = True):
    """Os ritmos de um objetivo, cada um sabendo se ESTA conta pode usa-lo.

    `locked` existe porque a tela precisa da mesma verdade que a rota de gravacao. Sem
    ele, o ritmo Agressivo aparecia escolhivel para todo mundo e so era recusado DEPOIS
    do clique em salvar — a pessoa selecionava, esperava, e levava "seu plano atual nao
    inclui este recurso". Oferecer e depois recusar e pior do que nao oferecer.

    Bloqueado aparece, e nao some: esconder faria a pessoa achar que o produto nao tem o
    recurso, quando na verdade ela e que nao escolheu o plano que tem. E a mesma decisao
    ja tomada no catalogo do questionario (`preassessment._objetivos_alimentares`).
    """
    cfg = FORGE_COACH_METHODOLOGY[nome_do_conjunto]
    return [
        {"id": k, "label": v["label"], "description": v["description"],
         "recommended": bool(v.get("recommended")), "advanced": bool(v.get("advanced")),
         "locked": bool(v.get("advanced")) and not permite_agressivo,
         "warning": v.get("warning"),
         # negativo = deficit, positivo = superavit; a interface so precisa do numero
         "delta_pct": round((v["kcal_pct"] - 1) * 100),
         "protein_g_per_kg": v["protein_g_per_kg"],
         "carb_range_g": ([v["carb_min_g"], v["carb_max_g"]]
                          if v.get("carb_mode") == "capped" else None)}
        for k, v in cfg.items()
    ]


@router.get("/goal-catalog")
async def goal_catalog(request: Request, user=Depends(get_current_user)):
    """Objetivos corporais e os ritmos de cada um, numa chamada so.

    A secao "Objetivo" do onboarding trata apenas do objetivo corporal/alimentar:
    desempenho e prioridade muscular sao outras etapas. Manutencao nao tem ritmo.

    Le o acesso da conta para marcar `locked` nos ritmos que este plano nao inclui. Esta
    rota alimenta as DUAS telas onde se escolhe o ritmo — o questionario e a troca de
    objetivo na Nutricao — entao e aqui que a oferta passa a bater com o que a gravacao
    aceita."""
    acesso = await acesso_de(request.app.state.db, user)
    permite_agressivo = PROTOCOLOS_AGRESSIVOS in (acesso.get("capabilities") or [])
    conjuntos = {"muscle_gain": "bulking_intensity", "fat_loss": "cutting_intensity"}
    padroes = {"muscle_gain": FORGE_COACH_METHODOLOGY["bulking_intensity_default"],
               "fat_loss": FORGE_COACH_METHODOLOGY["cutting_intensity_default"]}
    return {
        "protocol_version": FORGE_COACH_METHODOLOGY["cut_protocol_version"],
        # O nome do plano que libera o que esta bloqueado. A tela mostra isso em vez de um
        # card morto: quem quiser o ritmo agressivo precisa saber ONDE ele esta. Vem da
        # tabela de planos, nunca escrito a mao — a capacidade ja trocou de plano uma vez.
        "plan_for_advanced": (plano_minimo_com(PROTOCOLOS_AGRESSIVOS) or {}).get("nome"),
        "current_plan": (plano(acesso.get("plan_code")) or {}).get("nome"),
        "goals": [
            {**g,
             "default_intensity": padroes.get(g["id"]),
             "intensities": (_opcoes_de_intensidade(conjuntos[g["id"]], permite_agressivo)
                             if g["id"] in conjuntos else [])}
            for g in FORGE_COACH_METHODOLOGY["body_goals"]
        ],
    }


@router.get("/cutting-intensities")
async def cutting_intensities(request: Request, user=Depends(get_current_user)):
    """Catalogo das intensidades de emagrecimento. A UI monta os cards a partir daqui em
    vez de repetir rotulo, descricao e aviso — a metodologia continua com uma fonte so."""
    acesso = await acesso_de(request.app.state.db, user)
    opcoes = _opcoes_de_intensidade(
        "cutting_intensity", PROTOCOLOS_AGRESSIVOS in (acesso.get("capabilities") or []))
    return {
        "default": FORGE_COACH_METHODOLOGY["cutting_intensity_default"],
        "protocol_version": FORGE_COACH_METHODOLOGY["cut_protocol_version"],
        # deficit_pct e mantido (positivo) para nao quebrar quem ja consome este endpoint
        "options": [{**o, "deficit_pct": -o["delta_pct"]} for o in opcoes],
    }


async def _atualizar_meta_do_plano(db, target: str, na: dict) -> bool:
    """
    Recalcula `targets` do plano ja gravado a partir do questionario recem-salvo.

    Devolve True quando atualizou. Questionario incompleto, plano inexistente ou conta sem
    dados suficientes nao sao erro: nao ha o que recalcular, e a chamada segue em silencio
    — salvar a avaliacao nao pode falhar por causa disto.
    """
    if not _assessment_completo(na):
        return False
    stored = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0, "plan": 1})
    if not stored or not stored.get("plan"):
        return False
    if stored["plan"].get("source") == "manual_import":
        return False
    try:
        targets = compute_macro_targets(
            na["weight_kg"], na["height_cm"], na["age"], na.get("sex") or "male",
            na["training_days"], na.get("goal") or "maintenance",
            na.get("activity_level", "moderate"), na.get("intensity"))
    except Exception:  # noqa: BLE001 — questionario torto nao pode derrubar o salvamento
        logger.warning("nao foi possivel recalcular a meta do plano de profile_id=%s", target)
        return False
    await db.nutrition_plans.update_one({"profile_id": target}, {"$set": {"plan.targets": targets}})
    return True


@router.post("/assessment")
async def save_assessment(payload: NutritionAssessmentIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"] if user.get("role") == "ATHLETE" else user["id"]
    # "1,63" no campo que pede centimetros vira 1,63 cm sem isto, e o plano inteiro sai
    # errado sem nenhum erro aparecer.
    doc = _normalizar_medidas(payload.model_dump())
    # O modo Agressivo/Atleta e pago. Checado aqui, onde a escolha e gravada:
    # e o unico ponto por onde ela entra, entao nao ha como contornar chamando outra rota.
    if _intensity_key(doc.get("intensity")) == "agressivo":
        await exigir_capacidade(db, user, PROTOCOLOS_AGRESSIVOS)
    if not (doc.get("intensity") or "").strip():
        # O formulario manda intensity:"" quando o campo nao foi tocado. Isso apagaria em
        # silencio a escolha feita no onboarding, entao o valor anterior e carregado
        # adiante. Uma escolha explicita (string preenchida) continua vencendo.
        anterior = await db.profiles.find_one({"id": target}, {"_id": 0, "nutrition_assessment": 1})
        doc["intensity"] = ((anterior or {}).get("nutrition_assessment") or {}).get("intensity")
    doc["profile_id"] = target
    doc["user_id"] = target
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    doc["assessment_version"] = 1
    await db.nutrition_assessments.insert_one(doc)
    doc.pop("_id", None)  # insert_one mutates doc in place, adding a non-JSON-serializable ObjectId
    await db.profiles.update_one({"id": target}, {"$set": {"nutrition_assessment": doc}}, upsert=True)

    # A META DO PLANO ACOMPANHA O QUESTIONARIO.
    #
    # Sem isto, corrigir peso, altura ou objetivo nao mudava nada na tela: o plano ja
    # gravado seguia anunciando a meta de quando foi gerado. Foi assim que uma atleta
    # corrigiu a altura, viu o questionario certo, e continuou olhando uma meta de 427 kcal
    # — o numero nao vinha do dado novo, vinha de um plano velho que ninguem tocou.
    #
    # So a META e recalculada. As refeicoes ficam onde estao: a pessoa escolheu aquilo, e
    # jogar fora o plano dela porque mudou de peso seria pior que o defeito. O que a tela
    # passa a mostrar e a verdade — o que ela PRECISA contra o que o plano ENTREGA — e
    # regerar continua sendo uma decisao dela.
    atualizados = await _atualizar_meta_do_plano(db, target, doc)
    return {"assessment": doc, "assessment_version": 1, "plan_targets_updated": atualizados}


@router.put("/goal")
async def trocar_objetivo(payload: ObjetivoIn, request: Request, user=Depends(get_current_user)):
    """Trocar o objetivo alimentar e o ritmo direto da Nutricao.

    Antes, mudar de emagrecimento para ganho de massa exigia refazer o questionario
    inteiro — peso, altura, idade, dias, refeicoes, tudo — para alterar dois campos. O
    atleta pediu o botao, e ele esta certo: objetivo e a coisa que mais muda ao longo do
    ano, e era a mais cara de mudar.

    A meta calorica e os macros sao recalculados na hora. O CARDAPIO nao e regerado: as
    refeicoes continuam as que a pessoa escolheu, e ela decide se quer refazer o plano. Um
    plano montado refeicao por refeicao sumindo sozinho seria pior que um alvo novo.
    """
    db = request.app.state.db
    target = user["id"]
    await exigir_capacidade(db, user, ALIMENTACAO)

    objetivos = {g["id"] for g in FORGE_COACH_METHODOLOGY["body_goals"]}
    if payload.goal not in objetivos:
        raise HTTPException(400, f"Objetivo desconhecido. Use um de: {', '.join(sorted(objetivos))}.")

    # Mesma guarda da rota do questionario, e pelo mesmo motivo: o modo Agressivo/Atleta
    # e pago. Sem repetir aqui, esta rota viraria o contorno.
    if _intensity_key(payload.intensity) == "agressivo":
        await exigir_capacidade(db, user, PROTOCOLOS_AGRESSIVOS)

    perfil = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = dict((perfil or {}).get("nutrition_assessment") or {})
    _exigir_assessment(na, target, "trocar objetivo")

    anterior = {"goal": na.get("goal"), "intensity": na.get("intensity")}
    na["goal"] = payload.goal
    # Objetivo sem ritmo proprio (manutencao) limpa a intensidade em vez de carregar a
    # anterior: "manutencao agressiva" nao existe, e guardar isso faria o calculo aplicar um
    # deficit que a pessoa nao pediu quando ela voltasse para emagrecimento.
    na["intensity"] = payload.intensity or None

    await db.profiles.update_one({"id": target}, {"$set": {"nutrition_assessment": na}})
    recalculou = await _atualizar_meta_do_plano(db, target, na)

    alvos = compute_macro_targets(
        na["weight_kg"], na["height_cm"], na["age"], na.get("sex") or "male",
        na["training_days"], na["goal"], na.get("activity_level", "moderate"),
        na.get("intensity"))
    return {"goal": na["goal"], "intensity": na["intensity"], "anterior": anterior,
            "targets": alvos, "plano_atualizado": recalculou}


@router.post("/generate")
async def generate_plan(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment")
    _exigir_assessment(na, target, "gerar plano")
    targets = compute_macro_targets(
        na["weight_kg"], na["height_cm"], na["age"], na["sex"],
        na["training_days"], na["goal"], na.get("activity_level", "moderate"),
        na.get("intensity"))

    # Gera -> valida -> so entao persiste. Antes, o plano era salvo primeiro e
    # validate_daily_plan devolvia avisos que ninguem bloqueava: um plano fora dos limites
    # do protocolo substituia um plano valido e ainda era apresentado como correto. Uma
    # nova semente por tentativa e o proprio mecanismo de regeneracao do motor.
    plan, errors = None, []
    for _ in range(GENERATION_ATTEMPTS):
        candidate = generate_daily_plan(targets, na, na.get("meal_count", 4), na["goal"],
                                        random.randint(0, 999))
        errors = check_plan_hard_limits(candidate, targets)
        if not errors:
            plan = candidate
            break
    if plan is None:
        # Nada e gravado: o plano anterior, valido, continua de pe.
        raise HTTPException(422, {
            "message": "Nao foi possivel gerar um plano dentro dos limites do protocolo escolhido.",
            "errors": errors})

    doc = {"profile_id": target, "user_id": target, "plan": plan, "created_at": datetime.now(timezone.utc).isoformat(),
           "engine_version": FORGE_COACH_METHODOLOGY["engine_version"],
           "methodology_version": FORGE_COACH_METHODOLOGY["coach_version"],
           "intensity": (targets.get("cut_protocol") or {}).get("intensity"),
           "cut_protocol": targets.get("cut_protocol")}
    await db.nutrition_plans.replace_one({"profile_id": target}, doc, upsert=True)
    warnings = validate_daily_plan(plan, targets, na)
    return {"plan": plan, "targets": targets, "warnings": warnings}


@router.get("/plan")
async def get_plan(request: Request, user=Depends(get_current_user)):
    """Plano ativo com metas preservadas da dieta importada confirmada."""
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    target = user["id"]
    stored = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0})
    if not stored:
        raise HTTPException(404, "Plano nÃ£o encontrado. Gere primeiro via POST /api/nutrition/generate.")
    stored = await restore_import_targets(db, target, stored)
    if not stored:
        raise HTTPException(404, "Plano não encontrado.")
    # O peso cru e etiqueta, nao dado do plano: entra na resposta e nao no que esta gravado.
    return anotar_peso_cru(stored["plan"])


MAXIMO_DE_REFEICOES = 6


@router.post("/plan/add-meal")
async def acrescentar_refeicao(payload: RefeicaoNovaIn, request: Request,
                               user=Depends(get_current_user)):
    """Acrescentar uma refeicao ao plano, na posicao que a pessoa escolher.

    O caso do atleta: ele tem cafe da manha e quer um PRE-TREINO antes. Ate aqui a unica
    forma era refazer o questionario mudando a quantidade de refeicoes, o que joga fora o
    cardapio inteiro.

    A parte que precisa ser dita: acrescentar uma refeicao faz as OUTRAS ENCOLHEREM. O dia
    tem a mesma caloria; ela passa a ser dividida em mais partes. Entao as refeicoes que ja
    existiam mantem os ALIMENTOS que a pessoa escolheu e tem as PORCOES recalculadas — que
    e o que um treinador faz, e nao apagar o cardapio para comecar de novo.
    """
    db = request.app.state.db
    target = user["id"]
    await exigir_capacidade(db, user, ALIMENTACAO)

    guardado = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0})
    plano = (guardado or {}).get("plan")
    if not plano or not plano.get("meals"):
        raise HTTPException(404, "Plano não encontrado. Gere um plano antes de acrescentar refeições.")

    refeicoes = list(plano["meals"])
    if len(refeicoes) >= MAXIMO_DE_REFEICOES:
        raise HTTPException(
            400, f"O plano já tem {len(refeicoes)} refeições, que é o máximo. "
                 "Renomeie ou troque uma que já existe.")

    perfil = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (perfil or {}).get("nutrition_assessment") or {}
    objetivo = na.get("goal") or "maintenance"
    alvos = plano.get("targets") or {}

    posicao = payload.posicao if payload.posicao is not None else len(refeicoes)
    posicao = max(0, min(posicao, len(refeicoes)))
    refeicoes.insert(posicao, {"name": payload.nome.strip(), "foods": [], "archetype_id": None})

    # A divisao do dia muda porque o numero de refeicoes mudou. Sem isto, a refeicao nova
    # entraria "de graca" e o dia somaria acima da meta.
    quantas = len(refeicoes)
    m = FORGE_COACH_METHODOLOGY
    dist = m["meal_distribution"].get(quantas, m["meal_distribution"][4])
    gc = float(alvos.get("goal_calories") or 0)
    gp = float(alvos.get("protein_g") or 0)
    gf = float(alvos.get("fat_g") or 0)

    for i, refeicao in enumerate(refeicoes):
        fatia = dist[i] if i < len(dist) else dist[-1]
        refeicao["target_cal"] = round(gc * fatia)
        refeicao["target_protein"] = round(gp * fatia)
        refeicao["target_fat"] = round(gf * fatia, 1)

        if i == posicao:
            # A refeicao nova nasce montada, e nao vazia: plano com um buraco no meio nao e
            # plano. Quem quiser trocar usa o "Montar refeicao por refeicao".
            nova = generate_meal(refeicao["name"], _infer_meal_type(refeicao["name"]),
                                 refeicao["target_cal"], refeicao["target_protein"],
                                 refeicao["target_fat"], na, set(), objetivo)
            refeicao["foods"] = nova.get("foods") or []
            continue

        # As que ja existiam mantem os ALIMENTOS e mudam a PORCAO.
        ids = [item["food_id"] for item in (refeicao.get("foods") or [])]
        if not ids:
            continue
        porcoes = calculate_meal_portions(ids, refeicao["target_cal"], refeicao["target_protein"],
                                          refeicao["target_fat"], objetivo)
        refeicao["foods"] = [build_food_item(fid, porcoes.get(fid, 100)) for fid in ids]

    plano["meals"] = refeicoes
    await db.nutrition_plans.update_one({"profile_id": target}, {"$set": {"plan": plano}})
    # O questionario passa a refletir a quantidade nova, senao a proxima geracao voltaria
    # para a contagem antiga e a refeicao acrescentada sumiria sem aviso.
    if na:
        na["meal_count"] = min(MAXIMO_DE_REFEICOES, max(3, quantas))
        await db.profiles.update_one({"id": target}, {"$set": {"nutrition_assessment": na}})

    return {"plan": anotar_peso_cru(plano), "meal_count": quantas, "posicao": posicao}


@router.post("/substitute")
async def substitute_food(payload: SubstituteFoodIn, request: Request, user=Depends(get_current_user)):
    # target is always derived from the authenticated identity, never from client input —
    # this endpoint can only ever read/write the caller's own plan (no profile_id in the
    # payload at all), which is what makes cross-athlete IDOR structurally impossible here.
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    if payload.search is not None:
        await exigir_capacidade(db, user, BUSCA_ALIMENTOS_PLANO)
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    meal_idx = payload.meal_index
    food_id = payload.food_id

    stored = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0})
    if not stored or not stored.get("plan", {}).get("meals"):
        raise HTTPException(404, "Plano nao encontrado")
    plan = stored["plan"]
    original_meals = copy.deepcopy(plan.get("meals", []))
    meals = plan.get("meals", [])
    if meal_idx >= len(meals):
        raise HTTPException(400, "Indice de refeicao invalido")
    meal = meals[meal_idx]
    foods = meal.get("foods", [])

    if payload.food_index is not None:
        if payload.food_index >= len(foods) or foods[payload.food_index].get("food_id") != food_id:
            raise HTTPException(400, "Indice de alimento invalido")
        food_pos = payload.food_index
    else:
        food_pos = next((idx for idx, f in enumerate(foods) if f.get("food_id") == food_id), None)
        if food_pos is None:
            raise HTTPException(404, "Alimento nao encontrado na refeicao")

    original = foods[food_pos]
    current_foods = [f["food_id"] for f in foods]

    # find_substitutes() re-runs the full engine pipeline (allergies, avoid_foods,
    # dietary_restrictions, goal-directional tolerance, daily guardrails) against the
    # CURRENT persisted plan state — recomputed fresh on every call, list or apply, so a
    # stale client can never smuggle through a food that isn't valid right now.
    # meal_type/meal_target_* enable role-aware DNA-family candidates and simulation-based
    # portion equivalence (item 1/2); meals persisted before this field existed simply
    # fall back to the older calorie-equivalence sizing (has_meal_target=False upstream).
    # 6 e nao 3: o pedido e por 4 a 6 opcoes maduras para um alimento comum, e o pool
    # de candidatos agora comporta isso (ver _substitution_candidates).
    subs = find_substitutes(
        food_id, na, current_foods, max_results=len(FOOD_INDEX) if payload.search is not None else 6, orig_grams=original.get("grams", 100),
        goal=na.get("goal", "maintenance"), meal=foods,
        daily_totals=plan.get("daily_totals", {}), targets=plan.get("targets", {}),
        meal_type=_infer_meal_type(meal.get("name", "")),
        meal_target_cal=meal.get("target_cal"), meal_target_protein=meal.get("target_protein"),
        meal_target_fat=meal.get("target_fat"))

    options = []
    matched = None
    for s in subs:
        fid, grams, reason = s[0], s[1], s[2]
        opt = {**build_food_item(fid, grams), "reason": reason}
        if len(s) >= 4:
            evald = s[3]
            opt.update({
                "direction": evald.get("direction"), "goal_compatible": evald.get("goal_compatible"),
                "local_delta_kcal": evald.get("local_delta_kcal"), "daily_delta_kcal": evald.get("daily_delta_kcal"),
                "valid": evald.get("valid"), "sizing": evald.get("sizing"),
                "_sim": {k: evald.get(k) for k in ("sim_cal", "sim_protein", "sim_fat")},
            })
        opt["macros"] = _macros_da_porcao(fid, grams)
        options.append(opt)
        if payload.substitute_food_id and fid == payload.substitute_food_id:
            matched = opt

    # Macros da porcao ORIGINAL: e contra ela que a diferenca e mostrada.
    macros_orig = _macros_da_porcao(food_id, original.get("grams", 100))
    mais_equiv = min(options, key=lambda o: abs(o["macros"]["kcal"] - macros_orig["kcal"]),
                     default=None)
    for o in options:
        o["delta_kcal"] = o["macros"]["kcal"] - macros_orig["kcal"]
        o["badge"] = _selo(o["food_id"], o["macros"], macros_orig,
                           mais_equiv is not None and o is mais_equiv)

    if payload.search is not None and not payload.substitute_food_id:
        def normalized(value):
            return unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().casefold()
        terms = normalized(payload.search).split()
        options = [o for o in options if all(term in normalized(o.get("food", {}).get("name", o["food_id"])) for term in terms)]
    if not payload.substitute_food_id:
        return {"original": food_id, "original_macros": macros_orig,
                "options": [{k: v for k, v in o.items() if k != "_sim"} for o in options]}

    if not matched:
        raise HTTPException(400, "Substituicao nao permitida para este alimento e objetivo atual")

    # Backend remains the sole source of truth for grams/macros. When the meal carries a
    # real target (role-aware equivalence was used to find this candidate), every item in
    # the meal must be re-persisted at its simulated portion — not just the swapped slot —
    # since calculate_meal_portions resized the WHOLE meal around the swap (item 2:
    # "reconcilie os demais componentes da refeicao"). Leaving the other items at their
    # pre-swap grams would silently drift the persisted meal away from its own target.
    # O que se aplica tem que ser EXATAMENTE o que foi validado. O motor informa qual
    # dimensionamento aprovou a opcao: "meal_sim" redimensiona a refeicao inteira em torno
    # dos totais que ela entrega HOJE (a mesma referencia da validacao — usar o alvo
    # nominal aqui reconstruiria a refeicao de outro jeito e o dia sairia da faixa),
    # "one_to_one" troca so o alimento escolhido e preserva os demais.
    sim = matched.get("_sim") or {}
    if matched.get("sizing") == "meal_sim" and sim.get("sim_cal") is not None:
        new_food_ids = [matched["food_id"] if i == food_pos else f["food_id"] for i, f in enumerate(foods)]
        portions = calculate_meal_portions(new_food_ids, sim["sim_cal"], sim["sim_protein"],
                                            sim.get("sim_fat") or 0, na.get("goal", "maintenance"))
        new_foods = [build_food_item(fid, portions.get(fid, foods[i].get("grams", 100)))
                     for i, fid in enumerate(new_food_ids)]
    else:
        new_foods = list(foods)
        new_foods[food_pos] = build_food_item(matched["food_id"], matched["grams"])

    meal["foods"] = new_foods
    meals[meal_idx] = meal
    plan["meals"] = meals
    new_totals = sum_plan_totals(meals)
    plan["daily_totals"] = new_totals

    # Targeted, precise field update instead of replacing the whole document — a concurrent
    # request touching a different meal/food never gets clobbered by this write.
    selection = {"profile_id": target}
    if payload.search is not None:
        selection["plan.meals"] = original_meals
    result = await db.nutrition_plans.update_one(
        selection,
        {"$set": {
            f"plan.meals.{meal_idx}.foods": new_foods,
            "plan.daily_totals": new_totals,
        }},
    )

    if payload.search is not None and result.matched_count == 0:
        raise HTTPException(409, "O plano mudou em outra tela. Reabra a refeicao e tente novamente.")

    return {
        "original": food_id, "options": options, "applied": True,
        "meal_index": meal_idx, "food_index": food_pos,
        "food": new_foods[food_pos], "daily_totals": new_totals, "plan": plan,
    }


# ─── Guided flow (RESET_PLAN / MEAL_ARCHETYPES / FORGE_CHOOSES_FOR_ME) ─────────────
# "Refazer plano" replaces the old one-shot Regenerar. It only ever touches the plan
# draft below and, on confirm, the single nutrition_plans document — never the
# assessment, weight history, adherence, or the Training Engine. Legacy POST /generate
# is untouched and remains the fallback ("FORGE monta tudo de uma vez").

@router.post("/plan/reset")
async def reset_plan_draft(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment")
    _exigir_assessment(na, target, "refazer plano")
    # A intensidade faltava aqui: refazer o plano recalculava com o caminho legado e
    # descartava o protocolo escolhido, enquanto /generate ja o respeitava.
    targets = compute_macro_targets(
        na["weight_kg"], na["height_cm"], na["age"], na["sex"],
        na["training_days"], na["goal"], na.get("activity_level", "moderate"),
        na.get("intensity"))
    meal_count = na.get("meal_count", 4)
    draft = _build_empty_draft(targets, meal_count, na["goal"])
    doc = {"profile_id": target, "user_id": target, "created_at": datetime.now(timezone.utc).isoformat(), **draft}
    await db.nutrition_plan_drafts.replace_one({"profile_id": target}, doc, upsert=True)
    doc.pop("_id", None)
    return doc


@router.get("/plan/draft")
async def get_plan_draft(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento. Chame /plan/reset primeiro.")
    return draft


@router.post("/plan/draft/options")
async def draft_meal_options(payload: MealOptionsIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento. Chame /plan/reset primeiro.")
    idx = payload.meal_index
    if idx >= len(draft["meals"]):
        raise HTTPException(400, "Indice de refeicao invalido")
    goal = draft.get("goal", na.get("goal", "maintenance"))
    na = _com_protocolo(na, draft.get("targets"))
    meal = draft["meals"][idx]
    preferences = await _load_preferences(db, target)
    # "Mostrar outras opcoes": a fresh seed shifts which concrete foods each archetype
    # resolves to (existing rotation mechanism), without touching any guardrail.
    seed = payload.variety_seed if payload.variety_seed is not None else random.randint(0, 999)
    options = get_meal_archetype_options(
        meal["name"], meal["target_cal"], meal["target_protein"], meal.get("target_fat", 0),
        na, _locked_used_ids(draft), goal, None, idx, preferences, 5, seed)
    return {"meal_index": idx, "target_cal": meal["target_cal"], "target_protein": meal["target_protein"],
            # `metodo` chega a tela para a opcao poder se identificar como sendo o padrao do
            # treinador. Sem isso ela viria como mais uma da lista, e a pessoa nao teria como
            # saber que aquela e a combinacao que ele usa com os alunos dele.
            "options": [{
                "archetype_id": o["archetype_id"], "label": o["label"], "coherence_score": o["coherence_score"],
                "metodo": bool(o.get("metodo")),
                "foods": [build_food_item(it["food_id"], it["grams"]) for it in o["meal"]["foods"]],
            } for o in options]}


@router.post("/plan/draft/swap-food")
async def draft_swap_food(payload: SwapFoodIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento.")
    idx = payload.meal_index
    if idx >= len(draft["meals"]):
        raise HTTPException(400, "Indice de refeicao invalido")
    if payload.food_id not in payload.food_ids:
        raise HTTPException(400, "food_id nao esta na combinacao atual")
    goal = draft.get("goal", na.get("goal", "maintenance"))
    meal_target = draft["meals"][idx]

    # The structure the athlete picked stays put — only this one food's slot changes,
    # and portions are recalculated for the whole combination afterward.
    current_portions = calculate_meal_portions(
        payload.food_ids, meal_target["target_cal"], meal_target["target_protein"],
        meal_target.get("target_fat", 0), goal)
    orig_grams = current_portions.get(payload.food_id, 100)
    current_foods = [build_food_item(fid, current_portions.get(fid, 100)) for fid in payload.food_ids]
    locked_totals = sum_plan_totals([draft["meals"][i] for i, l in enumerate(draft["locked"]) if l])

    # validate_daily=False: the draft day is still in progress (locked_totals only covers
    # meals confirmed so far), so the whole-day guardrail would reject every substitution.
    # meal_type/meal_target_* give role-aware DNA-family candidates sized by simulating
    # THIS meal — the fix for "Nenhuma alternativa disponivel agora" (item 1/2).
    subs = find_substitutes(
        payload.food_id, na, payload.food_ids, max_results=3, orig_grams=orig_grams,
        goal=goal, meal=current_foods, daily_totals=locked_totals, targets=draft["targets"],
        meal_type=_infer_meal_type(meal_target.get("name", "")),
        meal_target_cal=meal_target["target_cal"], meal_target_protein=meal_target["target_protein"],
        meal_target_fat=meal_target.get("target_fat", 0), validate_daily=False)
    options = [{**build_food_item(s[0], s[1]), "reason": s[2]} for s in subs]

    if not payload.substitute_food_id:
        return {"meal_index": idx, "food_id": payload.food_id, "options": options}

    matched = next((o for o in options if o["food_id"] == payload.substitute_food_id), None)
    if not matched:
        raise HTTPException(400, "Substituicao nao permitida para este alimento e objetivo atual")

    new_food_ids = [matched["food_id"] if fid == payload.food_id else fid for fid in payload.food_ids]
    portions = calculate_meal_portions(
        new_food_ids, meal_target["target_cal"], meal_target["target_protein"],
        meal_target.get("target_fat", 0), goal)
    foods = [build_food_item(fid, portions.get(fid, 100)) for fid in new_food_ids]
    return {"meal_index": idx, "foods": foods, "applied": True}


def _item_manual(fid: str, gramas: float) -> dict:
    """Entrada de refeicao para um alimento que so existe no diario.

    `build_food_item` busca em FOOD_INDEX e devolveria `food: {}` para estes — a tela
    mostraria uma linha sem nome. Aqui o alimento vem do catalogo do diario, que e onde
    ele vive.
    """
    from food_diary import DIARY_FOODS
    alimento = DIARY_FOODS.get(fid)
    if not alimento:
        raise HTTPException(422, "Alimento nao encontrado no catalogo.")
    return {"food_id": fid, "grams": round(float(gramas), 1), "food": alimento,
            "manual": True}


def _somar_macros(itens) -> dict:
    """Soma o que os itens entregam de verdade, pela grama de cada um.

    Serve aos dois tipos: o dimensionado pelo motor e o que a pessoa pesou. O catalogo do
    diario contem o do motor, entao um lookup so resolve os dois.
    """
    from food_diary import DIARY_FOODS
    totais = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for item in itens:
        base = DIARY_FOODS.get(item["food_id"]) or {}
        fator = item["grams"] / max(1, base.get("grams", 100))
        totais["kcal"] += (base.get("kcal", 0) or 0) * fator
        totais["protein_g"] += (base.get("protein_g", 0) or 0) * fator
        totais["carbs_g"] += (base.get("carbs_g", 0) or 0) * fator
        totais["fat_g"] += (base.get("fat_g", 0) or 0) * fator
    return {k: round(v, 1) for k, v in totais.items()}


def _alvos_de_macro(refeicao: dict) -> dict:
    """Proteina, carboidrato e gordura que a refeicao precisa entregar.

    O carboidrato nao e gravado no rascunho: ele e o macro RESIDUAL — o que sobra da
    caloria depois da proteina e da gordura. Derivar aqui e o mesmo calculo que o motor faz
    em `calculate_carb_target`, e nao um numero paralelo.
    """
    cal = float(refeicao.get("target_cal") or 0)
    prot = float(refeicao.get("target_protein") or 0)
    gord = float(refeicao.get("target_fat") or 0)
    return {"protein_g": round(prot), "fat_g": round(gord),
            "carbs_g": max(0, round((cal - prot * 4 - gord * 9) / 4))}


def _dia_do_rascunho(draft: dict, idx: int, totais_desta: dict) -> dict:
    """Como o DIA fica se esta refeicao for confirmada assim.

    A tela de montagem so olhava a refeicao. Mas quem tem 2.000 kcal para bater nao se
    importa se o cafe da manha passou 80: importa se o DIA fecha. E o dia fecha, porque as
    refeicoes seguintes passam a mirar o que sobrou (`redistribute_remaining_targets`).

    A tolerancia nao e inventada aqui: vem de `tolerancia_de_caloria`, que vive no metodo
    do FORGE. Sao 5% com piso de 150 kcal, entao em 2.000 kcal da os 150 para cima ou para
    baixo que o treinador definiu — "isso depois a gente corta no treino".
    """
    alvo_do_dia = float((draft.get("targets") or {}).get("goal_calories") or 0)
    travado = 0.0
    for i, refeicao in enumerate(draft.get("meals") or []):
        if i == idx or not (draft.get("locked") or [])[i]:
            continue
        travado += _somar_macros(refeicao.get("foods") or [])["kcal"]

    desta = float(totais_desta.get("kcal") or 0)
    somado = travado + desta
    tolerancia = round(tolerancia_de_caloria(alvo_do_dia))
    # Quantas refeicoes ainda vao entrar. Enquanto houver alguma, o que sobra nao e "erro":
    # e orcamento que ainda vai ser gasto, e dizer "voce esta 900 kcal abaixo" assustaria
    # sem motivo.
    faltam = sum(1 for i, t in enumerate(draft.get("locked") or [])
                 if not t and i != idx)

    return {
        "alvo": round(alvo_do_dia),
        "ja_escolhido": round(somado),
        "restante": round(alvo_do_dia - somado),
        "tolerancia": tolerancia,
        "refeicoes_faltando": faltam,
        # So faz sentido julgar o dia quando ele esta completo. Antes disso o numero e
        # parcial por construcao.
        "fechado": faltam == 0,
        "dentro_da_tolerancia": abs(somado - alvo_do_dia) <= tolerancia,
    }


@router.get("/plan/draft/search-food")
async def draft_search_food(request: Request, q: str = Query(min_length=2, max_length=80),
                            user=Depends(get_current_user)):
    """Busca livre no catalogo, para quem ja sabe o que quer comer.

    `dimensionavel` diz como o alimento entra: `true` e o motor calcula a grama junto com o
    resto da refeicao; `false` e a pessoa informa, porque o alimento nao tem papel nem
    limite de porcao definidos e chutar isso seria inventar.
    """
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    perfil = await db.profiles.find_one({"id": user["id"]}, {"_id": 0})
    na = (perfil or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": user["id"]}, {"_id": 0})
    if draft:
        na = _com_protocolo(na, draft.get("targets"))
    achados = buscar_para_montagem(q, na)
    # "Nenhum alimento com esse nome" seria mentira quando o alimento EXISTE e foi barrado
    # pelo protocolo da pessoa. Ela digitou certo; o FORGE e que nao pode oferecer aquilo.
    motivo = None
    if not achados:
        sem_filtro = buscar_para_montagem(q, {})
        if sem_filtro:
            nomes = ", ".join(a["name"] for a in sem_filtro[:3])
            motivo = (f"Encontrei {nomes}, mas fora do seu protocolo atual. "
                      "Troque a intensidade no questionário se quiser liberar.")
    return {"foods": achados, "motivo": motivo}


async def _sugestao_do_plano_anterior(db, profile_id: str, nome_da_refeicao: str):
    """O que a pessoa escolheu nesta mesma refeicao no plano que esta valendo hoje.

    Casa pelo NOME da refeicao, e nao pelo indice: quem trocou de quatro para cinco
    refeicoes tem os indices deslocados, e o almoco do plano velho viraria o lanche do novo.

    Devolve tambem os itens manuais com a grama que a pessoa tinha informado — ela pesou
    aquilo uma vez, e nao ha por que pedir de novo.
    """
    salvo = await db.nutrition_plans.find_one({"profile_id": profile_id}, {"_id": 0, "plan": 1})
    refeicoes = ((salvo or {}).get("plan") or {}).get("meals") or []
    anterior = next((r for r in refeicoes if r.get("name") == nome_da_refeicao), None)
    if not anterior:
        return None
    automaticos, manuais = [], []
    for item in (anterior.get("foods") or []):
        if item.get("manual"):
            manuais.append({"food_id": item["food_id"], "grams": item["grams"]})
        else:
            automaticos.append(item["food_id"])
    if not automaticos and not manuais:
        return None
    return {"food_ids": automaticos, "manuais": manuais,
            "texto": "Deixamos marcado o que você escolheu da última vez."}


@router.get("/plan/draft/slots")
async def draft_meal_slots(request: Request, meal_index: int = Query(0, ge=0),
                           user=Depends(get_current_user)):
    """Os espacos de uma refeicao do rascunho, com o que cabe em cada um.

    E a lista que a pessoa vai usar para montar a refeicao dela. Alergia, restricao e
    alimento evitado ja saem daqui: nada que ela nao possa comer chega a ser oferecido.
    """
    db = request.app.state.db
    target = user["id"]
    await exigir_capacidade(db, user, ALIMENTACAO)
    perfil = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (perfil or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento. Chame /plan/reset primeiro.")
    if meal_index >= len(draft["meals"]):
        raise HTTPException(400, "Indice de refeicao invalido")

    refeicao = draft["meals"][meal_index]
    na = _com_protocolo(na, draft.get("targets"))
    escolhidos = [i["food_id"] for i in (refeicao.get("foods") or [])]

    # Sugestao do plano anterior: montar cinco refeicoes do zero toda semana cansa. Quem ja
    # escolheu uma vez costuma repetir, e recomecar do vazio transforma uma escolha feita em
    # trabalho refeito. So vale quando a refeicao AINDA esta vazia — nunca por cima do que a
    # pessoa acabou de escolher.
    sugestao = None
    if not escolhidos:
        sugestao = await _sugestao_do_plano_anterior(db, target, refeicao["name"])
        if sugestao:
            escolhidos = list(sugestao["food_ids"])

    alvo = {"cal": refeicao["target_cal"], "protein": refeicao["target_protein"],
            "fat": refeicao.get("target_fat", 0),
            "goal": draft.get("goal", na.get("goal", "maintenance"))}
    espacos = espacos_da_refeicao(refeicao["name"], na, escolhidos, alvo)
    # O que a sugestao trouxe e o motor nao reconhece em nenhum espaco nao pode ficar
    # pendurado: seria um alimento marcado que a tela nao tem onde mostrar.
    if sugestao:
        nos_espacos = {e["escolhido"] for e in espacos if e.get("escolhido")}
        sugestao["food_ids"] = [f for f in sugestao["food_ids"] if f in nos_espacos]
        if not sugestao["food_ids"] and not sugestao["manuais"]:
            sugestao = None

    return {"meal_index": meal_index, "name": refeicao["name"],
            "target_cal": refeicao["target_cal"], "target_protein": refeicao["target_protein"],
            "target_fat": refeicao.get("target_fat", 0),
            "alvos": _alvos_de_macro(refeicao),
            "espacos": espacos, "falta": falta_escolher(espacos),
            "sugestao": sugestao}


# ── Receitas ─────────────────────────────────────────────────────────────────────────
#
# A ordem importa: `/receitas/classes` precisa ser declarada ANTES de `/receitas/{id}`,
# senao o FastAPI casa "classes" como se fosse o id de uma receita.

@router.get("/receitas/classes")
async def receitas_classes(request: Request, user=Depends(get_current_user)):
    """As abas da tela de receitas, ja sem as vazias."""
    await exigir_capacidade(request.app.state.db, user, ALIMENTACAO)
    return {"classes": receitas_do_forge.classes_com_contagem()}


@router.get("/receitas")
async def receitas_listar(request: Request,
                          classe: Optional[str] = Query(None),
                          livres: bool = Query(False),
                          alvo_kcal: Optional[float] = Query(None, ge=0),
                          user=Depends(get_current_user)):
    """As receitas, opcionalmente de uma classe ou so as de refeicao livre.

    O ENCAIXE e o que separa esta tela de um livro de receitas: cada receita volta dizendo
    se CABE na refeicao daquela pessoa e quanto sobra. A margem e a mesma do resto do
    produto, entao a resposta aqui nunca discorda da tela do plano.

    E o alvo NAO precisa vir do cliente. Sem `alvo_kcal`, o servidor procura no plano da
    pessoa a refeicao daquela classe e usa o alvo dela — a tela nao precisa saber traduzir
    "sobremesa" para "lanche da tarde", e nao existe como as duas discordarem.
    """
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    lista = receitas_do_forge.listar(classe=classe, apenas_livres=livres)

    alvos = {} if alvo_kcal else await _alvos_por_classe(db, user["id"])
    for r in lista:
        alvo = alvo_kcal or alvos.get(r["classe"])
        if alvo:
            r["encaixe"] = receitas_do_forge.cabe_na_refeicao(r["id"], alvo)
    return {"receitas": lista, "quantas": len(lista)}


async def _alvos_por_classe(db, profile_id: str) -> dict:
    """O alvo de caloria de cada classe de receita, tirado do plano que a pessoa tem.

    Uma classe de receita ("sobremesa") aponta para um tipo de refeicao do motor ("snack"),
    e o plano guarda o alvo de cada refeicao. Juntar as duas pontas aqui, no servidor, evita
    que a tela tenha de adivinhar qual refeicao do dia corresponde a qual aba.
    """
    guardado = await db.nutrition_plans.find_one({"profile_id": profile_id},
                                                 {"_id": 0, "plan": 1})
    refeicoes = ((guardado or {}).get("plan") or {}).get("meals") or []
    por_tipo = {}
    for refeicao in refeicoes:
        tipo = _infer_meal_type(refeicao.get("name") or "")
        # A primeira de cada tipo manda: num dia com dois lanches, o alvo do lanche e o do
        # primeiro, e nao o do ultimo que o laco encontrar.
        por_tipo.setdefault(tipo, refeicao.get("target_cal"))
    return {classe: por_tipo[tipo]
            for classe, tipo in receitas_do_forge.CLASSE_PARA_REFEICAO.items()
            if por_tipo.get(tipo)}


@router.get("/receitas/{receita_id}")
async def receita_detalhe(receita_id: str, request: Request,
                          alvo_kcal: Optional[float] = Query(None, ge=0),
                          user=Depends(get_current_user)):
    await exigir_capacidade(request.app.state.db, user, ALIMENTACAO)
    r = receitas_do_forge.por_id(receita_id)
    if not r:
        raise HTTPException(404, "Receita não encontrada.")
    if alvo_kcal:
        r["encaixe"] = receitas_do_forge.cabe_na_refeicao(receita_id, alvo_kcal)
    return r


@router.get("/plan/draft/escolhas")
async def draft_meal_escolhas(request: Request, meal_index: int = Query(0, ge=0),
                              combinacao: Optional[str] = Query(None),
                              user=Depends(get_current_user)):
    """As duas perguntas daquela refeicao, no lugar de uma tela de macros.

    A montagem por espaco (`/plan/draft/slots`) pede que a pessoa preencha um formulario:
    escolha a proteina, escolha o carboidrato, escolha a gordura. Funciona, e nao e como
    um treinador conversa.

    Esta rota faz as duas perguntas que ele faz de verdade — qual montagem, e qual
    alimento dentro dela — e devolve as duas com a porcao ja calculada. O que muda nao e a
    capacidade (ela ja existia toda), e o tom.
    """
    db = request.app.state.db
    target = user["id"]
    await exigir_capacidade(db, user, ALIMENTACAO)
    perfil = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (perfil or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento. Chame /plan/reset primeiro.")
    if meal_index >= len(draft["meals"]):
        raise HTTPException(400, "Indice de refeicao invalido")

    refeicao = draft["meals"][meal_index]
    na = _com_protocolo(na, draft.get("targets"))
    # O que ja foi travado em OUTRAS refeicoes do dia. Serve para nao oferecer, de novo,
    # o mesmo prato que a pessoa acabou de escolher no almoco.
    usados = [i["food_id"]
              for j, m in enumerate(draft.get("meals") or [])
              if j != meal_index and (draft.get("locked") or [])[j]
              for i in (m.get("foods") or [])]

    resposta = escolhas_da_refeicao(
        refeicao["name"], na,
        {"kcal": refeicao["target_cal"], "protein_g": refeicao["target_protein"],
         "fat_g": refeicao.get("target_fat", 0)},
        goal=draft.get("goal", na.get("goal", "maintenance")),
        combinacao_escolhida=combinacao, usados=usados,
    )
    return {"meal_index": meal_index, **resposta}


@router.post("/plan/draft/compose")
async def draft_compose_meal(payload: ComporRefeicaoIn, request: Request,
                             user=Depends(get_current_user)):
    """A previa da refeicao que a pessoa esta montando, SEM gravar.

    A grama de cada alimento continua saindo do motor, nunca do cliente — a pessoa escolhe
    quais, `calculate_meal_portions` decide quanto. Sem esta previa ela so descobriria as
    porcoes depois de confirmar, que e tarde para mudar de ideia.

    Devolve tambem o quanto falta para a meta, que e o numero que a barra da tela enche.
    """
    db = request.app.state.db
    target = user["id"]
    await exigir_capacidade(db, user, ALIMENTACAO)
    perfil = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (perfil or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento.")
    idx = payload.meal_index
    if idx >= len(draft["meals"]):
        raise HTTPException(400, "Indice de refeicao invalido")

    refeicao = draft["meals"][idx]
    goal = draft.get("goal", na.get("goal", "maintenance"))
    na = _com_protocolo(na, draft.get("targets"))

    espacos = espacos_da_refeicao(
        refeicao["name"], na, payload.food_ids,
        {"cal": refeicao["target_cal"], "protein": refeicao["target_protein"],
         "fat": refeicao.get("target_fat", 0), "goal": goal})
    manuais = [_item_manual(m.food_id, m.grams) for m in payload.manuais]
    if not payload.food_ids and not manuais:
        vazio = {"kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
        return {"meal_index": idx, "foods": [], "totais": vazio,
                "alvo": refeicao["target_cal"],
                "proporcao": 0.0, "coerencia": 0, "espacos": espacos,
                "falta": falta_escolher(espacos),
                "alvos": _alvos_de_macro(refeicao),
                "dia": _dia_do_rascunho(draft, idx, vazio)}

    # A caloria que os manuais ja entregam SAI do alvo antes de dimensionar o resto: sem
    # isso, escolher 200 g de um alimento manual e depois deixar o motor preencher daria
    # uma refeicao muito acima da meta, porque cada lado estaria mirando o total cheio.
    ja_entregue = _somar_macros(manuais)
    alvo_cal = max(0.0, float(refeicao["target_cal"]) - ja_entregue["kcal"])
    alvo_prot = max(0.0, float(refeicao["target_protein"]) - ja_entregue["protein_g"])
    alvo_gord = max(0.0, float(refeicao.get("target_fat", 0)) - ja_entregue["fat_g"])

    porcoes = calculate_meal_portions(payload.food_ids, alvo_cal, alvo_prot, alvo_gord, goal)
    alimentos = [build_food_item(fid, porcoes.get(fid, 100)) for fid in payload.food_ids]
    alimentos += manuais

    totais = _somar_macros(alimentos)
    coerencia = calculate_meal_coherence_score(
        {"foods": alimentos}, _infer_meal_type(refeicao["name"]), goal)
    alvo = float(refeicao["target_cal"] or 0)
    return {"meal_index": idx, "foods": alimentos, "totais": totais,
            "alvo": round(alvo), "proporcao": round(totais["kcal"] / alvo, 3) if alvo else 0.0,
            "coerencia": round(coerencia), "espacos": espacos,
            "falta": falta_escolher(espacos),
            "alvos": _alvos_de_macro(refeicao),
            "dia": _dia_do_rascunho(draft, idx, totais)}


@router.post("/plan/draft/choose")
async def draft_choose_meal(payload: ChooseMealIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento.")
    idx = payload.meal_index
    if idx >= len(draft["meals"]):
        raise HTTPException(400, "Indice de refeicao invalido")
    if not payload.food_ids and not payload.manuais:
        raise HTTPException(400, "Selecione ao menos um alimento")
    goal = draft.get("goal", na.get("goal", "maintenance"))
    meal_target = draft["meals"][idx]

    # Backend remains the source of truth for grams: the client selects WHICH foods,
    # the engine — never the client — decides HOW MUCH, exactly like /substitute.
    #
    # A excecao sao os itens MANUAIS, e ela e declarada: alimento que so existe no diario
    # nao tem papel nem limite de porcao, entao quem diz a grama e a pessoa. A caloria deles
    # sai do alvo antes de dimensionar o resto, senao os dois lados mirariam o total cheio.
    manuais = [_item_manual(m.food_id, m.grams) for m in payload.manuais]
    entregue = _somar_macros(manuais)
    portions = calculate_meal_portions(
        payload.food_ids,
        max(0.0, float(meal_target["target_cal"]) - entregue["kcal"]),
        max(0.0, float(meal_target["target_protein"]) - entregue["protein_g"]),
        max(0.0, float(meal_target.get("target_fat", 0)) - entregue["fat_g"]), goal)
    foods = [build_food_item(fid, portions.get(fid, 100)) for fid in payload.food_ids]
    foods += manuais
    draft["meals"][idx]["foods"] = foods
    draft["meals"][idx]["archetype_id"] = payload.archetype_id
    draft["locked"][idx] = True
    redistribute_remaining_targets(draft["meals"], draft["locked"], draft["targets"], goal)

    await db.nutrition_plan_drafts.update_one(
        {"profile_id": target}, {"$set": {"meals": draft["meals"], "locked": draft["locked"]}})
    await _record_choice_preferences(db, target, payload.food_ids)
    draft.pop("_id", None)
    return draft


@router.post("/plan/draft/choose-remaining")
async def draft_choose_remaining(request: Request, user=Depends(get_current_user)):
    """FORGE_CHOOSES_FOR_ME across every meal that isn't locked in yet."""
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento.")
    goal = draft.get("goal", na.get("goal", "maintenance"))
    # O MESMO preparo que `/plan/draft/options` ja fazia: `_com_protocolo` injeta o teto de
    # carboidrato POR ALIMENTO do protocolo. Sem ele, "FORGE escolhe por mim" montava o dia
    # com alimentos que a tela de opcoes nunca ofereceria, o dia estourava o teto do
    # protocolo e a confirmacao morria em 422 — depois de seis escolhas.
    na = _com_protocolo(na, draft.get("targets"))
    preferences = await _load_preferences(db, target)
    chosen_food_ids = []
    for idx in range(len(draft["meals"])):
        if draft["locked"][idx]:
            continue
        meal_target = draft["meals"][idx]
        options = get_meal_archetype_options(
            meal_target["name"], meal_target["target_cal"], meal_target["target_protein"],
            meal_target.get("target_fat", 0), na, _locked_used_ids(draft), goal, None, idx,
            preferences, 1, random.randint(0, 999))
        best = options[0]
        draft["meals"][idx]["foods"] = best["meal"]["foods"]
        draft["meals"][idx]["archetype_id"] = best["archetype_id"]
        draft["locked"][idx] = True
        chosen_food_ids.extend(it["food_id"] for it in best["meal"]["foods"])
        redistribute_remaining_targets(draft["meals"], draft["locked"], draft["targets"], goal)

    await db.nutrition_plan_drafts.update_one(
        {"profile_id": target}, {"$set": {"meals": draft["meals"], "locked": draft["locked"]}})
    if chosen_food_ids:
        await _record_choice_preferences(db, target, chosen_food_ids)
    draft.pop("_id", None)
    return draft


@router.post("/plan/draft/confirm")
async def confirm_plan_draft(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    profile = await db.profiles.find_one({"id": target}, {"_id": 0})
    na = (profile or {}).get("nutrition_assessment", {})
    draft = await db.nutrition_plan_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not draft:
        raise HTTPException(404, "Nenhum rascunho de plano em andamento.")
    if not all(draft["locked"]):
        raise HTTPException(400, "Existem refeicoes ainda nao escolhidas. Use /choose ou /choose-remaining antes de confirmar.")
    goal = draft.get("goal", na.get("goal", "maintenance"))
    # Mesmo passe que `generate_daily_plan` aplica no fim: sob um protocolo com teto de
    # carboidrato, o pipeline infla alimento de volume por saciedade e estoura o teto. O
    # fluxo guiado nunca passava por aqui, entao montar o dia a mao no protocolo agressivo
    # terminava em 422 DEPOIS de a pessoa escolher as seis refeicoes — e sem plano salvo.
    # Sem teto no protocolo a funcao devolve as refeicoes intactas.
    draft["meals"] = aplicar_teto_de_carboidrato(draft["meals"], draft["targets"])
    totals = sum_plan_totals(draft["meals"])
    for i, meal in enumerate(draft["meals"]):
        # Cross-meal repetition check (item 10) against every OTHER meal in the final
        # plan — a true adjacent/daily view, not just what was known when this meal's
        # options were first generated.
        used_elsewhere = {it["food_id"] for j, m in enumerate(draft["meals"]) if j != i for it in m.get("foods", [])}
        meal["coherence_score"] = calculate_meal_coherence_score(meal, _infer_meal_type(meal["name"]), goal, used_elsewhere)
    plan = {"meals": draft["meals"], "daily_totals": totals, "pre_reconciliation_totals": totals,
            "targets": draft["targets"], "engine_version": FORGE_COACH_METHODOLOGY["engine_version"],
            "methodology_version": FORGE_COACH_METHODOLOGY["coach_version"], "composed_by": "guided"}
    # Same validator the legacy /generate uses — this IS the "porcoes, restricoes e
    # regras do coach foram respeitadas" confirmation surfaced to the review screen.
    warnings = validate_daily_plan(plan, draft["targets"], na)
    # Mesmo limite duro do /generate: um plano fora do teto do protocolo nao pode ser
    # gravado e apresentado como "Agressivo". O rascunho NAO e apagado aqui, entao o
    # atleta ajusta as refeicoes e confirma de novo — nada do trabalho guiado se perde,
    # e o plano anterior continua intacto ate um confirm valido.
    erros = check_plan_hard_limits(plan, draft["targets"])
    if erros:
        logger.warning("confirmacao bloqueada para profile_id=%s: %s", target, "; ".join(erros))
        raise HTTPException(422, {
            "message": "O plano montado ficou fora dos limites do protocolo escolhido.",
            "errors": erros})

    doc = {"profile_id": target, "user_id": target, "plan": plan, "created_at": datetime.now(timezone.utc).isoformat(),
           "engine_version": FORGE_COACH_METHODOLOGY["engine_version"],
           "methodology_version": FORGE_COACH_METHODOLOGY["coach_version"]}
    await db.nutrition_plans.replace_one({"profile_id": target}, doc, upsert=True)
    await db.nutrition_plan_drafts.delete_one({"profile_id": target})
    return {"plan": plan, "targets": draft["targets"], "warnings": warnings}


@router.post("/preferences")
async def set_food_preference(payload: PreferenceIn, request: Request, user=Depends(get_current_user)):
    """Explicit USER_PREFERENCES signal ('prefiro evitar' etc.) — a preference, never an
    allergy or restriction. Only ever nudges ranking inside get_meal_archetype_options;
    it can never widen what's offered past allergies/restrictions/avoid_foods/hard_max."""
    db = request.app.state.db
    target = user["id"]
    await db.nutrition_preferences.update_one(
        {"profile_id": target, "food_id": payload.food_id},
        {"$set": {"signal": payload.signal, "updated_at": datetime.now(timezone.utc).isoformat()},
         "$setOnInsert": {"chosen_count": 0}},
        upsert=True)
    return {"food_id": payload.food_id, "signal": payload.signal}


@router.post("/meal-status")
async def update_meal_status(payload: MealStatusIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    doc = {"profile_id": target, "user_id": target, "meal_index": payload.meal_index,
           "status": payload.status, "date": str(payload.date or datetime.now(timezone.utc).date()),
           "actual": None,
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.nutrition_adherence.update_one(
        {"_id": f"meal:{target}:{doc['date']}:{payload.meal_index}"}, {"$set": doc}, upsert=True)
    return {"status": "registered"}


@router.get("/adherence/{date}")
async def get_adherence(date: CalendarDate, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    rows = await db.nutrition_adherence.find({"profile_id": target, "date": str(date)}, {"_id": 0}).sort("created_at", 1).to_list(None)
    latest = {row["meal_index"]: row for row in rows}
    extras = await db.nutrition_consumed_extras.find({"profile_id": target, "date": str(date)}, {"_id": 0}).to_list(None)
    return {"date": str(date), "meals": list(latest.values()), "extras": extras}


MACROS_DA_SEMANA = ("kcal", "protein_g", "carbs_g", "fat_g")


def _somar(destino, origem):
    for macro in MACROS_DA_SEMANA:
        destino[macro] += float((origem or {}).get(macro) or 0)


def _totais_do_dia(refeicoes_do_plano, linhas, extras):
    """Soma o consumo de um dia com as MESMAS regras da tela de Nutricao.

    A sutileza que precisa ser repetida aqui: refeicao marcada como feita sem pesagem nao
    tem `actual`, e nesse caso vale o que o plano previa. Se a semana somasse so o que foi
    pesado, ela contradiria o numero que a pessoa ve no dia — dois totais diferentes para a
    mesma comida destroem a confianca nos dois.
    """
    total = {macro: 0.0 for macro in MACROS_DA_SEMANA}
    for linha in linhas:
        if linha.get("status") != "completed":
            continue
        atual = linha.get("actual")
        if atual:
            _somar(total, atual.get("totals"))
            continue
        indice = linha.get("meal_index")
        refeicao = refeicoes_do_plano[indice] if isinstance(indice, int) and 0 <= indice < len(refeicoes_do_plano) else None
        if not refeicao:
            continue
        itens = refeicao.get("foods") or []
        if not itens:
            _somar(total, {"kcal": refeicao.get("target_cal")})
            continue
        for item in itens:
            alimento = item.get("food") or {}
            base = float(alimento.get("grams") or 100) or 100
            proporcao = float(item.get("grams") or 0) / base
            _somar(total, {m: float(alimento.get(m) or 0) * proporcao for m in MACROS_DA_SEMANA})
    for extra in extras:
        _somar(total, (extra.get("actual") or {}).get("totals"))
    return {macro: round(valor, 2) for macro, valor in total.items()}


@router.get("/adherence-week")
async def get_adherence_week(request: Request, days: int = Query(7, ge=1, le=31),
                             start: Optional[CalendarDate] = Query(None),
                             end: Optional[CalendarDate] = Query(None),
                             user=Depends(get_current_user)):
    """O consumo de um intervalo de dias, num pedido so.

    A tela de Evolucao mostra a semana de alimentacao. Montar isso por `/adherence/{date}`
    custaria uma requisicao por dia para preencher um bloco de tres numeros.

    `start` e `end` vem do APARELHO, e nao sao um capricho: o servidor roda em UTC e o
    atleta vive em UTC-3. As 21h de sabado no Brasil ja e domingo em UTC, e uma semana
    calculada aqui comecaria e terminaria no dia errado — justamente o erro que o diario do
    dia ja evita usando a data local. Sem elas, cai na janela dos ultimos `days` dias.

    So volta dia que TEM registro. Dia sem registro nao e dia de jejum: e dia em que a
    pessoa esqueceu de anotar, e tratar os dois como iguais faria a tela acusar um deficit
    que nunca existiu. Quem decide o que dizer sobre os dias que faltam e a tela.
    """
    db = request.app.state.db
    target = user["id"]
    if start and end:
        if end < start:
            raise HTTPException(422, "O fim do intervalo nao pode ser antes do inicio.")
        if (end - start).days > 92:
            raise HTTPException(422, "Intervalo longo demais.")
        inicio, fim = start.isoformat(), end.isoformat()
    else:
        hoje = datetime.now(timezone.utc).date()
        inicio = (hoje - timedelta(days=days - 1)).isoformat()
        fim = hoje.isoformat()

    stored = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0, "plan": 1})
    plano = (stored or {}).get("plan") or {}
    refeicoes = plano.get("meals") or []
    alvos = plano.get("targets") or {}

    filtro = {"profile_id": target, "date": {"$gte": inicio, "$lte": fim}}
    linhas = await db.nutrition_adherence.find(filtro, {"_id": 0}).sort("created_at", 1).to_list(None)
    extras = await db.nutrition_consumed_extras.find(filtro, {"_id": 0}).to_list(None)

    por_dia = {}
    for linha in linhas:
        dia = str(linha.get("date") or "")
        if not dia:
            continue
        # `created_at` crescente: o ultimo registro da mesma refeicao vence, como no dia.
        por_dia.setdefault(dia, {"linhas": {}, "extras": []})["linhas"][linha.get("meal_index")] = linha
    for extra in extras:
        dia = str(extra.get("date") or "")
        if dia:
            por_dia.setdefault(dia, {"linhas": {}, "extras": []})["extras"].append(extra)

    dias = []
    for dia in sorted(por_dia):
        conteudo = por_dia[dia]
        totais = _totais_do_dia(refeicoes, list(conteudo["linhas"].values()), conteudo["extras"])
        if not any(totais[m] for m in MACROS_DA_SEMANA):
            continue
        dias.append({"date": dia, **totais})

    # O objetivo mora no PERFIL, nao no plano. Sem ele a tela descreve sem julgar direcao, o
    # que e correto mas pobre: comer abaixo em corte e comer abaixo em ganho sao coisas
    # opostas, e so o objetivo separa as duas.
    perfil = await db.profiles.find_one({"id": target}, {"_id": 0, "goal": 1, "body_goal": 1})
    objetivo = (perfil or {}).get("goal") or (perfil or {}).get("body_goal")

    janela = (CalendarDate.fromisoformat(fim) - CalendarDate.fromisoformat(inicio)).days + 1
    return {"days": dias, "registered_days": len(dias), "window_days": janela,
            "start": inicio, "end": fim,
            "targets": {m: alvos.get(m) for m in ("goal_calories", "protein_g", "carbs_g", "fat_g")},
            "goal": plano.get("goal") or alvos.get("goal") or objetivo}


class ItemComprado(BaseModel):
    food_id: str = Field(min_length=1, max_length=120)
    comprado: bool
    week_start: CalendarDate


@router.get("/shopping-list")
async def get_shopping_list(request: Request, week_start: CalendarDate = Query(...),
                            days: int = Query(7, ge=1, le=31),
                            user=Depends(get_current_user)):
    """A lista de compras da semana, com os itens ja marcados.

    `week_start` vem do aparelho pelo mesmo motivo da semana da dieta: o servidor roda em UTC
    e o atleta vive em UTC-3, entao calcular a segunda-feira aqui erraria o dia no fim da
    noite. Ela tambem e a chave do que foi marcado, e por isso a lista zera sozinha na
    virada da semana, sem ninguem precisar limpar nada.
    """
    db = request.app.state.db
    target = user["id"]
    await exigir_capacidade(db, user, ALIMENTACAO)
    stored = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0, "plan": 1})
    lista = montar_lista((stored or {}).get("plan") or {}, days)

    marcados = await db.nutrition_shopping_checks.find(
        {"profile_id": target, "week_start": str(week_start)}, {"_id": 0, "food_id": 1}
    ).to_list(400)
    comprados = {linha["food_id"] for linha in marcados}
    for secao in lista["secoes"]:
        for item in secao["itens"]:
            item["comprado"] = item["food_id"] in comprados

    lista["week_start"] = str(week_start)
    lista["comprados"] = sum(1 for s in lista["secoes"] for i in s["itens"] if i["comprado"])
    return lista


@router.post("/shopping-list/check")
async def check_shopping_item(payload: ItemComprado, request: Request,
                              user=Depends(get_current_user)):
    """Marca ou desmarca um item da semana.

    O `_id` carrega atleta, semana e alimento: marcar duas vezes o mesmo item nao cria duas
    linhas, e a semana seguinte comeca limpa porque a chave muda sozinha.
    """
    db = request.app.state.db
    target = user["id"]
    await exigir_capacidade(db, user, ALIMENTACAO)
    chave = f"compra:{target}:{payload.week_start}:{payload.food_id}"
    if payload.comprado:
        await db.nutrition_shopping_checks.update_one(
            {"_id": chave},
            {"$set": {"profile_id": target, "week_start": str(payload.week_start),
                      "food_id": payload.food_id,
                      "created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
    else:
        await db.nutrition_shopping_checks.delete_one({"_id": chave, "profile_id": target})
    return {"food_id": payload.food_id, "comprado": payload.comprado}


@router.get("/carb-cycle")
async def get_carb_cycle(request: Request, user=Depends(get_current_user)):
    """As metas de cada dia da semana, com o carboidrato concentrado no ponto fraco.

    INFORMATIVO por enquanto: devolve as metas do dia, e nao um cardapio diferente por dia.
    Regerar as refeicoes de sete dias mexe no gerador de plano, que ja esta servindo gente —
    e a meta ja e util sozinha, porque a pessoa ajusta a porcao de arroz sabendo que hoje o
    alvo e 530 g de carboidrato e nao 400.

    Quando nao ha o que ciclar, devolve `motivo` em vez de dado: dizer "nao da" sem dizer por
    que deixa a pessoa sem acao, e cada motivo aqui tem conserto que ela mesma faz.
    """
    db = request.app.state.db
    target = user["id"]
    await exigir_capacidade(db, user, ALIMENTACAO)

    plano_salvo = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0, "plan": 1})
    if ((plano_salvo or {}).get("plan") or {}).get("source") == "manual_import":
        return {"ativo": False, "motivo": "As metas seguem sua dieta importada."}

    perfil = await db.profiles.find_one({"id": target}, {"_id": 0}) or {}
    prioridades = perfil.get("priorities") or []
    na = perfil.get("nutrition_assessment")
    if not _assessment_completo(na):
        return {"ativo": False, "motivo": "Responda a avaliação de nutrição para o FORGE calcular suas metas."}

    alvos = compute_macro_targets(
        na["weight_kg"], na["height_cm"], na["age"], na["sex"],
        na["training_days"], na["goal"], na.get("activity_level", "moderate"),
        na.get("intensity"))

    if not prioridades:
        return {"ativo": False, "prioridades": [],
                "motivo": "Escolha um ponto fraco no seu perfil para o carboidrato se concentrar nele."}

    # `build_program_v2` e a mesma funcao que o bootstrap usa; o `db` vem do request para
    # nao depender do modulo global do server.
    programa = await build_program_v2(perfil, db)
    sessoes = programa.get("sessions") or []
    ciclo = ciclar_por_sessao(alvos, sessoes, na.get("training_days"), prioridades)
    if not ciclo:
        return {"ativo": False, "prioridades": list(prioridades),
                "motivo": "Nenhum treino da sua semana trabalha o ponto fraco que você escolheu."}

    # A sessao de hoje decide a meta de hoje. Quem nao tem agenda por dia da semana — que e
    # a maioria, porque o motor nomeia as sessoes "Upper 1" e avanca por conclusao — recebe
    # a classe da PROXIMA sessao, que e a que ela vai treinar.
    calendario = programa.get("calendar") or {}
    sessao_de_hoje = calendario.get("today")
    hoje = classe_da_sessao(sessao_de_hoje, prioridades)
    do_dia = ciclo["por_classe"][hoje]
    # Dizer o alvo sem dizer o movimento deixa a pessoa parada. A sugestao sai do PROPRIO
    # plano dela: mandar comer arroz para quem montou o plano com tapioca seria conselho de
    # outro aplicativo.
    plano_salvo = await db.nutrition_plans.find_one({"profile_id": target}, {"_id": 0, "plan": 1})
    refeicoes = ((plano_salvo or {}).get("plan") or {}).get("meals") or []
    ajuste = onde_colocar(do_dia["carbs_g"] - ciclo["base"]["carbs_g"], refeicoes)
    return {"ativo": True,
            "hoje": {"classe": hoje, "sessao": (sessao_de_hoje or {}).get("label"),
                     "ajuste": ajuste, **do_dia},
            **ciclo}


@router.get("/refeicoes-do-diario")
async def refeicoes_do_diario(_user=Depends(get_current_user)):
    """As refeicoes que o diario livre aceita, na ordem do dia.

    Vem do servidor para a tela nao manter uma segunda lista: duas taxonomias de refeicao
    no mesmo produto viram dois relatorios que nao batem.
    """
    return {"refeicoes": [{"id": k, "nome": v} for k, v in REFEICOES_DO_DIARIO.items()]}


@router.get("/consumed-foods")
async def consumed_food_catalog(request: Request, user=Depends(get_current_user)):
    return {"foods": [{k: f.get(k) for k in ("id", "name", "aliases", "grams", "kcal", "protein_g", "carbs_g", "fat_g", "source", "source_url")} for f in DIARY_FOODS.values()]}


@router.get("/consumed-foods/search")
async def search_consumed_foods(q: str = Query(min_length=2, max_length=80), user=Depends(get_current_user)):
    return {"foods": await search_external_foods(q)}


@router.post("/consumed-meal")
async def save_consumed_meal(payload: ConsumedMealIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    await exigir_capacidade(db, user, ALIMENTACAO)
    if payload.refeicao is not None:
        if payload.refeicao not in REFEICOES_DO_DIARIO:
            raise HTTPException(422, "Refeição desconhecida.")
        await exigir_capacidade(db, user, DIARIO_LIVRE)
    external_foods = {}
    for item in payload.foods:
        if item.food_id.startswith("off:"):
            resolved = await resolve_external_food(item.food_id)
            if not resolved:
                raise HTTPException(422, "Não foi possível confirmar os dados desse alimento. Tente buscá-lo novamente.")
            external_foods[item.food_id] = resolved
    try:
        actual = food_snapshot(payload.foods, external_foods)
    except ValueError as error:
        raise HTTPException(422, str(error))
    target = user["id"]
    day = str(payload.date)
    doc = {"profile_id": target, "date": day, "actual": actual, "created_at": datetime.now(timezone.utc).isoformat()}
    if payload.meal_index is not None:
        stored = await db.nutrition_plans.find_one({"profile_id": target})
        if not stored or payload.meal_index >= len(stored["plan"].get("meals", [])):
            raise HTTPException(422, "Refeição não encontrada no plano atual.")
        doc.update(meal_index=payload.meal_index, status="completed", user_id=target)
        await db.nutrition_adherence.update_one({"_id": f"meal:{target}:{day}:{payload.meal_index}"}, {"$set": doc}, upsert=True)
    else:
        doc["entry_id"] = str(payload.entry_id)
        if payload.refeicao:
            doc["refeicao"] = payload.refeicao
            doc["refeicao_nome"] = REFEICOES_DO_DIARIO[payload.refeicao]
        await db.nutrition_consumed_extras.update_one({"_id": f"extra:{target}:{payload.entry_id}"}, {"$set": doc}, upsert=True)
    return {"actual": actual}


@router.delete("/consumed-extra/{entry_id}")
async def remove_consumed_extra(entry_id: uuid.UUID, request: Request, user=Depends(get_current_user)):
    await exigir_capacidade(request.app.state.db, user, ALIMENTACAO)
    await request.app.state.db.nutrition_consumed_extras.delete_one({"_id": f"extra:{user['id']}:{entry_id}", "profile_id": user["id"]})
    return {"status": "removed"}


@router.post("/weight")
async def log_weight(payload: WeightLogIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    doc = {"profile_id": target, "user_id": target, "weight_kg": payload.weight_kg,
           "date": payload.date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.nutrition_weight_logs.insert_one(doc)
    await db.profiles.update_one({"id": target}, {"$set": {"latest_weight": payload.weight_kg,
                                  "latest_weight_date": doc["date"]}}, upsert=True)
    return {"weight": payload.weight_kg, "date": doc["date"]}


@router.get("/weight")
async def get_weight_history(request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    target = user["id"]
    rows = await db.nutrition_weight_logs.find({"profile_id": target}, {"_id": 0}).sort("date", -1).to_list(30)
    return {"history": rows}


from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import os, uuid, json, logging, base64
from google import genai as google_genai

from llm_providers import deepseek_model, get_coach_provider, FORGE_COACH_SYSTEM

from auth import router as auth_router, get_current_user, seed_super_admin
from admin_routes import router as admin_router
from nutrition_routes import router as nutrition_router
from nutrition_engine import resolve_intensity_protocol, _intensity_key
from billing_plans import PROTOCOLOS_AGRESSIVOS
from entitlements import exigir_capacidade
from manual_workout_routes import router as manual_workout_router
from nutrition_import_routes import router as nutrition_import_router
from billing_routes import router as billing_router
from password_reset_routes import router as password_reset_router
from preassessment_routes import router as preassessment_router
from signup_routes import router as signup_router
from muscles import (
    to_frontend, to_internal, get_profile_priorities_internal,
    get_assessment_internal, FRONTEND_MUSCLES as MUSCLES_FRONTEND_LIST,
    LEGACY_TO_INTERNAL, MUSCLE_IDS,
)
from engine import (
    FRONTEND_EXERCISE_LIST, EXERCISE_INDEX, build_program_v2,
    _is_empty_profile as engine_is_empty_profile,
    validate_sessions, determine_split, compatible_splits, TRAINING_METHOD_PROFILES,
    EXERCISES as ENGINE_EXERCISES,
)

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
def _docs_ligadas() -> bool:
    """A documentacao interativa fica DESLIGADA por padrao.

    /docs e /openapi.json descrevem a API inteira: cada rota, cada modelo, cada nome de
    campo. Isso e um mapa para quem estiver procurando o que atacar, e nao serve a nenhum
    usuario do produto. Quem precisar liga FORGE_ENABLE_DOCS=true num ambiente que nao
    seja o de producao."""
    return (os.environ.get("FORGE_ENABLE_DOCS") or "").strip().lower() in ("1", "true", "yes")


app = FastAPI(
    title="FORGE Training OS",
    docs_url="/docs" if _docs_ligadas() else None,
    redoc_url="/redoc" if _docs_ligadas() else None,
    openapi_url="/openapi.json" if _docs_ligadas() else None,
)
app.state.db = db
api = APIRouter(prefix="/api")
logger = logging.getLogger("forge")

MUSCLES = MUSCLES_FRONTEND_LIST

TECHNIQUES = [
    {"id":"straight","name":"Straight Sets","short":"Séries retas","fatigue":"baixa","recommended_for":["Iniciante","Intermediário","Avançado","Bodybuilder"],"description":"Todas as séries com o mesmo peso e faixa de reps, respeitando o RIR planejado.","protocol":"Peso fixo. Ex.: 3×8 @ RIR 2.","when":"Base do plano; não substitua sem motivo."},
    {"id":"drop-set","name":"Drop Set","short":"Redução de carga sem descanso","fatigue":"alta","recommended_for":["Avançado","Bodybuilder"],"description":"Depois da última série efetiva, reduza 20–30% da carga e continue até nova falha técnica.","protocol":"Série principal → −25% carga → ao fim, opcional novo −20%.","when":"1–2 exercícios por sessão, em músculo prioritário com boa recuperação."},
    {"id":"mechanical-drop-set","name":"Mechanical Drop Set","short":"Redução por biomecânica","fatigue":"alta","recommended_for":["Avançado","Bodybuilder"],"description":"Mantém a carga; muda a posição/pegada para uma mais forte quando falhar.","protocol":"Ex.: elevação lateral halter na posição forte → seguir até nova falha.","when":"Ombro lateral, bíceps, panturrilha; substitui bem o drop tradicional em máquinas fixas."},
    {"id":"rest-pause","name":"Rest-Pause","short":"Pausas curtas com mesma carga","fatigue":"alta","recommended_for":["Avançado","Bodybuilder"],"description":"Chegue perto da falha, descanse 10–20 s e retome. 2–3 pausas.","protocol":"Ex.: 8 reps → 15 s → 3 reps → 15 s → 2 reps.","when":"Fim do exercício; poupa tempo mantendo intensidade."},
    {"id":"myo-reps","name":"Myo-Reps","short":"Ativação + mini-séries","fatigue":"alta","recommended_for":["Avançado","Bodybuilder"],"description":"Uma série de ativação até próximo da falha, seguida de mini-séries de 3–5 reps com pausas curtíssimas.","protocol":"Ex.: 12 reps @ RIR 0–1 → 5 s pausa → 4 reps → 5 s → 4 reps → 5 s → 3 reps.","when":"Alta densidade em exercícios estáveis (máquina, cabo)."},
    {"id":"cluster","name":"Cluster Set","short":"Blocos com micro-pausas","fatigue":"moderada","recommended_for":["Intermediário","Avançado","Bodybuilder"],"description":"Divide a série em blocos com 10–20 s de pausa para manter carga alta com menos fadiga por rep.","protocol":"Ex.: 4+4+4 @ 85% 1RM com 15 s entre blocos.","when":"Trabalho de força ou densidade em exercícios compostos."},
    {"id":"top-set-backoff","name":"Top Set + Back-off","short":"Pico + volume","fatigue":"moderada","recommended_for":["Intermediário","Avançado","Bodybuilder"],"description":"Série pesada única no topo, seguida de séries de volume com carga reduzida.","protocol":"Ex.: 1×5 @ RIR 1 → 3×8 com −15% de carga.","when":"Compostos principais quando quer estímulo pesado sem gastar séries."},
    {"id":"pyramid","name":"Pyramid","short":"Escadas de carga","fatigue":"moderada","recommended_for":["Intermediário","Avançado"],"description":"Aumenta ou reduz progressivamente carga e reps ao longo das séries.","protocol":"Ex.: 12 → 10 → 8 → 6 reps subindo a carga; ou o inverso descendente.","when":"Aprendizado de esforço e aquecimento em exercícios compostos."},
    {"id":"lengthened-partials","name":"Lengthened Partials","short":"Parciais no alongamento","fatigue":"moderada","recommended_for":["Avançado","Bodybuilder"],"description":"Ao chegar próximo da falha na amplitude completa, continue com parciais na porção alongada.","protocol":"Ex.: 10 reps completas + 5 parciais na metade baixa.","when":"Exercícios com sobrecarga no alongamento (elevação lateral inclinada, cadeira extensora, curvas)."},
    {"id":"superset","name":"Superset","short":"Dois exercícios seguidos","fatigue":"moderada","recommended_for":["Intermediário","Avançado","Bodybuilder"],"description":"Executa dois exercícios em sequência sem descanso. Preferencialmente antagonistas ou complementares.","protocol":"Ex.: Rosca direta + Tríceps corda, 3 rounds.","when":"Densidade e economia de tempo; evite em compostos exigentes."},
]

EXERCISES = FRONTEND_EXERCISE_LIST

DEMO_PROFILE = {"id":"demo","user_id":"demo","name":"Rafael Mendes","goal":"Hipertrofia com especialização","experience":"Avançado","days":4,"session_minutes":70,"equipment":["Academia completa"],"priorities":["Deltóide lateral","Peitoral superior","Posteriores"],"assessment":{m:{"development":"fraco","priority":"alta"} if m in ["Deltóide lateral","Peitoral superior","Posteriores"] else {"development":"proporcional","priority":"normal"} for m in MUSCLES},"advanced_mode":True,"automation_mode":"FORGE_ASSISTED","created_at":datetime.now(timezone.utc).isoformat()}


class SetLog(BaseModel):
    profile_id: str = "demo"
    exercise_id: str
    set_number: int
    weight: float
    reps: int
    rir: int = Field(default=2, ge=0, le=5)
    session_day: Optional[int] = None
    technique: str = "Straight Sets"
    note: str = ""

class Recovery(BaseModel):
    profile_id: str = "demo"
    sleep: int = 4
    energy: int = 4
    motivation: int = 4
    soreness: int = 2
    stress: int = 2

class DeepAssessment(BaseModel):
    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Novo atleta"
    age: Optional[int] = None
    sex: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    training_years: float = 0
    consistency_years: float = 0
    experience: str = "Intermediário"
    goal: str = "Hipertrofia"
    # Transporte apenas: objetivo corporal e ritmo escolhidos no onboarding NAO viram
    # campos proprios do perfil. save_assessment os grava em nutrition_assessment
    # (goal/intensity), que ja e a fonte de verdade usada por compute_macro_targets — um
    # segundo campo concorrente deixaria onboarding e Alimentacao discordarem entre si.
    # body_goal: "muscle_gain" | "fat_loss" | "maintenance" (o enum que ja existia).
    body_goal: Optional[str] = None
    goal_intensity: Optional[str] = None
    # nome anterior do mesmo transporte; aceito para nao quebrar uma aba aberta durante o deploy
    cut_intensity: Optional[str] = None
    secondary_goal: str = ""
    days: int = 3
    session_minutes: int = 60
    split: str = ""
    split_preference: str = ""
    training_method: str = "balanced_hypertrophy"
    muscles_by_day: Dict[str, List[str]] = {}
    trains_near_failure: bool = True
    uses_rir: bool = True
    uses_rpe: bool = False
    tracks_loads: bool = True
    planned_progression: bool = True
    specialization_history: bool = False
    equipment: List[str] = ["Academia completa"]
    gym_complete: bool = True
    favorites: List[str] = []
    avoid_exercises: List[str] = []
    great_connection: List[str] = []
    poor_connection: List[str] = []
    assessment: Dict[str, Dict[str, str]] = {}
    priorities: List[str] = []
    recovery: Dict[str, Any] = {}
    limitations: List[str] = []
    preferences: Dict[str, Any] = {}
    baseline: List[Dict[str, Any]] = []
    visual_assessment: Optional[Dict[str, Any]] = None
    automation_mode: str = "FORGE_ASSISTED"
    microcycle_days: int = 7
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class WeeklyReview(BaseModel):
    profile_id: str
    recovery: int = 3
    performance: int = 3
    soreness: int = 2
    easy_recovery: List[str] = []
    worsened_exercises: List[str] = []
    improved_exercises: List[str] = []
    priority_changes: List[str] = []
    note: str = ""

class ProgramAnalysis(BaseModel):
    profile_id: str
    days: List[Dict[str, Any]] = []

class CustomProgramExercise(BaseModel):
    exercise_id: str
    sets: int = 3
    reps: str = "8–12"
    rir: str = "1–2"
    rest: str = "2 min"
    load: float = 0
    technique: str = "Straight Sets"
    technique_id: str = "straight"
    note: str = ""

class CustomProgramDay(BaseModel):
    day: int
    label: str = "Sessão"
    demand: str = "MODERATE"
    focus: List[str] = []
    exercises: List[CustomProgramExercise] = []

class CustomProgram(BaseModel):
    profile_id: str
    name: str = "Programa personalizado"
    week: str = "Microciclo manual"
    sessions: List[CustomProgramDay] = []
    session_minutes: int = 60


class ExerciseSubstituteIn(BaseModel):
    original_exercise_id: str
    new_exercise_id: str
    profile_id: Optional[str] = None


class WorkoutCompleteIn(BaseModel):
    day: Optional[int] = None
    profile_id: Optional[str] = None
    completed_sets: Optional[int] = Field(default=None, ge=0, le=200)
    total_sets: Optional[int] = Field(default=None, ge=0, le=200)
    duration_seconds: Optional[int] = Field(default=None, ge=0, le=43200)
    started_at: Optional[str] = Field(default=None, max_length=40)
    partial_reason: str = Field(default="", max_length=160)
    discomfort: str = Field(default="none", max_length=24)


class WorkoutSessionDraftIn(BaseModel):
    """Preenchimento parcial do treino em andamento (carga/reps por serie)."""
    day: Optional[int] = None
    inputs: Dict[str, Any] = {}
    profile_id: Optional[str] = None


class HydrationAddIn(BaseModel):
    amount_ml: int = Field(..., ge=50, le=1000)


class TrainingPreferencesIn(BaseModel):
    split_preference: str = Field(default="", max_length=40)
    training_method: str = Field(default="balanced_hypertrophy", max_length=40)
    profile_id: Optional[str] = None


def owned_profile_id(user: dict, requested: Optional[str]) -> str:
    """ATHLETE: always their own id. SUPER_ADMIN: may pass any id (falls back to 'demo')."""
    if user.get("role") == "SUPER_ADMIN":
        return requested or "demo"
    return user["id"]


def score_priority(profile: Dict[str, Any], muscle: str) -> int:
    internal = to_internal(muscle)
    assessment = get_assessment_internal(profile)
    raw = assessment.get(internal, {"development": "proporcional", "priority": "normal"})
    manual = raw.get("priority", "normal") if isinstance(raw, dict) else "normal"
    weights = {"baixa": 1, "normal": 2, "alta": 4, "máxima": 6, "maxima": 6}
    development = raw.get("development", "proporcional") if isinstance(raw, dict) else raw
    weakness = {"muito fraco": 4, "fraco": 3, "proporcional": 1, "forte": 0, "muito forte": 0}.get(str(development).lower(), 1)
    priorities = get_profile_priorities_internal(profile)
    return weights.get(str(manual).lower(), 2) + weakness + (3 if internal in priorities else 0)


def choose_split(days: int, experience: str, priorities: List[str] = None,
                 preference: Optional[str] = None) -> str:
    return determine_split(days, experience, "Hipertrofia", preference)


async def build_program(profile: Dict[str, Any]) -> Dict[str, Any]:
    return await build_program_v2(profile, db)


def _is_empty_profile(stored: dict) -> bool:
    return engine_is_empty_profile(stored)


async def load_profile(profile_id: str) -> Dict[str, Any]:
    stored = await db.profiles.find_one({"id": profile_id}, {"_id": 0})
    if profile_id == "demo":
        if stored and not stored.get("name"):
            stored = {**DEMO_PROFILE, **stored}
        return stored or DEMO_PROFILE
    if not stored:
        return {"id": profile_id, "user_id": profile_id, "name": "Novo atleta", "goal": "Hipertrofia", "experience": "Intermediário", "days": 3, "session_minutes": 60, "priorities": [], "assessment": {}, "automation_mode": "FORGE_ASSISTED", "onboarding_required": True}
    if stored.get("onboarding_required") is not False and _is_empty_profile(stored):
        stored["onboarding_required"] = True
    return stored


@api.get("/")
async def root(): return {"message": "FORGE API online", "version": "2.0"}


@api.get("/bootstrap")
async def bootstrap(user=Depends(get_current_user), profile_id: Optional[str] = None):
    target = owned_profile_id(user, profile_id)
    profile = await load_profile(target)
    program = await build_program(profile)
    recent = await db.set_logs.find({"profile_id": target}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"profile": profile, "program": program, "exercises": EXERCISES, "muscles": MUSCLES, "techniques": TECHNIQUES, "recent_sets": recent, "demo": target == "demo", "current_user": {"id": user["id"], "email": user["email"], "role": user["role"], "name": user.get("name"), "plan": user.get("plan"), "status": user.get("status"), "expires_at": user.get("expires_at")}}


# Objetivos corporais aceitos — os mesmos ids que NutritionAssessmentIn.goal ja usava.
BODY_GOALS = ("muscle_gain", "fat_loss", "maintenance")


# Objetivo de treino que corresponde a emagrecer/definir. O valor gravado continua sendo
# o mesmo de sempre ("Recomposicao"/"Recomposição"); so o rotulo na tela mudou.
def _is_fat_loss_goal(goal: str) -> bool:
    g = (goal or "").lower()
    return "recomposi" in g or "emagrec" in g


@api.post("/assessment")
async def save_assessment(assessment: DeepAssessment, user=Depends(get_current_user)):
    target = user["id"] if user.get("role") == "ATHLETE" else assessment.profile_id
    doc = assessment.model_dump()
    # transportes: saem do documento, nao viram campo do perfil
    body_goal = doc.pop("body_goal", None)
    escolha_ritmo = doc.pop("goal_intensity", None) or doc.pop("cut_intensity", None)
    doc.pop("cut_intensity", None)
    doc["id"] = target
    doc["user_id"] = target
    doc["assessment_version"] = 2
    # Quem terminou o questionario nao esta mais em onboarding. Sem isto, o atleta que
    # escolhe "treino equilibrado" (nenhuma regiao priorizada) cairia em
    # _is_empty_profile — sem avaliacao E sem prioridade — e receberia programa VAZIO.
    # Mesmo campo que manual_workout_routes ja usa para dizer a mesma coisa.
    doc["onboarding_required"] = False

    # replace_one troca o documento inteiro, entao o questionario ALIMENTAR (outro
    # questionario, com peso/altura/preferencias) era apagado sempre que o atleta
    # refazia a avaliacao de treino. Ele e carregado adiante de proposito.
    anterior = await db.profiles.find_one(
        {"id": target}, {"_id": 0, "nutrition_assessment": 1, "assessment": 1})

    # O muscle map individual saiu do onboarding, entao o formulario novo manda
    # assessment vazio. Isso nao pode apagar a avaliacao historica de quem ja respondeu
    # os 18 musculos: ela continua valendo para rebaixar ao tier de manutencao o que o
    # proprio atleta marcou como ja forte. Prioridade declarada continua vencendo, porque
    # calculate_weekly_volume checa o ranking antes de olhar o desenvolvimento.
    if not doc.get("assessment") and (anterior or {}).get("assessment"):
        doc["assessment"] = anterior["assessment"]

    nutricao = dict((anterior or {}).get("nutrition_assessment") or {})
    # O ritmo Agressivo/Atleta e do plano Elite, tambem quando escolhido no onboarding.
    if _intensity_key(escolha_ritmo) == "agressivo":
        await exigir_capacidade(db, user, PROTOCOLOS_AGRESSIVOS)

    if body_goal in BODY_GOALS:
        # Mesma fonte de verdade da area de Alimentacao, que continua podendo trocar os
        # dois explicitamente depois.
        nutricao["goal"] = body_goal
        # O ritmo e validado NO CONTEXTO do objetivo: resolve_intensity_protocol devolve
        # None para combinacao invalida ("leve" num ganho, qualquer ritmo na manutencao),
        # entao trocar de objetivo nunca deixa o ritmo anterior ativo por engano.
        protocolo = resolve_intensity_protocol(body_goal, escolha_ritmo)
        nutricao["intensity"] = protocolo["intensity"] if protocolo else None
    elif escolha_ritmo and _is_fat_loss_goal(assessment.goal):
        # Caminho anterior (cliente que ainda envia so cut_intensity com goal de treino)
        nutricao["goal"] = "fat_loss"
        protocolo = resolve_intensity_protocol("fat_loss", escolha_ritmo)
        nutricao["intensity"] = protocolo["intensity"] if protocolo else None
    if nutricao:
        doc["nutrition_assessment"] = nutricao

    await db.profiles.replace_one({"id": target}, doc, upsert=True)
    await db.assessments.insert_one({"profile_id": target, "user_id": target, "captured_at": assessment.created_at, "assessment": doc})
    return {"profile": {k: v for k, v in doc.items() if k != "_id"}, "program": await build_program(doc), "assessment_version": 2}


@api.get("/assessments/{profile_id}")
async def assessment_history(profile_id: str, user=Depends(get_current_user)):
    target = owned_profile_id(user, profile_id)
    rows = await db.assessments.find({"profile_id": target}, {"_id": 0, "profile_id": 1, "captured_at": 1, "assessment_version": 1}).sort("captured_at", -1).to_list(30)
    return {"history": rows}


@api.put("/training/preferences")
async def update_training_preferences(payload: TrainingPreferencesIn,
                                      user=Depends(get_current_user)):
    """Change the algorithmic programming style without rewriting athlete history."""
    target = owned_profile_id(user, payload.profile_id)
    profile = await load_profile(target)
    days = max(1, min(7, int(profile.get("days", 3))))
    experience = profile.get("experience", "Intermediário")
    allowed = compatible_splits(days, experience)
    if payload.split_preference not in allowed:
        raise HTTPException(422, "Divisão incompatível com seus dias disponíveis")
    if payload.training_method not in TRAINING_METHOD_PROFILES:
        raise HTTPException(422, "Método de treino inválido")
    manual_active = bool(profile.get("custom_program", {}).get("sessions"))
    fields = {
        "split_preference": payload.split_preference,
        "training_method": payload.training_method,
    }
    if not manual_active:
        fields["current_session_day"] = 1
    await db.profiles.update_one(
        {"id": target},
        {"$set": fields},
        upsert=False,
    )
    updated = await load_profile(target)
    return {
        "profile": updated,
        "program": await build_program(updated),
        "manual_program_active": manual_active,
    }


@api.get("/muscle-map/{profile_id}")
async def muscle_map(profile_id: str, user=Depends(get_current_user)):
    target = owned_profile_id(user, profile_id)
    profile = await load_profile(target)
    program = await build_program(profile)
    priorities = profile.get("priorities", [])
    rows = []
    ex_index = {e["id"]: e for e in EXERCISES}
    for m in MUSCLES:
        raw = profile.get("assessment", {}).get(m, "proporcional")
        if raw is None: raw = "proporcional"
        development = raw.get("development", "proporcional") if isinstance(raw, dict) else raw
        manual_priority = raw.get("priority", "normal") if isinstance(raw, dict) else "normal"
        rows.append({"muscle": m, "development": development, "priority": manual_priority, "score": score_priority(profile, m), "volume": sum(x["sets"] for s in program["sessions"] for x in s["exercises"] if ex_index.get(x["exercise_id"], {}).get("muscle") == m), "frequency": sum(1 for s in program["sessions"] if any(ex_index.get(x["exercise_id"], {}).get("muscle") == m for x in s["exercises"])), "status": "ESPECIALIZAÇÃO" if m in priorities else "MANUTENÇÃO"})
    return {"rows": rows}


@api.get("/exercises/{exercise_id}/alternatives")
async def alternatives(exercise_id: str, _user=Depends(get_current_user)):
    source = next((x for x in EXERCISES if x["id"] == exercise_id), None)
    if not source: raise HTTPException(404, "Exercício não encontrado")
    alt_ids = source.get("alternative_ids", [])
    return {"source": source, "alternatives": [
        {"id": aid, "name": name, "reason": f"Mantém {source['muscle']} e o padrão {source['pattern']}, com diferença de estabilidade e custo de fadiga."}
        for aid, name in zip(alt_ids, source["alternatives"])]}


@api.post("/exercises/substitute")
async def substitute_exercise(payload: ExerciseSubstituteIn, user=Depends(get_current_user)):
    target = owned_profile_id(user, payload.profile_id)
    ex_index = {e["id"]: e for e in EXERCISES}
    source = ex_index.get(payload.original_exercise_id)
    if not source:
        raise HTTPException(404, "Exercício original não encontrado")
    # Only ever accept a swap the matching engine itself already offered for this exact
    # exercise (same primary_muscle + movement_pattern) — this is what guarantees the
    # athlete's existing sets/reps/rest/rir prescription stays valid unchanged, without
    # needing a separate adaptation step.
    if payload.new_exercise_id not in source.get("alternative_ids", []):
        raise HTTPException(400, "Substituição não permitida: não é uma alternativa válida para este exercício")
    profile = await load_profile(target)
    subs = dict(profile.get("exercise_substitutions") or {})
    subs[payload.original_exercise_id] = payload.new_exercise_id
    await db.profiles.update_one(
        {"id": target}, {"$set": {"exercise_substitutions": subs, "user_id": target}}, upsert=True)
    profile = await load_profile(target)
    return {"program": await build_program(profile), "exercise_substitutions": subs}


@api.get("/techniques")
async def techniques(_user=Depends(get_current_user)): return {"techniques": TECHNIQUES}


@api.post("/custom-program")
async def save_custom_program(program: CustomProgram, user=Depends(get_current_user)):
    target = user["id"] if user.get("role") == "ATHLETE" else program.profile_id
    doc = program.model_dump()
    doc["saved_at"] = datetime.now(timezone.utc).isoformat()
    # onboarding_required=False pelo mesmo motivo de save_assessment e do treino manual:
    # quem montou o proprio programa ja disse o que quer. Sem isto, load_profile via um
    # perfil sem avaliacao, marcava onboarding de volta, e build_program devolvia o
    # programa VAZIO de ONBOARDING_REQUIRED — o treino recem-salvo era ignorado.
    await db.profiles.update_one(
        {"id": target},
        {"$set": {"custom_program": doc, "automation_mode": "FORGE_PRO",
                  "user_id": target, "onboarding_required": False},
         # $setOnInsert e nao $set: se o perfil ja existe, o nome dele nao pode ser
         # sobrescrito. Sem isto, um perfil criado SO pelo Program Builder nascia sem
         # nome, e o bootstrap devolvia um perfil que a tela nao tem como rotular.
         "$setOnInsert": {"name": "Novo atleta", "goal": "Hipertrofia",
                          "experience": "Intermediário", "days": 3,
                          "session_minutes": 60, "priorities": [], "assessment": {}}},
        upsert=True)
    profile = await load_profile(target)
    return {"program": await build_program(profile), "custom": doc}


@api.delete("/custom-program/{profile_id}")
async def clear_custom_program(profile_id: str, user=Depends(get_current_user)):
    target = owned_profile_id(user, profile_id)
    await db.profiles.update_one({"id": target}, {"$unset": {"custom_program": ""}})
    # Sem o programa manual o motor volta a mandar, e ele precisa da avaliacao. Se o
    # perfil nunca respondeu nada, o onboarding volta a ser exigido — senao a pessoa
    # receberia um programa generico sem nunca ter sido perguntada.
    perfil_atual = await db.profiles.find_one({"id": target}, {"_id": 0}) or {}
    if engine_is_empty_profile(perfil_atual):
        await db.profiles.update_one({"id": target}, {"$set": {"onboarding_required": True}})
    profile = await load_profile(target)
    return {"program": await build_program(profile), "cleared": True}


FORGE_MUSCLE_PROMPT = """Voc\u00ea \u00e9 um analista de f\u00edsico para atletas de hipertrofia. Analise a(s) foto(s) fornecida(s) e retorne EXCLUSIVAMENTE um JSON v\u00e1lido, sem texto fora do JSON, no seguinte formato:

{
  "observations": {
    "Peitoral superior": {"development": "fraco", "confidence": "alta"},
    "Peitoral esternal": {"development": "proporcional", "confidence": "m\u00e9dia"},
    "Delt\u00f3ide anterior": {"development": "proporcional", "confidence": "baixa"},
    "Delt\u00f3ide lateral": {"development": "fraco", "confidence": "alta"},
    "Delt\u00f3ide posterior": {"development": "proporcional", "confidence": "baixa"},
    "Dorsais / largura": {"development": "proporcional", "confidence": "m\u00e9dia"},
    "Costas / espessura": {"development": "proporcional", "confidence": "m\u00e9dia"},
    "Trap\u00e9zio": {"development": "proporcional", "confidence": "baixa"},
    "B\u00edceps": {"development": "proporcional", "confidence": "m\u00e9dia"},
    "Braquial": {"development": "proporcional", "confidence": "baixa"},
    "Tr\u00edceps": {"development": "proporcional", "confidence": "m\u00e9dia"},
    "Quadr\u00edceps": {"development": "proporcional", "confidence": "m\u00e9dia"},
    "Posteriores": {"development": "proporcional", "confidence": "baixa"},
    "Gl\u00fateos": {"development": "proporcional", "confidence": "baixa"},
    "Adutores": {"development": "proporcional", "confidence": "baixa"},
    "Panturrilhas": {"development": "proporcional", "confidence": "baixa"},
    "Abd\u00f4men": {"development": "proporcional", "confidence": "m\u00e9dia"},
    "Obl\u00edquos": {"development": "proporcional", "confidence": "baixa"}
  },
  "symmetry_notes": "Observa\u00e7\u00e3o sobre simetria aparente entre lados.",
  "proportion_notes": "Observa\u00e7\u00e3o sobre propor\u00e7\u00f5es entre grupos.",
  "suggested_priorities": ["M\u00fasculo 1", "M\u00fasculo 2"],
  "limitations": ["Limita\u00e7\u00e3o da an\u00e1lise por \u00e2ngulo ou qualidade"]
}

REGRAS OBRIGAT\u00d3RIAS:
- development DEVE ser um destes 5 valores exatos: "muito fraco", "fraco", "proporcional", "forte", "muito forte"
- confidence DEVE ser: "alta", "m\u00e9dia" ou "baixa"
- N\u00e3o fa\u00e7a diagn\u00f3stico m\u00e9dico. N\u00e3o estime condi\u00e7\u00f5es de sa\u00fade, doen\u00e7as ou les\u00f5es.
- N\u00e3o estime percentual de gordura corporal nem peso.
- N\u00e3o use termos cl\u00ednicos como "escoliose", "lordose", "atrofia", "hipertrofia patol\u00f3gica".
- N\u00e3o mencione \u00f3rg\u00e3os, ossos ou sistemas n\u00e3o-musculares vis\u00edveis.
- Baseie-se APENAS no que \u00e9 vis\u00edvel na(s) foto(s). Se n\u00e3o puder ver um m\u00fasculo, use confidence "baixa".
- suggested_priorities deve listar 2 a 4 m\u00fasculos com development "fraco" ou "muito fraco" e confidence alta/m\u00e9dia.
- limitations deve listar honestamente o que limita a an\u00e1lise (ex: \u00e2ngulo, ilumina\u00e7\u00e3o, roupa, pose).
- Analise o f\u00edsico como um todo: pontos fortes, pontos fracos, simetria aparente e propor\u00e7\u00f5es.
- Retorne SOMENTE o JSON, sem markdown, sem texto adicional."""


async def analyze_physique(image_bytes: bytes, mime_type: str, views: list) -> dict:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return {"status": "unavailable", "message": "GEMINI_API_KEY n\u00e3o configurada."}
    # Vision model is configurable so a provider retirement does not require another
    # emergency code change. The default tracks Google's current stable multimodal Flash.
    model = os.environ.get("GEMINI_VISION_MODEL", "gemini-3.7-flash").strip() or "gemini-3.7-flash"
    client = google_genai.Client(api_key=key)
    parts = [FORGE_MUSCLE_PROMPT]
    parts.append(google_genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type or "image/jpeg"))
    try:
        response = client.models.generate_content(
            model=model,
            contents=parts,
            config=google_genai.types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )
        raw = response.text.strip()
        if raw.startswith("```"): raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        result = json.loads(raw)
        for m in MUSCLES:
            if m not in result.get("observations", {}):
                result.setdefault("observations", {})[m] = {"development": "proporcional", "confidence": "baixa"}
        result["status"] = "completed"
        result["model"] = model
        result["views_analyzed"] = views
        return result
    except Exception as e:
        logger.exception("gemini vision failed")
        return {"status": "error", "message": f"Falha na an\u00e1lise visual: {str(e)[:200]}", "observations": {}, "suggested_priorities": [], "limitations": ["Erro interno do modelo."]}


# Tipos que o modelo de visao aceita. Allowlist, e nao lista de bloqueio: o que nao
# estiver aqui e recusado, inclusive o que ainda nem existe.
MIMES_DE_FOTO = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
# Assinatura real do arquivo. O content-type vem do cliente e nao prova nada; estes
# primeiros bytes provam.
ASSINATURAS_DE_IMAGEM = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")
LIMITE_DA_FOTO = 8 * 1024 * 1024


def _nome_seguro(nome: Optional[str]) -> str:
    """Nome de arquivo do cliente nunca e usado como caminho, mas ele volta na resposta e
    fica no banco. Guardar so o basename, sem separador e curto, evita que ele vire
    caminho em algum consumidor futuro."""
    base = os.path.basename((nome or "").replace("\\", "/"))
    limpo = "".join(c for c in base if c.isalnum() or c in "._- ")[:80]
    return limpo or "foto"


@api.post("/visual-assessment")
async def visual_assessment(user=Depends(get_current_user), profile_id: str = Form(...), consent: bool = Form(...), views: str = Form(""), photos: List[UploadFile] = File(default=[])):
    target = user["id"] if user.get("role") == "ATHLETE" else profile_id
    try:
        vistas = json.loads(views or "[]")
        if not isinstance(vistas, list):
            raise ValueError("views deve ser uma lista")
        vistas = [str(v)[:40] for v in vistas[:6]]
    except (ValueError, TypeError):
        # Antes isto subia como 500. E entrada do cliente: recusar e a resposta certa.
        raise HTTPException(400, "Campo 'views' inválido")

    record = {
        "id": str(uuid.uuid4()), "profile_id": target, "user_id": target,
        "consent": consent, "views": vistas,
        "files": [_nome_seguro(p.filename) for p in photos],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    if photos and photos[0].filename:
        mime = (photos[0].content_type or "").split(";")[0].strip().lower()
        if mime not in MIMES_DE_FOTO:
            raise HTTPException(415, {"message": "Envie uma imagem JPEG, PNG ou WebP.",
                                      "reason": "unsupported_media_type"})
        # Le com teto: sem isto, o arquivo inteiro entra em memoria antes de qualquer
        # verificacao, e o tamanho so seria conferido depois do estrago.
        contents = await photos[0].read(LIMITE_DA_FOTO + 1)
        if len(contents) > LIMITE_DA_FOTO:
            raise HTTPException(413, {"message": "Imagem acima de 8 MB.",
                                      "reason": "payload_too_large"})
        if not contents.startswith(ASSINATURAS_DE_IMAGEM):
            raise HTTPException(415, {"message": "O arquivo enviado não é uma imagem.",
                                      "reason": "not_an_image"})
        analysis = await analyze_physique(contents, mime, record["views"])
    else:
        analysis = {"status": "unavailable", "message": "Nenhuma foto enviada.", "observations": {}, "suggested_priorities": []}
    record.update(analysis)
    await db.visual_assessments.insert_one(record)
    if analysis.get("status") == "completed":
        vision_data = {m: {"development": obs.get("development", "proporcional"), "priority": "alta" if m in analysis.get("suggested_priorities", []) else "normal", "confidence": obs.get("confidence", "baixa")} for m, obs in analysis.get("observations", {}).items()}
        await db.profiles.update_one({"id": target}, {"$set": {"visual_assessment": vision_data, "visual_notes": {"symmetry": analysis.get("symmetry_notes", ""), "proportion": analysis.get("proportion_notes", ""), "limitations": analysis.get("limitations", [])}}}, upsert=True)
    return {k: v for k, v in record.items() if k != "_id"}


@api.get("/visual-assessment/{profile_id}")
async def get_visual_assessment(profile_id: str, user=Depends(get_current_user)):
    target = owned_profile_id(user, profile_id)
    latest = await db.visual_assessments.find_one({"profile_id": target}, {"_id": 0}, sort=[("created_at", -1)])
    manual = (await load_profile(target)).get("assessment", {})
    vision = (await load_profile(target)).get("visual_assessment", {})
    return {"latest": latest, "manual_assessment": manual, "vision_assessment": vision}


def _desenvolvimento(valor: Any, padrao: str = "proporcional") -> str:
    """Le o desenvolvimento tanto do formato atual quanto do legado.

    O campo ja foi gravado como texto puro ("fraco") e hoje e um dicionario. Perfis
    antigos ainda carregam a forma antiga, entao ler sem conferir o tipo quebra."""
    if isinstance(valor, dict):
        return str(valor.get("development", padrao))
    if isinstance(valor, str) and valor:
        return valor
    return padrao


@api.get("/visual-comparison/{profile_id}")
async def visual_comparison(profile_id: str, user=Depends(get_current_user)):
    target = owned_profile_id(user, profile_id)
    profile = await load_profile(target)
    # Cada um destes ja apareceu em outra forma no banco. Normalizar aqui evita que um
    # perfil antigo derrube a rota com 500 — que e o que acontecia com visual_assessment
    # gravado como texto.
    manual = profile.get("assessment") if isinstance(profile.get("assessment"), dict) else {}
    vision = profile.get("visual_assessment") if isinstance(profile.get("visual_assessment"), dict) else {}
    notes = profile.get("visual_notes") if isinstance(profile.get("visual_notes"), dict) else {}
    comparison = []
    for m in MUSCLES:
        md_dev = _desenvolvimento(manual.get(m))
        vd_dev = _desenvolvimento(vision.get(m), padrao=md_dev)
        agreement = "concordam" if md_dev == vd_dev else ("vis\u00e3o v\u00ea mais desenvolvido" if vd_dev in ("forte", "muito forte") and md_dev in ("fraco", "muito fraco", "proporcional") else "vis\u00e3o v\u00ea menos desenvolvido")
        comparison.append({"muscle": m, "manual": md_dev, "vision": vd_dev, "agreement": agreement})
    # A ordem dos dois "if" importava: numa compreensao, `if v.get(...) if isinstance(...)`
    # avalia o .get PRIMEIRO, entao um valor legado em texto levantava AttributeError e
    # a rota respondia 500. Uma condicao so, com a guarda antes do acesso.
    prioridades_da_visao = [m for m, v in vision.items()
                            if isinstance(v, dict) and v.get("priority") == "alta"]
    prioridades = profile.get("priorities")
    return {"comparison": comparison, "notes": notes,
            "manual_priorities": prioridades if isinstance(prioridades, list) else [],
            "vision_priorities": prioridades_da_visao}


@api.post("/weekly-review")
async def weekly_review(review: WeeklyReview, user=Depends(get_current_user)):
    target = user["id"] if user.get("role") == "ATHLETE" else review.profile_id
    doc = review.model_dump()
    doc["profile_id"] = target
    doc["user_id"] = target
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.weekly_reviews.insert_one(doc)
    actions = []
    if review.performance <= 2 and review.recovery <= 2: actions.append({"action": "reduzir fadiga", "reason": "performance e recuperação caíram juntas"})
    elif review.performance >= 4: actions.append({"action": "manter carga", "reason": "performance estável ou em alta"})
    if review.improved_exercises: actions.append({"action": "manter", "reason": "exercícios com evolução não precisam de troca"})
    if review.worsened_exercises: actions.append({"action": "trocar exercício", "reason": "há queda registrada nos exercícios selecionados"})
    return {"recommendations": actions or [{"action": "manter", "reason": "sem sinal suficiente para uma mudança agressiva"}], "next_week": "Revisão assistida criada a partir das respostas."}


@api.post("/program/analyze")
async def analyze_program(program: ProgramAnalysis, _user=Depends(get_current_user)):
    direct, indirect, sessions = {}, {}, len(program.days)
    for day in program.days:
        for item in day.get("exercises", []):
            ex = next((e for e in EXERCISES if e["id"] == item.get("exercise_id")), None)
            if not ex: continue
            direct[ex["muscle"]] = direct.get(ex["muscle"], 0) + int(item.get("sets", 0))
            for secondary in ex["secondary"]: indirect[secondary] = indirect.get(secondary, 0) + int(item.get("sets", 0)) * 0.5
    return {"volume_direct": direct, "volume_indirect_weighted": indirect, "sessions": sessions, "overlap_note": "Séries indiretas foram ponderadas em 0,5; não equivalem automaticamente a séries diretas.", "fatigue": "moderada" if sum(direct.values()) < 60 else "alta", "priorities_attended": list(direct.keys())}


@api.post("/sets")
async def log_set(item: SetLog, user=Depends(get_current_user)):
    target = user["id"] if user.get("role") == "ATHLETE" else item.profile_id
    doc = item.model_dump()
    doc["profile_id"] = target
    doc["user_id"] = target
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.set_logs.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@api.post("/recovery")
async def log_recovery(item: Recovery, user=Depends(get_current_user)):
    target = user["id"] if user.get("role") == "ATHLETE" else item.profile_id
    doc = item.model_dump()
    doc["profile_id"] = target
    doc["user_id"] = target
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.recovery.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@api.post("/workout/complete")
async def complete_workout(payload: WorkoutCompleteIn, user=Depends(get_current_user)):
    """Program sequence progression (Push -> Pull -> Legs): advances the athlete's
    current_session_day pointer to the NEXT day in the program's own sequence — never
    based on calendar date, never requiring logout/login or midnight. Atomic and
    persistent: the pointer write and the completion-history write both happen here,
    before returning the rebuilt program with the new active session already selected."""
    target = owned_profile_id(user, payload.profile_id)
    profile = await load_profile(target)
    program = await build_program(profile)
    sessions = program.get("sessions") or []
    if not sessions:
        raise HTTPException(400, "Nenhuma sessão disponível para concluir")
    day_values = sorted(s["day"] for s in sessions)
    completed_day = payload.day if payload.day in day_values else program.get("active_day", day_values[0])
    completed_session = next(s for s in sessions if s["day"] == completed_day)
    idx = day_values.index(completed_day)
    next_day = day_values[(idx + 1) % len(day_values)]
    next_session = next(s for s in sessions if s["day"] == next_day)
    now = datetime.now(timezone.utc).isoformat()

    completed_sets = payload.completed_sets
    total_sets = payload.total_sets
    if (completed_sets is not None and total_sets is not None and
            completed_sets < total_sets and not payload.partial_reason.strip()):
        raise HTTPException(400, "Informe por que o treino foi concluído parcialmente")
    adherence = None
    if completed_sets is not None and total_sets:
        adherence = round(min(100, completed_sets / total_sets * 100))
    summary = {
        "completed_sets": completed_sets,
        "total_sets": total_sets,
        "adherence_pct": adherence,
        "duration_seconds": payload.duration_seconds,
        "partial_reason": payload.partial_reason.strip(),
        "discomfort": payload.discomfort,
    }

    # Only the sequence pointer changes on the profile — sets/recovery/substitutions
    # already persisted by their own endpoints are never touched here.
    #
    # Compare-and-swap: only the caller that still sees the pointer on the session being
    # completed may advance it. A network retry, a second tab, a second device or a double
    # tap on the phone arrive with the pointer already moved, match nothing and become a
    # no-op — the rotation advances exactly one step and the completion is recorded exactly
    # once. Identifying the operation by the current session (not by a client-generated id)
    # is what makes this hold across devices, which a per-click token cannot do.
    #
    # The $nin arm is the bootstrap/stale case, and it also covers a missing field and null:
    # a pointer left on a day the program no longer has (the athlete changed days/split, so
    # day 4 of the old 5-day split is gone) must still be completable. _resolve_active_day
    # already falls back to the first day when that happens, so without this arm the CAS
    # would match nothing and the athlete could never complete a workout again.
    advanced = await db.profiles.update_one(
        {"id": target, "$or": [{"current_session_day": completed_day},
                               {"current_session_day": {"$nin": day_values}}]},
        {"$set": {"current_session_day": next_day}},
    )

    if advanced.matched_count == 0:
        # Either the athlete has no stored profile document yet (load_profile answers with a
        # synthetic dict without creating one, so the old upsert here was load-bearing), or
        # this session was already completed.
        if await db.profiles.find_one({"id": target}, {"_id": 1}) is None:
            await db.profiles.update_one(
                {"id": target}, {"$set": {"current_session_day": next_day}}, upsert=True)
        else:
            profile = await load_profile(target)
            return {"program": await build_program(profile), "completed_day": completed_day,
                    "next_day": profile.get("current_session_day", next_day),
                    "next_session": {"day": next_session["day"], "label": next_session.get("label")},
                    "completed_session": {"day": completed_day, "label": completed_session.get("label")},
                    "summary": summary, "already_completed": True}

    await db.workout_completions.insert_one({
        "id": str(uuid.uuid4()), "profile_id": target, "day": completed_day,
        "label": completed_session.get("label"), "completed_at": now,
        "started_at": payload.started_at, "summary": summary,
    })

    profile = await load_profile(target)
    return {"program": await build_program(profile), "completed_day": completed_day,
            "next_day": next_day,
            "next_session": {"day": next_session["day"], "label": next_session.get("label")},
            "completed_session": {"day": completed_day, "label": completed_session.get("label")},
            "summary": summary, "already_completed": False}


def _valid_hydration_day(day: str) -> str:
    try:
        parsed = datetime.strptime(day, "%Y-%m-%d")
    except (TypeError, ValueError):
        raise HTTPException(400, "Data de hidratação inválida")
    if parsed.strftime("%Y-%m-%d") != day:
        raise HTTPException(400, "Data de hidratação inválida")
    return day


def _hydration_goal_ml(profile: Dict[str, Any]) -> int:
    try:
        goal = int(profile.get("hydration_goal_ml") or 2500)
    except (TypeError, ValueError):
        goal = 2500
    return max(1000, min(6000, goal))


async def _hydration_snapshot(target: str, day: str) -> Dict[str, Any]:
    entries = await db.hydration_logs.find(
        {"profile_id": target, "date": day}, {"_id": 0, "amount_ml": 1}
    ).sort("created_at", 1).to_list(length=200)
    total = sum(max(0, int(x.get("amount_ml") or 0)) for x in entries)
    profile = await load_profile(target)
    goal = _hydration_goal_ml(profile)
    return {
        "date": day,
        "total_ml": total,
        "goal_ml": goal,
        "remaining_ml": max(0, goal - total),
        "progress_pct": min(100, round(total / goal * 100)) if goal else 0,
        "can_undo": bool(entries),
    }


@api.get("/hydration/{day}")
async def get_hydration(day: str, user=Depends(get_current_user)):
    day = _valid_hydration_day(day)
    return await _hydration_snapshot(user["id"], day)


@api.post("/hydration/{day}")
async def add_hydration(day: str, payload: HydrationAddIn,
                        user=Depends(get_current_user)):
    day = _valid_hydration_day(day)
    target = user["id"]
    snapshot = await _hydration_snapshot(target, day)
    if snapshot["total_ml"] + payload.amount_ml > 10000:
        raise HTTPException(400, "Limite diário de registro atingido")
    await db.hydration_logs.insert_one({
        "id": str(uuid.uuid4()),
        "profile_id": target,
        "user_id": target,
        "date": day,
        "amount_ml": payload.amount_ml,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return await _hydration_snapshot(target, day)


@api.delete("/hydration/{day}/last")
async def undo_hydration(day: str, user=Depends(get_current_user)):
    day = _valid_hydration_day(day)
    target = user["id"]
    last = await db.hydration_logs.find_one(
        {"profile_id": target, "date": day}, sort=[("created_at", -1)]
    )
    if last:
        await db.hydration_logs.delete_one({"_id": last["_id"]})
    return await _hydration_snapshot(target, day)


# Um treino em andamento so vale para a sessao do dia: um rascunho antigo (ciclo
# anterior, mesmo dia do split) nao deve ressuscitar cargas velhas por cima das
# sugestoes de progressao.
SESSION_DRAFT_TTL_HOURS = 12
MAX_DRAFT_ENTRIES = 400


def _sanitize_draft_inputs(raw: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """So passa {chave: {weight, reps, rir}} com texto curto: o rascunho e digitacao do
    atleta, nao um documento livre."""
    limpo: Dict[str, Dict[str, str]] = {}
    for key, value in list((raw or {}).items())[:MAX_DRAFT_ENTRIES]:
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        limpo[key[:80]] = {
            "weight": str(value.get("weight", ""))[:12],
            "reps": str(value.get("reps", ""))[:12],
            "rir": str(value.get("rir", ""))[:4],
        }
    return limpo


@api.put("/workout/session-draft")
async def save_session_draft(payload: WorkoutSessionDraftIn, user=Depends(get_current_user)):
    """Autosave do preenchimento em andamento. Nao registra serie nem toca no ponteiro
    do programa — POST /sets e POST /workout/complete seguem sendo os unicos donos
    disso. Aqui e so o rascunho, para nada digitado se perder num refresh."""
    target = owned_profile_id(user, payload.profile_id)
    doc = {
        "profile_id": target,
        "day": payload.day,
        "inputs": _sanitize_draft_inputs(payload.inputs),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.workout_session_drafts.replace_one({"profile_id": target}, doc, upsert=True)
    return {"saved_at": doc["updated_at"], "entries": len(doc["inputs"])}


@api.get("/workout/session-draft")
async def get_session_draft(user=Depends(get_current_user), day: Optional[int] = None,
                            profile_id: Optional[str] = None):
    """Devolve o rascunho apenas se for da MESMA sessao e ainda recente."""
    target = owned_profile_id(user, profile_id)
    doc = await db.workout_session_drafts.find_one({"profile_id": target}, {"_id": 0})
    if not doc:
        return {"inputs": {}, "saved_at": None}
    if day is not None and doc.get("day") is not None and int(doc["day"]) != int(day):
        return {"inputs": {}, "saved_at": None, "reason": "other_day"}
    try:
        idade = datetime.now(timezone.utc) - datetime.fromisoformat(doc["updated_at"])
        if idade > timedelta(hours=SESSION_DRAFT_TTL_HOURS):
            return {"inputs": {}, "saved_at": None, "reason": "expired"}
    except (KeyError, ValueError):
        return {"inputs": {}, "saved_at": None}
    return {"inputs": doc.get("inputs") or {}, "saved_at": doc.get("updated_at"), "day": doc.get("day")}


@api.get("/analytics")
async def analytics(user=Depends(get_current_user), profile_id: Optional[str] = None):
    target = owned_profile_id(user, profile_id)
    ex_index = {e["id"]: e for e in EXERCISES}
    now = datetime.now(timezone.utc)
    recent = await db.set_logs.find({"profile_id": target}).sort("created_at", -1).to_list(500)
    volume: Dict[str, int] = {}
    prs_map: Dict[str, Dict[str, Any]] = {}
    for s in recent:
        m = ex_index.get(s["exercise_id"], {}).get("muscle", "")
        if m: volume[m] = volume.get(m, 0) + 1
        weight = float(s.get("weight") or 0)
        if weight <= 0:
            continue
        current = prs_map.setdefault(s["exercise_id"], {
            "weight": weight, "reps": s["reps"], "date": s["created_at"][:10],
            "start_weight": weight,
        })
        # A consulta vem do registro mais novo para o mais antigo. Assim, a última
        # passagem guarda a linha de base e o melhor peso continua sendo o recorde.
        current["start_weight"] = weight
        if weight > float(current["weight"]):
            current.update({"weight": weight, "reps": s["reps"], "date": s["created_at"][:10]})
    trend = []
    for w in range(3, -1, -1):
        wk_start = (now - timedelta(days=now.weekday() + 1 + w*7)).strftime("%Y-%m-%d")
        wk_end = (now - timedelta(days=now.weekday() + 1 + max(0, w-1)*7)).strftime("%Y-%m-%d") if w > 0 else now.strftime("%Y-%m-%d")
        wk_sets = [s for s in recent if wk_start <= s["created_at"][:10] <= wk_end]
        avg = round(sum(float(s["weight"]) for s in wk_sets) / max(1, len(wk_sets)), 1)
        trend.append({"week": f"S{w+1}", "load": avg, "volume": sum(s["reps"] for s in wk_sets)})
    volume_list = [{"name": m, "value": v, "target": max(v, 10)} for m, v in sorted(volume.items(), key=lambda kv: -kv[1])[:10]]
    prs_list = [{
        "exercise": ex_index.get(eid, {}).get("name", eid),
        "value": f"{p['weight']:g} kg \u00d7 {p['reps']}", "date": p["date"],
        "weight": p["weight"], "reps": p["reps"], "start_weight": p["start_weight"],
        "delta_weight": round(float(p["weight"]) - float(p["start_weight"]), 1),
    } for eid, p in sorted(prs_map.items(), key=lambda kv: -float(kv[1]["weight"]))[:5]]
    # Product analytics: decision-oriented signals, never decorative estimates.
    # Every series below is derived from persisted athlete records and may be empty.
    logged_dates = {s.get("created_at", "")[:10] for s in recent if s.get("created_at")}
    adherence_calendar = []
    for offset in range(27, -1, -1):
        day = (now - timedelta(days=offset)).strftime("%Y-%m-%d")
        adherence_calendar.append({"date": day, "trained": day in logged_dates})
    recovery_rows = await db.recovery.find(
        {"profile_id": target}, {"_id": 0}
    ).sort("created_at", -1).to_list(28)
    recovery_by_day = {}
    for row in recovery_rows:
        day = str(row.get("created_at") or row.get("date") or "")[:10]
        if day and day not in recovery_by_day:
            recovery_by_day[day] = round((float(row.get("energy", 3)) + float(row.get("recovery", 3))) / 2, 1)
    recovery_load = []
    for offset in range(13, -1, -1):
        day = (now - timedelta(days=offset)).strftime("%Y-%m-%d")
        day_sets = [s for s in recent if str(s.get("created_at", ""))[:10] == day]
        recovery_load.append({"date": day, "sets": len(day_sets), "readiness": recovery_by_day.get(day)})
    weights = await db.nutrition_weight_logs.find(
        {"profile_id": target}, {"_id": 0, "date": 1, "weight_kg": 1}
    ).sort("date", 1).to_list(90)
    body_trend = [{"date": w.get("date"), "weight": w.get("weight_kg")} for w in weights if w.get("weight_kg")]
    milestones = [{"date": p["date"], "title": ex_index.get(eid, {}).get("name", eid), "detail": f"{p['weight']:g} kg × {p['reps']}"}
                  for eid, p in sorted(prs_map.items(), key=lambda kv: kv[1]["date"], reverse=True)[:6]]
    return {"volume": volume_list or [], "trend": trend, "prs": prs_list,
            "adherence_calendar": adherence_calendar, "recovery_load": recovery_load,
            "body_trend": body_trend, "milestones": milestones}


@api.get("/exercise-history/{exercise_id}")
async def exercise_history(exercise_id: str, user=Depends(get_current_user), profile_id: Optional[str] = None):
    target = owned_profile_id(user, profile_id)
    rows = await db.set_logs.find({"profile_id": target, "exercise_id": exercise_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    ex = next((e for e in EXERCISES if e["id"] == exercise_id), None)
    return {"exercise": ex, "history": rows, "count": len(rows)}


@api.post("/program/preview")
async def preview_program(profile: Dict[str, Any], user=Depends(get_current_user)):
    doc = {**profile}
    doc.setdefault("id", user["id"])
    doc.setdefault("days", int(doc.get("days", 3)))
    doc.setdefault("priorities", doc.get("priorities", []))
    doc.setdefault("experience", doc.get("experience", "Intermedi\u00e1rio"))
    doc.setdefault("assessment", doc.get("assessment", {}))
    program = await build_program(doc)
    split = choose_split(doc["days"], doc.get("experience", "Intermedi\u00e1rio"),
                         doc.get("priorities", []), doc.get("split_preference"))
    return {"program": program, "split": split, "preview": True, "profile_snapshot": {k: doc[k] for k in ["days", "priorities", "experience", "assessment", "session_minutes"] if k in doc}}


@api.get("/weekly-report")
async def weekly_report(user=Depends(get_current_user), profile_id: Optional[str] = None):
    target = owned_profile_id(user, profile_id)
    now = datetime.now(timezone.utc)
    wk_start = (now - timedelta(days=now.weekday() + 7)).strftime("%Y-%m-%d")
    set_count = await db.set_logs.count_documents({"profile_id": target, "created_at": {"$gte": wk_start}})
    recovery_rows = await db.recovery.find({"profile_id": target}).sort("created_at", -1).to_list(7)
    avg_energy = round(sum(r.get("energy", 3) for r in recovery_rows) / max(1, len(recovery_rows)), 1)
    profile = await load_profile(target)
    planned = int(profile.get("days", 4) or 4)
    completed = min(planned, max(1, set_count // 12))
    adherence = min(100, round(completed / max(1, planned) * 100))
    return {"completed": completed, "planned": planned, "adherence": adherence, "prs": 0, "headline": "Boa progress\u00e3o com consist\u00eancia de treino." if adherence >= 75 else "Ader\u00eancia abaixo do planejado. Revise o microciclo.", "signals": [f"Readiness m\u00e9dio de {avg_energy}/5.", f"{set_count} s\u00e9ries registradas esta semana."], "recommendation": "Mantenha o plano atual." if adherence >= 75 else "Considere reduzir dias ou volume para melhorar consist\u00eancia."}


async def check_ai_quota(user: dict) -> Optional[str]:
    if user.get("ai_enabled") is False:
        return "IA desabilitada para esta conta pelo administrador."
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month = today[:7]
    daily = await db.ai_usage.aggregate([{"$match": {"user_id": user["id"], "date": today}}, {"$group": {"_id": None, "total": {"$sum": "$count"}}}]).to_list(1)
    monthly = await db.ai_usage.aggregate([{"$match": {"user_id": user["id"], "date": {"$regex": f"^{month}"}}}, {"$group": {"_id": None, "total": {"$sum": "$count"}}}]).to_list(1)
    daily_used = daily[0]["total"] if daily else 0
    monthly_used = monthly[0]["total"] if monthly else 0
    if user.get("role") != "SUPER_ADMIN":
        if daily_used >= int(user.get("ai_daily_limit", 40)): return "Limite diário de perguntas ao coach atingido. Tente novamente amanhã."
        if monthly_used >= int(user.get("ai_monthly_limit", 800)): return "Limite mensal atingido."
    return None


async def bump_ai_usage(user: dict):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.ai_usage.update_one({"user_id": user["id"], "date": today}, {"$inc": {"count": 1}, "$set": {"model": deepseek_model(), "email": user["email"]}}, upsert=True)


@api.post("/coach")
async def coach(payload: Dict[str, Any], user=Depends(get_current_user)):
    question = (payload.get("question") or "").strip()
    context = payload.get("context", {})
    if not question: raise HTTPException(400, "Pergunta necess\u00e1ria")
    blocked = await check_ai_quota(user)
    if blocked: raise HTTPException(429, blocked)
    provider = get_coach_provider()
    if not provider:
        raise HTTPException(503, "Coach indispon\u00edvel: DEEPSEEK_API_KEY n\u00e3o configurada.")
    await bump_ai_usage(user)
    prompt = f"CONTEXTO REAL DO ATLETA:\n{json.dumps(context, ensure_ascii=False)}\n\nPERGUNTA: {question}"

    async def events():
        try:
            async for chunk in provider.stream_chat(FORGE_COACH_SYSTEM, prompt):
                try:
                    err = json.loads(chunk)
                    if isinstance(err, dict) and "error" in err:
                        line = "data: " + json.dumps(err, ensure_ascii=False) + "\n\n"
                        yield line
                        return
                except (json.JSONDecodeError, TypeError):
                    pass
                line = "data: " + json.dumps({'text': chunk}, ensure_ascii=False) + "\n\n"
                yield line
        except Exception:
            logger.exception("coach stream failed")
            line = "data: " + json.dumps({'error': 'N\u00e3o foi poss\u00edvel consultar o coach agora.'}) + "\n\n"
            yield line
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(nutrition_router)
app.include_router(manual_workout_router)
app.include_router(nutrition_import_router)
app.include_router(billing_router)
app.include_router(signup_router)
app.include_router(preassessment_router)
app.include_router(password_reset_router)
app.include_router(api)
def _origens_permitidas() -> List[str]:
    """Allowlist exata de origens.

    O padrao anterior era "*" junto com allow_credentials=True, combinacao que a propria
    especificacao de CORS proibe. Como o FORGE autentica por Bearer no cabecalho (e nao
    por cookie), o navegador nao mandava credencial sozinho e o estrago pratico era
    pequeno — mas "*" abre a API inteira para qualquer site fazer requisicao, e nao ha
    motivo: o frontend e servido pelo MESMO dominio, atraves do nginx, entao no uso
    normal nao existe requisicao cross-origin nenhuma.

    Quem precisar de outra origem (um app, um ambiente de teste) lista em CORS_ORIGINS,
    separado por virgula. "*" e recusado de proposito."""
    bruto = (os.environ.get("CORS_ORIGINS") or "").strip()
    site = (os.environ.get("FORGE_SITE_URL") or "https://forge.aiexec.com.br").rstrip("/")
    origens = [o.strip().rstrip("/") for o in bruto.split(",") if o.strip() and o.strip() != "*"]
    if bruto == "*":
        logger.warning("CORS_ORIGINS='*' ignorado: allowlist exige origens explicitas")
    if site not in origens:
        origens.append(site)
    return origens


# ── Limite de tamanho do corpo ───────────────────────────────────────────────────────
# O nginx ja corta em 25 MB, mas esse teto existe para a foto do visual assessment. Um
# corpo JSON de 25 MB continuaria sendo lido e desserializado inteiro em memoria, e a
# versao de starlette em uso tem falha conhecida de bufferizar campo de formulario sem
# limite (PYSEC-2026-1943). Recusar cedo, pelo Content-Length, custa quase nada.
LIMITE_DE_CORPO = 1 * 1024 * 1024          # 1 MB para qualquer rota
LIMITE_DE_UPLOAD = 8 * 1024 * 1024         # 8 MB onde ha foto de verdade
ROTAS_COM_UPLOAD = ("/api/visual-assessment",)


@app.middleware("http")
async def limitar_tamanho_do_corpo(request: Request, call_next):
    declarado = request.headers.get("content-length")
    if declarado:
        try:
            tamanho = int(declarado)
        except ValueError:
            return JSONResponse({"detail": "Content-Length inválido"}, status_code=400)
        # scope["path"] pelo mesmo motivo de auth.get_current_user: e o caminho que o
        # roteador vai casar. `request.url.path` e reconstruido, e um caminho forjado
        # que parecesse a rota de upload renderia o teto de 8 MB em qualquer rota.
        caminho = request.scope.get("path") or request.url.path
        teto = (LIMITE_DE_UPLOAD if any(caminho.startswith(r) for r in ROTAS_COM_UPLOAD)
                else LIMITE_DE_CORPO)
        if tamanho > teto:
            logger.warning("corpo recusado por tamanho: %s bytes em %s", tamanho, caminho)
            return JSONResponse(
                {"detail": {"message": "Conteúdo grande demais.", "reason": "payload_too_large"}},
                status_code=413)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_origens_permitidas(),
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("invite_token")
    await db.set_logs.create_index([("profile_id", 1), ("created_at", -1)])
    await db.profiles.create_index("user_id")
    await db.admin_audit_log.create_index([("created_at", -1)])
    await db.ai_usage.create_index([("user_id", 1), ("date", 1)])
    await db.nutrition_plan_drafts.create_index("profile_id", unique=True)
    await db.nutrition_preferences.create_index([("profile_id", 1), ("food_id", 1)], unique=True)
    # Cobranca. Os indices unicos sao a garantia estrutural contra: duas assinaturas para
    # o mesmo atleta, reprocessamento do mesmo evento e duas liberacoes pelo mesmo
    # pagamento — nenhuma delas depende de o codigo "lembrar" de checar.
    await db.subscriptions.create_index("user_id", unique=True)
    await db.subscriptions.create_index("provider_subscription_id", sparse=True)
    await db.billing_events.create_index("event_key", unique=True)
    await db.subscription_attempts.create_index("reference", unique=True)
    await db.subscription_attempts.create_index([("user_id", 1), ("created_at", -1)])
    await db.pix_attempts.create_index("reference", unique=True)
    await db.pix_attempts.create_index("provider_payment_id", sparse=True)
    await db.pix_attempts.create_index([("user_id", 1), ("created_at", -1)])
    await db.signup_attempts.create_index("email", unique=True)
    await db.signup_attempts.create_index("reference", sparse=True)
    email = os.environ.get("FORGE_SUPER_ADMIN_EMAIL")
    if email:
        uid, invite = await seed_super_admin(db, email)
        # persist invite link for main agent visibility (only when brand-new)
        if invite:
            memory = ROOT_DIR.parent / "memory"
            memory.mkdir(exist_ok=True)
            (memory / "super_admin_invite.txt").write_text(f"email: {email}\ninvite_token: {invite}\ninvite_url: /invite/{invite}\nuser_id: {uid}\n")


@app.on_event("shutdown")
async def shutdown(): client.close()

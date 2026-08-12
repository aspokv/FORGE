from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Depends, Request
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import os, uuid, json, logging, base64
from google import genai as google_genai

from llm_providers import get_coach_provider, FORGE_COACH_SYSTEM

from auth import router as auth_router, get_current_user, seed_super_admin
from admin_routes import router as admin_router
from nutrition_routes import router as nutrition_router
from muscles import (
    to_frontend, to_internal, get_profile_priorities_internal,
    get_assessment_internal, FRONTEND_MUSCLES as MUSCLES_FRONTEND_LIST,
    LEGACY_TO_INTERNAL, MUSCLE_IDS,
)
from engine import (
    FRONTEND_EXERCISE_LIST, EXERCISE_INDEX, build_program_v2,
    _is_empty_profile as engine_is_empty_profile,
    validate_sessions, determine_split, EXERCISES as ENGINE_EXERCISES,
)

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="FORGE Training OS")
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
    rir: int = 2
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
    secondary_goal: str = ""
    days: int = 3
    session_minutes: int = 60
    split: str = ""
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


def choose_split(days: int, experience: str, priorities: List[str] = None) -> str:
    return determine_split(days, experience, "Hipertrofia")


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


@api.post("/assessment")
async def save_assessment(assessment: DeepAssessment, user=Depends(get_current_user)):
    target = user["id"] if user.get("role") == "ATHLETE" else assessment.profile_id
    doc = assessment.model_dump()
    doc["id"] = target
    doc["user_id"] = target
    doc["assessment_version"] = 2
    await db.profiles.replace_one({"id": target}, doc, upsert=True)
    await db.assessments.insert_one({"profile_id": target, "user_id": target, "captured_at": assessment.created_at, "assessment": doc})
    return {"profile": {k: v for k, v in doc.items() if k != "_id"}, "program": await build_program(doc), "assessment_version": 2}


@api.get("/assessments/{profile_id}")
async def assessment_history(profile_id: str, user=Depends(get_current_user)):
    target = owned_profile_id(user, profile_id)
    rows = await db.assessments.find({"profile_id": target}, {"_id": 0, "profile_id": 1, "captured_at": 1, "assessment_version": 1}).sort("captured_at", -1).to_list(30)
    return {"history": rows}


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
    return {"source": source, "alternatives": [{"name": name, "reason": f"Mantém {source['muscle']} e o padrão {source['pattern']}, com diferença de estabilidade e custo de fadiga."} for name in source["alternatives"]]}


@api.get("/techniques")
async def techniques(_user=Depends(get_current_user)): return {"techniques": TECHNIQUES}


@api.post("/custom-program")
async def save_custom_program(program: CustomProgram, user=Depends(get_current_user)):
    target = user["id"] if user.get("role") == "ATHLETE" else program.profile_id
    doc = program.model_dump()
    doc["saved_at"] = datetime.now(timezone.utc).isoformat()
    await db.profiles.update_one({"id": target}, {"$set": {"custom_program": doc, "automation_mode": "FORGE_PRO", "user_id": target}}, upsert=True)
    profile = await load_profile(target)
    return {"program": await build_program(profile), "custom": doc}


@api.delete("/custom-program/{profile_id}")
async def clear_custom_program(profile_id: str, user=Depends(get_current_user)):
    target = owned_profile_id(user, profile_id)
    await db.profiles.update_one({"id": target}, {"$unset": {"custom_program": ""}})
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
    client = google_genai.Client(api_key=key)
    parts = [FORGE_MUSCLE_PROMPT]
    parts.append(google_genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type or "image/jpeg"))
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
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
        result["model"] = "gemini-2.0-flash"
        result["views_analyzed"] = views
        return result
    except Exception as e:
        logger.exception("gemini vision failed")
        return {"status": "error", "message": f"Falha na an\u00e1lise visual: {str(e)[:200]}", "observations": {}, "suggested_priorities": [], "limitations": ["Erro interno do modelo."]}


@api.post("/visual-assessment")
async def visual_assessment(user=Depends(get_current_user), profile_id: str = Form(...), consent: bool = Form(...), views: str = Form(""), photos: List[UploadFile] = File(default=[])):
    target = user["id"] if user.get("role") == "ATHLETE" else profile_id
    record = {
        "id": str(uuid.uuid4()), "profile_id": target, "user_id": target,
        "consent": consent, "views": json.loads(views or "[]"),
        "files": [p.filename for p in photos],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    if photos and photos[0].filename:
        contents = await photos[0].read()
        mime = photos[0].content_type or "image/jpeg"
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


@api.get("/visual-comparison/{profile_id}")
async def visual_comparison(profile_id: str, user=Depends(get_current_user)):
    target = owned_profile_id(user, profile_id)
    profile = await load_profile(target)
    manual = profile.get("assessment", {})
    vision = profile.get("visual_assessment", {})
    notes = profile.get("visual_notes", {})
    comparison = []
    for m in MUSCLES:
        md = manual.get(m, {})
        md_dev = md.get("development", "proporcional") if isinstance(md, dict) else md
        vd = vision.get(m, {})
        vd_dev = vd.get("development", "proporcional") if isinstance(vd, dict) else md_dev
        agreement = "concordam" if md_dev == vd_dev else ("vis\u00e3o v\u00ea mais desenvolvido" if vd_dev in ("forte", "muito forte") and md_dev in ("fraco", "muito fraco", "proporcional") else "vis\u00e3o v\u00ea menos desenvolvido")
        comparison.append({"muscle": m, "manual": md_dev, "vision": vd_dev, "agreement": agreement})
    return {"comparison": comparison, "notes": notes, "manual_priorities": profile.get("priorities", []), "vision_priorities": [m for m, v in vision.items() if v.get("priority") == "alta" if isinstance(v, dict)]}


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
        prev = prs_map.get(s["exercise_id"])
        if not prev or s["weight"] > prev["weight"]:
            prs_map[s["exercise_id"]] = {"weight": s["weight"], "reps": s["reps"], "date": s["created_at"][:10]}
    trend = []
    for w in range(3, -1, -1):
        wk_start = (now - timedelta(days=now.weekday() + 1 + w*7)).strftime("%Y-%m-%d")
        wk_end = (now - timedelta(days=now.weekday() + 1 + max(0, w-1)*7)).strftime("%Y-%m-%d") if w > 0 else now.strftime("%Y-%m-%d")
        wk_sets = [s for s in recent if wk_start <= s["created_at"][:10] <= wk_end]
        avg = round(sum(float(s["weight"]) for s in wk_sets) / max(1, len(wk_sets)), 1)
        trend.append({"week": f"S{w+1}", "load": avg, "volume": sum(s["reps"] for s in wk_sets)})
    volume_list = [{"name": m, "value": v, "target": max(v, 10)} for m, v in sorted(volume.items(), key=lambda kv: -kv[1])[:10]]
    prs_list = [{"exercise": ex_index.get(eid, {}).get("name", eid), "value": f"{p['weight']} kg \u00d7 {p['reps']}", "date": p["date"]} for eid, p in sorted(prs_map.items(), key=lambda kv: -float(kv[1]["weight"]))[:5]]
    return {"volume": volume_list or [{"name": "Sem dados", "value": 0, "target": 10}], "trend": trend, "prs": prs_list}


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
    split = choose_split(doc["days"], doc.get("experience", "Intermedi\u00e1rio"), doc.get("priorities", []))
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
    await db.ai_usage.update_one({"user_id": user["id"], "date": today}, {"$inc": {"count": 1}, "$set": {"model": "deepseek-chat", "email": user["email"]}}, upsert=True)


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
app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])


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

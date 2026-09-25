# -*- coding: utf-8 -*-
"""Refeições do jeito do atleta, de ponta a ponta (Elite).

O pedido veio assim: "quero excluir café da manhã e almoço, adicionar de novo e botar o
que eu quero — total livre arbítrio, no Elite". Esta suíte cobre o que a de unidade não
alcança: a porta do plano, a trava contra tela velha, as metas de cada tipo de plano e os
registros do dia andando junto com as refeições.
"""
import functools
import os
import sys
import uuid
from datetime import date as CalendarDate, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

ENV_FILE = Path(__file__).parent.parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
sys.path.insert(0, str(Path(__file__).parent.parent))

import server  # noqa: E402
from auth import create_token  # noqa: E402
from food_diary import DIARY_FOODS  # noqa: E402
from loop_do_motor import LOOP  # noqa: E402
from nutrition_engine import FOOD_INDEX, build_food_item  # noqa: E402

APP = server.app
DB = server.db
SO_DO_DIARIO = next(fid for fid in DIARY_FOODS if fid not in FOOD_INDEX)
# O dia que a tela manda. Fixo e explícito: o servidor usa o dia que o aparelho diz, e não
# o dia em UTC, que à noite no Brasil já é amanhã.
DIA = CalendarDate(2026, 9, 24).isoformat()


def asincrono(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return LOOP.run_until_complete(fn(*args, **kwargs))
    return wrapper


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP), base_url="http://forge.test")


def _refeicao(nome, itens):
    foods = [build_food_item(fid, g) for fid, g in itens]
    return {"name": nome, "foods": foods, "target_cal": 500, "target_protein": 30,
            "target_fat": 15, "archetype_id": "default", "coherence_score": 80}


PLANO_GERADO = [
    ("Café da manhã", [("eggs-whole", 100), ("oats", 40)]),
    ("Almoço", [("rice-white", 150), ("chicken-breast", 150)]),
    ("Lanche", [("banana", 100), ("whey-protein", 30)]),
    ("Jantar", [("potato", 200), ("beef-grill", 150)]),
]
METAS = {"goal_calories": 2400, "protein_g": 180, "carbs_g": 250, "fat_g": 70}


async def _atleta(plano="elite", importado=False):
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    uid = str(uuid.uuid4())
    agora = datetime.now(timezone.utc).isoformat()
    await DB.users.insert_one({
        "id": uid, "email": f"refeicoes.{uid[:8]}@example.com", "name": "Atleta",
        "role": "ATHLETE", "status": "ACTIVE", "created_at": agora,
        "signup_source": "public", "archived_at": None,
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": plano, "status": "active",
        "provider": "courtesy", "amount_cents": 0, "currency": "BRL"}}, upsert=True)
    await DB.profiles.insert_one({
        "id": uid, "user_id": uid, "name": "Atleta", "onboarding_required": False,
        "nutrition_assessment": {"weight_kg": 83, "height_cm": 180, "age": 30, "sex": "male",
                                 "goal": "recomp", "activity_level": "moderate",
                                 "training_days": 5, "meal_count": 4,
                                 "allergies": [], "dietary_restrictions": []}})
    plan = {"meals": [_refeicao(n, i) for n, i in PLANO_GERADO], "targets": dict(METAS),
            "daily_totals": {"kcal": 2000, "protein_g": 150, "carbs_g": 200, "fat_g": 60}}
    if importado:
        plan.update(source="manual_import", targets_source="manual_import")
    await DB.nutrition_plans.insert_one({"profile_id": uid, "user_id": uid, "plan": plan,
                                         "created_at": agora})
    return uid, {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}


async def _limpar(uid):
    for nome in ("users", "subscriptions", "profiles", "nutrition_plans", "nutrition_adherence"):
        await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid}, {"profile_id": uid}]})


async def _plano(uid):
    return (await DB.nutrition_plans.find_one({"profile_id": uid}))["plan"]


def _nomes(plano):
    return [m["name"] for m in plano["meals"]]


NOVA = {"nome": "Café reforçado", "itens": [{"food_id": "eggs-whole", "grams": 150},
                                            {"food_id": SO_DO_DIARIO, "grams": 60}]}


# ── A porta ────────────────────────────────────────────────────────────────────────────

@asincrono
async def test_so_o_elite_monta_refeicao_do_proprio_jeito():
    uid, h = await _atleta("pro")
    try:
        async with await _cliente() as c:
            criar = await c.post("/api/nutrition/plan/meals", headers=h, json=NOVA)
            editar = await c.put("/api/nutrition/plan/meals/0", headers=h, json=NOVA)
            excluir = await c.delete("/api/nutrition/plan/meals/0", headers=h,
                                     params={"nome": "Café da manhã"})
        # 402, e não 403: é falta de plano, e a tela leva para a página de planos.
        assert (criar.status_code, editar.status_code, excluir.status_code) == (402, 402, 402)
        assert _nomes(await _plano(uid)) == [n for n, _ in PLANO_GERADO]
    finally:
        await _limpar(uid)


# ── Excluir ────────────────────────────────────────────────────────────────────────────

@asincrono
async def test_excluir_tira_a_refeicao_e_nao_mexe_nas_outras():
    uid, h = await _atleta()
    try:
        antes = await _plano(uid)
        async with await _cliente() as c:
            r = await c.delete("/api/nutrition/plan/meals/0", headers=h,
                               params={"nome": "Café da manhã", "dia": DIA})
        assert r.status_code == 200, r.text
        depois = await _plano(uid)
        assert _nomes(depois) == ["Almoço", "Lanche", "Jantar"]
        # As outras NÃO crescem para cobrir o buraco: quem exclui está redesenhando o dia.
        assert depois["meals"] == antes["meals"][1:]
        # Plano gerado: a meta vem do questionário e fica.
        assert depois["targets"] == METAS
        assert r.json()["removida"] == "Café da manhã"
    finally:
        await _limpar(uid)


@asincrono
async def test_excluir_cafe_e_almoco_e_criar_de_novo_do_meu_jeito():
    """O pedido do atleta, na ordem em que ele descreveu."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            assert (await c.delete("/api/nutrition/plan/meals/0", headers=h,
                                   params={"nome": "Café da manhã"})).status_code == 200
            assert (await c.delete("/api/nutrition/plan/meals/0", headers=h,
                                   params={"nome": "Almoço"})).status_code == 200
            r = await c.post("/api/nutrition/plan/meals", headers=h, json={**NOVA, "posicao": 0})
            assert r.status_code == 200, r.text
            r = await c.post("/api/nutrition/plan/meals", headers=h, json={
                "nome": "Almoço livre", "posicao": 1,
                "itens": [{"food_id": "rice-white", "grams": 220}, {"food_id": "salmon", "grams": 180}]})
            assert r.status_code == 200, r.text
        plano = await _plano(uid)
        assert _nomes(plano) == ["Café reforçado", "Almoço livre", "Lanche", "Jantar"]
        almoco = plano["meals"][1]
        assert [(f["food_id"], f["grams"]) for f in almoco["foods"]] == [("rice-white", 220), ("salmon", 180)]
        assert almoco["livre"] is True
    finally:
        await _limpar(uid)


@asincrono
async def test_excluir_com_a_tela_desatualizada_nao_apaga_a_refeicao_errada():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            # Outra aba já excluiu o café: o índice 0 agora é o almoço.
            await c.delete("/api/nutrition/plan/meals/0", headers=h, params={"nome": "Café da manhã"})
            r = await c.delete("/api/nutrition/plan/meals/0", headers=h, params={"nome": "Café da manhã"})
        assert r.status_code == 409
        assert "Almoço" in _nomes(await _plano(uid))
    finally:
        await _limpar(uid)


@asincrono
async def test_a_ultima_refeicao_nao_pode_ser_excluida():
    """Plano sem refeição nenhuma não tem como receber a próxima."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            for nome in ("Café da manhã", "Almoço", "Lanche"):
                assert (await c.delete("/api/nutrition/plan/meals/0", headers=h,
                                       params={"nome": nome})).status_code == 200
            r = await c.delete("/api/nutrition/plan/meals/0", headers=h, params={"nome": "Jantar"})
        assert r.status_code == 400
        assert "Crie a nova antes" in r.json()["detail"]
        assert _nomes(await _plano(uid)) == ["Jantar"]
    finally:
        await _limpar(uid)


# ── Criar e editar ─────────────────────────────────────────────────────────────────────

@asincrono
async def test_criar_grava_exatamente_o_que_foi_escolhido():
    uid, h = await _atleta()
    try:
        antes = await _plano(uid)
        async with await _cliente() as c:
            r = await c.post("/api/nutrition/plan/meals", headers=h, json={**NOVA, "posicao": 1})
        assert r.status_code == 200, r.text
        plano = await _plano(uid)
        nova = plano["meals"][1]
        assert nova["name"] == "Café reforçado"
        assert [(f["food_id"], f["grams"]) for f in nova["foods"]] == [("eggs-whole", 150), (SO_DO_DIARIO, 60)]
        # O alimento só do diário chega com nome, para a tela não mostrar uma linha vazia.
        assert nova["foods"][1]["food"]["name"] == DIARY_FOODS[SO_DO_DIARIO]["name"]
        # Nada foi redimensionado: as outras são as mesmas de antes.
        assert [plano["meals"][i] for i in (0, 2, 3, 4)] == antes["meals"]
    finally:
        await _limpar(uid)


@asincrono
async def test_criar_alem_do_maximo_explica_o_que_fazer():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            for _ in range(2):
                assert (await c.post("/api/nutrition/plan/meals", headers=h, json=NOVA)).status_code == 200
            r = await c.post("/api/nutrition/plan/meals", headers=h, json=NOVA)
        assert r.status_code == 400
        assert "Exclua uma" in r.json()["detail"]
    finally:
        await _limpar(uid)


@asincrono
async def test_alimento_fora_do_catalogo_e_recusado():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/nutrition/plan/meals", headers=h, json={
                "nome": "Teste", "itens": [{"food_id": "inventado-xyz", "grams": 100}]})
        assert r.status_code == 422
        assert len((await _plano(uid))["meals"]) == 4
    finally:
        await _limpar(uid)


@asincrono
async def test_editar_troca_nome_e_alimentos_sem_mudar_de_lugar():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.put("/api/nutrition/plan/meals/2", headers=h, json={
                "nome": "Lanche da tarde", "nome_atual": "Lanche",
                "itens": [{"food_id": "yogurt-natural", "grams": 200}, {"food_id": "oats", "grams": 30}]})
            assert r.status_code == 200, r.text
            velho = await c.put("/api/nutrition/plan/meals/2", headers=h, json={**NOVA, "nome_atual": "Lanche"})
        plano = await _plano(uid)
        assert _nomes(plano) == ["Café da manhã", "Almoço", "Lanche da tarde", "Jantar"]
        assert [(f["food_id"], f["grams"]) for f in plano["meals"][2]["foods"]] == [
            ("yogurt-natural", 200), ("oats", 30)]
        # Com o nome antigo a tela está desatualizada: a edição não pode cair em outra refeição.
        assert velho.status_code == 409
    finally:
        await _limpar(uid)


# ── Metas ──────────────────────────────────────────────────────────────────────────────

@asincrono
async def test_dieta_importada_tem_a_meta_acompanhando_o_plano():
    """Numa dieta importada a meta É o que a dieta entrega; mudou a dieta, muda a meta."""
    uid, h = await _atleta(importado=True)
    try:
        async with await _cliente() as c:
            r = await c.delete("/api/nutrition/plan/meals/2", headers=h, params={"nome": "Lanche"})
        assert r.status_code == 200, r.text
        plano = await _plano(uid)
        assert plano["targets"]["goal_calories"] == round(plano["daily_totals"]["kcal"])
        assert plano["targets"] != METAS
    finally:
        await _limpar(uid)


# ── Os registros de hoje ───────────────────────────────────────────────────────────────

async def _marcar(c, h, indice, status):
    r = await c.post("/api/nutrition/meal-status", headers=h,
                     json={"meal_index": indice, "status": status, "date": DIA})
    assert r.status_code == 200, r.text


async def _registros(c, h):
    r = await c.get(f"/api/nutrition/adherence/{DIA}", headers=h)
    return {row["meal_index"]: row["status"] for row in r.json()["meals"]}


@asincrono
async def test_excluir_leva_os_registros_de_hoje_junto():
    """Sem mover, o almoço concluído apareceria como café da manhã concluído."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await _marcar(c, h, 0, "skipped")     # café
            await _marcar(c, h, 1, "completed")   # almoço
            await _marcar(c, h, 3, "skipped")     # jantar
            r = await c.delete("/api/nutrition/plan/meals/0", headers=h,
                               params={"nome": "Café da manhã", "dia": DIA})
            assert r.status_code == 200, r.text
            registros = await _registros(c, h)
        # Almoço virou a 0 e continua concluído; jantar virou a 2 e continua pulado; o
        # registro do café saiu com ele.
        assert registros == {0: "completed", 2: "skipped"}
    finally:
        await _limpar(uid)


@asincrono
async def test_criar_no_comeco_empurra_os_registros_de_hoje():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await _marcar(c, h, 0, "completed")   # café
            await _marcar(c, h, 2, "skipped")     # lanche
            r = await c.post("/api/nutrition/plan/meals", headers=h,
                             json={**NOVA, "posicao": 0, "dia": DIA})
            assert r.status_code == 200, r.text
            registros = await _registros(c, h)
        assert registros == {1: "completed", 3: "skipped"}
    finally:
        await _limpar(uid)


# ── O fluxo antigo de acrescentar respeita o que a pessoa montou ───────────────────────

@asincrono
async def test_acrescentar_pelo_metodo_nao_redimensiona_a_refeicao_montada():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.post("/api/nutrition/plan/meals", headers=h, json={**NOVA, "posicao": 0})
            assert r.status_code == 200, r.text
            montada = (await _plano(uid))["meals"][0]
            r = await c.post("/api/nutrition/plan/add-meal", headers=h,
                             json={"nome": "Ceia", "dia": DIA})
            assert r.status_code == 200, r.text
        plano = await _plano(uid)
        assert plano["meals"][0] == montada
        assert _nomes(plano)[-1] == "Ceia"
    finally:
        await _limpar(uid)


@asincrono
async def test_acrescentar_pelo_metodo_tambem_leva_os_registros_de_hoje():
    """O mesmo problema existia no fluxo antigo: acrescentar um pré-treino no começo
    fazia o café concluído aparecer como pré-treino concluído."""
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            await _marcar(c, h, 0, "completed")
            r = await c.post("/api/nutrition/plan/add-meal", headers=h,
                             json={"nome": "Pré-treino", "posicao": 0, "dia": DIA})
            assert r.status_code == 200, r.text
            registros = await _registros(c, h)
        assert registros == {1: "completed"}
    finally:
        await _limpar(uid)

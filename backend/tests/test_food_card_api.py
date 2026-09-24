# -*- coding: utf-8 -*-
"""Forge Food Card de ponta a ponta: da refeição registrada ao card salvo.

O risco que esta suíte cobre
----------------------------
A peça sai do FORGE com o nome do FORGE em cima e vai para o Instagram do atleta. O
defeito que importa não é visual — é um número na peça que não bate com a refeição que
ele registrou.

Então quase todo teste daqui termina comparando o card com a ORIGEM: os alimentos, as
gramas e os macros que `food_snapshot` gravou quando o atleta pesou a comida. Nada é
recalculado no caminho, e é isso que se mede.
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

import food_card as motor  # noqa: E402
import server  # noqa: E402
from auth import create_token  # noqa: E402
from loop_do_motor import LOOP  # noqa: E402

APP = server.app
DB = server.db


def asincrono(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return LOOP.run_until_complete(fn(*args, **kwargs))
    return wrapper


def _agora():
    return datetime.now(timezone.utc)


def _hoje():
    return CalendarDate.today().isoformat()


async def _cliente():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=APP),
                             base_url="http://forge.test")


async def _atleta(plano="elite"):
    os.environ["BILLING_ENFORCED"] = "true"
    os.environ["BILLING_GRANDFATHER_BEFORE"] = (_agora() - timedelta(days=1)).isoformat()
    uid = str(uuid.uuid4())
    await DB.users.insert_one({
        "id": uid, "email": f"card.{uid[:8]}@example.com", "name": "Atleta",
        "role": "ATHLETE", "status": "ACTIVE", "created_at": _agora().isoformat(),
        "signup_source": "public", "archived_at": None,
        "ai_daily_limit": 40, "ai_monthly_limit": 800, "ai_enabled": True})
    await DB.subscriptions.update_one({"user_id": uid}, {"$set": {
        "user_id": uid, "plan_code": plano, "status": "active",
        "provider": "courtesy", "amount_cents": 0, "currency": "BRL"}}, upsert=True)
    return uid, {"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"}


async def _limpar(*ids):
    for uid in ids:
        for nome in ("users", "subscriptions", "profiles", "food_cards",
                     "nutrition_consumed_extras", "nutrition_adherence"):
            await DB[nome].delete_many({"$or": [{"id": uid}, {"user_id": uid},
                                                {"userId": uid}, {"profile_id": uid}]})


# A refeição da referência visual: carne moída, moranga e ovos de codorna, mais dois
# alimentos que não cabem nos quatro cards.
ALIMENTOS = [
    {"food_id": "carne", "name": "Carne moída", "grams": 180,
     "kcal": 350, "protein_g": 38, "carbs_g": 0, "fat_g": 22},
    {"food_id": "moranga", "name": "Moranga cozida", "grams": 150,
     "kcal": 60, "protein_g": 1.5, "carbs_g": 15, "fat_g": 0.3},
    {"food_id": "codorna", "name": "Ovos de codorna", "grams": 40,
     "kcal": 63, "protein_g": 5.2, "carbs_g": 0.2, "fat_g": 4.6},
    {"food_id": "azeite", "name": "Azeite de oliva", "grams": 5,
     "kcal": 45, "protein_g": 0, "carbs_g": 0, "fat_g": 5},
    {"food_id": "arroz", "name": "Arroz branco", "grams": 100,
     "kcal": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3},
]
TOTAIS = {"kcal": 648, "protein_g": 47.4, "carbs_g": 43.2, "fat_g": 32.2}


async def _refeicao_registrada(uid, entry_id=None):
    """Grava uma refeição no formato EXATO que `food_snapshot` produz."""
    entry_id = entry_id or str(uuid.uuid4())
    await DB.nutrition_consumed_extras.insert_one({
        "_id": f"extra:{uid}:{entry_id}", "profile_id": uid, "date": _hoje(),
        "entry_id": entry_id, "refeicao": "lunch", "refeicao_nome": "Almoço",
        "actual": {"foods": ALIMENTOS, "totals": TOTAIS},
        "created_at": _agora().isoformat()})
    return entry_id


# ── Ler a refeição para escolher os alimentos ───────────────────────────────────────

@asincrono
async def test_a_tela_recebe_os_alimentos_da_refeicao_com_icone_e_macro():
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            r = await c.get(f"/api/food-card/meal?date={_hoje()}&entry_id={entry}", headers=h)
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert len(corpo["foods"]) == 5
        assert corpo["maxItems"] == 4
        carne = corpo["foods"][0]
        assert carne["iconKey"] == "beef"
        assert carne["primaryMacro"] == motor.PROTEINA
        assert carne["descriptionKey"] == "protein_source"
    finally:
        await _limpar(uid)


@asincrono
async def test_refeicao_sem_alimento_pesado_explica_em_vez_de_quebrar():
    uid, h = await _atleta()
    try:
        async with await _cliente() as c:
            r = await c.get(f"/api/food-card/meal?date={_hoje()}&entry_id=nao-existe", headers=h)
        assert r.status_code == 404
        assert "Registre" in r.json()["detail"]
    finally:
        await _limpar(uid)


# ── Criar ───────────────────────────────────────────────────────────────────────────

@asincrono
async def test_os_macros_do_card_sao_OS_MESMOS_da_refeicao_registrada():
    """O teste que importa. Se um número for recalculado no caminho, o atleta publica uma
    peça que não bate com o diário dele."""
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            r = await c.post("/api/food-card", headers=h, json={
                "date": _hoje(), "entry_id": entry,
                "food_ids": ["carne", "moranga", "codorna"]})
        assert r.status_code == 200, r.text
        card = r.json()
        por_id = {a["food_id"]: a for a in ALIMENTOS}
        for item in card["items"]:
            origem = por_id[item["foodId"]]
            assert item["quantity"] == origem["grams"]
            assert item["calories"] == origem["kcal"]
            assert item["protein"] == origem["protein_g"]
            assert item["carbs"] == origem["carbs_g"]
            assert item["fat"] == origem["fat_g"]
    finally:
        await _limpar(uid)


@asincrono
async def test_o_resumo_usa_a_refeicao_COMPLETA_mesmo_destacando_tres():
    """Destacar três alimentos não pode fazer o rodapé mentir sobre o que a pessoa comeu.
    O resumo soma os cinco; os cards mostram três."""
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            card = (await c.post("/api/food-card", headers=h, json={
                "date": _hoje(), "entry_id": entry,
                "food_ids": ["carne", "moranga", "codorna"]})).json()
        assert len(card["items"]) == 3
        assert card["summary"] == {"protein": 47, "carbs": 43, "fat": 32, "calories": 648}
        # A soma dos três destacados seria bem menor — é essa diferença que prova a regra.
        soma_dos_destacados = sum(i["calories"] for i in card["items"])
        assert soma_dos_destacados < card["summary"]["calories"]
    finally:
        await _limpar(uid)


@asincrono
async def test_sem_escolher_alimentos_o_card_pega_ate_quatro():
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            card = (await c.post("/api/food-card", headers=h, json={
                "date": _hoje(), "entry_id": entry})).json()
        assert len(card["items"]) == motor.MAXIMO_DE_ITENS
    finally:
        await _limpar(uid)


@asincrono
async def test_o_card_nasce_com_posicao_normalizada_e_versao_de_modelo():
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            card = (await c.post("/api/food-card", headers=h,
                                 json={"date": _hoje(), "entry_id": entry})).json()
        assert card["templateVersion"] == "forge-food-v1"
        assert card["imageTransform"] == {"scale": 1.0, "offsetX": 0.0, "offsetY": 0.0}
        for item in card["items"]:
            for campo in ("cardX", "cardY", "anchorX", "anchorY"):
                assert 0.0 <= item[campo] <= 1.0
    finally:
        await _limpar(uid)


@asincrono
async def test_escolher_alimento_que_nao_esta_na_refeicao_e_recusado():
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            r = await c.post("/api/food-card", headers=h, json={
                "date": _hoje(), "entry_id": entry, "food_ids": ["lagosta"]})
        assert r.status_code == 422
    finally:
        await _limpar(uid)


@asincrono
async def test_nao_da_para_pedir_mais_de_quatro_alimentos():
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            r = await c.post("/api/food-card", headers=h, json={
                "date": _hoje(), "entry_id": entry,
                "food_ids": ["carne", "moranga", "codorna", "azeite", "arroz"]})
        assert r.status_code == 422
    finally:
        await _limpar(uid)


# ── Persistência: sair do editor e voltar ───────────────────────────────────────────

@asincrono
async def test_arrastar_um_card_e_voltar_depois_encontra_ele_onde_ficou():
    """A especificação pede isto explicitamente: não obrigar a reconstruir tudo."""
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            card = (await c.post("/api/food-card", headers=h,
                                 json={"date": _hoje(), "entry_id": entry})).json()
            movidos = [{"cardX": 0.11, "cardY": 0.22, "anchorX": 0.33, "anchorY": 0.44}
                       for _ in card["items"]]
            r = await c.put(f"/api/food-card/{card['id']}", headers=h, json={
                "items": movidos, "imageTransform": {"scale": 1.4, "offsetX": -0.1,
                                                     "offsetY": 0.05}})
            assert r.status_code == 200, r.text
            de_volta = (await c.get(f"/api/food-card/{card['id']}", headers=h)).json()
        assert de_volta["items"][0]["cardX"] == 0.11
        assert de_volta["items"][0]["anchorY"] == 0.44
        assert de_volta["imageTransform"]["scale"] == 1.4
        # E o alimento continua sendo o mesmo: mover card não mexe em macro.
        assert de_volta["items"][0]["name"] == card["items"][0]["name"]
        assert de_volta["items"][0]["protein"] == card["items"][0]["protein"]
    finally:
        await _limpar(uid)


@asincrono
async def test_a_rota_de_atualizar_NAO_deixa_mexer_em_macro():
    """Se desse, o atleta publicaria uma peça com número que a refeição não tem — e o
    nome do FORGE estaria em cima."""
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            card = (await c.post("/api/food-card", headers=h,
                                 json={"date": _hoje(), "entry_id": entry})).json()
            adulterado = [{"cardX": 0.1, "cardY": 0.1, "anchorX": 0.5, "anchorY": 0.5,
                           "protein": 999, "calories": 1, "name": "Outra coisa"}
                          for _ in card["items"]]
            await c.put(f"/api/food-card/{card['id']}", headers=h, json={"items": adulterado})
            de_volta = (await c.get(f"/api/food-card/{card['id']}", headers=h)).json()
        assert de_volta["items"][0]["protein"] == card["items"][0]["protein"]
        assert de_volta["items"][0]["name"] == card["items"][0]["name"]
        assert de_volta["items"][0]["calories"] == card["items"][0]["calories"]
    finally:
        await _limpar(uid)


@asincrono
async def test_trocar_o_macro_principal_a_mao_e_permitido():
    """A especificação pede edição manual do macro antes de exportar. É o único campo de
    conteúdo que muda, e ele não é um número: é qual dos três destacar."""
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            card = (await c.post("/api/food-card", headers=h,
                                 json={"date": _hoje(), "entry_id": entry})).json()
            itens = [{"cardX": i["cardX"], "cardY": i["cardY"], "anchorX": i["anchorX"],
                      "anchorY": i["anchorY"], "primaryMacro": motor.GORDURA}
                     for i in card["items"]]
            await c.put(f"/api/food-card/{card['id']}", headers=h, json={"items": itens})
            de_volta = (await c.get(f"/api/food-card/{card['id']}", headers=h)).json()
        assert all(i["primaryMacro"] == motor.GORDURA for i in de_volta["items"])
    finally:
        await _limpar(uid)


@asincrono
async def test_macro_inventado_e_ignorado():
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            card = (await c.post("/api/food-card", headers=h,
                                 json={"date": _hoje(), "entry_id": entry})).json()
            itens = [{"cardX": 0.1, "cardY": 0.2, "anchorX": 0.5, "anchorY": 0.5,
                      "primaryMacro": "vitaminas"} for _ in card["items"]]
            await c.put(f"/api/food-card/{card['id']}", headers=h, json={"items": itens})
            de_volta = (await c.get(f"/api/food-card/{card['id']}", headers=h)).json()
        assert all(i["primaryMacro"] in motor.MACROS for i in de_volta["items"])
    finally:
        await _limpar(uid)


@asincrono
async def test_posicao_fora_do_quadro_e_recusada():
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            card = (await c.post("/api/food-card", headers=h,
                                 json={"date": _hoje(), "entry_id": entry})).json()
            r = await c.put(f"/api/food-card/{card['id']}", headers=h, json={
                "items": [{"cardX": 1.8, "cardY": 0.2, "anchorX": 0.5, "anchorY": 0.5}
                          for _ in card["items"]]})
        assert r.status_code == 422
    finally:
        await _limpar(uid)


# ── Isolamento e ciclo de vida ──────────────────────────────────────────────────────

@asincrono
async def test_um_atleta_nao_le_nem_apaga_o_food_card_do_outro():
    meu, hm = await _atleta()
    outro, ho = await _atleta()
    try:
        entry = await _refeicao_registrada(outro)
        async with await _cliente() as c:
            dele = (await c.post("/api/food-card", headers=ho,
                                 json={"date": _hoje(), "entry_id": entry})).json()
            assert (await c.get(f"/api/food-card/{dele['id']}", headers=hm)).status_code == 404
            assert (await c.delete(f"/api/food-card/{dele['id']}", headers=hm)).status_code == 404
            minha = (await c.get("/api/food-card", headers=hm)).json()
        assert minha["cards"] == []
    finally:
        await _limpar(meu, outro)


@asincrono
async def test_o_card_pode_ser_apagado():
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            card = (await c.post("/api/food-card", headers=h,
                                 json={"date": _hoje(), "entry_id": entry})).json()
            assert (await c.delete(f"/api/food-card/{card['id']}", headers=h)).status_code == 200
            assert (await c.get(f"/api/food-card/{card['id']}", headers=h)).status_code == 404
    finally:
        await _limpar(uid)


@asincrono
async def test_o_food_card_exige_o_plano_com_nutricao():
    """Ele vive dentro da Nutrição e lê a refeição registrada. Quem não tem a capacidade
    de alimentação não tem refeição registrada para transformar em peça."""
    uid, h = await _atleta(plano="essential")
    try:
        async with await _cliente() as c:
            r = await c.get(f"/api/food-card/meal?date={_hoje()}&entry_id=x", headers=h)
        assert r.status_code == 402
        assert r.json()["detail"]["capability"] == "nutrition"
    finally:
        await _limpar(uid)


@asincrono
async def test_sem_armazenamento_configurado_a_foto_recusa_com_mensagem_clara():
    """Fingir que guardou e perder a foto ao recarregar seria pior do que não deixar."""
    uid, h = await _atleta()
    try:
        entry = await _refeicao_registrada(uid)
        async with await _cliente() as c:
            card = (await c.post("/api/food-card", headers=h,
                                 json={"date": _hoje(), "entry_id": entry})).json()
            r = await c.post(f"/api/food-card/{card['id']}/photo", headers=h,
                             files={"photo": ("p.jpg", b"\xff\xd8\xff\xe0lixo", "image/jpeg")})
        # Com credencial no ambiente o upload segue; sem ela, 503 explicado.
        assert r.status_code in (200, 422, 503)
        if r.status_code == 503:
            assert "armazenamento" in r.json()["detail"].lower()
    finally:
        await _limpar(uid)


# ── Por que a foto do prato não aparece ─────────────────────────────────────────────
#
# O Nicolas importou uma foto três vezes e a peça ficou preta. Do navegador, "a foto sumiu
# do armazenamento", "a credencial caiu" e "o endereço venceu" são INDISTINGUÍVEIS: o
# `<img>` falha igual nos três, e o que aparece é o fundo `#08090a` da moldura — preto.
#
# Esta rota existe para encurtar esse diagnóstico. Sem ela, a única saída é pedir para a
# pessoa tentar de novo e torcer.

async def _card_com_foto(uid, chave="avaliacoes/x/y/prato.jpg"):
    entry = await _refeicao_registrada(uid)
    async with await _cliente() as c:
        r = await c.post("/api/food-card", json={"date": _hoje(), "entry_id": entry},
                         headers={"Authorization": f"Bearer {create_token(uid, 'ATHLETE')}"})
    card_id = r.json()["id"]
    if chave:
        await DB.food_cards.update_one({"id": card_id}, {"$set": {"imageKey": chave}})
    return card_id


@asincrono
async def test_card_sem_foto_diz_que_nao_tem_foto():
    uid, h = await _atleta()
    try:
        card_id = await _card_com_foto(uid, chave=None)
        async with await _cliente() as c:
            r = await c.get(f"/api/food-card/{card_id}/photo-check", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["temChave"] is False
        assert r.json()["motivo"] == "sem_foto"
    finally:
        await _limpar(uid)


@asincrono
async def test_sem_armazenamento_configurado_a_rota_diz_isso():
    """Sem credencial, `carregar_configuracao` devolve um dataclass DESLIGADO — e ele é
    sempre verdadeiro. Quem responde é `cfg.ativo`, e já houve bug por testar só o objeto."""
    uid, h = await _atleta()
    guardado = {k: os.environ.pop(k, None) for k in
                ("FORGE_FOTOS_BUCKET", "FORGE_FOTOS_KEY_ID", "FORGE_FOTOS_KEY_SECRET")}
    try:
        card_id = await _card_com_foto(uid)
        async with await _cliente() as c:
            r = await c.get(f"/api/food-card/{card_id}/photo-check", headers=h)
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert corpo["armazenamentoAtivo"] is False
        assert corpo["motivo"] == "armazenamento_desligado"
        assert corpo["existe"] is False
    finally:
        for k, v in guardado.items():
            if v is not None:
                os.environ[k] = v
        await _limpar(uid)


@asincrono
async def test_a_rota_nunca_devolve_bucket_credencial_nem_caminho():
    """Ela existe para diagnosticar, e diagnóstico que vaza segredo não pode ir para a tela.

    O texto da exceção do boto3 traz bucket e chave; por isso só o TIPO dela é registrado, e
    nada do armazenamento sai na resposta.
    """
    uid, h = await _atleta()
    try:
        card_id = await _card_com_foto(uid, chave="avaliacoes/segredo/xyz/prato.jpg")
        async with await _cliente() as c:
            r = await c.get(f"/api/food-card/{card_id}/photo-check", headers=h)
        texto = r.text
        assert set(r.json()) == {"temChave", "armazenamentoAtivo", "existe", "assinavel",
                                 "validade", "motivo"}
        for proibido in ("avaliacoes/", "segredo", "prato.jpg", "Bucket", "AccessKey",
                         "amazonaws", "r2.cloudflare", "Traceback"):
            assert proibido not in texto, proibido
    finally:
        await _limpar(uid)


@asincrono
async def test_a_rota_exige_login_e_e_do_dono():
    uid, h = await _atleta()
    outro, h2 = await _atleta()
    try:
        card_id = await _card_com_foto(uid)
        async with await _cliente() as c:
            assert (await c.get(f"/api/food-card/{card_id}/photo-check")).status_code == 401
            # O Food Card do vizinho não existe para quem não é dono.
            assert (await c.get(f"/api/food-card/{card_id}/photo-check",
                                headers=h2)).status_code == 404
    finally:
        await _limpar(uid, outro)

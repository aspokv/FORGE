"""/api/visual-comparison: dados ausentes, dados legados e acesso cruzado.

A rota respondia 500 quando `visual_assessment` carregava a forma antiga do campo (texto
em vez de dicionario). Perfil vazio nao e erro de servidor: e uma comparacao vazia.
"""
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from test_signup_publico import DB, _cliente, asincrono  # noqa: E402

import server  # noqa: E402
from auth import create_token  # noqa: E402


async def _atleta(email, perfil=None):
    uid = str(uuid.uuid4())
    await DB.users.delete_many({"email": email})
    await DB.users.insert_one({
        "id": uid, "email": email, "name": "VC", "role": "ATHLETE", "status": "ACTIVE",
        "created_at": datetime.now(timezone.utc).isoformat()})
    await DB.profiles.delete_many({"id": uid})
    if perfil is not None:
        await DB.profiles.insert_one({**perfil, "id": uid, "user_id": uid})
    return uid, {"Authorization": "Bearer " + create_token(uid, "ATHLETE")}


async def _limpar(uid):
    await DB.users.delete_many({"id": uid})
    await DB.profiles.delete_many({"id": uid})


# ── Ausencia de dados nao e erro ─────────────────────────────────────────────────────

@asincrono
async def test_perfil_sem_nenhum_dado_devolve_comparacao_vazia():
    uid, h = await _atleta("vc.vazio@example.com", perfil=None)
    async with await _cliente() as c:
        r = await c.get(f"/api/visual-comparison/{uid}", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["manual_priorities"] == []
    assert d["vision_priorities"] == []
    # a estrutura vem completa, so sem conteudo avaliado
    assert len(d["comparison"]) == len(server.MUSCLES)
    assert all(x["manual"] == "proporcional" for x in d["comparison"])
    await _limpar(uid)


@asincrono
async def test_perfil_sem_fotos_devolve_comparacao_sem_visao():
    uid, h = await _atleta("vc.semfoto@example.com",
                           perfil={"name": "VC", "assessment": {}, "priorities": ["Bíceps"]})
    async with await _cliente() as c:
        r = await c.get(f"/api/visual-comparison/{uid}", headers=h)
    assert r.status_code == 200
    assert r.json()["vision_priorities"] == []
    assert r.json()["manual_priorities"] == ["Bíceps"]
    await _limpar(uid)


# ── Dados legados nao derrubam a rota ────────────────────────────────────────────────

@pytest.mark.parametrize("perfil,rotulo", [
    ({"visual_assessment": {"Bíceps": "forte"}}, "visual_assessment em texto (forma antiga)"),
    ({"visual_assessment": "lixo"}, "visual_assessment nem e dicionario"),
    ({"assessment": {"Bíceps": "fraco"}}, "assessment em texto (forma antiga)"),
    ({"assessment": "lixo"}, "assessment nem e dicionario"),
    ({"visual_notes": "texto"}, "visual_notes em texto"),
    ({"priorities": "texto"}, "priorities nem e lista"),
    ({"visual_assessment": {"Bíceps": None}}, "valor nulo"),
])
@asincrono
async def test_dado_legado_nao_vira_500(perfil, rotulo):
    uid, h = await _atleta("vc.legado@example.com", perfil={"name": "VC", **perfil})
    async with await _cliente() as c:
        r = await c.get(f"/api/visual-comparison/{uid}", headers=h)
    assert r.status_code == 200, f"{rotulo} -> {r.status_code}"
    assert isinstance(r.json()["comparison"], list)
    await _limpar(uid)


def test_o_leitor_de_desenvolvimento_aceita_as_duas_formas():
    assert server._desenvolvimento({"development": "fraco"}) == "fraco"
    assert server._desenvolvimento("fraco") == "fraco"
    assert server._desenvolvimento(None) == "proporcional"
    assert server._desenvolvimento({}) == "proporcional"
    assert server._desenvolvimento(None, padrao="forte") == "forte"
    assert server._desenvolvimento(123) == "proporcional"


# ── Identidade e isolamento ──────────────────────────────────────────────────────────

@asincrono
async def test_id_inexistente_nao_vaza_nem_quebra():
    uid, h = await _atleta("vc.inexistente@example.com",
                           perfil={"name": "VC", "priorities": ["Glúteos"]})
    async with await _cliente() as c:
        r = await c.get("/api/visual-comparison/id-que-nao-existe", headers=h)
    # O atleta sempre resolve para o proprio perfil: o id do path e ignorado.
    assert r.status_code == 200
    assert r.json()["manual_priorities"] == ["Glúteos"]
    await _limpar(uid)


@asincrono
async def test_um_atleta_nao_le_a_comparacao_do_outro():
    a_id, a = await _atleta("vc.a@example.com", perfil={"name": "A", "priorities": ["Bíceps"]})
    b_id, _ = await _atleta("vc.b@example.com",
                            perfil={"name": "B", "priorities": ["Panturrilhas"],
                                    "visual_notes": {"symmetry": "marcador-de-b"}})
    async with await _cliente() as c:
        r = await c.get(f"/api/visual-comparison/{b_id}", headers=a)
    assert r.status_code == 200
    assert "marcador-de-b" not in r.text
    assert r.json()["manual_priorities"] == ["Bíceps"], "devolveu o perfil de A, como deve"
    await _limpar(a_id)
    await _limpar(b_id)


@asincrono
async def test_anonimo_nao_alcanca_a_comparacao():
    async with await _cliente() as c:
        r = await c.get("/api/visual-comparison/qualquer")
    assert r.status_code in (401, 403)

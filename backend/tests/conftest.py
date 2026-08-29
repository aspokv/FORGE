"""Semeadura do banco de teste para a suite de integracao.

Por que existe
--------------
Os arquivos `test_forge_v2_*` falam com um servidor de verdade e esperam duas contas com
senha conhecida: o SUPER_ADMIN e o atleta `joao.silva@example.com`. Nada no repositorio
criava essas contas, entao:

  - `seed_super_admin` cria o dono como convite PENDENTE e SEM senha, que e o
    comportamento certo em producao — o sistema nao deve inventar a senha de ninguem;
  - o atleta simplesmente nao existia;
  - os testes tentavam entrar, tomavam 401, e na sexta tentativa o bloqueio de login
    respondia 429. Dali em diante todo teste que precisava de token quebrava com
    `KeyError: 'token'`.

Ou seja: o produto estava certo nos dois pontos (nao semear senha, e bloquear tentativas
repetidas). O que faltava era a semeadura do AMBIENTE DE TESTE. E o que este arquivo faz.

Guarda
------
A semeadura escreve senha em conta de administrador. Isso so pode acontecer num banco
descartavel, entao a sessao aborta se o alvo nao for local e nao se chamar como um banco
de teste. Errar isso uma vez seria trocar a senha do dono em producao.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))

ENV = RAIZ / ".env"
if ENV.exists():
    load_dotenv(ENV)

# As mesmas credenciais que os testes de integracao esperam encontrar.
EMAIL_ADMIN = (os.environ.get("FORGE_SUPER_ADMIN_EMAIL") or "nicolas.ms13@gmail.com").lower()
SENHA_ADMIN = os.environ.get("FORGE_SUPER_ADMIN_PASSWORD") or "forge-admin-2026"
EMAIL_ATLETA = "joao.silva@example.com"
SENHA_ATLETA = "joaopass123"


def _banco_e_descartavel() -> tuple:
    """(pode_semear, motivo). Fail closed: na duvida, nao escreve."""
    url = (os.environ.get("MONGO_URL") or "").strip()
    nome = (os.environ.get("DB_NAME") or "").strip()
    if not url or not nome:
        return False, "MONGO_URL ou DB_NAME ausentes"
    if url.startswith("mongodb+srv://"):
        return False, "o alvo e um cluster Atlas"
    local = any(h in url for h in ("localhost", "127.0.0.1", "mongo:27017", "::1"))
    if not local:
        return False, "o alvo nao e um Mongo local"
    if "test" not in nome.lower():
        return False, f"DB_NAME={nome!r} nao parece um banco de teste"
    return True, f"{nome} em Mongo local"


async def _semear(db):
    from auth import hash_password

    agora = datetime.now(timezone.utc).isoformat()

    # O dono: existe como convite pendente e sem senha. Aqui ele ganha senha e fica ativo,
    # que e o estado em que os testes o encontram depois de aceitar o convite na vida real.
    await db.users.update_one(
        {"email": EMAIL_ADMIN},
        {"$set": {"role": "SUPER_ADMIN", "status": "ACTIVE",
                  "password_hash": hash_password(SENHA_ADMIN),
                  "invite_token": None, "invite_expires": None,
                  # sem carimbo de troca de senha: senao os tokens criados pelos proprios
                  # testes nasceriam revogados
                  "password_changed_at": None},
         "$setOnInsert": {"id": str(uuid.uuid4()), "email": EMAIL_ADMIN,
                          "name": "FORGE Admin", "created_at": agora,
                          "ai_daily_limit": 200, "ai_monthly_limit": 4000,
                          "ai_enabled": True}},
        upsert=True)

    atleta = await db.users.find_one({"email": EMAIL_ATLETA})
    uid = atleta["id"] if atleta else str(uuid.uuid4())
    await db.users.update_one(
        {"email": EMAIL_ATLETA},
        {"$set": {"role": "ATHLETE", "status": "ACTIVE",
                  "password_hash": hash_password(SENHA_ATLETA),
                  "expires_at": None, "password_changed_at": None},
         "$setOnInsert": {"id": uid, "email": EMAIL_ATLETA, "name": "João Silva",
                          "created_at": agora, "ai_daily_limit": 40,
                          "ai_monthly_limit": 800, "ai_enabled": True}},
        upsert=True)

    # Perfil do atleta: varios testes leem /api/bootstrap logo apos entrar.
    await db.profiles.update_one(
        {"id": uid},
        {"$setOnInsert": {"id": uid, "user_id": uid, "name": "João Silva",
                          "goal": "Hipertrofia", "experience": "Intermediário",
                          "days": 4, "session_minutes": 60,
                          "automation_mode": "FORGE_ASSISTED",
                          "assessment": {}, "priorities": [],
                          "onboarding_required": False}},
        upsert=True)

    # Perfis descartaveis de execucoes anteriores. Os testes os criam com ids que comecam
    # em "TEST_", e um documento antigo carrega o formato antigo: foi assim que um perfil
    # sem "name", criado antes de save_custom_program passar a preencher os campos, fez o
    # teste continuar falhando depois da correcao.
    await db.profiles.delete_many({"id": {"$regex": "^TEST_"}})

    # O bloqueio de login e por (ip, e-mail) e sobrevive entre execucoes. Zerar aqui evita
    # que a suite comece ja travada por causa da execucao anterior. O comportamento do
    # bloqueio continua coberto — em test_seguranca e test_recuperacao_de_senha, com
    # contas proprias.
    await db.login_attempts.delete_many({})


@pytest.fixture(scope="session", autouse=True)
def semear_banco_de_teste():
    pode, motivo = _banco_e_descartavel()
    if not pode:
        pytest.exit(f"semeadura recusada: {motivo}. "
                    "A suite escreve senha de administrador e so roda em banco de teste.",
                    returncode=2)

    import server

    laco = asyncio.new_event_loop()
    try:
        laco.run_until_complete(_semear(server.db))
    finally:
        laco.close()
    print(f"\n[conftest] contas de teste semeadas em {motivo}")
    yield

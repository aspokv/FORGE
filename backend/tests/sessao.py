"""Sessao HTTP autenticada para os testes de integracao que falam com o servidor real.

Os arquivos `test_forge_v2_iteration4` e `test_forge_v2_regressions` foram escritos quando
rotas como /api/techniques, /api/bootstrap e /api/muscle-map eram abertas. Elas passaram a
exigir login — e isso e o comportamento certo: `test_seguranca` verifica exatamente que
nenhuma delas responde a anonimo. Os testes e que ficaram para tras, e chamavam tudo sem
cabecalho nenhum.

Em vez de espalhar `headers=...` por trinta chamadas, o modulo devolve uma `Session` com o
Authorization ja preso. As contas sao as mesmas que `conftest.py` semeia.
"""
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ENV = Path(__file__).parent.parent / ".env"
if ENV.exists():
    load_dotenv(ENV)

BASE_URL = (os.environ.get("BACKEND_URL")
            or os.environ.get("REACT_APP_BACKEND_URL")
            or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

EMAIL_ADMIN = os.environ.get("FORGE_SUPER_ADMIN_EMAIL", "nicolas.ms13@gmail.com")
SENHA_ADMIN = os.environ.get("FORGE_SUPER_ADMIN_PASSWORD", "forge-admin-2026")

_cache = {}


def token_de_admin() -> str:
    """Token do SUPER_ADMIN, obtido uma vez por processo.

    Uma vez so tambem por seguranca do proprio teste: cada login errado conta para o
    bloqueio de tentativas, e repetir login a cada chamada aproximaria a suite do teto
    sem necessidade."""
    if "token" not in _cache:
        r = requests.post(f"{API}/auth/login",
                          json={"email": EMAIL_ADMIN, "password": SENHA_ADMIN},
                          timeout=30)
        if r.status_code != 200:
            raise RuntimeError(
                f"login do admin falhou ({r.status_code}). "
                "conftest.py semeia essa conta; confira se o servidor local esta no ar.")
        _cache["token"] = r.json()["token"]
    return _cache["token"]


def sessao_admin() -> requests.Session:
    """Session com o Authorization preso — use no lugar de `requests` nesses arquivos."""
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token_de_admin()}"})
    return s

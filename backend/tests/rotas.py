"""Enumeracao de rotas que funciona nas duas gerações do FastAPI.

Ate a 0.110, `app.routes` devolvia as rotas ja achatadas, cada uma com `.path` e
`.dependant`. Da 0.14x em diante ele devolve `_IncludedRouter`, um objeto de inclusao
preguicosa sem nenhum desses atributos — a varredura de seguranca simplesmente encontrava
zero rotas e passava sem testar nada, que e a pior forma de um teste falhar.

Este modulo tenta a API nova e cai na antiga, para o teste continuar valendo se alguem
precisar reverter a atualizacao.
"""
from typing import Any, List, NamedTuple


class Rota(NamedTuple):
    metodo: str
    caminho: str
    objeto: Any      # APIRoute, com .dependant e .endpoint


def _metodo(metodos) -> str:
    restantes = sorted(set(metodos or ()) - {"HEAD", "OPTIONS"})
    return restantes[0] if restantes else "GET"


def rotas_da_app(app) -> List[Rota]:
    """Todas as rotas HTTP registradas, achatadas."""
    try:
        # FastAPI >= 0.14x
        from fastapi.routing import iter_route_contexts
        contextos = list(iter_route_contexts(app.routes))
        achadas = [Rota(_metodo(c.methods), c.path, c.route) for c in contextos
                   if getattr(c, "path", None)]
        if achadas:
            return achadas
    except ImportError:
        pass

    # FastAPI <= 0.11x
    return [Rota(_metodo(getattr(r, "methods", None)), r.path, r)
            for r in app.routes if getattr(r, "path", None)]


def rotas_da_api(app) -> List[Rota]:
    return [r for r in rotas_da_app(app) if r.caminho.startswith("/api")]

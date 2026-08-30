"""
FORGE LLM Providers — modular abstraction layer.
Supports: DeepSeek (Coach), Gemini (Visual Assessment).
Easily extensible for future models without rewriting business logic.
"""
import os, json, logging
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional

import httpx

logger = logging.getLogger("forge.llm")

DEEPSEEK_V4_PRO = "deepseek-v4-pro"


def deepseek_model() -> str:
    """Modelo explicito e centralizado; evita aliases antigos mudarem em silencio."""
    return (os.environ.get("DEEPSEEK_MODEL") or DEEPSEEK_V4_PRO).strip()

FORGE_COACH_SYSTEM = """Voc\u00ea \u00e9 o coach t\u00e9cnico do FORGE. Responda em portugu\u00eas do Brasil, com clareza adulta e concisa. Use SOMENTE os dados do contexto fornecido; nunca invente hist\u00f3rico. Diferencie dados observados de heur\u00edsticas pr\u00e1ticas. N\u00e3o d\u00ea diagn\u00f3stico m\u00e9dico; para dor aguda ou condi\u00e7\u00e3o cl\u00ednica, recomende avalia\u00e7\u00e3o profissional. N\u00e3o trate volume como regra universal. Estruture em: leitura dos dados, decis\u00e3o recomendada, pr\u00f3ximo passo. Seja espec\u00edfico para hipertrofia intermedi\u00e1ria/avan\u00e7ada.
IMPORTANTE: Voc\u00ea N\u00c3O substitui o FORGE Training Engine. O engine \u00e9 a autoridade sobre programa\u00e7\u00e3o estruturada de treino. Voc\u00ea atua como coach interpretativo: explique decis\u00f5es do engine, contextualize dados, ajude o atleta a entender SEU progresso real. Nunca sugira substituir o programa gerado pelo engine arbitrariamente."""


class CoachProvider(ABC):
    """Abstract base for FORGE Coach LLM providers."""

    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model identifier for audit/usage tracking."""
        ...

    @abstractmethod
    async def stream_chat(self, system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
        """Yields text chunks. Provider must handle all errors internally."""
        ...


class DeepSeekCoach(CoachProvider):
    """DeepSeek API provider with SSE-compatible streaming."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self._model = deepseek_model()
        self._timeout = 45.0

    @property
    def model_name(self) -> str:
        return self._model

    async def stream_chat(self, system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        client = httpx.AsyncClient(timeout=self._timeout)
        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.6,
                    "max_tokens": 2048,
                    "stream": True,
                },
            ) as response:
                if response.status_code == 401:
                    yield json.dumps({"error": "Chave de API DeepSeek inv\u00e1lida."}, ensure_ascii=False)
                    return
                if response.status_code == 402:
                    yield json.dumps({"error": "Saldo DeepSeek insuficiente. Recarregue sua conta."}, ensure_ascii=False)
                    return
                if response.status_code == 429:
                    yield json.dumps({"error": "Limite de requisi\u00e7\u00f5es DeepSeek atingido. Aguarde alguns segundos."}, ensure_ascii=False)
                    return
                if response.status_code >= 500:
                    yield json.dumps({"error": f"Servi\u00e7o DeepSeek indispon\u00edvel (HTTP {response.status_code}). Tente novamente mais tarde."}, ensure_ascii=False)
                    return
                if response.status_code >= 400:
                    yield json.dumps({"error": f"Coach indispon\u00edvel (HTTP {response.status_code})."}, ensure_ascii=False)
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        return
                    try:
                        chunk = json.loads(payload)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except httpx.TimeoutException:
            logger.warning("deepseek timeout")
            yield json.dumps({"error": "Timeout ao consultar o coach DeepSeek. O servidor demorou para responder."}, ensure_ascii=False)
        except httpx.ConnectError:
            logger.warning("deepseek connection failed")
            yield json.dumps({"error": "N\u00e3o foi poss\u00edvel conectar ao servi\u00e7o DeepSeek. Verifique sua rede."}, ensure_ascii=False)
        except httpx.RemoteProtocolError:
            logger.warning("deepseek protocol error")
            yield json.dumps({"error": "Conex\u00e3o com DeepSeek interrompida. Tente novamente."}, ensure_ascii=False)
        except Exception:
            logger.exception("deepseek stream failed")
            yield json.dumps({"error": "Erro interno no coach. Nossa equipe foi notificada."}, ensure_ascii=False)
        finally:
            await client.aclose()


# ---------------------------------------------------------------------------
# Factory — single entry point for provider instantiation
# ---------------------------------------------------------------------------

def get_coach_provider() -> Optional[CoachProvider]:
    """Returns a CoachProvider if DEEPSEEK_API_KEY is configured, else None."""
    api_key = (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        return None
    return DeepSeekCoach(api_key)

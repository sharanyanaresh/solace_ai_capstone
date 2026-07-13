"""Groq LLM client: tiered models, primary->fallback key failover, retries, JSON mode.

Resilience layers (matches the design docs):
  1. exponential-backoff retries on transient errors (429 / 5xx / connection),
  2. switch from the primary API key to the fallback key,
  3. optional model downgrade (large -> small) as a last resort.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from ..config import settings

try:  # groq is only needed when the pipeline runs
    from groq import Groq
    from groq import APIConnectionError, APIStatusError, InternalServerError, RateLimitError
    _TRANSIENT = (RateLimitError, InternalServerError, APIConnectionError)
except Exception:  # pragma: no cover - import guard for envs without groq
    Groq = None  # type: ignore
    APIStatusError = Exception  # type: ignore
    _TRANSIENT = tuple()


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    tokens: int
    latency_ms: int
    model: str
    key: str  # "primary" | "fallback"


class LLMClient:
    def __init__(self) -> None:
        if Groq is None:
            raise LLMError("groq package not installed")
        self._keys: list[tuple[str, str]] = []
        if settings.groq_api_key:
            self._keys.append(("primary", settings.groq_api_key))
        if settings.groq_api_key_fallback:
            self._keys.append(("fallback", settings.groq_api_key_fallback))
        if not self._keys:
            raise LLMError("No GROQ_API_KEY configured")
        self._clients = {name: Groq(api_key=key) for name, key in self._keys}

    def _model(self, tier: str) -> str:
        return settings.groq_model_large if tier == "large" else settings.groq_model_small

    def complete(
        self,
        system: str,
        user: str,
        tier: str = "large",
        json_mode: bool = False,
        max_tokens: int = 1200,
        temperature: float = 0.2,
        allow_model_downgrade: bool = True,
    ) -> LLMResult:
        models = [self._model(tier)]
        if allow_model_downgrade and tier == "large":
            models.append(self._model("small"))

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        kwargs = {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_exc: Exception | None = None
        for model in models:
            for key_name, _ in self._keys:
                client = self._clients[key_name]
                for attempt in range(settings.groq_max_retries):
                    t0 = time.perf_counter()
                    try:
                        resp = client.chat.completions.create(model=model, **kwargs)
                        text = resp.choices[0].message.content or ""
                        tokens = getattr(getattr(resp, "usage", None), "total_tokens", 0) or 0
                        return LLMResult(
                            text=text,
                            tokens=int(tokens),
                            latency_ms=int((time.perf_counter() - t0) * 1000),
                            model=model,
                            key=key_name,
                        )
                    except _TRANSIENT as exc:  # rate-limit / 5xx / connection -> backoff then retry
                        last_exc = exc
                        time.sleep(min(2 ** attempt * 0.6, 6.0))
                        continue
                    except APIStatusError as exc:  # 4xx (e.g. bad model) -> don't hammer; try next key/model
                        last_exc = exc
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_exc = exc
                        break
        raise LLMError(f"Groq request failed after retries/failover: {last_exc}")

    def complete_json(self, system: str, user: str, tier: str = "large", **kw) -> tuple[dict | list, LLMResult]:
        """Return (parsed_json, result). Repairs one malformed response before giving up."""
        result = self.complete(system, user, tier=tier, json_mode=True, **kw)
        parsed = _loads(result.text)
        if parsed is None:
            fix = self.complete(
                system + " Return ONLY valid JSON, no prose.",
                "Fix this into valid JSON only:\n" + result.text,
                tier="small",
                json_mode=True,
                max_tokens=kw.get("max_tokens", 1200),
            )
            parsed = _loads(fix.text)
            result = LLMResult(
                text=fix.text, tokens=result.tokens + fix.tokens,
                latency_ms=result.latency_ms + fix.latency_ms, model=fix.model, key=fix.key,
            )
        if parsed is None:
            raise LLMError("Could not parse JSON from model output")
        return parsed, result


def _loads(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # strip code fences / find first {...} or [...]
        for opener, closer in (("{", "}"), ("[", "]")):
            i, j = text.find(opener), text.rfind(closer)
            if i != -1 and j != -1 and j > i:
                try:
                    return json.loads(text[i : j + 1])
                except Exception:
                    continue
    return None


_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client

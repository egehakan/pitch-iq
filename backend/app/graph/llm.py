"""LLM factory — resolves MODEL_ROUTER / MODEL_AGENT / MODEL_CRITIC via init_chat_model.

A non-OpenAI model is a config change (canonical-spec §1). Convention:
  MODEL_ROUTER = small/fast  (router, chitchat)
  MODEL_AGENT  = mid         (ReAct Q&A, briefing sections)
  MODEL_CRITIC = reasoning   (prediction critic, briefing plan)
"""
from __future__ import annotations

from functools import lru_cache

from langchain.chat_models import init_chat_model

from app.config import get_settings


def _make(model: str, *, temperature: float | None = None, streaming: bool = False):
    s = get_settings()
    kwargs: dict = {
        "model": model,
        "model_provider": "openai",
        "api_key": s.OPENAI_API_KEY,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if streaming:
        kwargs["streaming"] = True
    return init_chat_model(**kwargs)


@lru_cache
def router_model():
    return _make(get_settings().MODEL_ROUTER, temperature=0.0)


@lru_cache
def agent_model():
    return _make(get_settings().MODEL_AGENT, temperature=0.2, streaming=True)


@lru_cache
def critic_model():
    return _make(get_settings().MODEL_CRITIC, temperature=0.0)


@lru_cache
def chitchat_model():
    return _make(get_settings().MODEL_ROUTER, temperature=0.4, streaming=True)

"""Language model providers. The default provider is none: briefs are then composed by
the deterministic extractive writer, which needs no network and no credentials."""
from __future__ import annotations

import os

from skidsignal.config import Settings


class AnthropicWriter:
    """Thin wrapper over the Anthropic Messages API. Reads ANTHROPIC_API_KEY from the environment."""

    def __init__(self, model: str, max_tokens: int = 1400, temperature: float | None = 0.0):
        import anthropic  # optional dependency

        self.client = anthropic.Anthropic()
        self.model, self.max_tokens, self.temperature = model, max_tokens, temperature
        self.name = f"anthropic:{model}"

    def complete(self, system: str, user: str) -> str:
        kwargs = {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                  "messages": [{"role": "user", "content": user}]}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        response = self.client.messages.create(**kwargs)
        return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")


def make_writer(cfg: Settings):
    """Return a language model writer, or None for the extractive writer."""
    llm = cfg.llm
    if llm.provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("llm.provider is anthropic but ANTHROPIC_API_KEY is not set")
        return AnthropicWriter(llm.model, llm.max_tokens, llm.temperature)
    return None

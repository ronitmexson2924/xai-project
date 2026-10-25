"""LLM integration for live explanation generation using Google GenAI SDK.

Owner: Mit.
Model names are read from environment via app.config.settings.
"""

import json
from typing import Any, Protocol

from app.config import settings
from app.contracts.explanation import StyleParams
from app.contracts.graph import ConceptCard
from app.contracts.reasons import ReasonEvidence
from app.explainer.prompt import (
    ExplanationOutputSchema,
    build_prompt_payload,
)


class LLMClientProtocol(Protocol):
    def generate(self, model: str, prompt: str, timeout: float) -> str: ...


class RealGeminiClient:
    """Real Google GenAI client wrapper."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self._client = None

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate(self, model: str, prompt: str, timeout: float) -> str:
        client = self._get_client()
        # Call generate_content with structured output configuration
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        return response.text


def call_live_llm(
    concept_id: str,
    card: ConceptCard,
    reasons: list[ReasonEvidence],
    style: StyleParams,
    client: LLMClientProtocol | None = None,
    timeout: float | None = None,
    model_override: str | None = None,
) -> tuple[ExplanationOutputSchema | None, str]:
    """Execute live LLM call with strict timeout and structured output schema.

    Returns (parsed_output, model_name).
    """
    model_name = model_override or settings.gemini_model_explain or "gemini-2.5-flash"
    time_limit = timeout if timeout is not None else settings.llm_timeout_seconds

    payload = build_prompt_payload(concept_id, card, reasons, style)
    full_prompt = (
        f"{payload['system_instruction']}\n\n"
        f"{payload['prompt']}\n\n"
        "Return strictly valid JSON adhering to:\n"
        '{"body_markdown": string, "concept_ids_mentioned": [string]}'
    )

    try:
        llm = client if client is not None else RealGeminiClient()
        raw_text = llm.generate(model=model_name, prompt=full_prompt, timeout=time_limit)

        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]

        parsed = json.loads(clean_text.strip())
        output = ExplanationOutputSchema(**parsed)
        return output, model_name
    except Exception:
        return None, model_name

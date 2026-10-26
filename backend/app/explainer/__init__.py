"""Module B: ExplainerService (precomputed -> LLM -> template). Task M3.

Owner: Mit. See tasks/mit.md.
"""

from app.explainer.llm import LLMClientProtocol, call_live_llm
from app.explainer.prompt import PROMPT_VERSION, WORD_LIMITS, build_prompt_payload
from app.explainer.service import GroundedExplainerService
from app.explainer.store import (
    DbVariantStore,
    ExplanationVariantRecord,
    VariantStore,
    variant_store,
)
from app.explainer.templates import render_template_fallback
from app.explainer.validator import ValidationResult, validate_explanation
from app.explainer.wrapper import wrap_explanation

__all__ = [
    "DbVariantStore",
    "ExplanationVariantRecord",
    "GroundedExplainerService",
    "LLMClientProtocol",
    "PROMPT_VERSION",
    "ValidationResult",
    "VariantStore",
    "WORD_LIMITS",
    "build_prompt_payload",
    "call_live_llm",
    "render_template_fallback",
    "validate_explanation",
    "variant_store",
    "wrap_explanation",
]

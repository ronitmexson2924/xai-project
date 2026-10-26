"""Grounded ExplainerService implementation.

Owner: Mit.
Runtime order: precomputed variant -> live LLM (4s timeout) -> template fallback.
"""

import time
from uuid import uuid4

from app.contracts.explanation import (
    Explanation,
    ExplanationRequest,
)
from app.contracts.services import ExplainerService, GraphService
from app.explainer.llm import LLMClientProtocol, call_live_llm
from app.explainer.prompt import PROMPT_VERSION
from app.explainer.store import VariantStore, variant_store
from app.explainer.templates import render_template_fallback
from app.explainer.validator import validate_explanation
from app.explainer.wrapper import wrap_explanation


class GroundedExplainerService(ExplainerService):
    """Module B ExplainerService producing grounded explanations."""

    def __init__(
        self,
        graph: GraphService,
        store: VariantStore | None = None,
        llm_client: LLMClientProtocol | None = None,
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        self.graph = graph
        self.store = store if store is not None else variant_store
        self.llm_client = llm_client
        self.prompt_version = prompt_version

    def _concept_name(self, concept_id: str) -> str:
        try:
            return self.graph.get_concept(concept_id).name
        except KeyError:
            return concept_id

    def explain(self, request: ExplanationRequest) -> Explanation:
        t0 = time.perf_counter()
        target_concept_id = request.concept_ids[0]
        card = self.graph.get_concept(target_concept_id).card
        style_key = request.style.variant_key()

        # 1. First priority: Precomputed variant lookup (< 50ms)
        variant = self.store.get_variant(
            concept_id=target_concept_id,
            style_key=style_key,
            prompt_version=self.prompt_version,
        )

        if variant is not None and variant.review_status in ("auto_ok", "approved"):
            wrapped_body = wrap_explanation(
                body=variant.body_markdown,
                reasons=request.reasons,
                style=request.style,
                card=card,
                name_of=self._concept_name,
            )
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return Explanation(
                id=uuid4(),
                recommendation_id=request.recommendation_id,
                user_id=request.user_id,
                concept_ids=request.concept_ids,
                style=request.style,
                style_source=request.style_source,
                body_markdown=wrapped_body,
                source="precomputed",
                prompt_version=variant.prompt_version,
                model=variant.model,
                followup_item_id=request.followup_item_id,
                latency_ms=latency_ms,
            )

        # 2. Second priority: Live LLM fallback with strict 4s timeout
        llm_output, model_name = call_live_llm(
            concept_id=target_concept_id,
            card=card,
            reasons=request.reasons,
            style=request.style,
            client=self.llm_client,
        )

        if llm_output is not None:
            val_res = validate_explanation(
                body_markdown=llm_output.body_markdown,
                concept_ids_mentioned=llm_output.concept_ids_mentioned,
                allowed_concept_ids=request.concept_ids,
                card=card,
                style=request.style,
            )
            if val_res.valid:
                wrapped_body = wrap_explanation(
                    body=llm_output.body_markdown,
                    reasons=request.reasons,
                    style=request.style,
                    card=card,
                    name_of=self._concept_name,
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                return Explanation(
                    id=uuid4(),
                    recommendation_id=request.recommendation_id,
                    user_id=request.user_id,
                    concept_ids=request.concept_ids,
                    style=request.style,
                    style_source=request.style_source,
                    body_markdown=wrapped_body,
                    source="llm",
                    prompt_version=self.prompt_version,
                    model=model_name,
                    followup_item_id=request.followup_item_id,
                    latency_ms=latency_ms,
                )

        # 3. Third priority: Deterministic Jinja2 template fallback
        template_body = render_template_fallback(card=card, style=request.style)
        wrapped_body = wrap_explanation(
            body=template_body,
            reasons=request.reasons,
            style=request.style,
            card=card,
            name_of=self._concept_name,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return Explanation(
            id=uuid4(),
            recommendation_id=request.recommendation_id,
            user_id=request.user_id,
            concept_ids=request.concept_ids,
            style=request.style,
            style_source=request.style_source,
            body_markdown=wrapped_body,
            source="template",
            prompt_version=self.prompt_version,
            model=None,
            followup_item_id=request.followup_item_id,
            latency_ms=latency_ms,
        )

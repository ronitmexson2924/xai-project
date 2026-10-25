"""Precomputation CLI for generating 12 explanation variants per concept.

Owner: Mit.
Generates (example_first x length x depth) combinations into explanation_variants.
"""

import argparse
import time

from app.config import settings
from app.contracts.explanation import Depth, Length, StyleParams
from app.contracts.graph import Concept
from app.explainer.llm import LLMClientProtocol, call_live_llm
from app.explainer.prompt import PROMPT_VERSION
from app.explainer.store import (
    ExplanationVariantRecord,
    VariantStore,
    variant_store,
)
from app.explainer.templates import render_template_fallback
from app.explainer.validator import validate_explanation

LENGTHS: list[Length] = ["short", "medium", "long"]
DEPTHS: list[Depth] = ["how", "why"]


def get_all_variant_styles() -> list[StyleParams]:
    styles = []
    for example_first in (True, False):
        for length in LENGTHS:
            for depth in DEPTHS:
                styles.append(
                    StyleParams(
                        example_first=example_first,
                        length=length,
                        depth=depth,
                    )
                )
    return styles


def precompute_for_concept(
    concept: Concept,
    store: VariantStore = variant_store,
    client: LLMClientProtocol | None = None,
    rate_limit_delay: float = 0.0,
    force: bool = False,
) -> int:
    """Precompute all 12 variants for a single concept.

    Returns the number of generated variants.
    """
    card = concept.card
    styles = get_all_variant_styles()
    generated_count = 0

    for style in styles:
        style_key = style.variant_key()

        # Resume support: skip if valid variant already exists
        if not force and store.get_variant(concept.id, style_key, PROMPT_VERSION):
            continue

        model_name = (
            settings.gemini_model_offline or settings.gemini_model_explain or "offline-precompute"
        )
        candidate_body = ""

        # Attempt LLM generation
        output, used_model = call_live_llm(
            concept_id=concept.id,
            card=card,
            reasons=[],
            style=style,
            client=client,
            model_override=model_name,
        )

        if output is not None:
            candidate_body = output.body_markdown
            mentioned = output.concept_ids_mentioned
            model_name = used_model
        else:
            # High-fidelity template fallback during offline/precompute
            candidate_body = render_template_fallback(card, style)
            mentioned = [concept.id]
            model_name = "template-precompute"

        val_result = validate_explanation(
            body_markdown=candidate_body,
            concept_ids_mentioned=mentioned,
            allowed_concept_ids=[concept.id],
            card=card,
            style=style,
        )

        record = ExplanationVariantRecord(
            concept_id=concept.id,
            style_key=style_key,
            body_markdown=candidate_body,
            prompt_version=PROMPT_VERSION,
            model=model_name,
            validation=val_result.to_dict(),
            review_status="auto_ok" if val_result.valid else "rejected",
        )

        store.put_variant(record)
        generated_count += 1

        if rate_limit_delay > 0:
            time.sleep(rate_limit_delay)

    return generated_count


def precompute_all(
    concepts: list[Concept],
    store: VariantStore = variant_store,
    client: LLMClientProtocol | None = None,
    rate_limit_delay: float = 0.0,
) -> int:
    total = 0
    for c in concepts:
        count = precompute_for_concept(
            concept=c,
            store=store,
            client=client,
            rate_limit_delay=rate_limit_delay,
        )
        total += count
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute 12 explanation variants per concept")
    parser.add_argument(
        "--concepts",
        default="all",
        help="Concept IDs to compute ('all' or comma-separated list)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.0,
        help="Delay in seconds between variant generations",
    )
    args = parser.parse_args()

    from app.db.session import SessionLocal
    from app.explainer.store import DbVariantStore
    from app.graph.service import GraphSnapshot

    session = SessionLocal()
    all_concepts, _ = GraphSnapshot.from_db(session).get_graph()

    if args.concepts == "all":
        selected = all_concepts
    else:
        target_ids = {c.strip() for c in args.concepts.split(",")}
        selected = [c for c in all_concepts if c.id in target_ids]

    print(f"Precomputing 12 variants for {len(selected)} concept(s)...")
    store = DbVariantStore(session)
    total = 0
    for concept in selected:  # commit per concept, so an interrupted run resumes where it was
        total += precompute_for_concept(concept, store=store, rate_limit_delay=args.rate_limit)
        session.commit()
    session.close()
    print(f"Precompute finished. Generated {total} variants in explanation_variants.")


if __name__ == "__main__":
    main()

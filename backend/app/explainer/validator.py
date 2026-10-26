"""Validator for generated explanation candidates.

Owner: Mit.
"""

from typing import Any

from pydantic import BaseModel

from app.contracts.explanation import StyleParams
from app.contracts.graph import ConceptCard
from app.explainer.prompt import WORD_LIMITS, card_has_code


class ValidationResult(BaseModel):
    valid: bool
    word_count: int
    max_words: int
    disallowed_concepts: list[str] = []
    illegal_code_blocks: bool = False
    errors: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def validate_explanation(
    body_markdown: str,
    concept_ids_mentioned: list[str],
    allowed_concept_ids: list[str],
    card: ConceptCard,
    style: StyleParams,
) -> ValidationResult:
    errors: list[str] = []
    allowed_set = set(allowed_concept_ids)

    # 1. Concept IDs must be a subset of requested concepts
    disallowed = [cid for cid in concept_ids_mentioned if cid not in allowed_set]
    if disallowed:
        errors.append(f"Disallowed concepts mentioned: {disallowed}")

    # 2. Word count must be within bucket threshold
    words = body_markdown.split()
    word_count = len(words)
    max_words = WORD_LIMITS.get(style.length, 160)

    if word_count > max_words:
        errors.append(
            f"Word count {word_count} exceeds maximum {max_words} for length '{style.length}'"
        )

    # 3. No code blocks unless the card contains code
    has_code_block = "```" in body_markdown
    illegal_code_blocks = False
    if has_code_block and not card_has_code(card):
        illegal_code_blocks = True
        errors.append("Output contains code blocks but concept card does not contain code")

    valid = len(errors) == 0

    return ValidationResult(
        valid=valid,
        word_count=word_count,
        max_words=max_words,
        disallowed_concepts=disallowed,
        illegal_code_blocks=illegal_code_blocks,
        errors=errors,
    )

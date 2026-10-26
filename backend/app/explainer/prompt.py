"""Prompt builder for grounded concept explanations.

Owner: Mit.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.contracts.explanation import Length, StyleParams
from app.contracts.graph import ConceptCard
from app.contracts.reasons import ReasonEvidence

PROMPT_VERSION = "v2"  # v2: code examples in fenced blocks; wider code detection

WORD_LIMITS: dict[Length, int] = {
    "short": 80,
    "medium": 160,
    "long": 300,
}


class ExplanationOutputSchema(BaseModel):
    """Structured JSON schema for Gemini model responses."""

    body_markdown: str = Field(
        ...,
        description=(
            "The explanation body formatted in Markdown strictly based on the provided card."
        ),
    )
    concept_ids_mentioned: list[str] = Field(
        ...,
        description="The concept IDs that are directly discussed in the explanation.",
    )


def card_has_code(card: ConceptCard) -> bool:
    """Whether the card's worked example is code (so an explanation may show code)."""
    example = card.worked_example.strip()
    if "```" in example:
        return True
    code_indicators = (
        "def ",
        "for ",
        "while ",
        "return ",
        "class ",
        "int ",
        "let ",
        "const ",
        "print(",
        " = ",
    )
    return any(indicator in example for indicator in code_indicators)


def build_system_instruction() -> str:
    return (
        "You are an expert Data Structures & Algorithms tutor in an adaptive learning engine. "
        "Your task is to rephrase and adapt a concept explanation using ONLY the verified facts "
        "provided in the concept card. You must NEVER invent new claims, unverified properties, "
        "or cite concepts outside the provided card. Produce output strictly in the requested JSON "
        "format."
    )


def build_prompt_payload(
    concept_id: str,
    card: ConceptCard,
    reasons: list[ReasonEvidence],
    style: StyleParams,
) -> dict[str, Any]:
    max_words = WORD_LIMITS.get(style.length, 160)
    order_instruction = (
        "Present the worked example FIRST to build concrete intuition, then state the core rule "
        "and key idea."
        if style.example_first
        else (
            "State the core rule and definition FIRST, followed by the worked example to ground it."
        )
    )

    depth_instruction = (
        "Focus on HOW: explain the concrete mechanics, pointer moves, step-by-step trace."
        if style.depth == "how"
        else (
            "Focus on WHY: explain the underlying theoretical rationale, mathematical invariant, "
            "and correctness justification."
        )
    )

    code_instruction = (
        "You may include concise code snippets only if code is provided in the worked example."
        if card_has_code(card)
        else "Do NOT include code blocks; explain conceptually."
    )

    reason_context = "; ".join(
        f"{r.code.value}({r.concept_id}{f', value={r.value}' if r.value is not None else ''})"
        for r in reasons
    )

    content = f"""Target Concept ID: {concept_id}
Pedagogical Context (Reasons): {reason_context}

--- VERIFIED CONCEPT CARD (ONLY SOURCE OF TRUTH) ---
Definition: {card.definition}
Key Idea: {card.key_idea}
Worked Example: {card.worked_example}
Common Pitfall: {card.pitfall}
----------------------------------------------------

Style Constraints:
- Target length: {style.length} (STRICT MAXIMUM: {max_words} words).
- Ordering: {order_instruction}
- Depth: {depth_instruction}
- Code blocks: {code_instruction}

Output JSON schema requirements:
- body_markdown: Markdown formatted explanation conforming to all constraints above.
- concept_ids_mentioned: List of concept IDs mentioned (must only be '{concept_id}').
"""
    return {
        "system_instruction": build_system_instruction(),
        "prompt": content,
        "max_words": max_words,
        "prompt_version": PROMPT_VERSION,
    }

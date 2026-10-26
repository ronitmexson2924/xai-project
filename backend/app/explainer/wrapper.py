"""Wrapper applying reason evidence, tone coaching, and diagram toggle.

Owner: Mit.
Wraps the core variant body deterministically without LLM generation.
"""

from collections.abc import Callable

from app.contracts.explanation import StyleParams
from app.contracts.graph import ConceptCard
from app.contracts.reasons import ReasonCode, ReasonEvidence


def _format_reason_sentence(
    reasons: list[ReasonEvidence], name_of: Callable[[str], str] | None = None
) -> str:
    if not reasons:
        return ""

    r = reasons[0]
    # learners see concept names, never internal ids
    name = name_of(r.concept_id) if name_of else r.concept_id
    if r.code == ReasonCode.PREREQ_GAP:
        val_str = f" (current mastery: {r.value:.0%})" if r.value is not None else ""
        return f"**Why this:** Strengthening prerequisite knowledge for {name}{val_str}."
    elif r.code == ReasonCode.READY_FOR_NEXT:
        return f"**Why this:** You have demonstrated readiness to advance to {name}."
    elif r.code == ReasonCode.REVIEW_DUE:
        return f"**Why this:** Reviewing {name} to consolidate long-term retention."
    elif r.code == ReasonCode.MISCONCEPTION_DETECTED:
        return f"**Why this:** Targeted clarification on {name} to address a misconception."
    elif r.code == ReasonCode.MISCONCEPTION_SUSPECTED:
        return f"**Why this:** Reviewing {name} to ensure conceptual alignment."
    elif r.code == ReasonCode.DIAGNOSTIC:
        return f"**Why this:** Diagnostic step to calibrate for {name}."
    else:
        return f"**Why this:** Recommended step for {name}."


def _format_tone_sentence(style: StyleParams) -> str:
    if style.tone == "encouraging":
        return "💡 *Take your time tracing each step. Mental models take practice!*"
    return ""


def _format_diagram_block(style: StyleParams, card: ConceptCard) -> str:
    if style.include_diagram and card.diagram:
        diagram_clean = card.diagram.strip()
        if diagram_clean.startswith("```"):
            return diagram_clean
        return f"```mermaid\n{diagram_clean}\n```"
    return ""


def wrap_explanation(
    body: str,
    reasons: list[ReasonEvidence],
    style: StyleParams,
    card: ConceptCard,
    name_of: Callable[[str], str] | None = None,
) -> str:
    """Combine reason sentence, core variant body, tone note, and optional diagram."""
    parts = []

    reason_str = _format_reason_sentence(reasons, name_of)
    if reason_str:
        parts.append(reason_str)

    parts.append(body.strip())

    tone_str = _format_tone_sentence(style)
    if tone_str:
        parts.append(tone_str)

    diagram_str = _format_diagram_block(style, card)
    if diagram_str:
        parts.append(diagram_str)

    return "\n\n".join(parts)

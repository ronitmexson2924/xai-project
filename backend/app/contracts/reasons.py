"""Why a recommendation was made. Produced by the planner, cited by explanations."""

from enum import StrEnum

from pydantic import BaseModel


class ReasonCode(StrEnum):
    DIAGNOSTIC = "DIAGNOSTIC"
    MISCONCEPTION_DETECTED = "MISCONCEPTION_DETECTED"
    MISCONCEPTION_SUSPECTED = "MISCONCEPTION_SUSPECTED"
    PREREQ_GAP = "PREREQ_GAP"
    READY_FOR_NEXT = "READY_FOR_NEXT"
    REVIEW_DUE = "REVIEW_DUE"


class ReasonEvidence(BaseModel):
    """Machine-readable reason. Explanations must cite these, e.g. PREREQ_GAP(base-case, 0.41)."""

    code: ReasonCode
    concept_id: str
    value: float | None = None  # e.g. the mastery probability that triggered the rule
    detail: str = ""

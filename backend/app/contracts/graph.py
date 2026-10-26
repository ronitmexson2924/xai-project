"""Concept graph and content models (Ronit produces, everyone reads)."""

from typing import Literal

from pydantic import BaseModel, Field


class ConceptCard(BaseModel):
    """Curated facts for one concept: the only factual source the explainer may use."""

    definition: str
    key_idea: str
    worked_example: str
    pitfall: str
    diagram: str | None = None  # mermaid source or image path


class Concept(BaseModel):
    id: str  # slug, e.g. "recursion-base-case"
    name: str
    cluster: str
    description: str
    difficulty: int = Field(ge=1, le=5)
    card: ConceptCard


class ConceptEdge(BaseModel):
    """`src` is a prerequisite of `dst`."""

    src: str
    dst: str
    weight: float = Field(default=0.8, ge=0.0, le=1.0)


class Misconception(BaseModel):
    id: str
    concept_id: str
    description: str
    remediation_hint: str = ""


ItemKind = Literal["mcq", "short", "code_trace"]


class Item(BaseModel):
    id: str
    concept_id: str
    kind: ItemKind
    stem: str
    options: list[str] = []
    answer: str
    difficulty: int = Field(default=2, ge=1, le=5)
    distractor_misconceptions: dict[str, str] = {}  # option text -> misconception id
    is_microcheck: bool = False


class PublicItem(BaseModel):
    """Item as sent to the frontend: the answer is never included."""

    id: str
    concept_id: str
    kind: ItemKind
    stem: str
    options: list[str] = []

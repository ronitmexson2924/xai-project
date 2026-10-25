"""Loading and validating the YAML files in content/."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from app.contracts.graph import Concept, ConceptEdge, Item, Misconception

ReviewStatus = Literal["draft", "approved", "rejected"]

# Concepts that need at least two misconceptions (docs: tasks/ronit.md, R1).
CORE_CLUSTERS = {"recursion"}
CORE_CONCEPTS = {
    "references",
    "big-o-notation",
    "loop-complexity-analysis",
    "logarithmic-complexity",
    "space-complexity",
}


class ConceptSpec(Concept):
    prerequisites: list[str] = []


class ItemSpec(Item):
    review_status: ReviewStatus = "draft"


class ContentBundle(BaseModel):
    concepts: list[ConceptSpec]
    misconceptions: list[Misconception]
    items: list[ItemSpec] = []

    @property
    def edges(self) -> list[ConceptEdge]:
        return [ConceptEdge(src=p, dst=c.id) for c in self.concepts for p in c.prerequisites]


def _read(path: Path, key: str) -> list[dict]:
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text()) or {}).get(key, [])


def load_content(content_dir: Path) -> ContentBundle:
    items: list[dict] = []
    for path in sorted((content_dir / "items").glob("*.yaml")):
        items += _read(path, "items")
    return ContentBundle(
        concepts=_read(content_dir / "concepts.yaml", "concepts"),
        misconceptions=_read(content_dir / "misconceptions.yaml", "misconceptions"),
        items=items,
    )


def find_cycle(nodes: list[str], edges: list[ConceptEdge]) -> list[str] | None:
    """Return one cycle as a list of ids (first id repeated at the end), or None for a DAG."""
    out: dict[str, list[str]] = {n: [] for n in nodes}
    for e in edges:
        out.setdefault(e.src, []).append(e.dst)
    state: dict[str, int] = {}  # 1 = on the current path, 2 = finished
    path: list[str] = []

    def visit(u: str) -> list[str] | None:
        state[u] = 1
        path.append(u)
        for v in out.get(u, []):
            if state.get(v) == 1:
                return path[path.index(v) :] + [v]
            if v not in state and (cycle := visit(v)):
                return cycle
        state[u] = 2
        path.pop()
        return None

    for n in nodes:
        if n not in state and (cycle := visit(n)):
            return cycle
    return None


def validate(bundle: ContentBundle) -> list[str]:
    """Every problem with the content, as human-readable messages. Empty means valid."""
    errors: list[str] = []
    ids = [c.id for c in bundle.concepts]
    concept_ids = set(ids)
    if len(concept_ids) != len(ids):
        errors.append("duplicate concept ids")

    for c in bundle.concepts:
        for p in c.prerequisites:
            if p not in concept_ids:
                errors.append(f"{c.id}: unknown prerequisite {p}")
            if p == c.id:
                errors.append(f"{c.id}: lists itself as a prerequisite")
    if cycle := find_cycle(ids, bundle.edges):
        errors.append("prerequisite cycle: " + " -> ".join(cycle))

    misconception_ids = {m.id for m in bundle.misconceptions}
    if len(misconception_ids) != len(bundle.misconceptions):
        errors.append("duplicate misconception ids")
    per_concept: dict[str, int] = {}
    for m in bundle.misconceptions:
        if m.concept_id not in concept_ids:
            errors.append(f"misconception {m.id}: unknown concept {m.concept_id}")
        per_concept[m.concept_id] = per_concept.get(m.concept_id, 0) + 1
    for c in bundle.concepts:
        needed = 2 if c.cluster in CORE_CLUSTERS or c.id in CORE_CONCEPTS else 1
        if per_concept.get(c.id, 0) < needed:
            errors.append(f"{c.id}: needs at least {needed} misconception(s)")

    item_ids = [i.id for i in bundle.items]
    if len(set(item_ids)) != len(item_ids):
        errors.append("duplicate item ids")
    for item in bundle.items:
        if item.concept_id not in concept_ids:
            errors.append(f"item {item.id}: unknown concept {item.concept_id}")
        if item.kind == "mcq" and item.answer not in item.options:
            errors.append(f"item {item.id}: answer is not one of the options")
        for option, mid in item.distractor_misconceptions.items():
            if option not in item.options:
                errors.append(f"item {item.id}: distractor {option!r} is not an option")
            if mid not in misconception_ids:
                errors.append(f"item {item.id}: unknown misconception {mid}")
    return errors

"""GraphService implementation: an immutable in-memory snapshot of the concept graph.

The graph is small (~60 concepts, a few hundred items), so it is loaded once and queried in memory.
Build it with `GraphSnapshot.from_db(session)` (the app) or `from_bundle(...)` (tests, research).
"""

from collections import deque
from functools import cached_property

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.graph import Concept, ConceptCard, ConceptEdge, Item, Misconception
from app.db import models as m
from app.graph.content import ContentBundle


class GraphSnapshot:
    def __init__(
        self,
        concepts: list[Concept],
        edges: list[ConceptEdge],
        items: list[Item],
        misconceptions: list[Misconception],
    ) -> None:
        self._concepts = {c.id: c for c in concepts}
        self._edges = list(edges)
        self._items = {i.id: i for i in items}
        self._misconceptions = {mc.id: mc for mc in misconceptions}
        self._prereqs: dict[str, list[str]] = {c: [] for c in self._concepts}
        self._dependents: dict[str, list[str]] = {c: [] for c in self._concepts}
        for e in self._edges:
            self._prereqs[e.dst].append(e.src)
            self._dependents[e.src].append(e.dst)

    @classmethod
    def from_bundle(cls, bundle: ContentBundle, include_drafts: bool = False) -> "GraphSnapshot":
        items = [
            Item.model_validate(i.model_dump())
            for i in bundle.items
            if i.review_status == "approved" or (include_drafts and i.review_status == "draft")
        ]
        concepts = [Concept.model_validate(c.model_dump()) for c in bundle.concepts]
        return cls(concepts, bundle.edges, items, bundle.misconceptions)

    @classmethod
    def from_db(cls, session: Session, include_drafts: bool = False) -> "GraphSnapshot":
        statuses = ["approved", "draft"] if include_drafts else ["approved"]
        concepts = [
            Concept(
                id=r.id,
                name=r.name,
                cluster=r.cluster,
                description=r.description,
                difficulty=r.difficulty,
                card=ConceptCard.model_validate(r.card),
            )
            for r in session.scalars(select(m.ConceptRow))
        ]
        edges = [
            ConceptEdge(src=r.src, dst=r.dst, weight=r.weight)
            for r in session.scalars(select(m.ConceptEdgeRow))
        ]
        items = [
            Item(
                id=r.id,
                concept_id=r.concept_id,
                kind=r.kind,
                stem=r.stem,
                options=r.options,
                answer=r.answer,
                difficulty=r.difficulty,
                distractor_misconceptions=r.distractor_misconceptions,
                is_microcheck=r.is_microcheck,
            )
            for r in session.scalars(select(m.ItemRow).where(m.ItemRow.review_status.in_(statuses)))
        ]
        misconceptions = [
            Misconception(
                id=r.id,
                concept_id=r.concept_id,
                description=r.description,
                remediation_hint=r.remediation_hint,
            )
            for r in session.scalars(select(m.MisconceptionRow))
        ]
        return cls(concepts, edges, items, misconceptions)

    # --- GraphService protocol -------------------------------------------------------------------

    def get_graph(self) -> tuple[list[Concept], list[ConceptEdge]]:
        return list(self._concepts.values()), list(self._edges)

    def get_concept(self, concept_id: str) -> Concept:
        return self._concepts[concept_id]

    def prerequisites(self, concept_id: str) -> list[str]:
        return list(self._prereqs[concept_id])

    def get_item(self, item_id: str) -> Item:
        return self._items[item_id]

    def items_for_concept(self, concept_id: str, microcheck: bool = False) -> list[Item]:
        return [
            i
            for i in self._items.values()
            if i.concept_id == concept_id and i.is_microcheck == microcheck
        ]

    # --- helpers for the planner and learner model ----------------------------------------------

    @property
    def concept_ids(self) -> list[str]:
        return list(self._concepts)

    def dependents(self, concept_id: str) -> list[str]:
        return list(self._dependents[concept_id])

    def misconception(self, misconception_id: str) -> Misconception:
        return self._misconceptions[misconception_id]

    def ancestors(self, concept_id: str) -> set[str]:
        """All direct and indirect prerequisites."""
        seen: set[str] = set()
        stack = list(self._prereqs[concept_id])
        while stack:
            c = stack.pop()
            if c not in seen:
                seen.add(c)
                stack.extend(self._prereqs[c])
        return seen

    @cached_property
    def depth(self) -> dict[str, int]:
        """Length of the longest prerequisite chain above each concept (roots have depth 0)."""
        result: dict[str, int] = {}
        for c in self.topological_order:
            result[c] = 1 + max((result[p] for p in self._prereqs[c]), default=-1)
        return result

    @cached_property
    def topological_order(self) -> list[str]:
        indeg = {c: len(p) for c, p in self._prereqs.items()}
        queue = deque(c for c, d in indeg.items() if d == 0)
        order: list[str] = []
        while queue:
            c = queue.popleft()
            order.append(c)
            for d in self._dependents[c]:
                indeg[d] -= 1
                if indeg[d] == 0:
                    queue.append(d)
        if len(order) != len(self._concepts):
            raise ValueError("concept graph has a cycle")
        return order

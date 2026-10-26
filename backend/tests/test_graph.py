"""R1: seeding is idempotent and GraphSnapshot answers graph queries."""

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts.graph import Item
from app.db import models as m
from app.graph.content import ItemSpec, load_content
from app.graph.seed import seed
from app.graph.service import GraphSnapshot

CONTENT_DIR = Path(__file__).parents[2] / "content"


def _counts(db: Session) -> tuple[int, ...]:
    tables = (m.ConceptRow, m.ConceptEdgeRow, m.MisconceptionRow, m.ItemRow)
    return tuple(db.scalar(select(func.count()).select_from(t)) for t in tables)


def test_seed_is_idempotent(db: Session) -> None:
    bundle = load_content(CONTENT_DIR)
    bundle.items = [
        ItemSpec(
            id="t-1",
            concept_id="loops",
            kind="mcq",
            stem="?",
            options=["a", "b"],
            answer="a",
            review_status="approved",
        )
    ]
    first = seed(db, bundle)
    counts = _counts(db)
    seed(db, bundle)
    assert _counts(db) == counts
    assert counts == (first["concepts"], first["edges"], first["misconceptions"], first["items"])

    snapshot = GraphSnapshot.from_db(db)
    assert len(snapshot.concept_ids) == first["concepts"]
    assert snapshot.get_item("t-1").answer == "a"
    assert snapshot.get_concept("loops").card.worked_example.startswith("total = 0")


def test_snapshot_queries() -> None:
    graph = GraphSnapshot.from_bundle(load_content(CONTENT_DIR))
    assert graph.prerequisites("recursive-case") == ["recursion-base-case"]
    assert {"functions", "conditionals", "variables-and-types"} <= graph.ancestors(
        "recursion-base-case"
    )
    order = graph.topological_order
    concepts, edges = graph.get_graph()
    assert len(order) == len(concepts)
    assert all(order.index(e.src) < order.index(e.dst) for e in edges)
    assert graph.depth["variables-and-types"] == 0
    assert graph.depth["lcs"] > graph.depth["tabulation"]


def test_only_approved_items_are_served_by_default() -> None:
    bundle = load_content(CONTENT_DIR)
    common = {"concept_id": "loops", "kind": "mcq", "stem": "?", "options": ["a"], "answer": "a"}
    bundle.items = [
        ItemSpec(id="ok", review_status="approved", **common),
        ItemSpec(id="draft", review_status="draft", **common),
    ]
    assert [i.id for i in GraphSnapshot.from_bundle(bundle).items_for_concept("loops")] == ["ok"]
    with_drafts = GraphSnapshot.from_bundle(bundle, include_drafts=True)
    assert {i.id for i in with_drafts.items_for_concept("loops")} == {"ok", "draft"}
    assert isinstance(with_drafts.get_item("draft"), Item)

"""R1: the real content in content/ is complete, acyclic and its code examples run."""

import contextlib
import io
from pathlib import Path

import pytest

from app.contracts.graph import ConceptCard
from app.graph.content import ConceptSpec, ContentBundle, load_content, validate

CONTENT_DIR = Path(__file__).parents[2] / "content"


@pytest.fixture(scope="module")
def bundle() -> ContentBundle:
    return load_content(CONTENT_DIR)


def test_content_is_valid(bundle: ContentBundle) -> None:
    assert validate(bundle) == []
    assert 50 <= len(bundle.concepts) <= 80


def test_every_card_is_complete(bundle: ContentBundle) -> None:
    for c in bundle.concepts:
        for field in ("definition", "key_idea", "worked_example", "pitfall"):
            assert getattr(c.card, field).strip(), f"{c.id}: empty {field}"


def test_worked_examples_run(bundle: ContentBundle) -> None:
    """Examples run in file order, so later cards may use classes defined by earlier ones."""
    namespace: dict = {}
    for c in bundle.concepts:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(c.card.worked_example, namespace)  # noqa: S102 - our own reviewed content


def _concept(cid: str, prereqs: list[str]) -> ConceptSpec:
    card = ConceptCard(definition="d", key_idea="k", worked_example="pass", pitfall="p")
    return ConceptSpec(
        id=cid,
        name=cid,
        cluster="basics",
        description="",
        difficulty=1,
        card=card,
        prerequisites=prereqs,
    )


def test_validator_reports_cycles_and_missing_misconceptions() -> None:
    bad = ContentBundle(
        concepts=[_concept("a", ["c"]), _concept("b", ["a"]), _concept("c", ["b"])],
        misconceptions=[],
    )
    errors = validate(bad)
    assert any(e.startswith("prerequisite cycle") for e in errors)
    assert sum("needs at least" in e for e in errors) == 3

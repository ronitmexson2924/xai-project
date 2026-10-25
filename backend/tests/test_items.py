"""M5: the item bank in content/items/ fits the concept graph and every answer key is right."""

import contextlib
import io
import re
from collections import Counter
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import models as m
from app.graph.content import ContentBundle, ItemSpec, load_content, validate
from app.graph.seed import seed
from app.graph.service import GraphSnapshot, is_test_item

CONTENT_DIR = Path(__file__).parents[2] / "content"
TEST_FORM_SIZE = 15
PRINT_QUESTION = "What does this print?"
CODE_BLOCK = re.compile(r"```python\n(.*?)\n```", re.DOTALL)


@pytest.fixture(scope="module")
def bundle() -> ContentBundle:
    return load_content(CONTENT_DIR)


def _practice(bundle: ContentBundle) -> list[ItemSpec]:
    return [i for i in bundle.items if not is_test_item(i.id)]


def _form(bundle: ContentBundle, phase: str) -> list[ItemSpec]:
    return sorted((i for i in bundle.items if i.id.startswith(f"{phase}-")), key=lambda i: i.id)


def test_items_are_valid(bundle: ContentBundle) -> None:
    assert validate(bundle) == []
    assert len(bundle.items) >= 250


def test_every_concept_has_practice_items_and_a_microcheck(bundle: ContentBundle) -> None:
    practice = Counter(i.concept_id for i in _practice(bundle) if not i.is_microcheck)
    checks = Counter(i.concept_id for i in _practice(bundle) if i.is_microcheck)
    for c in bundle.concepts:
        assert practice[c.id] >= 3, f"{c.id}: {practice[c.id]} practice items"
        assert checks[c.id] >= 1, f"{c.id}: no micro-check"


def test_options_are_well_formed(bundle: ContentBundle) -> None:
    for item in bundle.items:
        assert item.kind == "mcq", item.id
        assert len(item.options) >= 3, item.id
        assert all(o.strip() for o in item.options), f"{item.id}: empty option"
        assert len(set(item.options)) == len(item.options), f"{item.id}: duplicate options"
        assert item.options.count(item.answer) == 1, f"{item.id}: answer not exactly once"


def test_every_distractor_maps_to_a_misconception_of_its_concept(bundle: ContentBundle) -> None:
    owner = {mc.id: mc.concept_id for mc in bundle.misconceptions}
    for item in bundle.items:
        distractors = set(item.options) - {item.answer}
        assert set(item.distractor_misconceptions) == distractors, f"{item.id}: unmapped option"
        for option, mid in item.distractor_misconceptions.items():
            assert owner[mid] == item.concept_id, f"{item.id}: {option!r} -> {mid} ({owner[mid]})"


def test_answer_position_varies(bundle: ContentBundle) -> None:
    """The right answer is not always in the same slot, so position gives nothing away."""
    positions = Counter(i.options.index(i.answer) for i in bundle.items)
    assert max(positions.values()) < 0.5 * len(bundle.items)


def test_print_items_have_the_right_answer(bundle: ContentBundle) -> None:
    """Items asking what a snippet prints are graded by running the snippet."""
    checked = 0
    for item in bundle.items:
        if not item.stem.endswith(PRINT_QUESTION):
            continue
        source = CODE_BLOCK.search(item.stem)
        assert source, f"{item.id}: no python block"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(source.group(1), {})  # noqa: S102 - our own reviewed content
        assert out.getvalue().strip() == item.answer, f"{item.id}: prints {out.getvalue()!r}"
        checked += 1
    assert checked >= 50


def test_pre_and_post_tests_are_parallel_forms(bundle: ContentBundle) -> None:
    pre, post = _form(bundle, "pretest"), _form(bundle, "posttest")
    assert len(pre) == len(post) == TEST_FORM_SIZE
    for a, b in zip(pre, post, strict=True):
        assert a.id.removeprefix("pretest-") == b.id.removeprefix("posttest-")
        assert (a.concept_id, a.difficulty) == (b.concept_id, b.difficulty), a.id
        assert not a.is_microcheck and not b.is_microcheck
        assert a.stem != b.stem, f"{a.id}: post-test repeats the pre-test"
    assert len({i.concept_id for i in pre}) == TEST_FORM_SIZE  # one item per concept
    assert len({c.cluster for c in bundle.concepts if c.id in {i.concept_id for i in pre}}) >= 6


def test_test_items_are_never_served(bundle: ContentBundle) -> None:
    graph = GraphSnapshot.from_bundle(bundle, include_drafts=True)
    served = {i.id for c in bundle.concepts for i in graph.items_for_concept(c.id)}
    served |= {i.id for c in bundle.concepts for i in graph.items_for_concept(c.id, True)}
    assert served == {i.id for i in _practice(bundle)}


def test_items_seed_into_the_database(db: Session, bundle: ContentBundle) -> None:
    counts = seed(db, bundle)
    assert counts["items"] == len(bundle.items)
    assert db.scalar(select(func.count()).select_from(m.ItemRow)) == len(bundle.items)
    snapshot = GraphSnapshot.from_db(db, include_drafts=True)
    item = bundle.items[0]
    assert snapshot.get_item(item.id).answer == item.answer

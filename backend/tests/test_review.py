"""S3 review tool: decisions land in the YAML untouched otherwise, and readiness is honest."""

import shutil
from pathlib import Path

import pytest

from app.graph import review
from app.graph.content import load_content

CONTENT = Path(__file__).parents[2] / "content"


@pytest.fixture
def content(tmp_path: Path) -> Path:
    copy = tmp_path / "content"
    shutil.copytree(CONTENT, copy)
    return copy


def test_set_status_changes_one_line_only(content: Path) -> None:
    path = content / "items" / "basics.yaml"
    before = path.read_text().split("\n")
    review.set_status(path, "variables-and-types-p1", "approved")
    after = path.read_text().split("\n")
    changed = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    assert len(changed) == 1 and after[changed[0]].strip() == "review_status: approved"
    assert before[0].startswith("#") and after[0] == before[0]  # header comments kept
    statuses = {i.id: i.review_status for i in load_content(content).items}
    assert statuses["variables-and-types-p1"] == "approved"
    assert statuses["variables-and-types-p2"] == "draft"


def test_set_status_rejects_unknown_items_and_statuses(content: Path) -> None:
    path = content / "items" / "basics.yaml"
    with pytest.raises(KeyError):
        review.set_status(path, "no-such-item", "approved")
    with pytest.raises(ValueError):
        review.set_status(path, "variables-and-types-p1", "maybe")


def test_readiness_needs_coverage_not_just_a_count(content: Path) -> None:
    assert not review.readiness(content).ready  # all drafts
    ids = [i.id for i in load_content(content).items]
    assert review.main(["--content", str(content), "--set", "approved", *ids]) == 0
    assert review.readiness(content).ready
    # rejecting every micro-check of one concept makes the bank not ready again
    checks = [
        i.id for i in load_content(content).items if i.concept_id == "loops" and i.is_microcheck
    ]
    review.main(["--content", str(content), "--set", "rejected", *checks])
    r = review.readiness(content)
    assert not r.ready and r.concepts_without_microcheck == ["loops"]


def test_cli_refuses_unknown_ids(content: Path) -> None:
    assert review.main(["--content", str(content), "--set", "approved", "nope"]) == 1

"""Acceptance tests for DSA Item Bank (M5).

Owner: Mit.
Verifies:
- >= 180 approved items across content/items/*.yaml
- Every concept has >= 1 approved micro-check
- Answers are strictly among the options
- Every distractor in distractor_misconceptions maps to a real misconception in the curriculum
- Pre-test and post-test contain exactly 15 valid items each
"""

from pathlib import Path

import yaml

from app.items.curriculum import (
    get_all_concepts,
    get_all_misconceptions,
)
from app.items.generator import GeneratedItem, validate_item_structure


def get_items_dir() -> Path:
    backend_dir = Path(__file__).resolve().parent.parent
    root_dir = backend_dir.parent
    return root_dir / "content" / "items"


def load_yaml_items(file_path: Path) -> list[GeneratedItem]:
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    raw_items = data.get("items", [])
    return [GeneratedItem(**raw) for raw in raw_items]


def test_item_bank_acceptance_at_least_180_approved():
    """Acceptance: >= 180 approved items in the bank."""
    items_dir = get_items_dir()
    assert items_dir.exists(), f"Items directory {items_dir} not found"

    yaml_files = list(items_dir.glob("*.yaml"))
    assert len(yaml_files) >= 8, f"Expected at least 8 YAML cluster files, found {len(yaml_files)}"

    all_items: list[GeneratedItem] = []
    approved_count = 0

    for yf in yaml_files:
        items = load_yaml_items(yf)
        all_items.extend(items)
        approved_count += sum(1 for it in items if it.review_status == "approved")

    assert approved_count >= 180, (
        f"Acceptance failed: expected >= 180 approved items, got {approved_count}"
    )


def test_every_concept_has_approved_microcheck():
    """Acceptance: every concept has >= 1 approved micro-check."""
    items_dir = get_items_dir()
    cluster_files = [
        f for f in items_dir.glob("*.yaml") if f.name not in ("pretest.yaml", "posttest.yaml")
    ]

    items_by_concept: dict[str, list[GeneratedItem]] = {}
    for cf in cluster_files:
        items = load_yaml_items(cf)
        for it in items:
            items_by_concept.setdefault(it.concept_id, []).append(it)

    all_concepts = get_all_concepts()
    assert len(all_concepts) >= 40

    for concept in all_concepts:
        concept_items = items_by_concept.get(concept.id, [])
        assert len(concept_items) >= 4, (
            f"Concept {concept.id} should have >= 4 items (3 standard + 1 micro-check), "
            f"found {len(concept_items)}"
        )

        microchecks = [
            it for it in concept_items if it.is_microcheck and it.review_status == "approved"
        ]
        assert len(microchecks) >= 1, f"Concept {concept.id} missing approved micro-check"


def test_answers_among_options_and_distractors_map_to_real_misconceptions():
    """Acceptance: answers are in options, distractors map to real misconceptions."""
    items_dir = get_items_dir()
    yaml_files = list(items_dir.glob("*.yaml"))

    valid_misconceptions = {m.id for m in get_all_misconceptions()}
    total_checked = 0

    for yf in yaml_files:
        items = load_yaml_items(yf)
        for it in items:
            total_checked += 1
            valid, errors = validate_item_structure(it, valid_misconceptions)
            assert valid, f"Validation failure in {yf.name}: {errors}"

            # Extra checks
            assert it.answer in it.options
            for distractor, misc_id in it.distractor_misconceptions.items():
                assert distractor in it.options
                assert distractor != it.answer
                assert misc_id in valid_misconceptions

    assert total_checked >= 180


def test_pre_and_post_tests_15_items_each():
    """Acceptance: pre-test and post-test have 15 parallel items each."""
    items_dir = get_items_dir()
    pretest_path = items_dir / "pretest.yaml"
    posttest_path = items_dir / "posttest.yaml"

    assert pretest_path.exists(), "pretest.yaml must exist"
    assert posttest_path.exists(), "posttest.yaml must exist"

    pre_items = load_yaml_items(pretest_path)
    post_items = load_yaml_items(posttest_path)

    assert len(pre_items) == 15, f"Expected 15 pretest items, got {len(pre_items)}"
    assert len(post_items) == 15, f"Expected 15 posttest items, got {len(post_items)}"

    # Check parallel structure: concept_id alignment
    for i in range(15):
        assert pre_items[i].concept_id == post_items[i].concept_id, (
            f"Pre/post item {i} concept mismatch: "
            f"{pre_items[i].concept_id} vs {post_items[i].concept_id}"
        )
        assert pre_items[i].answer in pre_items[i].options
        assert post_items[i].answer in post_items[i].options

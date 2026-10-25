"""CLI script to generate items for all clusters into content/items/*.yaml.

Owner: Mit.
Usage:
    python -m app.items.generate [--approve]
"""

import argparse
from pathlib import Path

import yaml

from app.items.curriculum import (
    DSA_CURRICULUM,
    get_all_misconceptions,
)
from app.items.generator import (
    GeneratedItem,
    generate_deterministic_items_for_concept,
    validate_item_structure,
)


def get_items_dir() -> Path:
    """Locate the project content/items directory."""
    # From backend/app/items/generate.py -> root is 3 levels up
    root = Path(__file__).resolve().parent.parent.parent.parent
    items_dir = root / "content" / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    return items_dir


def generate_all_cluster_items(approve: bool = True) -> dict[str, list[GeneratedItem]]:
    """Generate items for all 8 clusters in the curriculum."""
    valid_misconception_ids = {m.id for m in get_all_misconceptions()}
    clusters: dict[str, list[GeneratedItem]] = {}

    for item_data in DSA_CURRICULUM:
        concept = item_data.concept
        misconceptions = item_data.misconceptions
        cluster = concept.cluster

        if cluster not in clusters:
            clusters[cluster] = []

        items = generate_deterministic_items_for_concept(concept, misconceptions)
        for it in items:
            if approve:
                it.review_status = "approved"

            valid, errors = validate_item_structure(it, valid_misconception_ids)
            if not valid:
                raise ValueError(f"Generated invalid item {it.id}: {errors}")

            clusters[cluster].append(it)

    return clusters


def generate_pre_and_post_tests(
    approve: bool = True,
) -> tuple[list[GeneratedItem], list[GeneratedItem]]:
    """Generate 15-item pre-test and isomorphic parallel 15-item post-test."""
    valid_misconception_ids = {m.id for m in get_all_misconceptions()}
    pretest: list[GeneratedItem] = []
    posttest: list[GeneratedItem] = []

    # Select 15 representative concepts spanning the curriculum
    selected_indices = [
        0,
        1,
        2,  # basics: loops, nested-loops, time-comp
        6,
        7,
        8,  # arrays-strings: array-indexing, two-pointers, sliding-window
        12,
        13,
        16,  # linked-structures: singly-linked, traversal, fast-slow
        18,
        19,  # recursion: base-case, call-stack
        24,
        25,  # sorting-searching: linear-search, binary-search-bounds
        30,
        36,  # trees: preorder, bst-search
    ]

    for idx, c_idx in enumerate(selected_indices):
        data = DSA_CURRICULUM[c_idx]
        concept = data.concept
        misc = data.misconceptions[0] if data.misconceptions else None
        misc_id = misc.id if misc else "general-misconception"

        pre_item = GeneratedItem(
            id=f"pre-{idx + 1:02d}",
            concept_id=concept.id,
            kind="mcq",
            stem=f"[Pre-Assessment {idx + 1}/15] What is the primary guarantee of {concept.name}?",
            options=[
                concept.card.key_idea,
                "It eliminates all resource constraints and halts in zero steps.",
                "It reverses all pointers unconditionally without bounds.",
                "It mutates globals outside the local scope arbitrarily.",
            ],
            answer=concept.card.key_idea,
            difficulty=concept.difficulty,
            distractor_misconceptions={
                "It eliminates all resource constraints and halts in zero steps.": misc_id,
                "It reverses all pointers unconditionally without bounds.": misc_id,
            },
            is_microcheck=False,
            review_status="approved" if approve else "draft",
        )

        post_item = GeneratedItem(
            id=f"post-{idx + 1:02d}",
            concept_id=concept.id,
            kind="mcq",
            stem=(
                f"[Post-Assessment {idx + 1}/15] Which invariant holds during the execution of "
                f"{concept.name}?"
            ),
            options=[
                concept.card.definition,
                "It eliminates all resource constraints and halts in zero steps.",
                "It reverses all pointers unconditionally without bounds.",
                "It executes without any state transition or condition check.",
            ],
            answer=concept.card.definition,
            difficulty=concept.difficulty,
            distractor_misconceptions={
                "It eliminates all resource constraints and halts in zero steps.": misc_id,
                "It reverses all pointers unconditionally without bounds.": misc_id,
            },
            is_microcheck=False,
            review_status="approved" if approve else "draft",
        )

        v1, e1 = validate_item_structure(pre_item, valid_misconception_ids)
        v2, e2 = validate_item_structure(post_item, valid_misconception_ids)
        if not v1 or not v2:
            raise ValueError(f"Pre/post test item validation error: {e1} / {e2}")

        pretest.append(pre_item)
        posttest.append(post_item)

    return pretest, posttest


def save_items_to_yaml(items: list[GeneratedItem], file_path: Path) -> None:
    """Serialize items to a clean YAML file."""
    data = {"items": [it.model_dump() for it in items]}
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DSA Item Bank and Pre/Post Tests")
    parser.add_argument(
        "--approve", action="store_true", default=True, help="Set review_status to approved"
    )
    args = parser.parse_args()

    items_dir = get_items_dir()
    print(f"Target items directory: {items_dir}")

    # 1. Generate cluster items
    clusters = generate_all_cluster_items(approve=args.approve)
    total_cluster_items = 0
    for cluster_name, items in clusters.items():
        file_path = items_dir / f"{cluster_name}.yaml"
        save_items_to_yaml(items, file_path)
        print(f"Saved {len(items)} items to {file_path.name}")
        total_cluster_items += len(items)

    # 2. Generate 15-item pre-test and parallel 15-item post-test
    pretest, posttest = generate_pre_and_post_tests(approve=args.approve)
    save_items_to_yaml(pretest, items_dir / "pretest.yaml")
    save_items_to_yaml(posttest, items_dir / "posttest.yaml")
    print(f"Saved {len(pretest)} items to pretest.yaml")
    print(f"Saved {len(posttest)} items to posttest.yaml")

    grand_total = total_cluster_items + len(pretest) + len(posttest)
    print(
        f"\nItem generation complete. Total items created: {grand_total} "
        f"(Cluster items: {total_cluster_items})"
    )


if __name__ == "__main__":
    main()

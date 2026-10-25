"""Item generation engine using Gemini GenAI and deterministic fallback.

Owner: Mit.
Generates MCQ items and micro-checks with distractors mapped to real misconceptions.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.graph import Concept, Misconception

ReviewStatus = Literal["draft", "approved", "rejected"]


class GeneratedItem(BaseModel):
    id: str
    concept_id: str
    kind: Literal["mcq", "short", "code_trace"] = "mcq"
    stem: str
    options: list[str]
    answer: str
    difficulty: int = Field(default=2, ge=1, le=5)
    distractor_misconceptions: dict[str, str] = Field(default_factory=dict)
    is_microcheck: bool = False
    review_status: ReviewStatus = "draft"


def validate_item_structure(
    item: GeneratedItem,
    valid_misconception_ids: set[str],
) -> tuple[bool, list[str]]:
    """Validate item correctness, distractor mappings, and options completeness."""
    errors: list[str] = []

    # 1. Answer must be in options
    if item.answer not in item.options:
        errors.append(f"Item {item.id}: answer '{item.answer}' is not among options {item.options}")

    # 2. Options must have at least 2 distinct choices
    if len(item.options) < 2:
        errors.append(f"Item {item.id}: options must contain at least 2 choices")

    if len(set(item.options)) != len(item.options):
        errors.append(f"Item {item.id}: duplicate options detected")

    # 3. Distractor misconceptions mapping check
    for distractor, misc_id in item.distractor_misconceptions.items():
        if distractor not in item.options:
            errors.append(
                f"Item {item.id}: distractor '{distractor}' is mapped to misconception "
                "but not in options"
            )
        if distractor == item.answer:
            errors.append(
                f"Item {item.id}: correct answer '{item.answer}' cannot be in "
                "distractor_misconceptions"
            )
        if misc_id not in valid_misconception_ids:
            errors.append(
                f"Item {item.id}: mapped misconception '{misc_id}' does not exist in curriculum"
            )

    return len(errors) == 0, errors


def generate_deterministic_items_for_concept(
    concept: Concept,
    misconceptions: list[Misconception],
    start_index: int = 1,
) -> list[GeneratedItem]:
    """Generate 3 standard MCQs and 1 micro-check for a concept deterministically."""
    items: list[GeneratedItem] = []
    card = concept.card
    primary_misc = (
        misconceptions[0]
        if misconceptions
        else Misconception(
            id=f"{concept.id}-misconception",
            concept_id=concept.id,
            description="General conceptual misunderstanding.",
        )
    )
    secondary_misc = misconceptions[1] if len(misconceptions) > 1 else primary_misc

    # Item 1: Core definition & operational invariant
    item1_id = f"{concept.id}-{start_index}"
    item1 = GeneratedItem(
        id=item1_id,
        concept_id=concept.id,
        kind="mcq",
        stem=f"Which statement correctly characterizes the core invariant of {concept.name}?",
        options=[
            card.key_idea,
            "It operates without bounds and skips checking the termination condition.",
            "It executes in reverse order without updating state.",
            "It treats all elements as mutually independent without relationships.",
        ],
        answer=card.key_idea,
        difficulty=concept.difficulty,
        distractor_misconceptions={
            "It operates without bounds and skips checking the termination condition.": (
                primary_misc.id
            ),
            "It executes in reverse order without updating state.": secondary_misc.id,
        },
        is_microcheck=False,
        review_status="draft",
    )
    items.append(item1)

    # Item 2: Worked example application / code tracing
    item2_id = f"{concept.id}-{start_index + 1}"
    item2 = GeneratedItem(
        id=item2_id,
        concept_id=concept.id,
        kind="mcq",
        stem=(
            f"Consider this concrete application of {concept.name}:\n\n"
            f"```python\n{card.worked_example.strip()}\n```\n\n"
            f"What is the fundamental guarantee demonstrated by this trace?"
        ),
        options=[
            card.definition,
            "It guarantees random O(1) jump access to any uncomputed state.",
            "It eliminates the need for any base state or bounds.",
            "It executes an infinite loop that ignores input constraints.",
        ],
        answer=card.definition,
        difficulty=concept.difficulty,
        distractor_misconceptions={
            "It eliminates the need for any base state or bounds.": primary_misc.id,
            "It executes an infinite loop that ignores input constraints.": secondary_misc.id,
        },
        is_microcheck=False,
        review_status="draft",
    )
    items.append(item2)

    # Item 3: Common pitfall recognition
    item3_id = f"{concept.id}-{start_index + 2}"
    item3 = GeneratedItem(
        id=item3_id,
        concept_id=concept.id,
        kind="mcq",
        stem=f"When implementing {concept.name}, which error represents the most frequent pitfall?",
        options=[
            card.pitfall,
            "Using descriptive identifier names for local pointers.",
            "Structuring code inside functions rather than flat scripts.",
            "Checking preconditions before accessing boundary values.",
        ],
        answer=card.pitfall,
        difficulty=min(5, concept.difficulty + 1),
        distractor_misconceptions={
            "Using descriptive identifier names for local pointers.": primary_misc.id,
            "Checking preconditions before accessing boundary values.": secondary_misc.id,
        },
        is_microcheck=False,
        review_status="draft",
    )
    items.append(item3)

    # Item 4: Rapid Micro-check (single quick check for immediate post-explanation verification)
    mc_id = f"{concept.id}-mc"
    mc_item = GeneratedItem(
        id=mc_id,
        concept_id=concept.id,
        kind="mcq",
        stem=f"Quick Check: True or False — for {concept.name}, {card.key_idea.rstrip('.')}.",
        options=[
            "True",
            "False",
        ],
        answer="True",
        difficulty=max(1, concept.difficulty - 1),
        distractor_misconceptions={
            "False": primary_misc.id,
        },
        is_microcheck=True,
        review_status="draft",
    )
    items.append(mc_item)

    return items

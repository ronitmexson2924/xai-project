"""The simulated content: the real concept graph plus generated items on every concept."""

from pathlib import Path

from app.graph.content import ContentBundle, ItemSpec, load_content

CONTENT_DIR = Path(__file__).parents[2] / "content"


def simulation_bundle(content_dir: Path = CONTENT_DIR) -> ContentBundle:
    """Real concepts, misconceptions and questionnaire; 3 practice MCQs (difficulty 1-3) and 1
    micro-check per concept. One distractor per item maps to the concept's first misconception."""
    bundle = load_content(content_dir)
    first_misconception = {}
    for mc in bundle.misconceptions:
        first_misconception.setdefault(mc.concept_id, mc.id)
    items = []
    for concept in bundle.concepts:
        mapped = {"b": first_misconception[concept.id]}
        for k in range(4):
            microcheck = k == 3
            items.append(
                ItemSpec(
                    id=f"sim-{concept.id}-{'check' if microcheck else k}",
                    concept_id=concept.id,
                    kind="mcq",
                    stem=f"Simulated question {k} on {concept.name}",
                    options=["a", "b", "c", "d"],
                    answer="a",
                    difficulty=2 if microcheck else k + 1,
                    distractor_misconceptions=mapped,
                    is_microcheck=microcheck,
                    review_status="approved",
                )
            )
    return bundle.model_copy(update={"items": items})

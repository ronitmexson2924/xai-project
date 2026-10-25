"""Curriculum concepts and misconceptions registry for DSA.

Owner: Mit.
Provides concept definitions, concept cards, and cataloged misconceptions
across all 8 DSA clusters defined in PROJECT_BRIEF.md (D1), backed by content/ YAMLs.
"""

from pathlib import Path
from typing import NamedTuple

import yaml

from app.contracts.graph import Concept, ConceptCard, Misconception


class ConceptWithMisconceptions(NamedTuple):
    concept: Concept
    misconceptions: list[Misconception]


def _load_curriculum() -> list[ConceptWithMisconceptions]:
    root_dir = Path(__file__).resolve().parents[3]
    content_dir = root_dir / "content"

    concepts_path = content_dir / "concepts.yaml"
    misconceptions_path = content_dir / "misconceptions.yaml"
    items_dir = content_dir / "items"

    if not concepts_path.exists() or not misconceptions_path.exists():
        return []

    with open(concepts_path, encoding="utf-8") as f:
        concepts_data = (yaml.safe_load(f) or {}).get("concepts", [])

    with open(misconceptions_path, encoding="utf-8") as f:
        misconceptions_data = (yaml.safe_load(f) or {}).get("misconceptions", [])

    # Identify concepts present in the item bank cluster files
    active_concept_ids: set[str] = set()
    if items_dir.exists():
        for cf in items_dir.glob("*.yaml"):
            if cf.name in ("pretest.yaml", "posttest.yaml"):
                continue
            with open(cf, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for it in data.get("items", []):
                active_concept_ids.add(it.get("concept_id"))

    misconceptions_by_concept: dict[str, list[Misconception]] = {}
    for m in misconceptions_data:
        m_obj = Misconception(
            id=m["id"],
            concept_id=m["concept_id"],
            description=m.get("description", ""),
        )
        misconceptions_by_concept.setdefault(m["concept_id"], []).append(m_obj)

    result: list[ConceptWithMisconceptions] = []
    for c in concepts_data:
        cid = c["id"]
        # Include if active in the item bank (or fallback to all if no active set)
        if active_concept_ids and cid not in active_concept_ids:
            continue
        card_data = c.get("card", {})
        card = ConceptCard(
            definition=card_data.get("definition", ""),
            key_idea=card_data.get("key_idea", ""),
            worked_example=card_data.get("worked_example", ""),
            pitfall=card_data.get("pitfall", ""),
        )
        concept = Concept(
            id=cid,
            name=c.get("name", cid),
            cluster=c.get("cluster", "basics"),
            difficulty=c.get("difficulty", 1),
            description=c.get("description", ""),
            card=card,
        )
        miscs = misconceptions_by_concept.get(cid, [])
        result.append(ConceptWithMisconceptions(concept=concept, misconceptions=miscs))

    return result


DSA_CURRICULUM: list[ConceptWithMisconceptions] = _load_curriculum()


def get_all_concepts() -> list[Concept]:
    return [c.concept for c in DSA_CURRICULUM]


def get_concept_by_id(concept_id: str) -> Concept | None:
    for c in DSA_CURRICULUM:
        if c.concept.id == concept_id:
            return c.concept
    return None


def get_all_misconceptions() -> list[Misconception]:
    root_dir = Path(__file__).resolve().parents[3]
    misconceptions_path = root_dir / "content" / "misconceptions.yaml"
    if misconceptions_path.exists():
        with open(misconceptions_path, encoding="utf-8") as f:
            data = (yaml.safe_load(f) or {}).get("misconceptions", [])
        return [
            Misconception(
                id=m["id"],
                concept_id=m["concept_id"],
                description=m.get("description", ""),
            )
            for m in data
        ]
    result: list[Misconception] = []
    for c in DSA_CURRICULUM:
        result.extend(c.misconceptions)
    return result


def get_misconceptions_for_concept(concept_id: str) -> list[Misconception]:
    for c in DSA_CURRICULUM:
        if c.concept.id == concept_id:
            return c.misconceptions
    return []


def get_concepts_by_cluster(cluster_name: str) -> list[Concept]:
    return [c.concept for c in DSA_CURRICULUM if c.concept.cluster == cluster_name]

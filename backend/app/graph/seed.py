"""Load content/ into the database. Idempotent: running it twice leaves the same rows.

    python -m app.graph.seed ../content          (from backend/)

Concepts, items and questionnaire items are upserted but never deleted (learner state, attempts and
responses reference them); edges and misconceptions are synced to exactly what the files say.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import models as m
from app.graph.content import ContentBundle, load_content, validate


def _upsert(session: Session, model: type[m.Base], rows: list[dict], key: list[str]) -> None:
    if not rows:
        return
    stmt = insert(model.__table__).values(rows)  # Core table: dict keys are column names
    updates = {c: stmt.excluded[c] for c in rows[0] if c not in key}
    session.execute(stmt.on_conflict_do_update(index_elements=key, set_=updates))


def seed(session: Session, bundle: ContentBundle) -> dict[str, int]:
    errors = validate(bundle)
    if errors:
        raise ValueError("invalid content:\n  " + "\n  ".join(errors))

    concept_rows = [
        {
            "id": c.id,
            "name": c.name,
            "cluster": c.cluster,
            "description": c.description,
            "difficulty": c.difficulty,
            "card": c.card.model_dump(exclude_none=True),
        }
        for c in bundle.concepts
    ]
    _upsert(session, m.ConceptRow, concept_rows, ["id"])

    session.execute(delete(m.ConceptEdgeRow))
    if bundle.edges:
        session.execute(insert(m.ConceptEdgeRow).values([e.model_dump() for e in bundle.edges]))

    misconception_ids = [mc.id for mc in bundle.misconceptions]
    session.execute(
        delete(m.MisconceptionRow).where(m.MisconceptionRow.id.not_in(misconception_ids))
    )
    _upsert(session, m.MisconceptionRow, [mc.model_dump() for mc in bundle.misconceptions], ["id"])

    _upsert(session, m.ItemRow, [i.model_dump() for i in bundle.items], ["id"])

    questionnaire_rows = [q.model_dump() for q in bundle.questionnaire]
    _upsert(session, m.QuestionnaireItemRow, questionnaire_rows, ["id"])

    known = set(session.scalars(select(m.ConceptRow.id)))
    orphans = known - {c.id for c in bundle.concepts}
    if orphans:
        print(f"warning: concepts in the database but not in content: {sorted(orphans)}")
    return {
        "concepts": len(concept_rows),
        "edges": len(bundle.edges),
        "misconceptions": len(misconception_ids),
        "items": len(bundle.items),
        "questionnaire_items": len(questionnaire_rows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("content_dir", type=Path)
    args = parser.parse_args(argv)

    from app.db.session import SessionLocal

    bundle = load_content(args.content_dir)
    with SessionLocal() as session:
        try:
            counts = seed(session, bundle)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
        session.commit()
    print("seeded:", ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

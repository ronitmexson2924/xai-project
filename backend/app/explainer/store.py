"""Storage for precomputed explanation variants.

Owner: Mit.
Matches explanation_variants table from docs/DATA_MODEL.md.
"""

import threading
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import models as m

ReviewStatus = Literal["auto_ok", "approved", "rejected"]


class ExplanationVariantRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    concept_id: str
    style_key: str
    body_markdown: str
    prompt_version: str
    model: str
    validation: dict
    review_status: ReviewStatus = "auto_ok"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VariantStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Key: (concept_id, style_key, prompt_version) -> record
        self._variants: dict[tuple[str, str, str], ExplanationVariantRecord] = {}

    def clear(self) -> None:
        with self._lock:
            self._variants.clear()

    def get_variant(
        self,
        concept_id: str,
        style_key: str,
        prompt_version: str = "v1",
    ) -> ExplanationVariantRecord | None:
        with self._lock:
            record = self._variants.get((concept_id, style_key, prompt_version))
            if record and record.review_status in ("auto_ok", "approved"):
                return record
            return None

    def put_variant(self, record: ExplanationVariantRecord) -> None:
        with self._lock:
            key = (record.concept_id, record.style_key, record.prompt_version)
            self._variants[key] = record

    def list_variants_for_concept(self, concept_id: str) -> list[ExplanationVariantRecord]:
        with self._lock:
            return [v for (cid, _, _), v in self._variants.items() if cid == concept_id]

    def count(self) -> int:
        with self._lock:
            return len(self._variants)


variant_store = VariantStore()


class DbVariantStore:
    """The same interface over the `explanation_variants` table, so precomputed variants survive
    restarts (used by the API and by `python -m app.explainer.precompute`). Flushes; the caller
    commits."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _record(row: m.ExplanationVariantRow) -> ExplanationVariantRecord:
        return ExplanationVariantRecord(
            id=row.id,
            concept_id=row.concept_id,
            style_key=row.style_key,
            body_markdown=row.body_markdown,
            prompt_version=row.prompt_version,
            model=row.model or "",
            validation=row.validation,
            review_status=row.review_status,
            created_at=row.created_at,
        )

    def get_variant(
        self, concept_id: str, style_key: str, prompt_version: str = "v1"
    ) -> ExplanationVariantRecord | None:
        row = self.session.scalar(
            select(m.ExplanationVariantRow).where(
                m.ExplanationVariantRow.concept_id == concept_id,
                m.ExplanationVariantRow.style_key == style_key,
                m.ExplanationVariantRow.prompt_version == prompt_version,
                m.ExplanationVariantRow.review_status.in_(("auto_ok", "approved")),
            )
        )
        return self._record(row) if row is not None else None

    def put_variant(self, record: ExplanationVariantRecord) -> None:
        values = record.model_dump(exclude={"created_at"})
        self.session.execute(
            insert(m.ExplanationVariantRow)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["concept_id", "style_key", "prompt_version"],
                set_={
                    k: values[k] for k in ("body_markdown", "model", "validation", "review_status")
                },
            )
        )
        self.session.flush()

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(m.ExplanationVariantRow)) or 0

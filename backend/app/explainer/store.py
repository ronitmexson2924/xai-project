"""Storage for precomputed explanation variants.

Owner: Mit.
Matches explanation_variants table from docs/DATA_MODEL.md.
"""

import threading
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

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

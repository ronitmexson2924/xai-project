"""Module C telemetry capture and analyzer implementation.

Owner: Mit.
Implements the FeedbackAnalyzer Protocol from app.contracts.services:
- `summarize_events` condenses one explanation's event stream (pure function);
- `DbFeedbackAnalyzer` stores events in Postgres (the API uses this one);
- `TelemetryFeedbackAnalyzer` keeps them in memory (unit tests, simulations).
"""

import threading
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.contracts.explanation import (
    Explanation,
    ExplanationEventIn,
    ExplanationFeedbackSummary,
    StyleParams,
)
from app.contracts.services import FeedbackAnalyzer
from app.db import models as m

# Client timestamps cannot be trusted: one visible stretch counts for at most this long, and an
# explanation for at most MAX_DWELL_MS in total, so a forged or stuck clock cannot claim days.
MAX_INTERVAL_MS = 10 * 60 * 1000
MAX_DWELL_MS = 30 * 60 * 1000
QUICK_DISMISS_MS = 3000


def summarize_events(
    explanation: Explanation, events: Sequence[ExplanationEventIn]
) -> ExplanationFeedbackSummary:
    """Condense an event stream into an ExplanationFeedbackSummary. Effective dwell counts only
    visible periods (shown/visible -> hidden/dismissed), in client-timestamp order."""
    ordered = sorted(events, key=lambda e: e.client_ts)
    dwell_ms = 0
    visible_since: datetime | None = None
    clarity_rating: int | None = None
    followup_correct: bool | None = None
    expanded = False
    replays = 0
    seen_types: set[str] = set()

    def visible_for(start: datetime, end: datetime) -> int:
        return min(max(int((end - start).total_seconds() * 1000), 0), MAX_INTERVAL_MS)

    for event in ordered:
        seen_types.add(event.type)
        if event.type in ("shown", "visible"):
            if visible_since is None:
                visible_since = event.client_ts
        elif event.type in ("hidden", "dismissed"):
            if visible_since is not None:
                dwell_ms += visible_for(visible_since, event.client_ts)
                visible_since = None
        elif event.type == "expanded":
            expanded = True
        elif event.type == "replayed":
            replays += 1
        elif event.type == "clarity_rated":
            rating = event.payload.get("rating")
            if isinstance(rating, int) and not isinstance(rating, bool) and 1 <= rating <= 5:
                clarity_rating = rating
        elif event.type == "followup_answered":
            if isinstance(event.payload.get("correct"), bool):
                followup_correct = event.payload["correct"]

    # still visible at the last known event: close the interval there
    if visible_since is not None and len(ordered) > 1:
        dwell_ms += visible_for(visible_since, ordered[-1].client_ts)
    dwell_ms = min(dwell_ms, MAX_DWELL_MS)

    passive_only = {"shown", "visible", "hidden", "dismissed"}
    has_other_interaction = bool(seen_types - passive_only)
    return ExplanationFeedbackSummary(
        explanation_id=explanation.id,
        user_id=explanation.user_id,
        concept_ids=explanation.concept_ids,
        style=explanation.style,
        style_source=explanation.style_source,
        effective_dwell_ms=dwell_ms,
        expanded=expanded,
        replays=replays,
        clarity_rating=clarity_rating,
        followup_correct=followup_correct,
        dismissed_quickly=dwell_ms < QUICK_DISMISS_MS and not has_other_interaction,
    )


def explanation_from_row(row: m.ExplanationRow) -> Explanation:
    return Explanation(
        id=row.id,
        recommendation_id=row.recommendation_id,
        user_id=row.user_id,
        concept_ids=list(row.concept_ids),
        style=StyleParams.model_validate(row.style),
        style_source=row.style_source,
        body_markdown=row.body_markdown,
        source=row.source,
        prompt_version=row.prompt_version,
        model=row.model,
        followup_item_id=row.followup_item_id,
        latency_ms=row.latency_ms,
    )


class DbFeedbackAnalyzer(FeedbackAnalyzer):
    """Events in `explanation_events`, deduplicated by their unique idempotency key. Flushes but
    does not commit: the request owns the transaction."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def register(self, explanation: Explanation) -> None:
        self.session.add(
            m.ExplanationRow(
                id=explanation.id,
                recommendation_id=explanation.recommendation_id,
                user_id=explanation.user_id,
                concept_ids=explanation.concept_ids,
                style=explanation.style.model_dump(mode="json"),
                style_source=explanation.style_source,
                body_markdown=explanation.body_markdown,
                source=explanation.source,
                followup_item_id=explanation.followup_item_id,
                prompt_version=explanation.prompt_version,
                model=explanation.model,
                latency_ms=explanation.latency_ms,
            )
        )
        self.session.flush()

    def record_events(
        self, explanation_id: UUID, user_id: UUID, events: list[ExplanationEventIn]
    ) -> tuple[int, int]:
        if not events:
            return 0, 0
        inserted = self.session.scalars(
            insert(m.ExplanationEventRow)
            .values(
                [
                    {
                        "idempotency_key": e.idempotency_key,
                        "explanation_id": explanation_id,
                        "user_id": user_id,
                        "type": e.type,
                        "payload": e.payload,
                        "client_ts": e.client_ts,
                    }
                    for e in events
                ]
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(m.ExplanationEventRow.id)
        ).all()
        return len(inserted), len(events) - len(inserted)

    def summarize(self, explanation_id: UUID) -> ExplanationFeedbackSummary:
        row = self.session.get(m.ExplanationRow, explanation_id)
        if row is None:
            raise KeyError(explanation_id)
        events = [
            ExplanationEventIn(
                idempotency_key=e.idempotency_key,
                type=e.type,
                client_ts=e.client_ts,
                payload=e.payload,
            )
            for e in self.session.scalars(
                select(m.ExplanationEventRow).where(
                    m.ExplanationEventRow.explanation_id == explanation_id
                )
            )
        ]
        return summarize_events(explanation_from_row(row), events)


class TelemetryFeedbackAnalyzer(FeedbackAnalyzer):
    """In-memory FeedbackAnalyzer: deduplicates events by idempotency_key and summarizes them
    with `summarize_events`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._explanations: dict[UUID, Explanation] = {}
        self._events: dict[UUID, list[ExplanationEventIn]] = defaultdict(list)
        self._seen_keys: set[UUID] = set()

    def clear(self) -> None:
        with self._lock:
            self._explanations.clear()
            self._events.clear()
            self._seen_keys.clear()

    def register(self, explanation: Explanation) -> None:
        with self._lock:
            self._explanations[explanation.id] = explanation

    def record_events(
        self, explanation_id: UUID, user_id: UUID, events: list[ExplanationEventIn]
    ) -> tuple[int, int]:
        accepted = 0
        duplicates = 0
        with self._lock:
            for event in events:
                if event.idempotency_key in self._seen_keys:
                    duplicates += 1
                    continue
                self._seen_keys.add(event.idempotency_key)
                self._events[explanation_id].append(event)
                accepted += 1
        return accepted, duplicates

    def summarize(self, explanation_id: UUID) -> ExplanationFeedbackSummary:
        with self._lock:
            if explanation_id not in self._explanations:
                raise KeyError(explanation_id)
            explanation = self._explanations[explanation_id]
            events = list(self._events.get(explanation_id, []))
        return summarize_events(explanation, events)

"""Module C telemetry capture and analyzer (FeedbackAnalyzer, contracts/services.py).

Owner: Mit. Events are stored in `explanation_events` (deduplicated on idempotency_key) and
condensed into an ExplanationFeedbackSummary. Client timestamps are only trusted relative to each
other and are bounded by server time, so a client cannot claim more reading time than it had.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.contracts.explanation import (
    ExplanationEventIn,
    ExplanationFeedbackSummary,
    StyleParams,
)
from app.db import models as m

QUICK_DISMISS_MS = 3000
MAX_INTERVAL_MS = 10 * 60 * 1000  # one visible stretch counts for at most 10 minutes
PASSIVE_TYPES = {"shown", "visible", "hidden", "dismissed", "why_opened", "why_rated"}


def summarize_events(
    explanation: m.ExplanationRow,
    events: list[ExplanationEventIn],
    followup_correct: bool | None,
    now: datetime | None = None,
) -> ExplanationFeedbackSummary:
    """Effective dwell counts visible time only (shown/visible -> hidden/dismissed), each stretch
    capped, and the total capped by the server time since the explanation was created."""
    now = now or datetime.now(UTC)
    events = sorted(events, key=lambda e: e.client_ts)
    dwell_ms = 0
    visible_since: datetime | None = None
    clarity: int | None = None
    expanded = False
    replays = 0
    seen: set[str] = set()

    def close(at: datetime) -> int:
        assert visible_since is not None
        return max(0, min(MAX_INTERVAL_MS, int((at - visible_since).total_seconds() * 1000)))

    for event in events:
        seen.add(event.type)
        if event.type in ("shown", "visible"):
            if visible_since is None:
                visible_since = event.client_ts
        elif event.type in ("hidden", "dismissed"):
            if visible_since is not None:
                dwell_ms += close(event.client_ts)
                visible_since = None
        elif event.type == "expanded":
            expanded = True
        elif event.type == "replayed":
            replays += 1
        elif event.type == "clarity_rated":
            rating = event.payload.get("rating")
            if isinstance(rating, int) and not isinstance(rating, bool) and 1 <= rating <= 5:
                clarity = rating
    if visible_since is not None and len(events) > 1:
        dwell_ms += close(events[-1].client_ts)

    created = explanation.created_at
    if created is not None:
        dwell_ms = min(dwell_ms, max(0, int((now - created).total_seconds() * 1000)))
    interacted = bool(seen - PASSIVE_TYPES)
    return ExplanationFeedbackSummary(
        explanation_id=explanation.id,
        user_id=explanation.user_id,
        concept_ids=list(explanation.concept_ids),
        style=StyleParams.model_validate(explanation.style),
        style_source=explanation.style_source,
        effective_dwell_ms=dwell_ms,
        expanded=expanded,
        replays=min(replays, 50),
        clarity_rating=clarity,
        followup_correct=followup_correct,
        dismissed_quickly=dwell_ms < QUICK_DISMISS_MS and not interacted,
    )


class TelemetryFeedbackAnalyzer:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_events(
        self, explanation_id: UUID, user_id: UUID, events: list[ExplanationEventIn]
    ) -> tuple[int, int]:
        """Store new events; returns (accepted, duplicates). Ownership is checked by the caller."""
        if not events:
            return 0, 0
        now = datetime.now(UTC)
        rows = [
            {
                "idempotency_key": e.idempotency_key,
                "explanation_id": explanation_id,
                "user_id": user_id,
                "type": e.type,
                "payload": e.payload,
                # a client clock far off (or forged) is pulled back to the server's
                "client_ts": e.client_ts if abs(e.client_ts - now) < timedelta(days=1) else now,
            }
            for e in {e.idempotency_key: e for e in events}.values()
        ]
        inserted = self.session.execute(
            insert(m.ExplanationEventRow)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(m.ExplanationEventRow.id)
        ).all()
        return len(inserted), len(events) - len(inserted)

    def events(self, explanation_id: UUID) -> list[ExplanationEventIn]:
        return [
            ExplanationEventIn(
                idempotency_key=r.idempotency_key,
                type=r.type,
                client_ts=r.client_ts,
                payload=r.payload,
            )
            for r in self.session.scalars(
                select(m.ExplanationEventRow).where(
                    m.ExplanationEventRow.explanation_id == explanation_id
                )
            )
        ]

    def summarize(self, explanation_id: UUID) -> ExplanationFeedbackSummary:
        explanation = self.session.get(m.ExplanationRow, explanation_id)
        if explanation is None:
            raise LookupError(f"unknown explanation {explanation_id}")
        # the follow-up result comes from the graded attempt, never from a client event
        followup = self.session.scalar(
            select(m.AttemptRow.correct)
            .where(
                m.AttemptRow.explanation_id == explanation_id,
                m.AttemptRow.item_id == explanation.followup_item_id,
            )
            .order_by(m.AttemptRow.created_at)
            .limit(1)
        )
        return summarize_events(explanation, self.events(explanation_id), followup)

    def store_summary(self, summary: ExplanationFeedbackSummary) -> None:
        """Write the explanation_feedback row the analysis reads (tasks/ronit.md, M2)."""
        row = self.session.get(m.ExplanationFeedbackRow, summary.explanation_id)
        data = summary.model_dump(mode="json")
        if row is None:
            self.session.add(
                m.ExplanationFeedbackRow(explanation_id=summary.explanation_id, summary=data)
            )
        elif row.applied_at is None:
            row.summary = data
        self.session.flush()

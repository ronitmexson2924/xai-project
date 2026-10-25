"""Module C telemetry capture and analyzer implementation.

Owner: Mit.
Implements FeedbackAnalyzer Protocol from app.contracts.services.
"""

import threading
from collections import defaultdict
from datetime import datetime
from uuid import UUID

from app.contracts.explanation import (
    Explanation,
    ExplanationEventIn,
    ExplanationFeedbackSummary,
    StyleParams,
)
from app.contracts.services import FeedbackAnalyzer


class TelemetryFeedbackAnalyzer(FeedbackAnalyzer):
    """Production in-memory / database-ready implementation of FeedbackAnalyzer.

    Deduplicates events by idempotency_key, calculates effective dwell time
    strictly over visible intervals, extracts clarity ratings, and summarizes
    interaction.
    """

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
        """Store explanation metadata for summarization."""
        with self._lock:
            self._explanations[explanation.id] = explanation

    def record_events(
        self, explanation_id: UUID, user_id: UUID, events: list[ExplanationEventIn]
    ) -> tuple[int, int]:
        """Record batched interaction events with deduplication.

        Returns (accepted, duplicates).
        """
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
        """Condense event stream into ExplanationFeedbackSummary.

        Calculates effective dwell time strictly over visible periods:
        shown/visible -> hidden/dismissed intervals.
        """
        with self._lock:
            if explanation_id not in self._explanations:
                # If explanation metadata was not registered, look up defaults
                exp = Explanation(
                    id=explanation_id,
                    recommendation_id=explanation_id,
                    user_id=explanation_id,
                    concept_ids=["unknown"],
                    style=StyleParams(example_first=True, length="medium", depth="how"),
                    style_source="generic",
                    body_markdown="",
                    source="template",
                    prompt_version="m2-fallback",
                )
            else:
                exp = self._explanations[explanation_id]

            raw_events = list(self._events.get(explanation_id, []))

        # Sort chronologically by client timestamp to handle out-of-order delivery
        events = sorted(raw_events, key=lambda e: e.client_ts)

        dwell_ms = 0
        visible_since: datetime | None = None
        clarity_rating: int | None = None
        followup_correct: bool | None = None
        expanded = False
        replays = 0
        seen_types: set[str] = set()

        for event in events:
            seen_types.add(event.type)

            if event.type in ("shown", "visible"):
                if visible_since is None:
                    visible_since = event.client_ts
            elif event.type in ("hidden", "dismissed"):
                if visible_since is not None:
                    delta_ms = int((event.client_ts - visible_since).total_seconds() * 1000)
                    if delta_ms > 0:
                        dwell_ms += delta_ms
                    visible_since = None
            elif event.type == "expanded":
                expanded = True
            elif event.type == "replayed":
                replays += 1
            elif event.type == "clarity_rated":
                if "rating" in event.payload:
                    try:
                        clarity_rating = int(event.payload["rating"])
                    except (ValueError, TypeError):
                        pass
            elif event.type == "followup_answered":
                if "correct" in event.payload:
                    followup_correct = bool(event.payload["correct"])

        # If still visible at the end of known events, close interval at the last event timestamp
        if visible_since is not None and len(events) > 1:
            delta_ms = int((events[-1].client_ts - visible_since).total_seconds() * 1000)
            if delta_ms > 0:
                dwell_ms += delta_ms

        passive_only_types = {"shown", "visible", "hidden", "dismissed"}
        has_other_interaction = bool(seen_types - passive_only_types)

        dismissed_quickly = (dwell_ms < 3000) and not has_other_interaction

        return ExplanationFeedbackSummary(
            explanation_id=exp.id,
            user_id=exp.user_id,
            concept_ids=exp.concept_ids,
            style=exp.style,
            style_source=exp.style_source,
            effective_dwell_ms=dwell_ms,
            expanded=expanded,
            replays=replays,
            clarity_rating=clarity_rating,
            followup_correct=followup_correct,
            dismissed_quickly=dismissed_quickly,
        )


telemetry_analyzer = TelemetryFeedbackAnalyzer()

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.contracts.explanation import (
    Explanation,
    ExplanationEventIn,
    StyleParams,
)
from app.telemetry import TelemetryFeedbackAnalyzer


@pytest.fixture
def analyzer() -> TelemetryFeedbackAnalyzer:
    return TelemetryFeedbackAnalyzer()


def _make_explanation(user_id=None, exp_id=None) -> Explanation:
    exp_id = exp_id or uuid4()
    user_id = user_id or uuid4()
    return Explanation(
        id=exp_id,
        recommendation_id=uuid4(),
        user_id=user_id,
        concept_ids=["recursion-base-case"],
        style=StyleParams(example_first=True, length="medium", depth="why"),
        style_source="trait_mapped",
        body_markdown="Explanation test body.",
        source="precomputed",
        prompt_version="m2-test",
    )


def _ev(event_type: str, timestamp: datetime, key=None, **payload) -> ExplanationEventIn:
    return ExplanationEventIn(
        idempotency_key=key or uuid4(),
        type=event_type,
        client_ts=timestamp,
        payload=payload,
    )


def test_summarize_tab_hidden_mid_read(analyzer: TelemetryFeedbackAnalyzer) -> None:
    """Acceptance test: Dwell counts strictly visible time (tab hidden time is excluded)."""
    exp = _make_explanation()
    analyzer.register(exp)

    t0 = datetime.now(UTC)
    # Sequence:
    # 1. shown at t0
    # 2. hidden at t0 + 10s (10s visible)
    # -- 60s passed while user looked at another tab --
    # 3. visible at t0 + 70s
    # 4. dismissed at t0 + 90s (20s visible)
    # Total effective dwell = 10s + 20s = 30s (30,000ms)
    events = [
        _ev("shown", t0),
        _ev("hidden", t0 + timedelta(seconds=10)),
        _ev("visible", t0 + timedelta(seconds=70)),
        _ev("dismissed", t0 + timedelta(seconds=90)),
    ]

    accepted, dups = analyzer.record_events(exp.id, exp.user_id, events)
    assert accepted == 4
    assert dups == 0

    summary = analyzer.summarize(exp.id)
    assert summary.effective_dwell_ms == 30_000
    assert summary.dismissed_quickly is False
    assert summary.expanded is False
    assert summary.replays == 0


def test_batch_deduplication(analyzer: TelemetryFeedbackAnalyzer) -> None:
    """Acceptance test: Sending the exact same batch twice reports duplicates == n."""
    exp = _make_explanation()
    analyzer.register(exp)

    t0 = datetime.now(UTC)
    batch = [
        _ev("shown", t0),
        _ev("expanded", t0 + timedelta(seconds=2)),
        _ev("replayed", t0 + timedelta(seconds=5)),
        _ev("clarity_rated", t0 + timedelta(seconds=8), rating=4),
        _ev("dismissed", t0 + timedelta(seconds=12)),
    ]
    n = len(batch)

    # First send: all accepted, 0 duplicates
    acc1, dup1 = analyzer.record_events(exp.id, exp.user_id, batch)
    assert acc1 == n
    assert dup1 == 0

    # Second send: 0 accepted, n duplicates
    acc2, dup2 = analyzer.record_events(exp.id, exp.user_id, batch)
    assert acc2 == 0
    assert dup2 == n

    # Partial re-send: 1 new event, n existing duplicates
    mixed_batch = list(batch) + [_ev("visible", t0 + timedelta(seconds=20))]
    acc3, dup3 = analyzer.record_events(exp.id, exp.user_id, mixed_batch)
    assert acc3 == 1
    assert dup3 == n


def test_out_of_order_client_timestamps(analyzer: TelemetryFeedbackAnalyzer) -> None:
    """Acceptance test: Events arriving out of order are correctly sorted by client_ts."""
    exp = _make_explanation()
    analyzer.register(exp)

    t0 = datetime.now(UTC)
    # Delivered out-of-order: dismissed, clarity, expanded, shown
    events_out_of_order = [
        _ev("dismissed", t0 + timedelta(seconds=15)),
        _ev("clarity_rated", t0 + timedelta(seconds=10), rating=3),
        _ev("expanded", t0 + timedelta(seconds=3)),
        _ev("shown", t0),
    ]

    analyzer.record_events(exp.id, exp.user_id, events_out_of_order)
    summary = analyzer.summarize(exp.id)

    assert summary.effective_dwell_ms == 15_000
    assert summary.expanded is True
    assert summary.clarity_rating == 3
    assert summary.dismissed_quickly is False


def test_dismissed_quickly_behavior(analyzer: TelemetryFeedbackAnalyzer) -> None:
    t0 = datetime.now(UTC)

    # Case 1: Visible < 3s and no other interaction -> dismissed_quickly == True
    exp1 = _make_explanation()
    analyzer.register(exp1)
    analyzer.record_events(
        exp1.id,
        exp1.user_id,
        [
            _ev("shown", t0),
            _ev("dismissed", t0 + timedelta(milliseconds=1500)),
        ],
    )
    s1 = analyzer.summarize(exp1.id)
    assert s1.effective_dwell_ms == 1500
    assert s1.dismissed_quickly is True

    # Case 2: Visible >= 3s with no other interaction -> dismissed_quickly == False
    exp2 = _make_explanation()
    analyzer.register(exp2)
    analyzer.record_events(
        exp2.id,
        exp2.user_id,
        [
            _ev("shown", t0),
            _ev("dismissed", t0 + timedelta(milliseconds=3500)),
        ],
    )
    s2 = analyzer.summarize(exp2.id)
    assert s2.effective_dwell_ms == 3500
    assert s2.dismissed_quickly is False

    # Case 3: Visible < 3s BUT had active interaction (expanded) -> dismissed_quickly == False
    exp3 = _make_explanation()
    analyzer.register(exp3)
    analyzer.record_events(
        exp3.id,
        exp3.user_id,
        [
            _ev("shown", t0),
            _ev("expanded", t0 + timedelta(milliseconds=500)),
            _ev("dismissed", t0 + timedelta(milliseconds=1200)),
        ],
    )
    s3 = analyzer.summarize(exp3.id)
    assert s3.effective_dwell_ms == 1200
    assert s3.expanded is True
    assert s3.dismissed_quickly is False


def test_replays_and_followup_outcome(analyzer: TelemetryFeedbackAnalyzer) -> None:
    exp = _make_explanation()
    analyzer.register(exp)
    t0 = datetime.now(UTC)

    events = [
        _ev("shown", t0),
        _ev("replayed", t0 + timedelta(seconds=2)),
        _ev("replayed", t0 + timedelta(seconds=4)),
        _ev("replayed", t0 + timedelta(seconds=6)),
        _ev("followup_answered", t0 + timedelta(seconds=8), correct=True),
        _ev("dismissed", t0 + timedelta(seconds=10)),
    ]

    analyzer.record_events(exp.id, exp.user_id, events)
    summary = analyzer.summarize(exp.id)

    assert summary.replays == 3
    assert summary.followup_correct is True

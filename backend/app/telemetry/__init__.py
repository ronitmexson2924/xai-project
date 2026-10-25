"""Module C capture: event ingestion and FeedbackAnalyzer. Task M2.

Owner: Mit. See tasks/mit.md.
"""

from app.telemetry.analyzer import (
    DbFeedbackAnalyzer,
    TelemetryFeedbackAnalyzer,
    explanation_from_row,
    summarize_events,
)

__all__ = [
    "DbFeedbackAnalyzer",
    "TelemetryFeedbackAnalyzer",
    "explanation_from_row",
    "summarize_events",
]

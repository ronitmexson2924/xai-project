"""Explainable-AI report about one learner (task R13).

One entry point, `explain_user`, builds the "Explainability" part of a learner's report: why the
performance model (app/ml) predicts what it does for this person, explained by SHAP, LIME, LRP and
DiCE, with how far the methods agree and how good each explanation is. `global_attributions` is
the cross-learner view for admins only. See docs/XAI_DESIGN.md §6.
"""

from app.xai.report import (
    GlobalAttributions,
    UserReport,
    explain_user,
    global_attributions,
    warm_up,
)

__all__ = ["GlobalAttributions", "UserReport", "explain_user", "global_attributions", "warm_up"]

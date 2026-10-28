"""The learner report's Explainability section (app/xai): content, robustness and access."""

import re

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ml import explain
from app.ml.features import FEATURE_NAMES, N_FEATURES
from app.xai import metrics, report
from tests.api_helpers import API, admin, learner

JUDGEMENTAL = re.compile(r"\b(bad|poor|weak|lazy|stupid|fail\w*|smart|gifted)\b", re.I)


def practised(client: TestClient, db: Session, answers: int = 4):
    """A learner who has answered a few questions and has a new one recommended."""
    who = learner(client, db, arm="closed_loop")
    who.questionnaire(4)
    for _ in range(answers):
        who.next()
        assert who.answer().status_code == 200
    who.next()
    return who


# --- metrics --------------------------------------------------------------------------------


def test_top_k_overlap_and_agreement_words() -> None:
    a = np.array([5.0, -4, 3, 0.1, 0.0])
    assert metrics.top_k_overlap(a, a, k=3) == 1.0
    assert metrics.top_k_overlap(a, np.array([0.0, 0, 0.1, 4, 5]), k=2) == 0.0
    assert metrics.agreement_word(0.9) == "agree closely"
    assert metrics.agreement_word(0.5) == "partly agree"
    assert metrics.agreement_word(0.1) == "disagree"
    pairs = metrics.agreement({"shap": a, "lime": a * 2, "lrp": -a})
    assert [p for p, _, _ in pairs] == ["shap~lime", "shap~lrp", "lime~lrp"]
    assert pairs[0][1] == pytest.approx(1.0)


def test_dice_quality_measures() -> None:
    x = np.zeros(N_FEATURES)
    scale = np.ones(N_FEATURES)
    one, two = x.copy(), x.copy()
    one[0], two[1] = 1.0, 2.0
    found = [
        explain.Counterfactual(one, 0.7, {FEATURE_NAMES[0]: (0.0, 1.0)}),
        explain.Counterfactual(two, 0.6, {FEATURE_NAMES[1]: (0.0, 2.0)}),
        explain.Counterfactual(x, 0.4, {}),  # did not flip the prediction: not valid
    ]
    q = metrics.dice_quality(x, 0.3, found, requested=4, scale=scale)
    assert q["found"] == 2 and q["validity"] == 0.5
    assert q["proximity"] == pytest.approx(1.5)  # mean of 1 and 2 typical spreads
    assert q["sparsity"] == 1.0
    assert q["diversity"] == pytest.approx(3.0)
    assert metrics.dice_quality(x, 0.3, [], 4, scale)["validity"] == 0.0


# --- the learner's own report ---------------------------------------------------------------------


def test_a_learners_report_explains_their_latest_prediction(
    client: TestClient, db: Session
) -> None:
    ada = practised(client, db)
    r = ada.get("/learners/me/report")
    assert r.status_code == 200, r.text
    rep = r.json()

    assert rep["focus"]["recommendation_id"] == ada.last["recommendation"]["id"]
    assert all(m["ok"] for m in rep["methods"]), rep["methods"]
    assert {m["method"] for m in rep["methods"]} == {
        "shap",
        "lime",
        "lrp",
        "dice",
        "shap_recent",
        "lrp_recent",
    }

    # the XAI matrix: every factor, strongest first, three methods, a direction and a meaning
    matrix = rep["matrix"]
    assert sorted(row["name"] for row in matrix) == sorted(FEATURE_NAMES)
    assert [abs(row["shap"]) for row in matrix] == sorted(
        (abs(r["shap"]) for r in matrix), reverse=True
    )
    for row in matrix:
        assert row["lime"] is not None and row["lrp"] is not None
        assert row["direction"] in ("raises", "lowers", "neutral") and row["meaning"]

    # SHAP is complete: the waterfall adds up to the prediction
    wf = rep["waterfall"]
    assert wf["base"] + sum(s["value"] for s in wf["steps"]) == pytest.approx(
        wf["output"], abs=1e-6
    )
    assert wf["output"] == pytest.approx(rep["focus"]["p_correct"])

    assert [a["pair"] for a in rep["agreement"]] == ["shap~lime", "shap~lrp", "lime~lrp"]
    for a in rep["agreement"]:
        assert -1 <= a["spearman"] <= 1 and 0 <= a["top_k_overlap"] <= 1
    q = rep["quality"]
    assert q["shap_additivity_error"] < 1e-6
    assert q["lime_r2"] is not None
    assert 0 <= q["dice"]["validity"] <= 1 and q["dice"]["requested"] == report.DICE_TOTAL

    # DiCE: only things a learner can change, and every option moves the prediction across 50%
    table = rep["counterfactuals"]
    assert "item_difficulty" not in table["features"] and "self_efficacy" not in table["features"]
    for option in table["options"]:
        assert (option["p_correct"] >= 0.5) != (table["p_now"] >= 0.5)
        assert any(option["changed"])

    # person-level views over the answered questions
    assert rep["recent_predictions"] == 4
    assert len(rep["decision"]["predictions"]) == 4
    assert len(rep["heatmap"]["values"]) == N_FEATURES
    assert all(len(row) == 4 for row in rep["heatmap"]["values"])

    assert [a["key"] for a in rep["radar"]["traits"]] == [
        "abstraction_preference",
        "load_tolerance",
        "depth_preference",
        "persistence",
        "self_efficacy",
    ]
    assert len(rep["radar"]["clusters"]) == 8
    assert "not a clinical" in rep["disclaimer"]
    assert rep["summary"].startswith("For the latest question")
    assert not JUDGEMENTAL.search(rep["summary"])


def test_a_new_learner_gets_a_report_with_nothing_to_explain_yet(
    client: TestClient, db: Session
) -> None:
    bob = learner(client, db)
    bob.questionnaire(3)
    rep = bob.get("/learners/me/report").json()
    assert rep["focus"] is None and rep["matrix"] == [] and rep["waterfall"] is None
    assert rep["summary"].startswith("There is nothing to explain yet")
    assert len(rep["radar"]["traits"]) == 5  # the profile is there from the questionnaire


def test_one_failing_method_does_not_take_the_report_down(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ada = practised(client, db, answers=2)

    def broken(*args, **kwargs):
        raise RuntimeError("LIME is unavailable")

    monkeypatch.setattr(explain, "lime_attribution", broken)
    rep = ada.get("/learners/me/report").json()
    status = {m["method"]: m for m in rep["methods"]}
    assert status["lime"] == {"method": "lime", "ok": False, "detail": "RuntimeError"}
    assert status["shap"]["ok"] and status["dice"]["ok"]
    assert all(row["lime"] is None and row["shap"] is not None for row in rep["matrix"])
    assert [a["pair"] for a in rep["agreement"]] == ["shap~lrp"]
    assert rep["quality"]["lime_r2"] is None


def test_the_report_is_cached_until_the_learner_answers_again(
    client: TestClient, db: Session
) -> None:
    ada = practised(client, db, answers=1)
    first = ada.get("/learners/me/report").json()
    assert ada.get("/learners/me/report").json()["generated_at"] == first["generated_at"]
    assert ada.answer().status_code == 200
    ada.next()
    again = ada.get("/learners/me/report").json()
    assert again["generated_at"] != first["generated_at"]
    assert again["recent_predictions"] == 2


# --- access ---------------------------------------------------------------------------------------


def test_reports_are_private_and_admins_see_them_only_by_pseudonym(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(report, "_global", None)
    ada = practised(client, db, answers=2)
    bob = learner(client, db)
    boss = admin(client, db)

    assert client.get(f"{API}/learners/me/report").status_code == 401
    for path in ("/admin/learners", "/admin/xai/global"):
        assert ada.get(path).status_code == 403

    listing = boss.get("/admin/learners").json()
    text = str(listing)
    assert ada.email not in text and bob.email not in text and "Test Learner" not in text
    assert {"pseudonym", "arm", "attempts", "last_active"} == set(listing[0])
    ada_row = next(row for row in listing if row["attempts"] == 2)

    own = ada.get("/learners/me/report").json()
    seen = boss.get(f"/admin/learners/{ada_row['pseudonym']}/report").json()
    assert seen["summary"] == own["summary"] and seen["matrix"] == own["matrix"]
    assert boss.get("/admin/learners/000000000000/report").status_code == 404

    # the cross-learner view identifies no one
    view = boss.get("/admin/xai/global").json()
    assert view["predictions"] >= 2 and view["learners"] >= 1
    assert {f["name"] for f in view["features"]} == set(FEATURE_NAMES)
    assert set(view["features"][0]["points"][0]) == {"shap", "position"}
    assert ada.email not in str(view) and str(ada.id) not in str(view)

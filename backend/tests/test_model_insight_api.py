"""The performance model through the API: a learner's question, its prediction and explanations."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ml.features import FEATURE_NAMES
from tests.api_helpers import API, learner


def test_a_recommended_question_comes_with_an_explained_prediction(
    client: TestClient, db: Session
) -> None:
    ada = learner(client, db)
    ada.questionnaire(4)
    rec = ada.next()["recommendation"]

    r = ada.get(f"/recommendations/{rec['id']}/model")
    assert r.status_code == 200, r.text
    insight = r.json()
    assert 0 < insight["p_correct"] < 1
    assert insight["answered_correctly"] is None  # not answered yet
    assert insight["summary"].startswith("The model put your chance of answering correctly at")
    assert [f["name"] for f in insight["features"]] == list(FEATURE_NAMES)
    by_method = {a["method"]: a for a in insight["attributions"]}
    assert set(by_method) == {"shap", "lime", "lrp"}
    shap = by_method["shap"]
    assert abs(shap["base"] + sum(shap["contributions"].values()) - insight["p_correct"]) < 1e-6
    assert by_method["lime"]["fidelity"] is not None
    assert set(insight["agreement"]) == {"shap~lime", "shap~lrp", "lime~lrp"}
    for cf in insight["counterfactuals"]:  # DiCE: a different predicted outcome
        assert (cf["p_correct"] >= 0.5) != (insight["p_correct"] >= 0.5)
        assert cf["changes"]

    # after answering, the same (cached) prediction now shows how it turned out
    assert ada.answer().status_code == 200
    after = ada.get(f"/recommendations/{rec['id']}/model").json()
    assert after["answered_correctly"] in (True, False)
    assert after["p_correct"] == insight["p_correct"]


def test_another_learners_prediction_is_not_found(client: TestClient, db: Session) -> None:
    ada, bob = learner(client, db), learner(client, db)
    ada.questionnaire(4)
    rec = ada.next()["recommendation"]
    assert bob.get(f"/recommendations/{rec['id']}/model").status_code == 404
    assert client.get(f"{API}/recommendations/{rec['id']}/model").status_code == 401


def test_the_model_card_is_public_to_signed_in_users(client: TestClient, db: Session) -> None:
    ada = learner(client, db)
    card = ada.get("/model/card").json()
    assert card["test_metrics"]["BKT (the learner model)"]["auc"] > 0
    assert [f["name"] for f in card["features"]] == list(FEATURE_NAMES)
    assert client.get(f"{API}/model/card").status_code == 401
